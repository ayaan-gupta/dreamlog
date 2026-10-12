"""Shapes that cross the HTTP boundary."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SymbolOut(BaseModel):
    id: int
    name: str
    kind: str
    salience: float
    surfaces: list[str]
    glyph: str | None


class EntryOut(BaseModel):
    id: UUID
    created_at: datetime
    updated_at: datetime
    transcript: str
    title: str
    moods: list[str]
    symbols: list[SymbolOut]
    image_url: str | None
    thumb_url: str | None
    has_audio: bool
    duration_s: float | None
    source: str
    engines: dict[str, str]
    timings_ms: dict[str, int] | None = None


class TextIn(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    created_at: datetime | None = None


class GraphNode(BaseModel):
    id: int
    name: str
    kind: str
    glyph: str | None
    count: int
    aliases: list[str]
    cluster: int | None


class GraphEdge(BaseModel):
    source: int
    target: int
    weight: int


class GraphCluster(BaseModel):
    id: int
    name: str
    named_by: str
    members: list[int]


class GraphOut(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    clusters: list[GraphCluster]
    entries: int


class SearchHit(BaseModel):
    entry: EntryOut
    score: float
    via: str
    """"symbol", "meaning" or "both"."""


class SearchOut(BaseModel):
    query: str
    cleaned: str
    matched_symbol: str | None
    matched_similarity: float | None
    hits: list[SearchHit]


class MonthOut(BaseModel):
    month: str
    entries: int


class AtlasSymbol(BaseModel):
    name: str
    glyph: str | None
    strength: float
    entries: int


class AtlasOut(BaseModel):
    month: str
    mood: str
    symbols: list[AtlasSymbol]
    image_url: str


class PrivacyOut(BaseModel):
    local_only: bool
    transcriber: str
    extractor: str
    embedder: str
    illustrator: str
    keep_audio: bool
    key_source: str
    entries: int
    symbols: int
    files: int
    audio_files: int
    encrypted: list[str]
    not_encrypted: list[str]


class DeletedOut(BaseModel):
    entries: int
    symbols: int
    aliases: int
    links: int
    files: int


class SeedStatus(BaseModel):
    running: bool
    done: int
    total: int
    error: str | None = None
