"""What every symbol extractor returns."""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

Kind = Literal["place", "person", "animal", "object", "nature", "body", "event"]
KINDS: tuple[Kind, ...] = ("place", "person", "animal", "object", "nature", "body", "event")

Mood = Literal["calm", "joyful", "anxious", "fearful", "sad", "nostalgic", "awed", "confused", "angry", "tender", "neutral"]
MOODS: tuple[Mood, ...] = ("calm", "joyful", "anxious", "fearful", "sad", "nostalgic", "awed", "confused", "angry", "tender", "neutral")

MAX_SYMBOLS = 12


class ExtractedSymbol(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=40)
    """Singular, lower case, one to three words: "staircase", "swimming pool"."""
    kind: Kind
    salience: float = Field(ge=0.0, le=1.0)
    """How central the symbol is to this dream. The most central one is 1.0."""


class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbols: list[ExtractedSymbol] = Field(max_length=MAX_SYMBOLS)
    moods: list[Mood] = Field(min_length=1, max_length=3)


class SymbolExtractor(Protocol):
    name: str

    def extract(self, text: str) -> Extraction: ...
