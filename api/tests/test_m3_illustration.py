"""Milestone 3: illustration generation and the entry timeline."""

from __future__ import annotations

import colorsys
import io
import re
from datetime import UTC, datetime
from typing import Any

import httpx
import numpy as np
import pytest
import resvg_py
from PIL import Image

from dreamlog.embed import FastEmbedEmbedder, symbol_text
from dreamlog.illustrate import ApiIllustrator, ProceduralIllustrator
from dreamlog.illustrate.geometry import Affine, emit, parse_path
from dreamlog.illustrate.glyphs import GLYPHS, word_index
from dreamlog.illustrate.matcher import GlyphMatcher
from dreamlog.illustrate.palette import MOODS, palette_for
from dreamlog.illustrate.procedural import SceneSpec, SceneSymbol, render_scene, seed_from
from dreamlog.illustrate.prompt import build_prompt
from dreamlog.illustrate.raster import svg_to_png
from dreamlog.service import Dreamlog


def spec(seed: str, mood: str, *symbols: tuple[str, float, str | None]) -> SceneSpec:
    return SceneSpec(seed_from(seed), [mood], [SceneSymbol(*s) for s in symbols])


def pixels(svg: str) -> np.ndarray[Any, Any]:
    return np.asarray(Image.open(io.BytesIO(svg_to_png(svg))).convert("RGB"), dtype=np.float32) / 255.0


WATER_SCENE = (("ocean", 1.0, "water"), ("door", 0.9, "door"), ("moon", 0.7, "moon"))


def test_same_entry_same_picture_and_different_entries_differ() -> None:
    first = render_scene(spec("entry-a", "calm", *WATER_SCENE))
    assert first == render_scene(spec("entry-a", "calm", *WATER_SCENE))
    assert first != render_scene(spec("entry-b", "calm", *WATER_SCENE))
    assert svg_to_png(first) == svg_to_png(first)


def test_style_bible_no_text_and_no_figures() -> None:
    svg = render_scene(spec("x", "nostalgic", ("mother", 1.0, "presence"), ("house", 0.8, "house"), ("kettle", 0.3, None)))
    assert "<text" not in svg and "<tspan" not in svg and "font" not in svg
    assert "<image" not in svg and "href" not in svg, "the picture must be self-contained"
    assert svg.startswith("<svg") and 'viewBox="0 0 800 1000"' in svg
    assert not any(tag in key for key in GLYPHS for tag in ("person", "man", "woman", "face", "figure"))


@pytest.mark.parametrize("mood", [m for m in MOODS if m != "neutral"])
def test_one_dominant_colour_per_mood(mood: str) -> None:
    """The painted area should sit at the mood's hue."""
    image = pixels(render_scene(spec("hue", mood, ("mountain", 1.0, "mountain"))))
    saturated = [colorsys.rgb_to_hsv(*px) for px in image[60:940:12, 60:740:12].reshape(-1, 3)]
    hues = np.array([h for h, s, v in saturated if s > 0.18])
    wash = palette_for([mood]).wash
    target = colorsys.rgb_to_hsv(*(int(wash[i : i + 2], 16) / 255 for i in (1, 3, 5)))[0]
    distance = np.minimum(np.abs(hues - target), 1 - np.abs(hues - target))
    assert len(hues) > 500 and float(np.median(distance)) < 0.06
    assert float(np.mean(distance < 0.12)) > 0.8


def test_every_mood_has_its_own_colour() -> None:
    washes = {palette_for([m]).wash for m in MOODS}
    assert len(washes) == len(MOODS)
    assert palette_for(["nonsense", "awed"]).mood == "awed" and palette_for([]).mood == "neutral"


def test_water_goes_low_in_the_frame() -> None:
    """With water, the lower third is painted darker than without it."""
    wet = pixels(render_scene(spec("frame", "calm", ("ocean", 1.0, "water"))))
    dry = pixels(render_scene(spec("frame", "calm")))
    lower_wet, lower_dry = wet[700:940, 80:720].mean(), dry[700:940, 80:720].mean()
    upper_wet, upper_dry = wet[80:400, 80:720].mean(), dry[80:400, 80:720].mean()
    assert lower_wet < lower_dry - 0.04
    assert abs(upper_wet - upper_dry) < 0.03


def test_moon_is_light_in_the_upper_half() -> None:
    with_moon = pixels(render_scene(spec("moon", "fearful", ("moon", 1.0, "moon"))))
    without = pixels(render_scene(spec("moon", "fearful")))
    gain = (with_moon - without).mean(axis=2)
    assert gain[:500].max() > 0.25 and float((gain[:500] > 0.2).sum()) > 4000
    assert float((gain[600:] > 0.2).sum()) < 200


def test_the_most_salient_object_is_painted_out_of_scale() -> None:
    """The hero is two to three times its natural size; a supporting copy of
    the same glyph is not."""
    hero = pixels(render_scene(spec("scale", "calm", ("door", 1.0, "door"))))
    support = pixels(render_scene(spec("scale", "calm", ("tree", 1.0, "tree"), ("door", 0.2, "door"))))
    empty = pixels(render_scene(spec("scale", "calm")))

    def glow_area(image: np.ndarray[Any, Any]) -> int:  # the lit gap in the door is the only warm light
        return int(((image[..., 0] - empty[..., 0] > 0.15) & (image[..., 0] > 0.85)).sum())

    assert glow_area(hero) > 4 * max(glow_area(support), 1)


