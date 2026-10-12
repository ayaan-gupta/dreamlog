"""Sentence embeddings behind one small interface."""

from __future__ import annotations

import hashlib
import re
import threading
from pathlib import Path
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

Vectors = NDArray[np.float32]


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> Vectors:
        """Returns one L2-normalised row per text."""
        ...


def symbol_text(name: str) -> str:
    """How a symbol is phrased before embedding: "a door", "an ocean".

    A bare word is a poor input for a sentence model. Adding the article moved
    the labelled calibration pairs further apart (scripts/calibrate_threshold.py
    prints the comparison).
    """
    article = "an" if name[:1].lower() in "aeiou" else "a"
    return f"{article} {name}"


class FastEmbedEmbedder:
    """all-MiniLM-L6-v2 through ONNX Runtime. No PyTorch, about 90 MB on disk."""

    def __init__(self, model: str, cache_dir: Path) -> None:
        self.name = f"fastembed:{model}"
        self.dim = 384
        self._model_name = model
        self._cache_dir = cache_dir
        self._model: Any = None
        self._lock = threading.Lock()

    def load(self) -> None:
        with self._lock:
            if self._model is None:
                from fastembed import TextEmbedding

                self._cache_dir.mkdir(parents=True, exist_ok=True)
                self._model = TextEmbedding(self._model_name, cache_dir=str(self._cache_dir))

    def embed(self, texts: list[str]) -> Vectors:
        if not texts:
            return np.zeros((0, self.dim), dtype=np.float32)
        self.load()
        with self._lock:
            rows = np.array(list(self._model.embed(texts)), dtype=np.float32)
        norms = np.linalg.norm(rows, axis=1, keepdims=True)
        return rows / np.clip(norms, 1e-12, None)


class HashEmbedder:
    """Deterministic stand-in for unit tests. Not semantic.

    Each word is hashed into a signed bucket, so two texts are similar exactly
    as far as they share words. Good enough to test plumbing, and it lets the
    fast tests run with no model on disk. Never the default.
    """

    name = "hash"
    dim = 384

    def embed(self, texts: list[str]) -> Vectors:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in re.findall(r"[a-z']+", text.lower()):
                if word in {"a", "an", "the"}:
                    continue
                digest = hashlib.sha256(word.encode()).digest()
                out[row, int.from_bytes(digest[:4], "big") % self.dim] += 1.0 if digest[4] % 2 else -1.0
            norm = float(np.linalg.norm(out[row]))
            if norm == 0.0:
                out[row, 0] = 1.0
            else:
                out[row] /= norm
        return out
