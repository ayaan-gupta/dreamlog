"""Folding extracted symbols into the canonical list by embedding match.

Two surface forms are the same symbol when they are the same kind of thing and
the cosine similarity of their embeddings reaches the threshold, or when a
chain of such pairs joins them. A canonical symbol is therefore a connected
component of the similarity graph over everything the journal has mentioned.

For each extracted symbol:

1. If its exact surface form has been seen before, it goes where it went then.
2. Otherwise every known surface form of the same kind within the threshold is
   fetched from pgvector. If they all belong to one symbol, the newcomer joins
   it. If they belong to several, the newcomer is a bridge and those symbols
   become one.
3. If nothing is within the threshold it founds a new canonical symbol.

There is no synonym table anywhere. "ocean" and "water" end up as one symbol
because all-MiniLM-L6-v2 gives "an ocean" and "a water" a cosine of 0.653 and
the threshold is 0.60. The threshold was chosen on labelled pairs that do not
include that pair; see scripts/calibrate_threshold.py.

Why components and not "join the nearest symbol". The first version compared a
new word with each symbol's name only, and the result depended on the order
the dreams arrived in: after a dream about a river, "water" joined "river"
(0.68) and a later "ocean", too far from "river", was left on its own.
Components do not care about order, which a test checks by shuffling the
sample dreams. The price is chaining: house, home, room, hotel and attic end up
as one symbol because each is close to the next.

Only symbols of the same kind can merge. Without that rule the model merges
things that are merely associated: on the sample dreams it put "dentist" into
"tooth" (0.80), "teacher" into "school" (0.63) and "radio" into "station"
(0.68). A person is never the same symbol as an object, so those are refused
outright instead of by tuning the number.

The name of a symbol is whichever of its surface forms appears in the most
entries. Merges are never undone by deleting an entry: if the word that
bridged two groups goes away, the groups stay together until delete-all.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

import numpy as np
from numpy.typing import NDArray

from .db import Conn, as_array
from .extract.base import ExtractedSymbol

GlyphFor = Callable[[str, str, NDArray[np.float32]], str | None]


@dataclass
class Assigned:
    symbol_id: int
    salience: float
    surfaces: list[str] = field(default_factory=list)


def _absorb(conn: Conn, target: int, other: int) -> None:
    """Folds symbol ``other`` into ``target``, entries and aliases included."""
    conn.execute(
        """
        UPDATE entry_symbols t SET salience = GREATEST(t.salience, o.salience), surfaces = t.surfaces || o.surfaces
        FROM entry_symbols o WHERE o.entry_id = t.entry_id AND t.symbol_id = %s AND o.symbol_id = %s
        """,
        (target, other),
    )
    conn.execute(
        "DELETE FROM entry_symbols o USING entry_symbols t WHERE o.symbol_id = %s AND t.symbol_id = %s AND o.entry_id = t.entry_id",
        (other, target),
    )
    conn.execute("UPDATE entry_symbols SET symbol_id = %s WHERE symbol_id = %s", (target, other))
    conn.execute("UPDATE symbol_aliases SET symbol_id = %s WHERE symbol_id = %s", (target, other))
    conn.execute("DELETE FROM symbols WHERE id = %s", (other,))


def canonicalise(
    conn: Conn,
    symbols: list[ExtractedSymbol],
    vectors: NDArray[np.float32],
    threshold: float,
    glyph_for: GlyphFor,
) -> list[Assigned]:
    """Assigns each extracted symbol to a canonical symbol, creating and
    merging as needed. Must run inside ``Database.write``."""
    out: dict[int, Assigned] = {}
    for symbol, vector in zip(symbols, vectors, strict=True):
        known = conn.execute("SELECT symbol_id FROM symbol_aliases WHERE alias = %s", (symbol.name,)).fetchone()
        if known:
            symbol_id = int(known["symbol_id"])
        else:
            near = conn.execute(
                """
                SELECT symbol_id, max(1 - (embedding <=> %s)) AS similarity
                FROM symbol_aliases WHERE kind = %s AND 1 - (embedding <=> %s) >= %s
                GROUP BY symbol_id ORDER BY symbol_id
                """,
                (vector, symbol.kind, vector, threshold),
            ).fetchall()
            if near:
                symbol_id = int(near[0]["symbol_id"])  # the oldest symbol keeps its id
                similarity = max(float(row["similarity"]) for row in near)
                for row in near[1:]:
                    other = int(row["symbol_id"])
                    _absorb(conn, symbol_id, other)
                    moved = out.pop(other, None)
                    if moved is not None:
                        slot = out.setdefault(symbol_id, Assigned(symbol_id, 0.0))
                        slot.salience = max(slot.salience, moved.salience)
                        slot.surfaces.extend(s for s in moved.surfaces if s not in slot.surfaces)
            else:
                created = conn.execute(
                    "INSERT INTO symbols (canonical, kind, embedding, glyph) VALUES (%s, %s, %s, %s) RETURNING id",
                    (symbol.name, symbol.kind, vector, glyph_for(symbol.name, symbol.kind, vector)),
                ).fetchone()
                assert created is not None
                symbol_id, similarity = int(created["id"]), 1.0
            conn.execute(
                "INSERT INTO symbol_aliases (alias, symbol_id, kind, embedding, similarity) VALUES (%s, %s, %s, %s, %s)",
                (symbol.name, symbol_id, symbol.kind, vector, similarity),
            )
        slot = out.setdefault(symbol_id, Assigned(symbol_id, 0.0))
        slot.salience = max(slot.salience, symbol.salience)
        if symbol.name not in slot.surfaces:
            slot.surfaces.append(symbol.name)
    return list(out.values())


def tidy(conn: Conn, glyph_for: GlyphFor) -> None:
    """Removes what no entry refers to any more, then fixes the names.

    Run after any change to entry_symbols. Deleting or editing a dream must not
    leave its words behind in the alias table.
    """
    conn.execute(
        """
        DELETE FROM symbol_aliases a
        WHERE NOT EXISTS (
            SELECT 1 FROM entry_symbols es WHERE es.symbol_id = a.symbol_id AND a.alias = ANY (es.surfaces)
        )
        """
    )
    conn.execute("DELETE FROM symbols s WHERE NOT EXISTS (SELECT 1 FROM entry_symbols es WHERE es.symbol_id = s.id)")
    rows = conn.execute(
        """
        SELECT s.id, s.canonical, a.alias, a.kind, a.embedding,
               (SELECT count(*) FROM entry_symbols es WHERE es.symbol_id = s.id AND a.alias = ANY (es.surfaces)) AS uses
        FROM symbols s JOIN symbol_aliases a ON a.symbol_id = s.id
        ORDER BY s.id, uses DESC, a.alias
        """
    ).fetchall()
    seen: set[int] = set()
    for row in rows:
        if row["id"] in seen:
            continue
        seen.add(row["id"])  # first row per symbol: its most used surface form, ties broken by spelling
        if row["alias"] != row["canonical"]:
            vector = as_array(row["embedding"])
            conn.execute(
                "UPDATE symbols SET canonical = %s, kind = %s, embedding = %s, glyph = %s WHERE id = %s",
                (row["alias"], row["kind"], vector, glyph_for(row["alias"], row["kind"], vector), row["id"]),
            )
