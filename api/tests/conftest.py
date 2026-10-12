"""Shared fixtures.

Two kinds of core. ``core`` is fast: a fake transcriber and a hashing embedder,
for testing plumbing. ``real_core`` uses the real embedding model and, where a
test asks for it, real Whisper; those tests are marked ``model`` and download
about 240 MB of models the first time they run.

Every test gets an empty database (``dreamlog_test`` on the dev Postgres) and
an empty data directory.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import replace
from pathlib import Path

import pytest

from dreamlog.config import REPO_ROOT, Settings
from dreamlog.crypto import generate_key
from dreamlog.db import ensure_database
from dreamlog.embed import FastEmbedEmbedder
from dreamlog.service import FIXTURES, Dreamlog, build_services
from dreamlog.transcribe import FasterWhisperTranscriber

TEST_DB = os.environ.get("DREAMLOG_TEST_DATABASE_URL", "postgresql://dreamlog:dreamlog@localhost:5504/dreamlog_test")
MODEL_CACHE = Path(os.environ.get("DREAMLOG_MODEL_CACHE_DIR", REPO_ROOT / ".cache" / "models"))
AUDIO = Path(__file__).parent / "fixtures"


def make_settings(data_dir: Path, **overrides: object) -> Settings:
    base: dict[str, object] = {
        "database_url": TEST_DB,
        "data_dir": data_dir,
        "model_cache_dir": MODEL_CACHE,
        "encryption_key": generate_key(),
        "transcriber": "fake",
        "embedder": "hash",
        "extractor": "lexicon",
        "illustrator": "procedural",
    }
    return Settings(**(base | overrides))  # type: ignore[arg-type]


@pytest.fixture(scope="session", autouse=True)
def _database() -> None:
    ensure_database(TEST_DB)


@pytest.fixture
def core(tmp_path: Path) -> Iterator[Dreamlog]:
    dreamlog = Dreamlog(build_services(make_settings(tmp_path)))
    dreamlog.delete_all()
    yield dreamlog
    dreamlog.s.db.close()


@pytest.fixture(scope="session")
def embedder() -> FastEmbedEmbedder:
    model = FastEmbedEmbedder("sentence-transformers/all-MiniLM-L6-v2", MODEL_CACHE)
    model.load()
    return model


@pytest.fixture(scope="session")
def whisper() -> FasterWhisperTranscriber:
    model = FasterWhisperTranscriber(os.environ.get("DREAMLOG_WHISPER_MODEL", "base.en"), "int8", MODEL_CACHE)
    model.load()
    return model


def real(tmp_path: Path, embedder: FastEmbedEmbedder, **overrides: object) -> Dreamlog:
    services = build_services(make_settings(tmp_path, embedder="fastembed", **overrides))
    dreamlog = Dreamlog(replace(services, embedder=embedder))
    dreamlog.delete_all()
    return dreamlog


@pytest.fixture
def real_core(tmp_path: Path, embedder: FastEmbedEmbedder) -> Iterator[Dreamlog]:
    dreamlog = real(tmp_path, embedder)
    yield dreamlog
    dreamlog.s.db.close()


@pytest.fixture(scope="module")
def fixture_core(tmp_path_factory: pytest.TempPathFactory, embedder: FastEmbedEmbedder) -> Iterator[Dreamlog]:
    """The 30 sample dreams loaded through the real pipeline, without pictures."""
    dreamlog = real(tmp_path_factory.mktemp("fixture"), embedder)
    assert dreamlog.load_fixtures(illustrate=False) == 30
    yield dreamlog
    dreamlog.s.db.close()


@pytest.fixture(scope="session")
def dreams() -> list[dict[str, object]]:
    return json.loads(FIXTURES.read_text())["dreams"]  # type: ignore[no-any-return]
