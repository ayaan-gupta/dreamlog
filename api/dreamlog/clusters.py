"""Groups canonical symbols with HDBSCAN and names the groups."""

from __future__ import annotations

import logging
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray
from sklearn.cluster import HDBSCAN

from .extract.anthropic_llm import first_text

log = logging.getLogger(__name__)

MIN_CLUSTER_SIZE = 3


def cluster_symbols(vectors: NDArray[np.float32]) -> NDArray[np.int64]:
    """One label per row, -1 for symbols that belong to no cluster.

    HDBSCAN on cosine distance between the unit vectors. With a personal
    journal's few hundred symbols most are noise, and that is the honest
    answer: a cluster is only reported where several symbols really are close.
    """
    if len(vectors) < MIN_CLUSTER_SIZE * 2:
        return np.full(len(vectors), -1, dtype=np.int64)
    distances = np.clip(1.0 - vectors.astype(np.float64) @ vectors.astype(np.float64).T, 0.0, 2.0)
    np.fill_diagonal(distances, 0.0)
    model = HDBSCAN(min_cluster_size=MIN_CLUSTER_SIZE, min_samples=2, metric="precomputed", cluster_selection_method="leaf", copy=True)
    return np.asarray(model.fit_predict(distances), dtype=np.int64)


def most_central(vectors: NDArray[np.float32], members: list[int]) -> int:
    """The member whose vector is closest to the cluster mean."""
    block = vectors[members]
    centre = block.mean(axis=0)
    return members[int(np.argmax(block @ centre))]


class ClusterNamer(Protocol):
    name: str

    def name_cluster(self, members: list[str], central: str) -> str: ...


class CentralNamer:
    """The offline rule: a cluster is called after its most central member."""

    name = "most-central"

    def name_cluster(self, members: list[str], central: str) -> str:
        return central


class AnthropicNamer:
    """Asks Claude for a two or three word label.

    UNTESTED against the live API, for the same reason as the LLM extractor.
    Only symbol names are sent, never a transcript.
    """

    def __init__(self, model: str, fallback: ClusterNamer, client: Any | None = None) -> None:
        import anthropic

        self.name = f"anthropic:{model}"
        self._model = model
        self._fallback = fallback
        self._errors = (anthropic.APIStatusError, anthropic.APIConnectionError)
        self._client = client if client is not None else anthropic.Anthropic()
        self._cache: dict[tuple[str, ...], str] = {}

    def name_cluster(self, members: list[str], central: str) -> str:
        key = tuple(sorted(members))
        if key in self._cache:
            return self._cache[key]
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=200,
                system=(
                    "You label groups of related words from a dream journal. Reply with a plain descriptive label of one "
                    "to three lower-case words that names what the words have in common. Describe, do not interpret."
                ),
                messages=[{"role": "user", "content": ", ".join(members)}],
                output_config={
                    "effort": "low",
                    "format": {
                        "type": "json_schema",
                        "schema": {
                            "type": "object",
                            "properties": {"label": {"type": "string"}},
                            "required": ["label"],
                            "additionalProperties": False,
                        },
                    },
                },
            )
            if response.stop_reason != "end_turn":
                raise ValueError(f"stop_reason {response.stop_reason}")
            import json

            body = first_text(response.content)
            label = " ".join(str(json.loads(body)["label"]).lower().split())[:40]
            if not label:
                raise ValueError("empty label")
        except (*self._errors, ValueError, KeyError) as exc:
            log.warning("cluster naming failed (%s); using the central member", type(exc).__name__)
            label = self._fallback.name_cluster(members, central)
        self._cache[key] = label
        return label
