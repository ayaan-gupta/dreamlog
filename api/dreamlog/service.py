"""The application: every operation the HTTP layer exposes, with no HTTP in it.

Pipeline for one entry: transcribe, extract symbols and moods, embed the
transcript and each symbol in one batch, fold the symbols into the canonical
list, paint the picture, store everything.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import re
import tempfile
import threading
import time
import uuid
import zipfile
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from psycopg.types.json import Jsonb

from . import canonical
from .clusters import AnthropicNamer, CentralNamer, ClusterNamer, cluster_symbols, most_central
from .config import Settings
from .crypto import Cipher, generate_key, load_cipher
from .db import TABLES, Conn, Database, as_array
from .embed import Embedder, FastEmbedEmbedder, HashEmbedder, symbol_text
from .extract.anthropic_llm import AnthropicExtractor
from .extract.base import SymbolExtractor
from .extract.lexicon import LexiconExtractor
from .illustrate import ApiIllustrator, Illustration, Illustrator, ProceduralIllustrator
from .illustrate.atlas import AtlasSpec, render_atlas, strongest
from .illustrate.atlas import AtlasSymbol as AtlasGlyph
from .illustrate.matcher import GlyphMatcher
from .illustrate.procedural import SceneSpec, SceneSymbol, render_scene, seed_from
from .illustrate.prompt import build_prompt
from .illustrate.raster import paint_webp, svg_to_png, to_webp
from .models import (
    AtlasOut,
    AtlasSymbol,
    DeletedOut,
    EntryOut,
    GraphCluster,
    GraphEdge,
    GraphNode,
    GraphOut,
    MonthOut,
    PrivacyOut,
    SearchHit,
    SearchOut,
    SeedStatus,
    SymbolOut,
)
from .storage import EncryptedStore, LocalDirStore, ObjectStore
from .transcribe import FakeTranscriber, FasterWhisperTranscriber, Transcriber

log = logging.getLogger(__name__)

FIXTURES = Path(__file__).with_name("data") / "fixture_dreams.json"
_QUERY_LEAD = re.compile(r"^(?:(?:dreams?|ones?|entries|nights?)\s+)?(?:(?:about|of|with|where|involving|featuring)\s+)?", re.I)
_ARTICLE = re.compile(r"^(?:a|an|the|my|our|some)\s+", re.I)


class NotFound(LookupError):
    pass


@dataclass
class Services:
    """Everything swappable, built once from settings."""

    settings: Settings
    db: Database
    cipher: Cipher
    store: ObjectStore
    transcriber: Transcriber
    extractor: SymbolExtractor
    embedder: Embedder
    illustrator: Illustrator
    namer: ClusterNamer


def build_services(settings: Settings) -> Services:
    cipher = load_cipher(settings.encryption_key, settings.data_dir)
    store = EncryptedStore(LocalDirStore(settings.data_dir / "objects"), cipher)
    transcriber: Transcriber
    if settings.transcriber == "fake":
        transcriber = FakeTranscriber()
    else:
        transcriber = FasterWhisperTranscriber(settings.whisper_model, settings.whisper_compute_type, settings.model_cache_dir)
    embedder: Embedder = HashEmbedder() if settings.embedder == "hash" else FastEmbedEmbedder(settings.embedding_model, settings.model_cache_dir)
    lexicon = LexiconExtractor()
    use_llm = settings.extractor == "anthropic" or (settings.extractor == "auto" and bool(settings.anthropic_api_key))
    extractor: SymbolExtractor = AnthropicExtractor(settings.llm_model, lexicon) if use_llm else lexicon
    namer: ClusterNamer = AnthropicNamer(settings.llm_model, CentralNamer()) if use_llm else CentralNamer()
    painter = ProceduralIllustrator()
    use_api = settings.illustrator == "api" or (settings.illustrator == "auto" and bool(settings.image_api_key))
    illustrator: Illustrator = ApiIllustrator(settings.image_api_url, settings.image_api_key, settings.image_model, painter) if use_api else painter
    return Services(settings, Database(settings.database_url), cipher, store, transcriber, extractor, embedder, illustrator, namer)


def title_of(text: str, limit: int = 64) -> str:
    first = re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0].strip()
    if len(first) <= limit:
        return first.rstrip(".")
    cut = first[:limit].rsplit(" ", 1)[0]
    return cut.rstrip(",;:") + "…"


def clean_query(query: str) -> str:
    """ "dreams about the sea" becomes "sea". Every entry is a dream, so the
    lead-in only adds noise to the embedding."""
    text = " ".join(query.strip().split())
    stripped = _ARTICLE.sub("", _QUERY_LEAD.sub("", text, count=1)).strip()
    return stripped or text


class Dreamlog:
    def __init__(self, services: Services) -> None:
        self.s = services
        self.settings = services.settings
        self.matcher = GlyphMatcher(services.embedder)
        self._tmp = self.settings.data_dir / "tmp"
        self._seed = SeedStatus(running=False, done=0, total=0)
        self._seed_lock = threading.Lock()

    # ------------------------------------------------------------------ helpers

    def warm(self) -> None:
        """Loads the models so the first recording does not pay for it."""
        for part in (self.s.transcriber, self.s.embedder):
            load = getattr(part, "load", None)
            if callable(load):
                load()

    def _glyph_for(self, name: str, kind: str, vector: NDArray[np.float32]) -> str | None:
        return self.matcher.match(name, kind, vector)

    def _engines(self, transcriber: str | None) -> dict[str, str]:
        engines = {"extractor": self.s.extractor.name, "embedder": self.s.embedder.name, "illustrator": self.s.illustrator.name}
        if transcriber:
            engines["transcriber"] = transcriber
        return engines

    def _scene(self, conn: Conn, entry_id: uuid.UUID, moods: list[str]) -> tuple[SceneSpec, str]:
        rows = conn.execute(
            """
            SELECT s.canonical, s.kind, s.glyph, es.salience
            FROM entry_symbols es JOIN symbols s ON s.id = es.symbol_id
            WHERE es.entry_id = %s ORDER BY es.salience DESC, s.canonical
            """,
            (entry_id,),
        ).fetchall()
        spec = SceneSpec(
            seed=seed_from(str(entry_id)),
            moods=moods,
            symbols=[SceneSymbol(r["canonical"], float(r["salience"]), r["glyph"]) for r in rows],
        )
        return spec, build_prompt([(r["canonical"], r["kind"]) for r in rows], moods)

    def _store_picture(self, entry_id: uuid.UUID, image: bytes, thumb: bytes) -> tuple[str, str]:
        image_key, thumb_key = f"images/{entry_id}.webp", f"thumbs/{entry_id}.webp"
        self.s.store.put(image_key, image)
        self.s.store.put(thumb_key, thumb)
        return image_key, thumb_key

    def _drop_atlas_cache(self) -> None:
        for key in self.s.store.list("atlas/"):
            self.s.store.delete(key)

    # ------------------------------------------------------------------ entries

    def create_from_text(
        self,
        text: str,
        *,
        created_at: datetime | None = None,
        source: str = "text",
        illustrate: bool = True,
        transcriber: str | None = None,
        duration_s: float | None = None,
        audio: tuple[bytes, str] | None = None,
        timings: dict[str, int] | None = None,
    ) -> EntryOut:
        text = " ".join(text.split())
        if not text:
            raise ValueError("an entry needs some words")
        timings = dict(timings or {})
        entry_id = uuid.uuid4()
        now = datetime.now(UTC)
        created = created_at or now

        t = time.perf_counter()
        extraction = self.s.extractor.extract(text)
        timings["extract"] = round((time.perf_counter() - t) * 1000)
        t = time.perf_counter()
        vectors = self.s.embedder.embed([text] + [symbol_text(s.name) for s in extraction.symbols])
        timings["embed"] = round((time.perf_counter() - t) * 1000)

        audio_key: str | None = None
        written: list[str] = []
        try:
            t = time.perf_counter()
            with self.s.db.write() as conn:
                conn.execute(
                    """
                    INSERT INTO entries (id, created_at, updated_at, transcript, mood, embedding, duration_s, source, engines)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        entry_id,
                        created,
                        now,
                        self.s.cipher.encrypt_text(text, context=entry_id.bytes),
                        list(extraction.moods),
                        vectors[0],
                        duration_s,
                        source,
                        Jsonb(self._engines(transcriber)),
                    ),
                )
                assigned = canonical.canonicalise(conn, extraction.symbols, vectors[1:], self.settings.canonical_threshold, self._glyph_for)
                for a in assigned:
                    conn.execute(
                        "INSERT INTO entry_symbols (entry_id, symbol_id, salience, surfaces) VALUES (%s, %s, %s, %s)",
                        (entry_id, a.symbol_id, a.salience, a.surfaces),
                    )
                canonical.tidy(conn, self._glyph_for)
                timings["canonicalise"] = round((time.perf_counter() - t) * 1000)
                if audio is not None:
                    audio_key = f"audio/{entry_id}{audio[1]}"
                    self.s.store.put(audio_key, audio[0])
                    written.append(audio_key)
                    conn.execute("UPDATE entries SET audio_key = %s WHERE id = %s", (audio_key, entry_id))
                if illustrate:
                    t = time.perf_counter()
                    spec, prompt = self._scene(conn, entry_id, list(extraction.moods))
                    picture = self.s.illustrator.illustrate(spec, prompt)
                    keys = self._store_picture(entry_id, picture.image, picture.thumb)
                    written.extend(keys)
                    conn.execute("UPDATE entries SET image_key = %s, thumb_key = %s WHERE id = %s", (*keys, entry_id))
                    timings["illustrate"] = round((time.perf_counter() - t) * 1000)
        except Exception:
            for key in written:  # the transaction rolled back; do not leave files behind
                self.s.store.delete(key)
            raise
        self._drop_atlas_cache()
        entry = self.get_entry(entry_id)
        entry.timings_ms = timings
        return entry

    def create_from_audio(self, data: bytes, suffix: str) -> EntryOut:
        """Stop-to-saved: everything between the upload arriving and the entry
        being in the database with its picture."""
        started = time.perf_counter()
        self._tmp.mkdir(parents=True, exist_ok=True)
        timings: dict[str, int] = {}
        with tempfile.NamedTemporaryFile(dir=self._tmp, suffix=suffix, delete=False) as fh:
            fh.write(data)
            path = Path(fh.name)
        try:
            t = time.perf_counter()
            transcript = self.s.transcriber.transcribe(path)
            timings["transcribe"] = round((time.perf_counter() - t) * 1000)
        finally:
            path.unlink(missing_ok=True)  # the plaintext recording never outlives this call
        if not transcript.text.strip():
            raise ValueError("no speech was found in the recording")
        entry = self.create_from_text(
            transcript.text,
            source="voice",
            transcriber=transcript.engine,
            duration_s=transcript.duration_s,
            audio=(data, suffix) if self.settings.keep_audio else None,
            timings=timings,
        )
        assert entry.timings_ms is not None
        entry.timings_ms["total"] = round((time.perf_counter() - started) * 1000)
        return entry

    def update_entry(self, entry_id: uuid.UUID, text: str) -> EntryOut:
        text = " ".join(text.split())
        if not text:
            raise ValueError("an entry needs some words")
        extraction = self.s.extractor.extract(text)
        vectors = self.s.embedder.embed([text] + [symbol_text(s.name) for s in extraction.symbols])
        with self.s.db.write() as conn:
            row = conn.execute("SELECT engines FROM entries WHERE id = %s FOR UPDATE", (entry_id,)).fetchone()
            if row is None:
                raise NotFound(str(entry_id))
            engines = dict(row["engines"]) | self._engines(None)
            conn.execute("DELETE FROM entry_symbols WHERE entry_id = %s", (entry_id,))
            assigned = canonical.canonicalise(conn, extraction.symbols, vectors[1:], self.settings.canonical_threshold, self._glyph_for)
            for a in assigned:
                conn.execute(
                    "INSERT INTO entry_symbols (entry_id, symbol_id, salience, surfaces) VALUES (%s, %s, %s, %s)",
                    (entry_id, a.symbol_id, a.salience, a.surfaces),
                )
            canonical.tidy(conn, self._glyph_for)
            spec, prompt = self._scene(conn, entry_id, list(extraction.moods))
            picture = self.s.illustrator.illustrate(spec, prompt)
            keys = self._store_picture(entry_id, picture.image, picture.thumb)
            conn.execute(
                """
                UPDATE entries SET transcript = %s, mood = %s, embedding = %s, updated_at = %s, image_key = %s, thumb_key = %s, engines = %s
                WHERE id = %s
                """,
                (
                    self.s.cipher.encrypt_text(text, context=entry_id.bytes),
                    list(extraction.moods),
                    vectors[0],
                    datetime.now(UTC),
                    *keys,
                    Jsonb(engines),
                    entry_id,
                ),
            )
        self._drop_atlas_cache()
        return self.get_entry(entry_id)

    def delete_entry(self, entry_id: uuid.UUID) -> None:
        with self.s.db.write() as conn:
            row = conn.execute("DELETE FROM entries WHERE id = %s RETURNING image_key, thumb_key, audio_key", (entry_id,)).fetchone()
            if row is None:
                raise NotFound(str(entry_id))
            canonical.tidy(conn, self._glyph_for)
        for key in (row["image_key"], row["thumb_key"], row["audio_key"]):
            if key:
                self.s.store.delete(key)
        self._drop_atlas_cache()

    def _entries(self, where: str, params: tuple[Any, ...], order: str = "e.created_at DESC") -> list[EntryOut]:
        with self.s.db.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT e.id, e.created_at, e.updated_at, e.transcript, e.mood, e.image_key, e.thumb_key, e.audio_key,
                       e.duration_s, e.source, e.engines,
                       COALESCE(json_agg(json_build_object('id', s.id, 'name', s.canonical, 'kind', s.kind, 'glyph', s.glyph,
                                'salience', es.salience, 'surfaces', es.surfaces) ORDER BY es.salience DESC, s.canonical)
                                FILTER (WHERE s.id IS NOT NULL), '[]') AS symbols
                FROM entries e
                LEFT JOIN entry_symbols es ON es.entry_id = e.id
                LEFT JOIN symbols s ON s.id = es.symbol_id
                {where}
                GROUP BY e.id ORDER BY {order}
                """,  # noqa: S608 - where and order are fixed strings from this module
                params,
            ).fetchall()
        return [self._entry(row) for row in rows]

    def _entry(self, row: dict[str, Any]) -> EntryOut:
        text = self.s.cipher.decrypt_text(row["transcript"], context=row["id"].bytes)
        version = int(row["updated_at"].timestamp())
        return EntryOut(
            id=row["id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            transcript=text,
            title=title_of(text),
            moods=list(row["mood"]),
            symbols=[SymbolOut(**s) for s in row["symbols"]],
            image_url=f"/api/entries/{row['id']}/image?v={version}" if row["image_key"] else None,
            thumb_url=f"/api/entries/{row['id']}/image?size=thumb&v={version}" if row["thumb_key"] else None,
            has_audio=bool(row["audio_key"]),
            duration_s=row["duration_s"],
            source=row["source"],
            engines=dict(row["engines"]),
        )

    def get_entry(self, entry_id: uuid.UUID) -> EntryOut:
        found = self._entries("WHERE e.id = %s", (entry_id,))
        if not found:
            raise NotFound(str(entry_id))
        return found[0]

    def list_entries(self, symbol_id: int | None = None) -> list[EntryOut]:
        if symbol_id is None:
            return self._entries("", ())
        return self._entries("WHERE e.id IN (SELECT entry_id FROM entry_symbols WHERE symbol_id = %s)", (symbol_id,))

    def entry_image(self, entry_id: uuid.UUID, thumb: bool) -> bytes:
        with self.s.db.connect() as conn:
            row = conn.execute("SELECT image_key, thumb_key FROM entries WHERE id = %s", (entry_id,)).fetchone()
        key = row and (row["thumb_key"] if thumb else row["image_key"])
        if not key:
            raise NotFound(str(entry_id))
        return self.s.store.get(key)

    # -------------------------------------------------------------------- graph

    def graph(self) -> GraphOut:
        with self.s.db.connect() as conn:
            symbols = conn.execute(
                """
                SELECT s.id, s.canonical, s.kind, s.glyph, s.embedding, count(es.entry_id) AS uses,
                       (SELECT array_agg(a.alias ORDER BY a.alias) FROM symbol_aliases a WHERE a.symbol_id = s.id) AS aliases
                FROM symbols s JOIN entry_symbols es ON es.symbol_id = s.id
                GROUP BY s.id ORDER BY s.id
                """
            ).fetchall()
            edges = conn.execute(
                """
                SELECT a.symbol_id AS source, b.symbol_id AS target, count(*) AS weight
                FROM entry_symbols a JOIN entry_symbols b ON a.entry_id = b.entry_id AND a.symbol_id < b.symbol_id
                GROUP BY 1, 2 ORDER BY 1, 2
                """
            ).fetchall()
            total = conn.execute("SELECT count(*) AS n FROM entries").fetchone()
        assert total is not None
        if not symbols:
            return GraphOut(nodes=[], edges=[], clusters=[], entries=int(total["n"]))
        vectors = np.stack([as_array(row["embedding"]) for row in symbols])
        labels = cluster_symbols(vectors)
        clusters: list[GraphCluster] = []
        for label in sorted({int(v) for v in labels if v >= 0}):
            members = [i for i, v in enumerate(labels) if v == label]
            central = symbols[most_central(vectors, members)]["canonical"]
            names = [symbols[i]["canonical"] for i in members]
            clusters.append(
                GraphCluster(
                    id=label,
                    name=self.s.namer.name_cluster(names, central),
                    named_by=self.s.namer.name,
                    members=[int(symbols[i]["id"]) for i in members],
                )
            )
        nodes = [
            GraphNode(
                id=int(row["id"]),
                name=row["canonical"],
                kind=row["kind"],
                glyph=row["glyph"],
                count=int(row["uses"]),
                aliases=list(row["aliases"] or []),
                cluster=int(labels[i]) if labels[i] >= 0 else None,
            )
            for i, row in enumerate(symbols)
        ]
        return GraphOut(
            nodes=nodes,
            edges=[GraphEdge(source=int(e["source"]), target=int(e["target"]), weight=int(e["weight"])) for e in edges],
            clusters=clusters,
            entries=int(total["n"]),
        )

    # ------------------------------------------------------------------- search

    def search(self, query: str, limit: int | None = None) -> SearchOut:
        """Two channels. Meaning: cosine between the query and each transcript.
        Symbol: if the query would be canonicalised into an existing symbol,
        every dream carrying that symbol matches, which is how "water" finds a
        dream that only says "ocean". Symbol matches are listed first."""
        limit = limit or self.settings.search_limit
        cleaned = clean_query(query)
        if not cleaned:
            return SearchOut(query=query, cleaned=cleaned, matched_symbol=None, matched_similarity=None, hits=[])
        text_vec, symbol_vec = self.s.embedder.embed([cleaned, symbol_text(cleaned)])
        with self.s.db.connect() as conn:
            symbol = conn.execute(
                """
                SELECT s.id, s.canonical, GREATEST(1 - (a.embedding <=> %s), (a.alias = %s)::int) AS similarity
                FROM symbol_aliases a JOIN symbols s ON s.id = a.symbol_id
                ORDER BY similarity DESC, a.alias LIMIT 1
                """,
                (symbol_vec, cleaned.lower()),
            ).fetchone()
            matched = symbol if symbol and float(symbol["similarity"]) >= self.settings.canonical_threshold else None
            rows = conn.execute(
                """
                SELECT e.id, 1 - (e.embedding <=> %s) AS score,
                       (SELECT es.salience FROM entry_symbols es WHERE es.entry_id = e.id AND es.symbol_id = %s) AS salience
                FROM entries e
                """,
                (text_vec, matched["id"] if matched else None),
            ).fetchall()
        ranked = sorted(
            (r for r in rows if r["salience"] is not None or float(r["score"]) >= self.settings.search_floor),
            key=lambda r: (r["salience"] is None, -float(r["score"]) if r["salience"] is None else -float(r["salience"]) - float(r["score"])),
        )[:limit]
        by_id = {e.id: e for e in self._entries("WHERE e.id = ANY(%s)", ([r["id"] for r in ranked],))} if ranked else {}
        hits = [
            SearchHit(
                entry=by_id[r["id"]],
                score=round(float(r["score"]), 4),
                via="symbol"
                if r["salience"] is not None and float(r["score"]) < self.settings.search_floor
                else ("both" if r["salience"] is not None else "meaning"),
            )
            for r in ranked
        ]
        return SearchOut(
            query=query,
            cleaned=cleaned,
            matched_symbol=matched["canonical"] if matched else None,
            matched_similarity=round(float(matched["similarity"]), 3) if matched else None,
            hits=hits,
        )

    # -------------------------------------------------------------------- atlas

    def months(self) -> list[MonthOut]:
        with self.s.db.connect() as conn:
            rows = conn.execute(
                "SELECT to_char(created_at AT TIME ZONE 'UTC', 'YYYY-MM') AS month, count(*) AS n FROM entries GROUP BY 1 ORDER BY 1 DESC"
            ).fetchall()
        return [MonthOut(month=r["month"], entries=int(r["n"])) for r in rows]

    def _atlas_spec(self, month: str) -> tuple[AtlasSpec, list[AtlasSymbol]]:
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
            raise ValueError("month must look like 2026-10")
        with self.s.db.connect() as conn:
            rows = conn.execute(
                """
                SELECT s.id, s.canonical, s.glyph, sum(es.salience) AS strength, count(*) AS n
                FROM entry_symbols es JOIN symbols s ON s.id = es.symbol_id JOIN entries e ON e.id = es.entry_id
                WHERE to_char(e.created_at AT TIME ZONE 'UTC', 'YYYY-MM') = %s
                GROUP BY s.id
                """,
                (month,),
            ).fetchall()
            mood = conn.execute(
                """
                SELECT m AS mood, count(*) AS n FROM entries e, unnest(e.mood[1:1]) AS m
                WHERE to_char(e.created_at AT TIME ZONE 'UTC', 'YYYY-MM') = %s GROUP BY m ORDER BY n DESC, m LIMIT 1
                """,
                (month,),
            ).fetchone()
            if not rows:
                raise NotFound(month)
            ids = {r["canonical"]: int(r["id"]) for r in rows}
            top = strongest([(r["canonical"], r["glyph"], float(r["strength"]), int(r["n"])) for r in rows])
            index = {ids[name]: i for i, (name, *_rest) in enumerate(top)}
            pairs = conn.execute(
                """
                SELECT DISTINCT a.symbol_id AS a, b.symbol_id AS b
                FROM entry_symbols a JOIN entry_symbols b ON a.entry_id = b.entry_id AND a.symbol_id < b.symbol_id
                JOIN entries e ON e.id = a.entry_id
                WHERE to_char(e.created_at AT TIME ZONE 'UTC', 'YYYY-MM') = %s AND a.symbol_id = ANY(%s) AND b.symbol_id = ANY(%s)
                ORDER BY 1, 2
                """,
                (month, list(index), list(index)),
            ).fetchall()
        spec = AtlasSpec(
            month=month,
            mood=mood["mood"] if mood else "neutral",
            symbols=[AtlasGlyph(name, glyph, strength) for name, glyph, strength, _n in top],
            routes=sorted((min(index[p["a"]], index[p["b"]]), max(index[p["a"]], index[p["b"]])) for p in pairs),
        )
        listed = [AtlasSymbol(name=name, glyph=glyph, strength=round(strength, 2), entries=n) for name, glyph, strength, n in top]
        return spec, listed

    def atlas(self, month: str) -> AtlasOut:
        spec, listed = self._atlas_spec(month)
        return AtlasOut(month=month, mood=spec.mood, symbols=listed, image_url=f"/api/atlas/{month}/image?v={self._atlas_hash(spec)}")

    @staticmethod
    def _atlas_hash(spec: AtlasSpec) -> str:
        blob = json.dumps([spec.month, spec.mood, [(s.name, s.glyph, round(s.strength, 3)) for s in spec.symbols], spec.routes])
        return hashlib.sha256(blob.encode()).hexdigest()[:12]

    def atlas_image(self, month: str, fmt: str = "webp") -> bytes:
        """Rendered once per distinct month content and cached in the object store."""
        spec, _ = self._atlas_spec(month)
        base = f"atlas/{month}-{self._atlas_hash(spec)}"
        key = f"{base}.{'png' if fmt == 'png' else 'webp'}"
        try:
            return self.s.store.get(key)
        except KeyError:
            pass
        png = svg_to_png(render_atlas(spec), width=1200)
        self.s.store.put(f"{base}.png", png)
        self.s.store.put(f"{base}.webp", to_webp(png, width=1000, quality=84))
        return self.s.store.get(key)

    # ------------------------------------------------------------------ privacy

    def privacy(self) -> PrivacyOut:
        with self.s.db.connect() as conn:
            counts = conn.execute("SELECT (SELECT count(*) FROM entries) AS entries, (SELECT count(*) FROM symbols) AS symbols").fetchone()
        assert counts is not None
        files = self.s.store.list()
        local = (
            self.s.transcriber.name.startswith(("faster-whisper", "fake"))
            and self.s.extractor.name == "lexicon"
            and self.s.illustrator.name == "procedural"
        )
        return PrivacyOut(
            local_only=local,
            transcriber=self.s.transcriber.name,
            extractor=self.s.extractor.name,
            embedder=self.s.embedder.name,
            illustrator=self.s.illustrator.name,
            keep_audio=self.settings.keep_audio,
            key_source=self.s.cipher.source,
            entries=int(counts["entries"]),
            symbols=int(counts["symbols"]),
            files=len(files),
            audio_files=sum(1 for f in files if f.startswith("audio/")),
            encrypted=["transcripts", "illustrations", "atlas posters", "audio, when kept"],
            not_encrypted=["embeddings", "symbol names", "mood tags", "dates"],
        )

    def export_zip(self) -> bytes:
        """Everything, decrypted, in one archive the owner can read without this app."""
        entries = sorted(self.list_entries(), key=lambda e: e.created_at)
        graph = self.graph()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            listing = []
            for entry in entries:
                item: dict[str, Any] = {
                    "id": str(entry.id),
                    "created_at": entry.created_at.isoformat(),
                    "updated_at": entry.updated_at.isoformat(),
                    "transcript": entry.transcript,
                    "moods": entry.moods,
                    "symbols": [s.model_dump(exclude={"id", "glyph"}) for s in entry.symbols],
                    "source": entry.source,
                    "engines": entry.engines,
                    "image": None,
                    "audio": None,
                }
                with self.s.db.connect() as conn:
                    keys = conn.execute("SELECT image_key, audio_key FROM entries WHERE id = %s", (entry.id,)).fetchone()
                if keys and keys["image_key"]:
                    item["image"] = f"images/{entry.id}.webp"
                    archive.writestr(item["image"], self.s.store.get(keys["image_key"]))
                if keys and keys["audio_key"]:
                    item["audio"] = keys["audio_key"]
                    archive.writestr(item["audio"], self.s.store.get(keys["audio_key"]))
                listing.append(item)
            archive.writestr("entries.json", json.dumps(listing, indent=2, ensure_ascii=False))
            archive.writestr(
                "symbols.json",
                json.dumps([{"name": n.name, "kind": n.kind, "dreams": n.count, "also_written_as": n.aliases} for n in graph.nodes], indent=2),
            )
            archive.writestr(
                "README.txt",
                "Dreamlog export.\n\nentries.json holds every entry with its full transcript, moods and symbols.\n"
                "images/ holds one illustration per entry. audio/ is present only if audio retention was on.\n"
                "symbols.json is the canonical symbol list with every spelling folded into each symbol.\n"
                "Nothing in this archive is encrypted. Keep it somewhere you trust.\n",
            )
        return buffer.getvalue()

    def delete_all(self) -> DeletedOut:
        """Removes every row, every file and every embedding.

        TRUNCATE, not DELETE: it drops the table files instead of marking rows
        dead, so nothing waits for a vacuum. When the key was generated by the
        app it is replaced too, which makes any stray copy of old ciphertext
        unreadable.
        """
        with self.s.db.write() as conn:
            counts = conn.execute(
                """
                SELECT (SELECT count(*) FROM entries) AS entries, (SELECT count(*) FROM symbols) AS symbols,
                       (SELECT count(*) FROM symbol_aliases) AS aliases, (SELECT count(*) FROM entry_symbols) AS links
                """
            ).fetchone()
            assert counts is not None
            conn.execute(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE")  # noqa: S608 - fixed table names
        files = self.s.store.delete_all()
        if self._tmp.exists():
            for leftover in self._tmp.iterdir():
                leftover.unlink()
                files += 1
        if self.s.cipher.source == "generated":
            key_path = self.settings.data_dir / "dev.key"
            key_path.write_text(generate_key())
            fresh = load_cipher("", self.settings.data_dir)
            self.s.cipher = fresh
            if isinstance(self.s.store, EncryptedStore):
                self.s.store.cipher = fresh
        return DeletedOut(
            entries=int(counts["entries"]), symbols=int(counts["symbols"]), aliases=int(counts["aliases"]), links=int(counts["links"]), files=files
        )

    # ----------------------------------------------------------------- fixtures

    def seed_status(self) -> SeedStatus:
        return self._seed.model_copy()

    def load_fixtures(self, progress: Callable[[int, int], None] | None = None, *, illustrate: bool = True, workers: int = 6) -> int:
        """Adds the 30 sample dreams that are not already present.

        Rows are written one at a time, oldest first, because canonicalisation
        depends on order. The pictures are then painted in worker processes.
        """
        dreams = json.loads(FIXTURES.read_text())["dreams"]
        with self.s.db.connect() as conn:
            have = {r["source"] for r in conn.execute("SELECT source FROM entries WHERE source LIKE 'fixture:%'").fetchall()}
        todo = [d for d in sorted(dreams, key=lambda d: d["date"]) if f"fixture:{d['id']}" not in have]
        total = len(todo) * (2 if illustrate else 1)
        done = 0

        def tick() -> None:
            nonlocal done
            done += 1
            if progress:
                progress(done, total)

        created: list[EntryOut] = []
        for dream in todo:
            stamp = datetime.fromisoformat(dream["date"] + "T06:40:00+00:00")
            created.append(self.create_from_text(dream["text"], created_at=stamp, source=f"fixture:{dream['id']}", illustrate=False))
            tick()
        if illustrate and created:
            jobs: list[tuple[uuid.UUID, str]] = []
            with self.s.db.connect() as conn:
                for entry in created:
                    spec, _prompt = self._scene(conn, entry.id, entry.moods)
                    jobs.append((entry.id, render_scene(spec)))
            with ProcessPoolExecutor(max_workers=workers) as pool:
                for (entry_id, _svg), (image, thumb) in zip(jobs, pool.map(paint_webp, [svg for _id, svg in jobs]), strict=True):
                    keys = self._store_picture(entry_id, image, thumb)
                    with self.s.db.write() as conn:
                        conn.execute("UPDATE entries SET image_key = %s, thumb_key = %s WHERE id = %s", (*keys, entry_id))
                    tick()
        self._drop_atlas_cache()
        return len(todo)

    def start_seed(self) -> SeedStatus:
        with self._seed_lock:
            if self._seed.running:
                return self._seed.model_copy()
            self._seed = SeedStatus(running=True, done=0, total=60)

        def run() -> None:
            try:
                self.load_fixtures(lambda done, total: setattr(self, "_seed", SeedStatus(running=True, done=done, total=total)))
                self._seed = SeedStatus(running=False, done=self._seed.total, total=self._seed.total)
            except Exception as exc:  # surfaced to the client through the status endpoint
                log.exception("loading the sample dreams failed")
                self._seed = SeedStatus(running=False, done=self._seed.done, total=self._seed.total, error=type(exc).__name__)

        threading.Thread(target=run, name="seed", daemon=True).start()
        return self._seed.model_copy()


__all__ = ["Dreamlog", "Services", "build_services", "NotFound", "Illustration"]
