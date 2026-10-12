"""Draws the interim design-time art into assets/interim.

    .venv/bin/python scripts/build_art.py

Every file here stands in for an image requested in assets/prompts.md. The
scenes are painted by the same code that illustrates entries, so the interim
art already matches the product. A delivered file at the same path under
assets/generated replaces its interim twin with no code change.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from dreamlog.illustrate.atlas import AtlasSpec, AtlasSymbol, render_atlas  # noqa: E402
from dreamlog.illustrate.procedural import SceneSpec, SceneSymbol, render_scene, seed_from  # noqa: E402
from dreamlog.illustrate.raster import svg_to_png  # noqa: E402

OUT = ROOT / "assets" / "interim"
INK = "#2b2760"
PAPER = "#f7f2e8"
GLOW = "#f6cf7e"


def mark(scale: float = 1.0, rounded: bool = True) -> str:
    """The logo: a crescent moon holding three linked points. The moon is the
    dream; the linked points are the recurrence graph."""
    inner = (
        f'<circle cx="236" cy="262" r="142" fill="{PAPER}"/><circle cx="296" cy="222" r="130" fill="{INK}"/>'
        f'<path d="M318 170 L374 238 L332 320" fill="none" stroke="{GLOW}" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<circle cx="318" cy="170" r="17" fill="{GLOW}"/><circle cx="374" cy="238" r="12" fill="{GLOW}"/><circle cx="332" cy="320" r="21" fill="{GLOW}"/>'
    )
    shift = 256 * (1 - scale)
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512">'
        f'<rect width="512" height="512" rx="{116 if rounded else 0}" fill="{INK}"/>'
        f'<g transform="translate({shift:.1f} {shift:.1f}) scale({scale})">{inner}</g></svg>'
    )


def save(name: str, png: bytes, size: tuple[int, int] | None = None, crop: tuple[int, int, int, int] | None = None, colours: int | None = None) -> None:
    image = Image.open(io.BytesIO(png)).convert("RGBA" if colours is None else "RGB")
    if crop:
        image = image.crop(crop)
    if size:
        image = image.resize(size, Image.Resampling.LANCZOS)
    if colours:
        image = image.quantize(colours, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
    path = OUT / name
    image.save(path, "PNG", optimize=True)
    print(f"{name:26s} {image.size[0]}x{image.size[1]}  {path.stat().st_size // 1024} KB")


def scene(seed: str, mood: str, *symbols: tuple[str, float, str | None]) -> bytes:
    return svg_to_png(render_scene(SceneSpec(seed_from(seed), [mood], [SceneSymbol(*s) for s in symbols])))


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    logo = svg_to_png(mark())
    save("logo.png", logo, (256, 256))
    save("icon-192.png", logo, (192, 192))
    save("icon-512.png", logo, (512, 512))
    save("icon-maskable.png", svg_to_png(mark(scale=0.78, rounded=False)), (512, 512))

    band = (0, 170, 800, 770)  # the 4:3 middle of a 4:5 painting
    wide = (720, 540)
    save("onboarding-record.png", scene("onboarding-record-2", "fearful", ("moon", 1.0, "moon"), ("bed", 0.9, "bed"), ("window", 0.5, "window"), ("star", 0.4, "star")), wide, band, 200)
    save("onboarding-picture.png", scene("onboarding-picture", "calm", ("ocean", 1.0, "water"), ("door", 0.95, "door"), ("moon", 0.7, "moon"), ("house", 0.4, "house")), wide, band, 200)
    atlas = AtlasSpec(
        "interim",
        "awed",
        [AtlasSymbol("water", "water", 3.0), AtlasSymbol("door", "door", 2.6), AtlasSymbol("key", "key", 2.2), AtlasSymbol("moon", "moon", 1.8), AtlasSymbol("stairs", "stairs", 1.5), AtlasSymbol("bird", "bird", 1.2)],
        [(0, 1), (1, 2), (0, 3), (2, 4), (3, 5)],
    )
    save("onboarding-patterns.png", svg_to_png(render_atlas(atlas)), wide, (0, 60, 800, 660), 200)
    save("empty-timeline.png", scene("empty-timeline", "neutral", ("moon", 0.5, "moon"), ("door", 1.0, "door")), wide, band, 160)
    save("empty-patterns.png", scene("empty-patterns", "neutral", ("star", 1.0, "star"), ("mountain", 0.6, "mountain")), wide, band, 160)
    save("empty-search.png", scene("empty-search", "neutral", ("key", 1.0, "key"), ("cloud", 0.4, "cloud")), wide, band, 160)
    save("empty-atlas.png", scene("empty-atlas-3", "neutral", ("sea", 1.0, "water"), ("boat", 0.9, "boat"), ("bird", 0.3, "bird")), wide, band, 160)


if __name__ == "__main__":
    main()
