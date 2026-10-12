"""Milestone 2: symbol extraction and canonicalisation, on the 30 sample dreams."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from dreamlog.config import REPO_ROOT, Settings
from dreamlog.embed import FastEmbedEmbedder, HashEmbedder, symbol_text
from dreamlog.extract.anthropic_llm import SCHEMA, AnthropicExtractor
from dreamlog.extract.base import KINDS, MOODS
from dreamlog.extract.lexicon import LexiconExtractor, lemma, tag_moods, tokenize
from dreamlog.service import Dreamlog

# ---------------------------------------------------------------- the fixture


def test_fixture_is_thirty_labelled_dreams(dreams: list[dict[str, Any]]) -> None:
    assert len(dreams) == 30 and len({d["id"] for d in dreams}) == 30
    assert sum(d["water"] for d in dreams) == 8 and sum(d["pursuit"] for d in dreams) == 7
    for dream in dreams:
        assert isinstance(dream["water"], bool) and isinstance(dream["pursuit"], bool)
        assert 40 <= len(dream["text"].split()) <= 80
    text = " ".join(d["text"] for d in dreams).lower()
    assert " ocean" in text and " water" in text, "both words must occur or the merge test proves nothing"
    literal = [d["id"] for d in dreams if d["pursuit"] and "chas" in d["text"].lower()]
    assert len(literal) == 1, "pursuit dreams must not all say 'chase', or search could be keyword matching"


# ----------------------------------------------------------- offline extractor


def test_lexicon_extractor_on_the_fixture(dreams: list[dict[str, Any]]) -> None:
    """Scored against hand-listed symbols. The lexicon and the labels were
    written by the same person for the same dreams, so this measures that the
    extractor works on this fixture, not how it does on dreams in general."""
    extractor = LexiconExtractor()
    hit = extra = missed = 0
    for dream in dreams:
        got = {s.name for s in extractor.extract(dream["text"]).symbols}
        want = set(dream["expected_symbols"])
        hit, extra, missed = hit + len(got & want), extra + len(got - want), missed + len(want - got)
    precision, recall = hit / (hit + extra), hit / (hit + missed)
    print(f"\nlexicon extractor on 30 dreams: precision {precision:.3f}, recall {recall:.3f} ({hit} hit, {extra} extra, {missed} missed)")
    assert recall >= 0.95 and precision >= 0.85


def test_extraction_is_deterministic_and_well_formed(dreams: list[dict[str, Any]]) -> None:
    extractor = LexiconExtractor()
    for dream in dreams[:10]:
        first, second = extractor.extract(dream["text"]), extractor.extract(dream["text"])
        assert first == second
        assert first.symbols[0].salience == 1.0
        assert all(0 < s.salience <= 1 and s.kind in KINDS for s in first.symbols)
        assert [s.salience for s in first.symbols] == sorted((s.salience for s in first.symbols), reverse=True)
        assert all(m in MOODS for m in first.moods) and 1 <= len(first.moods) <= 2


def test_plurals_possessives_and_phrases() -> None:
    assert [lemma(w) for w in ("teeth", "wolves", "babies", "boxes", "stairs", "glass", "keys")] == [
        "tooth", "wolf", "baby", "box", "stairs", "glass", "key",
    ]  # fmt: skip
    assert tokenize("My grandmother’s house.") == ["my", "grandmother", "house", "."]
    names = {s.name: s.kind for s in LexiconExtractor().extract("We met at the swimming pool near the train station.").symbols}
    assert names == {"swimming pool": "place", "train station": "place"}


def test_unknown_nouns_are_found_by_grammar_with_lower_salience() -> None:
    found = {s.name: s.salience for s in LexiconExtractor().extract("The lecturer gave me a trombone and I climbed a mountain.").symbols}
    assert {"lecturer", "trombone", "mountain"} <= set(found)
    assert found["trombone"] < found["mountain"]
    assert "gave" not in found and "climbed" not in found


def test_mood_cues_respect_negation() -> None:
    assert tag_moods(tokenize("I was terrified and I hid.")) == ["fearful"]
    assert tag_moods(tokenize("It was not frightening. I felt calm and safe.")) == ["calm"]
    assert tag_moods(tokenize("Nobody panicked. It was funny.")) == ["joyful"]
    assert tag_moods(tokenize("A grey room with a table.")) == ["neutral"]


# ------------------------------------------------------- the LLM extractor


class _StubClient:
    """Stands in for anthropic.Anthropic. Records the request, replays a response."""

    def __init__(self, text: str, stop_reason: str = "end_turn") -> None:
        self.request: dict[str, Any] = {}
        self._response = SimpleNamespace(
            stop_reason=stop_reason, content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)]
        )
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **kwargs: Any) -> Any:
        self.request = kwargs
        return self._response


def test_llm_extractor_sends_a_strict_schema_and_validates_the_reply() -> None:
    reply = json.dumps(
        {
            "symbols": [
                {"name": "Ocean", "kind": "nature", "salience": 1.4},
                {"name": "front door", "kind": "object", "salience": 0.5},
                {"name": "ocean", "kind": "nature", "salience": 0.2},
            ],
            "moods": ["calm", "calm", "awed"],
        }
    )
    client = _StubClient(reply)
    result = AnthropicExtractor("claude-sonnet-5-5", LexiconExtractor(), client=client).extract("I stood by the ocean at a door.")
    assert [(s.name, s.salience) for s in result.symbols] == [("ocean", 1.0), ("front door", 0.5)]
    assert result.moods == ["calm", "awed"]
    sent = client.request
    assert sent["model"] == "claude-sonnet-5-5"
    assert sent["output_config"]["format"] == {"type": "json_schema", "schema": SCHEMA}
    assert SCHEMA["additionalProperties"] is False and SCHEMA["properties"]["symbols"]["items"]["additionalProperties"] is False
    assert "thinking" not in sent and "temperature" not in sent
    assert "interpret" in sent["system"]


@pytest.mark.parametrize(
    ("text", "stop_reason"),
    [
        ("", "refusal"),
        ('{"symbols": [', "max_tokens"),
        ("not json", "end_turn"),
        ('{"symbols": [{"name": "x", "kind": "vibe", "salience": 1}], "moods": ["calm"]}', "end_turn"),
    ],
)
def test_llm_extractor_falls_back_to_the_lexicon(text: str, stop_reason: str) -> None:
    extractor = AnthropicExtractor("claude-sonnet-5-5", LexiconExtractor(), client=_StubClient(text, stop_reason))
    assert {s.name for s in extractor.extract("A wolf stood at the door.").symbols} == {"wolf", "door"}


# ------------------------------------------------------------ canonicalisation


@pytest.mark.model
def test_water_and_ocean_merge_into_one_canonical_symbol(fixture_core: Dreamlog, dreams: list[dict[str, Any]]) -> None:
    """PRD acceptance test."""
    with fixture_core.s.db.connect() as conn:
        rows = conn.execute(
            "SELECT a.alias, a.symbol_id, s.canonical FROM symbol_aliases a JOIN symbols s ON s.id = a.symbol_id WHERE a.alias IN ('water', 'ocean')"
        ).fetchall()
    by_alias = {r["alias"]: r for r in rows}
    assert set(by_alias) == {"water", "ocean"}, "both words must have been extracted from the fixture"
    assert by_alias["water"]["symbol_id"] == by_alias["ocean"]["symbol_id"]
    canonical = by_alias["water"]["canonical"]

    # How much of the labelled water imagery does that one symbol catch?
    entries = {e.source.split(":")[1]: e for e in fixture_core.list_entries()}
    tagged = {d["id"] for d in dreams if any(s.name == canonical for s in entries[d["id"]].symbols)}
    truth = {d["id"] for d in dreams if d["water"]}
    precision, recall = len(tagged & truth) / len(tagged), len(tagged & truth) / len(truth)
    print(
        f"\ncanonical symbol {canonical!r}: aliases {sorted(by_alias)}, in {len(tagged)} dreams; against the water labels precision {precision:.2f}, recall {recall:.2f}"
    )
    assert canonical == "water", "the commoner word should name the symbol"
    assert precision == 1.0 and recall >= 0.75


@pytest.mark.model
def test_the_canonical_list_does_not_depend_on_the_order_of_the_dreams(real_core: Dreamlog, dreams: list[dict[str, Any]]) -> None:
    """Same thirty dreams in five different orders, same partition every time.
    The first version of canonicalisation failed this: whether ocean met water
    depended on whether a river had been dreamt first."""
    import random

    def partition(order: list[dict[str, Any]]) -> set[frozenset[str]]:
        real_core.delete_all()
        for dream in order:
            real_core.create_from_text(dream["text"], illustrate=False)
        return {frozenset(n.aliases) for n in real_core.graph().nodes}

    reference = partition(dreams)
    assert any({"water", "ocean"} <= group for group in reference)
    for seed in range(4):
        shuffled = dreams[:]
        random.Random(seed).shuffle(shuffled)
        assert partition(shuffled) == reference, f"order {seed} gave a different canonical list"
    merged = sorted((sorted(g) for g in reference if len(g) > 1), key=lambda g: (-len(g), g))
    print(f"\n{len(reference)} canonical symbols in every order; merged groups: {merged}")


@pytest.mark.model
def test_merging_really_is_by_similarity(embedder: FastEmbedEmbedder) -> None:
    """No table maps ocean to water: the pair clears the threshold on cosine
    similarity, and an unrelated pair does not."""
    water, ocean, door = embedder.embed([symbol_text(w) for w in ("water", "ocean", "door")])
    threshold = Settings().canonical_threshold
    print(f"\ncosine(water, ocean) = {float(water @ ocean):.3f}, cosine(water, door) = {float(water @ door):.3f}, threshold {threshold}")
    assert float(water @ ocean) >= threshold > float(water @ door)
    source = (REPO_ROOT / "api" / "dreamlog" / "canonical.py").read_text()
    code = source.split('"""', 2)[2]
    assert "ocean" not in code and "water" not in code


