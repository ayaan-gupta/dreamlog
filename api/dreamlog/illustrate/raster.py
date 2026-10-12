"""SVG to pixels. resvg is a self-contained Rust renderer, so the same SVG
gives the same image on a laptop and in CI, with no system libraries."""

from __future__ import annotations

import io

import resvg_py
from PIL import Image


def svg_to_png(svg: str, width: int | None = None) -> bytes:
    return bytes(resvg_py.svg_to_bytes(svg_string=svg, width=width) if width else resvg_py.svg_to_bytes(svg_string=svg))


def to_webp(png: bytes, *, width: int | None = None, quality: int = 82) -> bytes:
    image = Image.open(io.BytesIO(png)).convert("RGB")
    if width and width != image.width:
        image = image.resize((width, round(image.height * width / image.width)), Image.Resampling.LANCZOS)
    out = io.BytesIO()
    image.save(out, "WEBP", quality=quality, method=4)
    return out.getvalue()


def paint_webp(svg: str) -> tuple[bytes, bytes]:
    """Full image and thumbnail for one SVG. Top-level so a worker process can
    run it: resvg holds the GIL, so threads do not help."""
    png = svg_to_png(svg)
    return to_webp(png), to_webp(png, width=400, quality=80)
