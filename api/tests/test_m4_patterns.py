"""Milestone 4: recurrence graph, clusters, search, monthly atlas, export and delete."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from dreamlog.clusters import AnthropicNamer, CentralNamer, cluster_symbols, most_central
from dreamlog.db import TABLES, as_array
from dreamlog.embed import FastEmbedEmbedder
from dreamlog.illustrate.atlas import AtlasSpec, AtlasSymbol, render_atlas, strongest
from dreamlog.main import DISCLAIMER, create_app
from dreamlog.service import Dreamlog, NotFound, clean_query

from .conftest import AUDIO, make_settings, real

# ---------------------------------------------------------------------- graph


def test_graph_counts_dreams_and_links_symbols_that_share_one(core: Dreamlog) -> None:
    core.create_from_text("A door and a key.", illustrate=False)
    core.create_from_text("A door and a moon.", illustrate=False)
    core.create_from_text("A whale.", illustrate=False)
    graph = core.graph()
    nodes = {n.name: n for n in graph.nodes}
    assert {name: n.count for name, n in nodes.items()} == {"door": 2, "key": 1, "moon": 1, "whale": 1}
    links = {
        frozenset((next(n.name for n in graph.nodes if n.id == e.source), next(n.name for n in graph.nodes if n.id == e.target))): e.weight
        for e in graph.edges
    }
    assert links == {frozenset(("door", "key")): 1, frozenset(("door", "moon")): 1}
    assert graph.entries == 3 and nodes["door"].glyph == "door"


def test_edge_weight_is_the_number_of_shared_dreams(core: Dreamlog) -> None:
    for _ in range(3):
        core.create_from_text("A snake under a bridge.", illustrate=False)
    (edge,) = core.graph().edges
    assert edge.weight == 3


@pytest.mark.model
def test_fixture_graph_matches_a_recount_from_the_entries(fixture_core: Dreamlog) -> None:
    graph = fixture_core.graph()
    entries = fixture_core.list_entries()
    counts: dict[int, int] = {}
    pairs: dict[tuple[int, int], int] = {}
    for entry in entries:
        ids = sorted(s.id for s in entry.symbols)
        for symbol_id in ids:
            counts[symbol_id] = counts.get(symbol_id, 0) + 1
        for pair in combinations(ids, 2):
            pairs[pair] = pairs.get(pair, 0) + 1
    assert {n.id: n.count for n in graph.nodes} == counts
    assert {(e.source, e.target): e.weight for e in graph.edges} == pairs
    recurring = sorted(((n.count, n.name) for n in graph.nodes if n.count >= 3), reverse=True)
    print(f"\n{len(graph.nodes)} canonical symbols, {len(graph.edges)} links, {len(graph.clusters)} clusters; recurring: {recurring}")


@pytest.mark.model
def test_hdbscan_clusters_are_coherent_and_named_by_their_central_member(fixture_core: Dreamlog) -> None:
    graph = fixture_core.graph()
    names = {n.id: n.name for n in graph.nodes}
    assert len(graph.clusters) >= 5
    clustered = [m for c in graph.clusters for m in c.members]
    assert len(clustered) == len(set(clustered)), "a symbol is in at most one cluster"
    assert {n.id for n in graph.nodes if n.cluster is not None} == set(clustered)
    for cluster in graph.clusters:
        assert len(cluster.members) >= 3 and cluster.named_by == "most-central"
        assert cluster.name in {names[m] for m in cluster.members}
    print("\nclusters:", [(c.name, sorted(names[m] for m in c.members)) for c in graph.clusters])
    # Coherent means: members are closer to each other than to everything else.
    with fixture_core.s.db.connect() as conn:
        vectors = {r["id"]: as_array(r["embedding"]) for r in conn.execute("SELECT id, embedding FROM symbols").fetchall()}
    margins = []
    for cluster in graph.clusters:
        inside = np.stack([vectors[m] for m in cluster.members])
        outside = np.stack([v for i, v in vectors.items() if i not in cluster.members])
        within = (inside @ inside.T)[np.triu_indices(len(inside), 1)].mean()
        across = (inside @ outside.T).mean()
        margins.append(float(within - across))
        assert within > across + 0.1, cluster.name
    print(f"mean cosine inside a cluster exceeds the mean to outsiders by {np.mean(margins):.2f} on average (smallest {min(margins):.2f})")
    assert graph.model_dump() == fixture_core.graph().model_dump(), "clustering is deterministic"


def test_clustering_on_synthetic_blobs() -> None:
    rng = np.random.default_rng(0)
    centres = np.eye(8, dtype=np.float32)[:3] * 4
    points = np.concatenate([c + rng.normal(0, 0.05, (6, 8)).astype(np.float32) for c in centres])
    points /= np.linalg.norm(points, axis=1, keepdims=True)
    labels = cluster_symbols(points)
    assert len(set(labels[:6])) == 1 and len(set(labels[6:12])) == 1 and len(set(labels[12:])) == 1
    assert len({labels[0], labels[6], labels[12]}) == 3
    assert most_central(points, list(range(6))) in range(6)
    assert list(cluster_symbols(points[:4])) == [-1, -1, -1, -1], "too few symbols to call anything a cluster"


def test_llm_cluster_namer_uses_the_reply_and_falls_back() -> None:
    def client(text: str, stop: str = "end_turn") -> Any:
        response = SimpleNamespace(stop_reason=stop, content=[SimpleNamespace(type="text", text=text)])
        return SimpleNamespace(messages=SimpleNamespace(create=lambda **_: response))

    good = AnthropicNamer("claude-sonnet-5-5", CentralNamer(), client=client('{"label": "Bodies of Water"}'))
    assert good.name_cluster(["lake", "river", "sea"], "river") == "bodies of water"
    refused = AnthropicNamer("claude-sonnet-5-5", CentralNamer(), client=client("", "refusal"))
    assert refused.name_cluster(["lake", "river", "sea"], "river") == "river"


# --------------------------------------------------------------------- search


def test_query_cleaning() -> None:
    assert clean_query("dreams about water") == "water"
    assert clean_query("  Dreams  with my mother ") == "mother"
    assert clean_query("the sea") == "sea"
    assert clean_query("being chased") == "being chased"
    assert clean_query("dreams") == "dreams"


@pytest.mark.model
def test_search_for_being_chased_returns_the_pursuit_dreams(fixture_core: Dreamlog, dreams: list[dict[str, Any]]) -> None:
    """PRD acceptance test, with numbers. The app shows a ranked list of ten."""
    truth = {d["id"] for d in dreams if d["pursuit"]}
    result = fixture_core.search("being chased")
    ranked = [hit.entry.source.split(":")[1] for hit in result.hits]
    returned = set(ranked)
    precision, recall = len(returned & truth) / len(returned), len(returned & truth) / len(truth)
    hits = 0
    average_precision = 0.0
    for rank, dream_id in enumerate(ranked, 1):
        if dream_id in truth:
            hits += 1
            average_precision += hits / rank
    average_precision /= len(truth)
    r_precision = len(set(ranked[: len(truth)]) & truth) / len(truth)
    print(
        f"\n'being chased': {len(ranked)} returned, {len(returned & truth)} of {len(truth)} pursuit dreams among them. "
        f"precision {precision:.2f}, recall {recall:.2f}, average precision {average_precision:.2f}, "
        f"precision in the first {len(truth)}: {r_precision:.2f}"
    )
    print("ranking:", [(d + ("*" if d in truth else ""), h.score) for d, h in zip(ranked, result.hits, strict=True)])
    assert result.matched_symbol is None and all(h.via == "meaning" for h in result.hits), "this query must be answered by meaning alone"
    assert recall == 1.0
    assert r_precision >= 0.85, "the pursuit dreams should lead the list"
    assert precision >= 0.6


@pytest.mark.model
def test_search_for_water_finds_ocean_dreams_through_the_symbol(fixture_core: Dreamlog, dreams: list[dict[str, Any]]) -> None:
    truth = {d["id"] for d in dreams if d["water"]}
    result = fixture_core.search("dreams about water")
    ranked = [hit.entry.source.split(":")[1] for hit in result.hits]
    assert result.cleaned == "water" and result.matched_symbol == "water"
    first = set(ranked[: len(truth)])
    print(f"\n'dreams about water': first {len(truth)} results contain {len(first & truth)} of {len(truth)} water dreams; all returned: {ranked}")
    assert first == truth
    ocean_only = [d["id"] for d in dreams if d["water"] and "water" not in d["text"].lower()]
    assert ocean_only and set(ocean_only) <= first, "dreams that never say 'water' are found through the merged symbol"


@pytest.mark.model
def test_search_returns_nothing_for_something_no_dream_is_near(fixture_core: Dreamlog) -> None:
    assert fixture_core.search("quarterly tax return").hits == []
    assert len(fixture_core.search("a house with hidden rooms").hits) >= 1


# ---------------------------------------------------------------------- atlas


def test_atlas_picks_the_six_strongest_symbols_of_the_month(core: Dreamlog) -> None:
    september = datetime(2026, 9, 10, 7, tzinfo=UTC)
    for text in ("A door. A door again and a key.", "A door and a moon and a whale.", "A door, a key, a bridge, a snake, a tower, a boat, a clock."):
        core.create_from_text(text, created_at=september, illustrate=False)
    core.create_from_text("A dragon in October.", created_at=datetime(2026, 10, 2, 7, tzinfo=UTC), illustrate=False)
    atlas = core.atlas("2026-09")
    assert len(atlas.symbols) == 6 and [s.name for s in atlas.symbols[:2]] == ["door", "key"]
    assert atlas.symbols[0].entries == 3 and "dragon" not in {s.name for s in atlas.symbols}
    strengths = [s.strength for s in atlas.symbols]
    assert strengths == sorted(strengths, reverse=True)
    assert [m.month for m in core.months()] == ["2026-10", "2026-09"]
    with pytest.raises(NotFound):
        core.atlas("2026-01")
    with pytest.raises(ValueError, match="2026-10"):
        core.atlas("September")


def test_strongest_breaks_ties_by_count_then_name() -> None:
    rows = [("b", None, 1.0, 1), ("a", None, 1.0, 1), ("c", None, 1.0, 2), ("d", None, 2.0, 1)]
    assert [r[0] for r in strongest(rows, 3)] == ["d", "c", "a"]


def test_atlas_poster_is_a_cached_downloadable_image(core: Dreamlog) -> None:
    for text in ("A door by the sea under the moon.", "A key and a door and a bridge.", "A snake at the door."):
        core.create_from_text(text, created_at=datetime(2026, 9, 10, 7, tzinfo=UTC), illustrate=False)
    png = core.atlas_image("2026-09", "png")
    poster = Image.open(io.BytesIO(png))
    assert (poster.format, poster.size) == ("PNG", (1200, 1500))
    assert core.atlas_image("2026-09", "png") == png and len(core.s.store.list("atlas/")) == 2
    assert Image.open(io.BytesIO(core.atlas_image("2026-09", "webp"))).format == "WEBP"
    core.create_from_text("A whale and a whale and a whale.", created_at=datetime(2026, 9, 12, 7, tzinfo=UTC), illustrate=False)
    assert core.s.store.list("atlas/") == [], "a new dream that month invalidates the poster"
    assert core.atlas("2026-09").image_url != "", "and the next request paints a new one"


def test_atlas_svg_is_textless_and_deterministic() -> None:
    spec = AtlasSpec(
        "2026-09", "awed", [AtlasSymbol("water", "water", 3.0), AtlasSymbol("door", "door", 2.0), AtlasSymbol("kettle", None, 1.0)], [(0, 1)]
    )
    svg = render_atlas(spec)
    assert svg == render_atlas(spec) and "<text" not in svg and "stroke-dasharray" in svg


# -------------------------------------------------------------------- privacy


def test_export_contains_everything_decrypted(core: Dreamlog) -> None:
    first = core.create_from_text("A red door in the sea.")
    second = core.create_from_text("I was terrified of a wolf.")
    archive = zipfile.ZipFile(io.BytesIO(core.export_zip()))
    names = set(archive.namelist())
    assert names == {"entries.json", "symbols.json", "README.txt", f"images/{first.id}.webp", f"images/{second.id}.webp"}
    entries = json.loads(archive.read("entries.json"))
    assert [e["transcript"] for e in entries] == [first.transcript, second.transcript]
    assert entries[1]["moods"] == ["fearful"] and {s["name"] for s in entries[0]["symbols"]} == {"door", "sea"}
    assert archive.read(f"images/{first.id}.webp")[:4] == b"RIFF"
    assert {s["name"] for s in json.loads(archive.read("symbols.json"))} == {"door", "sea", "wolf"}


@pytest.mark.model
def test_delete_all_removes_every_row_file_and_embedding(tmp_path: Path, embedder: FastEmbedEmbedder) -> None:
    """PRD acceptance test. Real embeddings, real pictures, audio retention on
    so there are audio files to remove as well."""
    core = real(tmp_path, embedder, keep_audio=True)
    try:
        core.load_fixtures(illustrate=False)
        with_picture = core.create_from_text("A door standing in the ocean under an enormous moon.")
        core.create_from_audio((AUDIO / "clip-short.m4a").read_bytes(), ".m4a")
        core.atlas_image("2026-10")

        with core.s.db.connect() as conn:
            before = {t: conn.execute(f"SELECT count(*) AS n FROM {t}").fetchone()["n"] for t in TABLES}  # type: ignore[index]
            vectors = conn.execute(
                "SELECT (SELECT count(embedding) FROM entries) + (SELECT count(embedding) FROM symbols) + (SELECT count(embedding) FROM symbol_aliases) AS n"
            ).fetchone()
        files_before = [p for p in tmp_path.rglob("*") if p.is_file() and p.name != "dev.key"]
        assert before["entries"] == 32 and all(n > 0 for n in before.values())
        assert vectors is not None and vectors["n"] > 300
        assert {p.parent.name for p in files_before} >= {"images", "thumbs", "audio", "atlas"}

        deleted = core.delete_all()
        print(f"\ndelete-all removed {deleted.model_dump()}; before: {before}, {vectors['n']} vectors, {len(files_before)} files")
        assert deleted.entries == 32 and deleted.files == len(files_before)

        with core.s.db.connect() as conn:
            # Every table in the schema, not just the ones this test knows about.
            tables = [r["tablename"] for r in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'").fetchall()]
            assert sorted(tables) == sorted(TABLES)
            for table in tables:
                assert conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"] == 0, table  # type: ignore[index]
            vector_columns = conn.execute(
                "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'public' AND udt_name = 'vector'"
            ).fetchall()
            assert len(vector_columns) == 3
            for column in vector_columns:
                left = conn.execute(f"SELECT count({column['column_name']}) AS n FROM {column['table_name']}").fetchone()
                assert left is not None and left["n"] == 0
            # TRUNCATE gives each table a fresh, empty file: nothing waits for a vacuum.
            sizes = conn.execute("SELECT sum(pg_relation_size(c.oid)) AS bytes FROM pg_class c WHERE c.relname = ANY(%s)", (list(TABLES),)).fetchone()
            assert sizes is not None and sizes["bytes"] == 0
        assert [p for p in tmp_path.rglob("*") if p.is_file() and p.name != "dev.key"] == []
        assert core.s.store.list() == []
        assert not (tmp_path / "objects" / "images").exists()
        assert core.list_entries() == [] and core.graph().nodes == [] and core.search("door").hits == []
        with pytest.raises(NotFound):
            core.entry_image(with_picture.id, thumb=False)
    finally:
        core.s.db.close()


def test_delete_all_replaces_a_generated_key(tmp_path: Path) -> None:
    from dreamlog.service import build_services

    core = Dreamlog(build_services(make_settings(tmp_path, encryption_key="")))
    try:
        core.delete_all()
        core.create_from_text("A door.", illustrate=False)
        old = (tmp_path / "dev.key").read_text()
        core.delete_all()
        assert (tmp_path / "dev.key").read_text() != old
        saved = core.create_from_text("A key.", illustrate=False)
        assert core.get_entry(saved.id).transcript == "A key."
    finally:
        core.s.db.close()


def test_privacy_status_and_disclaimer_over_http(tmp_path: Path) -> None:
    with TestClient(create_app(make_settings(tmp_path), warm=False)) as client:
        client.delete("/api/all", params={"confirm": "delete-everything"})
        status = client.get("/api/privacy").json()
        assert status["local_only"] is True and status["keep_audio"] is False and status["key_source"] == "environment"
        assert "embeddings" in status["not_encrypted"] and "transcripts" in status["encrypted"]
        meta = client.get("/api/meta").json()
        assert meta["disclaimer"] == DISCLAIMER and "patterns only" in DISCLAIMER and "not medical or psychological advice" in DISCLAIMER
        assert client.delete("/api/all").status_code == 400, "delete-all needs the confirmation phrase"
        client.post("/api/entries", json={"text": "A door by the sea."})
        export = client.get("/api/export")
        assert export.headers["content-type"] == "application/zip" and "attachment" in export.headers["content-disposition"]
        assert client.delete("/api/all", params={"confirm": "delete-everything"}).json()["entries"] == 1
        assert client.get("/api/entries").json() == []