def test_glyph_paths_survive_placement() -> None:
    for glyph in GLYPHS.values():
        for shape in glyph.shapes:
            segments = parse_path(shape.d)
            assert segments and segments[0][0] == "M", glyph.key
            placed = emit(segments, Affine.place(400, 600, 200, rotate=15))
            numbers = [float(n) for n in re.findall(r"-?\d+\.\d", placed)]
            assert numbers and all(-200 < n < 1200 for n in numbers), glyph.key
    m = Affine.place(400, 600, 200)
    assert m.apply((50, 100)) == pytest.approx((400, 600)) and m.apply((50, 0)) == pytest.approx((400, 400))
    mirrored = Affine.place(400, 600, 200, squash=-0.7)
    assert mirrored.apply((50, 0))[1] == pytest.approx(740), "a reflection hangs below its baseline"


def test_resvg_displacement_still_behaves_as_measured() -> None:
    """A canary. The pinned resvg moves a pixel by scale squared over two where
    the SVG spec says scale over two, and the painter compensates. If this
    fails after an upgrade, fix ``procedural._disp``."""

    def shift(scale: int) -> int:
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="400"><defs>'
            '<filter id="f" x="-100%" y="-100%" width="300%" height="300%" color-interpolation-filters="sRGB">'
            f'<feFlood flood-color="rgb(0,128,128)" result="m"/><feDisplacementMap in="SourceGraphic" in2="m" scale="{scale}" '
            'xChannelSelector="R" yChannelSelector="G"/></filter></defs><rect width="400" height="400" fill="#fff"/>'
            '<g filter="url(#f)"><rect x="140" y="140" width="120" height="120" fill="#000"/></g></svg>'
        )
        image = np.asarray(Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=svg)))).convert("L"))
        return int(np.where(image < 128)[1].min()) - 140

    measured = [shift(s) for s in (2, 4, 8)]
    print(f"\nresvg displacement for scale 2, 4, 8: {measured} px (the spec says 1, 2, 4)")
    assert measured == [2, 8, 32]


def test_glyph_lookup_by_word_and_by_kind() -> None:
    index = word_index()
    assert index["ocean"] == index["water"] == "water" and index["wolf"] == "dog"
    assert all(key in GLYPHS for key in index.values())
    listed = [w for g in GLYPHS.values() for w in g.words]
    assert len(listed) == len(set(listed)), "a word may point at one glyph only"


@pytest.mark.model
def test_glyph_lookup_by_embedding(embedder: FastEmbedEmbedder) -> None:
    matcher = GlyphMatcher(embedder)

    def glyph(word: str, kind: str = "object") -> str | None:
        return matcher.match(word, kind, embedder.embed([symbol_text(word)])[0])

    assert glyph("serpent", "animal") == "snake" and glyph("yacht") == "boat" and glyph("puppy", "animal") == "dog"
    assert glyph("grandmother", "person") == "presence" and glyph("dentist", "person") == "presence"
    assert glyph("questionnaire") is None and glyph("homesickness") is None


def test_illustrator_output_is_two_webps() -> None:
    picture = ProceduralIllustrator().illustrate(spec("webp", "awed", *WATER_SCENE), "unused")
    full, thumb = Image.open(io.BytesIO(picture.image)), Image.open(io.BytesIO(picture.thumb))
    assert (full.format, full.size) == ("WEBP", (800, 1000)) and (thumb.format, thumb.size) == ("WEBP", (400, 500))
    assert len(picture.image) < 250_000 and picture.engine == "procedural"


def test_api_illustrator_falls_back_to_the_painter(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: Any, **_kwargs: Any) -> httpx.Response:
        raise httpx.ConnectError("no network in tests")

    monkeypatch.setattr(httpx, "post", refuse)
    api = ApiIllustrator("https://example.invalid/images", "key", "some-model", ProceduralIllustrator())
    picture = api.illustrate(spec("fallback", "calm", *WATER_SCENE), "a prompt")
    assert picture.engine == "procedural" and picture.image[:4] == b"RIFF"


def test_prompt_follows_the_style_bible_and_leaves_the_dream_out() -> None:
    prompt = build_prompt([("door", "object"), ("mother", "person"), ("ocean", "nature")], ["calm"])
    assert "watercolour" in prompt.lower() and "No text" in prompt and "no people" in prompt
    assert "muted teal" in prompt and "door, ocean" in prompt
    assert "mother" not in prompt and "standing stones" in prompt


def test_timeline_is_newest_first_with_pictures(core: Dreamlog) -> None:
    old = core.create_from_text("A door in the sea.", created_at=datetime(2026, 5, 1, 7, tzinfo=UTC))
    new = core.create_from_text("A key under the moon.", created_at=datetime(2026, 9, 1, 7, tzinfo=UTC))
    listed = core.list_entries()
    assert [e.id for e in listed] == [new.id, old.id]
    for entry in listed:
        assert entry.image_url and entry.thumb_url and "size=thumb" in entry.thumb_url
        assert Image.open(io.BytesIO(core.entry_image(entry.id, thumb=True))).size == (400, 500)
    assert sorted(core.s.store.list()) == sorted(f"{kind}/{e.id}.webp" for e in listed for kind in ("images", "thumbs"))
    on_disk = (core.settings.data_dir / "objects" / f"images/{new.id}.webp").read_bytes()
    assert on_disk[:4] != b"RIFF", "pictures are encrypted at rest too"


def test_editing_repaints_and_deleting_removes_the_picture(core: Dreamlog) -> None:
    saved = core.create_from_text("A calm lake with a boat.")
    before = core.entry_image(saved.id, thumb=False)
    edited = core.update_entry(saved.id, "I was terrified. Wolves in the snow by a cabin.")
    assert core.entry_image(saved.id, thumb=False) != before
    assert edited.image_url != saved.image_url, "the URL carries a version so the browser refetches"
    core.delete_entry(saved.id)
    assert core.s.store.list() == []
