"""The monthly dream atlas: the month's six strongest symbols as one poster.

Drawn as a chart of islands. Each symbol gets an island sized by its strength
that month, ringed with depth contours, and a dotted route joins two islands
whenever their symbols turned up in the same dream. Same paint, same paper and
the same rule as the illustrations: no text and no people.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .geometry import Affine, band, blob, circle_path
from .glyphs import GLYPHS
from .palette import palette_for
from .procedural import MARGIN, H, W, _defs, _splatter, paint_glyph, seed_from

SLOTS: tuple[tuple[float, float], ...] = ((0.31, 0.22), (0.70, 0.30), (0.33, 0.52), (0.71, 0.61), (0.29, 0.81), (0.67, 0.86))


@dataclass(frozen=True)
class AtlasSymbol:
    name: str
    glyph: str | None
    strength: float


@dataclass(frozen=True)
class AtlasSpec:
    month: str
    mood: str
    symbols: list[AtlasSymbol]
    """At most six, strongest first."""
    routes: list[tuple[int, int]]
    """Index pairs into ``symbols`` that shared a dream this month."""


def render_atlas(spec: AtlasSpec) -> str:
    """Returns a self-contained SVG, 800 by 1000. Rasterise larger for a poster."""
    seed = seed_from("atlas:" + spec.month)
    rng = random.Random(seed)
    pal = palette_for([spec.mood])
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
        _defs(seed, pal),
        f'<rect width="{W}" height="{H}" fill="{pal.paper}"/>',
        f'<g filter="url(#wash)" style="mix-blend-mode:multiply"><path d="{band(rng, MARGIN, W - MARGIN, MARGIN, H - MARGIN)}" fill="{pal.wash}" opacity="0.5"/></g>',
    ]
    top = max((s.strength for s in spec.symbols), default=1.0) or 1.0
    centres: list[tuple[float, float, float]] = []
    for i, _symbol in enumerate(spec.symbols[:6]):
        sx, sy = SLOTS[i]
        r = 62 + 58 * (spec.symbols[i].strength / top)
        centres.append((sx * W + rng.uniform(-16, 16), sy * H + rng.uniform(-14, 14), r))

    # Routes go under the islands so they seem to leave from the shore.
    routes: list[str] = []
    for a, b in spec.routes:
        if a >= len(centres) or b >= len(centres):
            continue
        (ax, ay, _), (bx, by, _) = centres[a], centres[b]
        mx, my = (ax + bx) / 2, (ay + by) / 2
        bow = rng.uniform(-0.18, 0.18)
        cx, cy = mx - (by - ay) * bow, my + (bx - ax) * bow
        routes.append(f'<path d="M{ax:.1f},{ay:.1f} Q{cx:.1f},{cy:.1f} {bx:.1f},{by:.1f}"/>')
    if routes:
        parts.append(
            f'<g fill="none" stroke="{pal.deep}" stroke-width="2.4" stroke-linecap="round" stroke-dasharray="1 10" '
            f'style="mix-blend-mode:multiply" opacity="0.55">{"".join(routes)}</g>'
        )

    for (cx, cy, r), symbol in zip(centres, spec.symbols, strict=False):
        own = random.Random(seed_from(f"island:{spec.month}:{symbol.name}"))
        rings = "".join(
            f'<path d="{blob(own, cx, cy, r + gap, (r + gap) * 0.86, points=9, wobble=0.1)}" fill="none" stroke="{pal.paper}" stroke-width="{width}"/>'
            for gap, width in ((16, 2.0), (30, 1.4))
        )
        parts.append(f'<g filter="url(#soft)" opacity="0.6">{rings}</g>')
        # Land is paper left unpainted, with the sea pooling darker along its shore.
        island = blob(own, cx, cy, r, r * 0.86, points=9, wobble=0.16)
        parts.append(
            f'<g filter="url(#wash)" style="mix-blend-mode:multiply" opacity="0.55">'
            f'<path d="{island}" fill="none" stroke="{pal.ground}" stroke-width="9"/></g>'
        )
        parts.append(f'<g filter="url(#soft)" opacity="0.9"><path d="{island}" fill="{pal.paper}"/></g>')
        glyph = GLYPHS.get(symbol.glyph or "")
        if glyph is None:
            # No glyph: a dark pebble whose shape is fixed by the name. A light
            # would vanish against the paper island.
            pebble = blob(random.Random(seed_from("pebble:" + symbol.name)), cx, cy, r * 0.3, r * 0.24, points=7, wobble=0.22)
            parts.append(f'<g filter="url(#ink)" style="mix-blend-mode:multiply" opacity="0.8"><path d="{pebble}" fill="{pal.mid}"/></g>')
        else:
            size = r * 1.12
            parts.append(paint_glyph(glyph, Affine.place(cx, cy + size * 0.5, size), pal))

    # A compass star in the emptiest corner, and a little spray.
    star = GLYPHS["star"]
    parts.append(paint_glyph(star, Affine.place(W - MARGIN - 70, MARGIN + 120, 64, rotate=rng.uniform(-10, 10)), pal))
    parts.append(
        f'<g filter="url(#soft)" opacity="0.5"><path d="{circle_path(W - MARGIN - 70, MARGIN + 88, 44)}" fill="none" stroke="{pal.paper}" stroke-width="1.6"/></g>'
    )
    parts.append(_splatter(rng, pal))
    parts.append(f'<rect width="{W}" height="{H}" filter="url(#paper)" style="mix-blend-mode:multiply" opacity="0.5"/>')
    parts.append("</svg>")
    return "".join(parts)


def strongest(rows: list[tuple[str, str | None, float, int]], limit: int = 6) -> list[tuple[str, str | None, float, int]]:
    """Orders (name, glyph, summed salience, entry count) rows: strength, then
    how many dreams, then name, so the choice never depends on row order."""
    return sorted(rows, key=lambda row: (-round(row[2], 4), -row[3], row[0]))[:limit]
