"""Picks a glyph for a symbol.

A word the library lists gets its glyph directly. A person of any kind becomes
a standing shape, because people are never drawn. Anything else is compared
with every listed word by embedding, so "serpent" finds the snake and "yacht"
finds the boat without either being written down. Below the cut-off a symbol
has no glyph and is painted as a small floating light.
"""

from __future__ import annotations

import numpy as np
from numpy.typing import NDArray

from ..embed import Embedder, symbol_text
from .glyphs import word_index

GLYPH_THRESHOLD = 0.62
"""Deliberately a little stricter than the canonicalisation threshold: a wrong
glyph is more visible than a missing one."""


class GlyphMatcher:
    def __init__(self, embedder: Embedder) -> None:
        self._index = word_index()
        self._words = list(self._index)
        self._embedder = embedder
        self._vectors: NDArray[np.float32] | None = None

    def match(self, name: str, kind: str, vector: NDArray[np.float32]) -> str | None:
        if name in self._index:
            return self._index[name]
        if kind == "person":
            return "presence"
        if self._vectors is None:
            self._vectors = self._embedder.embed([symbol_text(w) for w in self._words])
        scores = self._vectors @ np.asarray(vector, dtype=np.float32)
        best = int(np.argmax(scores))
        return self._index[self._words[best]] if float(scores[best]) >= GLYPH_THRESHOLD else None
