"""Illustration behind an adapter.

``Illustrator`` has two implementations. ``ProceduralIllustrator`` is the
default: it paints the scene itself and needs nothing. ``ApiIllustrator`` posts
the prompt to a hosted image model and falls back to the built-in painter on
any failure, so an entry always gets a picture.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Protocol

import httpx

from .procedural import SceneSpec, render_scene
from .raster import svg_to_png, to_webp

log = logging.getLogger(__name__)

IMAGE_WIDTH = 800
THUMB_WIDTH = 400


@dataclass(frozen=True)
class Illustration:
    image: bytes
    """WebP, 800 pixels wide, 4:5."""
    thumb: bytes
    """WebP, 400 pixels wide."""
    engine: str


class Illustrator(Protocol):
    name: str

    def illustrate(self, spec: SceneSpec, prompt: str) -> Illustration: ...


class ProceduralIllustrator:
    name = "procedural"

    def illustrate(self, spec: SceneSpec, prompt: str) -> Illustration:
        png = svg_to_png(render_scene(spec))
        return Illustration(image=to_webp(png), thumb=to_webp(png, width=THUMB_WIDTH, quality=80), engine=self.name)


class ApiIllustrator:
    """A hosted image model, spoken to in the OpenAI images dialect.

    UNTESTED: there was no image API key on the machine this was written on, so
    this code path has never run against a real service. It expects a JSON
    response with ``data[0].b64_json``.
    """

    def __init__(self, url: str, api_key: str, model: str, fallback: Illustrator, timeout_s: float = 60.0) -> None:
        self.name = f"api:{model}"
        self._url = url
        self._key = api_key
        self._model = model
        self._fallback = fallback
        self._timeout = timeout_s

    def illustrate(self, spec: SceneSpec, prompt: str) -> Illustration:
        try:
            response = httpx.post(
                self._url,
                headers={"Authorization": f"Bearer {self._key}"},
                json={"model": self._model, "prompt": prompt, "size": "1024x1536", "n": 1},
                timeout=self._timeout,
            )
            response.raise_for_status()
            png = base64.b64decode(response.json()["data"][0]["b64_json"])
            return Illustration(image=to_webp(png, width=IMAGE_WIDTH), thumb=to_webp(png, width=THUMB_WIDTH, quality=80), engine=self.name)
        except Exception as exc:  # any failure at all means: paint it ourselves
            log.warning("image API failed (%s); using the built-in painter", type(exc).__name__)
            return self._fallback.illustrate(spec, prompt)
