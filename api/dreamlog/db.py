"""Postgres access: one pool, plain SQL, pgvector types registered per connection."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np
import psycopg
from numpy.typing import NDArray
from pgvector.psycopg import register_vector
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

Conn = psycopg.Connection[dict[str, Any]]

_SCHEMA = Path(__file__).with_name("schema.sql")

TABLES: tuple[str, ...] = ("entry_symbols", "symbol_aliases", "symbols", "entries")
"""Every table that holds user data, children first."""

# One writer at a time. Canonicalisation reads the symbol list and then adds to
# it, so two entries saved at once could each found the same symbol.
WRITE_LOCK = 41040


def as_array(value: Any) -> NDArray[np.float32]:
    """A pgvector value as a float32 array. The driver hands back its own Vector type."""
    raw = value.to_numpy() if hasattr(value, "to_numpy") else value
    return np.asarray(raw, dtype=np.float32)


class Database:
    def __init__(self, url: str) -> None:
        self.url = url
        # The vector type has to exist before a connection can register it.
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute(_SCHEMA.read_text())
        self.pool: ConnectionPool[Conn] = ConnectionPool(
            url, min_size=1, max_size=6, configure=self._configure, kwargs={"row_factory": dict_row}, open=True
        )

    @staticmethod
    def _configure(conn: Conn) -> None:
        register_vector(conn)

    @contextmanager
    def connect(self) -> Iterator[Conn]:
        """A connection in a transaction: commits on success, rolls back on error."""
        with self.pool.connection() as conn:
            yield conn

    @contextmanager
    def write(self) -> Iterator[Conn]:
        """Like ``connect``, but serialised against every other writer."""
        with self.pool.connection() as conn:
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (WRITE_LOCK,))
            yield conn

    def close(self) -> None:
        self.pool.close()


def ensure_database(url: str, wait_s: float = 30.0) -> None:
    """Creates the database named in the URL if the server does not have it.

    Waits for the server first: a container that says it is ready may not be
    reachable through its published port for another second or two.
    """
    info = psycopg.conninfo.conninfo_to_dict(url)
    name = str(info["dbname"])
    admin = psycopg.conninfo.make_conninfo(url, dbname="postgres")
    deadline = time.monotonic() + wait_s
    while True:
        try:
            with psycopg.connect(admin, autocommit=True, connect_timeout=3) as conn:
                exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone()
                if not exists:
                    conn.execute(psycopg.sql.SQL("CREATE DATABASE {}").format(psycopg.sql.Identifier(name)))
            return
        except psycopg.OperationalError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.5)