@pytest.mark.model
def test_threshold_matches_the_calibration(embedder: FastEmbedEmbedder) -> None:
    """The configured threshold must be the F1-optimal one on the labelled
    pairs, which do not include water/ocean."""
    pairs = json.loads((REPO_ROOT / "api" / "dreamlog" / "data" / "calibration_pairs.json").read_text())
    assert ["water", "ocean"] not in pairs["merge"] and ["ocean", "water"] not in pairs["merge"]
    words = sorted({w for key in ("merge", "distinct") for pair in pairs[key] for w in pair})
    vectors = dict(zip(words, embedder.embed([symbol_text(w) for w in words]), strict=True))
    merge = [float(vectors[a] @ vectors[b]) for a, b in pairs["merge"]]
    distinct = [float(vectors[a] @ vectors[b]) for a, b in pairs["distinct"]]

    def f1(t: float) -> float:
        tp, fp = sum(m >= t for m in merge), sum(d >= t for d in distinct)
        return 2 * tp / (2 * tp + fp + (len(merge) - tp))

    grid = [round(0.30 + 0.01 * i, 2) for i in range(66)]
    best = max(f1(t) for t in grid)
    chosen = Settings().canonical_threshold
    print(f"\nbest F1 {best:.3f}; F1 at the configured {chosen} is {f1(chosen):.3f}")
    assert f1(chosen) == pytest.approx(best)


@pytest.mark.model
def test_only_symbols_of_one_kind_merge(real_core: Dreamlog) -> None:
    real_core.create_from_text("My tooth fell out at the school.", illustrate=False)
    real_core.create_from_text("The dentist and the teacher were there.", illustrate=False)
    real_core.create_from_text("I swam in the sea.", illustrate=False)
    real_core.create_from_text("I swam in the ocean.", illustrate=False)
    graph = real_core.graph()
    names = {n.name: n.aliases for n in graph.nodes}
    assert {"tooth", "dentist", "school", "teacher"} <= set(names), "a person never merges into a thing, however close the vectors"
    assert ["ocean", "sea"] in names.values()


def test_exact_repeats_reuse_a_symbol_and_the_commoner_alias_names_it(core: Dreamlog) -> None:
    """Plumbing only, with the hashing embedder and a forced merge."""
    a = core.create_from_text("A key.", illustrate=False)
    b = core.create_from_text("A key again.", illustrate=False)
    assert a.symbols[0].id == b.symbols[0].id
    with core.s.db.write() as conn:  # fold a second spelling into the same symbol by hand
        vector = HashEmbedder().embed([symbol_text("latchkey")])[0]
        conn.execute(
            "INSERT INTO symbol_aliases (alias, symbol_id, kind, embedding, similarity) VALUES ('latchkey', %s, 'object', %s, 0.7)",
            (a.symbols[0].id, vector),
        )
        entry_ids = []
        for i in range(3):
            import uuid
            from datetime import UTC, datetime

            entry_id = uuid.uuid4()
            entry_ids.append(entry_id)
            conn.execute(
                "INSERT INTO entries (id, created_at, updated_at, transcript, embedding, source) VALUES (%s, %s, %s, %s, %s, 'test')",
                (entry_id, datetime.now(UTC), datetime.now(UTC), core.s.cipher.encrypt_text(f"dream {i}", context=entry_id.bytes), vector),
            )
            conn.execute("INSERT INTO entry_symbols VALUES (%s, %s, 1.0, %s)", (entry_id, a.symbols[0].id, ["latchkey"]))
        from dreamlog import canonical

        canonical.tidy(conn, lambda *_: None)
    assert [n.name for n in core.graph().nodes] == ["latchkey"], "three uses beat two"
    for entry_id in entry_ids:
        core.delete_entry(entry_id)
    assert [n.name for n in core.graph().nodes] == ["key"], "and the name goes back when those dreams are deleted"


def test_embeddings_are_unit_vectors_of_the_stored_width(core: Dreamlog) -> None:
    saved = core.create_from_text("A lantern on a hill.", illustrate=False)
    with core.s.db.connect() as conn:
        entry = conn.execute("SELECT vector_dims(embedding) AS d, vector_norm(embedding) AS n FROM entries WHERE id = %s", (saved.id,)).fetchone()
        symbols = conn.execute("SELECT vector_dims(embedding) AS d, vector_norm(embedding) AS n FROM symbols").fetchall()
    assert entry is not None and entry["d"] == 384 and entry["n"] == pytest.approx(1.0, abs=1e-4)
    assert len(symbols) == 2 and all(r["d"] == 384 and r["n"] == pytest.approx(1.0, abs=1e-4) for r in symbols)
    assert np.isfinite(HashEmbedder().embed(["", "the"])).all()
