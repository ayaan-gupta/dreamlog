"""The built-in illustrator: a watercolour painted in SVG.

No network and no model. A scene is laid out from the entry's symbols, painted
in the colour of its mood, and seeded by the entry id so the same dream always
gets the same picture and two dreams never share one.

How the paint works. Every wash is a plain shape pushed through one filter:
low-frequency noise displaces the outline so it wanders like a wet edge, finer
noise thins the pigment in patches, and the difference between the shape and
an eroded, blurred copy of itself leaves a darker rim where real paint pools
as it dries. Washes are multiplied onto the paper, so overlaps darken the way
glazes do. Light is never painted: moons, sails and windows are paper showing
through.

Scale is deliberately wrong. The most salient object is painted two to three
times its natural size and the least salient is shrunk, which is most of what
makes a scene read as a dream instead of a postcard.
"""

from __future__ import annotations

import hashlib
import math
import random
from dataclasses import dataclass

from .geometry import Affine, band, blob, circle_path, emit, parse_path, smooth_open
from .glyphs import GLYPHS, Glyph
from .palette import Palette, palette_for

W = 800
H = 1000
MARGIN = 38


@dataclass(frozen=True)
class SceneSymbol:
    name: str
    salience: float
    glyph: str | None
    """Key into the glyph library, or None for an abstract mark."""


@dataclass(frozen=True)
class SceneSpec:
    seed: int
    moods: list[str]
    symbols: list[SceneSymbol]


def seed_from(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode()).digest()[:6], "big")


def _disp(pixels: float) -> str:
    """The scale attribute that makes resvg displace by up to ``pixels / 2``.

    The SVG spec says a displacement map moves a pixel by scale * (c - 0.5).
    The resvg build this project pins applies scale twice: a flat map with
    scale 8 moves a square 32 pixels, and scales 1, 2, 4, 8, 16 give 0.5, 2, 8,
    32, 128. So the renderer asks for the square root of what it wants.
    ``tests/test_illustration.py`` measures this and fails if resvg changes.
    """
    return f"{math.sqrt(pixels):.3f}"


def _defs(seed: int, pal: Palette) -> str:
    a, b, c, d = (seed % 9973, seed // 7 % 9973, seed // 61 % 9973, seed // 331 % 9973)
    return f"""<defs>
<filter id="wash" x="-12%" y="-12%" width="124%" height="124%" color-interpolation-filters="sRGB">
<feTurbulence type="fractalNoise" baseFrequency="0.007 0.010" numOctaves="2" seed="{a}" result="warp"/>
<feColorMatrix in="warp" type="matrix" values="1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 0 1" result="map"/>
<feDisplacementMap in="SourceGraphic" in2="map" scale="{_disp(58)}" xChannelSelector="R" yChannelSelector="G" result="shape"/>
<feGaussianBlur in="shape" stdDeviation="1.5" result="soft"/>
<feTurbulence type="fractalNoise" baseFrequency="0.012" numOctaves="3" seed="{b}" result="grain"/>
<feColorMatrix in="grain" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 1.25 0 0 0 0.2" result="density"/>
<feComposite in="soft" in2="density" operator="in" result="body"/>
<feMorphology in="soft" operator="erode" radius="4" result="inner"/>
<feGaussianBlur in="inner" stdDeviation="7" result="innerSoft"/>
<feComposite in="soft" in2="innerSoft" operator="out" result="rim"/>
<feMerge><feMergeNode in="body"/><feMergeNode in="rim"/></feMerge>
</filter>
<filter id="ink" x="-12%" y="-12%" width="124%" height="124%" color-interpolation-filters="sRGB">
<feTurbulence type="fractalNoise" baseFrequency="0.024" numOctaves="2" seed="{c}" result="warp"/>
<feColorMatrix in="warp" type="matrix" values="1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 0 1" result="map"/>
<feDisplacementMap in="SourceGraphic" in2="map" scale="{_disp(9)}" xChannelSelector="R" yChannelSelector="G" result="shape"/>
<feGaussianBlur in="shape" stdDeviation="0.8" result="soft"/>
<feTurbulence type="fractalNoise" baseFrequency="0.05" numOctaves="3" seed="{d}" result="grain"/>
<feColorMatrix in="grain" type="matrix" values="0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0.9 0 0 0 0.5" result="density"/>
<feComposite in="soft" in2="density" operator="in"/>
</filter>
<filter id="soft" x="-15%" y="-15%" width="130%" height="130%">
<feTurbulence type="fractalNoise" baseFrequency="0.03" numOctaves="2" seed="{b}" result="warp"/>
<feColorMatrix in="warp" type="matrix" values="1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 0 1" result="map"/>
<feDisplacementMap in="SourceGraphic" in2="map" scale="{_disp(6)}" xChannelSelector="G" yChannelSelector="R"/>
<feGaussianBlur stdDeviation="1.1"/>
</filter>
<filter id="bloom" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="16"/></filter>
<filter id="halo" x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="20"/></filter>
<filter id="ripple" x="-15%" y="-15%" width="130%" height="130%">
<feTurbulence type="fractalNoise" baseFrequency="0.004 0.07" numOctaves="2" seed="{c}" result="warp"/>
<feColorMatrix in="warp" type="matrix" values="1 0 0 0 0 0 1 0 0 0 0 0 1 0 0 0 0 0 0 1" result="map"/>
<feDisplacementMap in="SourceGraphic" in2="map" scale="{_disp(30)}" xChannelSelector="R" yChannelSelector="G"/>
<feGaussianBlur stdDeviation="1.6"/>
</filter>
<filter id="paper" x="0" y="0" width="100%" height="100%">
<feTurbulence type="fractalNoise" baseFrequency="0.75" numOctaves="3" seed="{a % 97}" result="tooth"/>
<feDiffuseLighting in="tooth" surfaceScale="1.5" diffuseConstant="1.05" lighting-color="#ffffff"><feDistantLight azimuth="50" elevation="62"/></feDiffuseLighting>
</filter>
<linearGradient id="skyfade" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="{pal.wash}" stop-opacity="1"/>
<stop offset="0.55" stop-color="{pal.wash}" stop-opacity="0.78"/>
<stop offset="1" stop-color="{pal.wash}" stop-opacity="0.38"/>
</linearGradient>
<linearGradient id="groundfade" x1="0" y1="0" x2="0" y2="1">
<stop offset="0" stop-color="{pal.ground}" stop-opacity="0.72"/>
<stop offset="1" stop-color="{pal.ground}" stop-opacity="1"/>
</linearGradient>
</defs>"""


def _tone(tone: str, pal: Palette) -> str:
    return {"deep": pal.deep, "mid": pal.mid, "paper": pal.paper, "glow": pal.glow}[tone]


def _wash(d: str, fill: str, opacity: float) -> str:
    return f'<g filter="url(#wash)" style="mix-blend-mode:multiply" opacity="{opacity:.2f}"><path d="{d}" fill="{fill}"/></g>'


def paint_glyph(glyph: Glyph, m: Affine, pal: Palette, *, opacity: float = 1.0, reflection: bool = False) -> str:
    """Paints one glyph. Dark and light shapes alternate in the order written.

    A reflection is the same glyph mirrored by the caller, painted thinner and
    pulled sideways by the ripple filter, with no halo around its lights.
    """
    scale = math.sqrt(abs(m.a * m.d - m.b * m.c))
    out: list[str] = []
    run: list[str] = []
    run_dark: bool | None = None
    glows: list[str] = []

    def flush() -> None:
        nonlocal run, run_dark
        if not run:
            return
        if run_dark:
            name, alpha = ("ripple", 0.4) if reflection else ("ink", 0.9)
            out.append(f'<g filter="url(#{name})" style="mix-blend-mode:multiply" opacity="{alpha * opacity:.2f}">{"".join(run)}</g>')
        else:
            name, alpha = ("ripple", 0.28) if reflection else ("soft", 0.95)
            out.append(f'<g filter="url(#{name})" opacity="{alpha * opacity:.2f}">{"".join(run)}</g>')
        run = []
        run_dark = None

    for shape in glyph.shapes:
        dark = shape.tone in ("deep", "mid")
        if run_dark is not None and dark != run_dark:
            flush()
        run_dark = dark
        d = emit(parse_path(shape.d), m)
        colour = _tone(shape.tone, pal)
        if shape.stroke:
            el = (
                f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="{max(shape.stroke * scale, 1.2):.1f}" '
                'stroke-linecap="round" stroke-linejoin="round"/>'
            )
        else:
            el = f'<path d="{d}" fill="{colour}"/>'
        run.append(el)
        if shape.tone == "glow" and not shape.stroke:
            glows.append(el)
    flush()
    halo = f'<g filter="url(#halo)" opacity="{0.5 * opacity:.2f}">{"".join(glows)}</g>' if glows and not reflection else ""
    return halo + "".join(out)


def _lantern(name: str, cx: float, cy: float, pal: Palette) -> str:
    """A small floating light for a symbol that has no glyph.

    The name fixes its size and shape, so the same symbol leaves the same
    light in every dream it turns up in.
    """
    own = random.Random(seed_from("lantern:" + name))
    r = own.uniform(9, 17)
    body = blob(own, cx, cy, r, r * own.uniform(0.8, 1.25), points=own.randint(5, 8), wobble=0.14)
    return (
        f'<g filter="url(#halo)" opacity="0.6"><path d="{circle_path(cx, cy, r * 1.9)}" fill="{pal.glow}"/></g>'
        f'<g filter="url(#soft)" opacity="0.95"><path d="{body}" fill="{pal.glow}"/></g>'
    )


def _waves(rng: random.Random, top: float, bottom: float, pal: Palette) -> str:
    light: list[str] = []
    dark: list[str] = []
    rows = 9
    for i in range(rows):
        t = (i + 0.5) / rows
        y = top + (bottom - top) * (t**1.25)
        count = rng.randint(2, 4)
        for _ in range(count):
            length = rng.uniform(60, 190) * (0.6 + t)
            x0 = rng.uniform(MARGIN + 20, W - MARGIN - 20 - length)
            amp = rng.uniform(2, 6) * (0.6 + t)
            pts = [(x0 + length * k / 4, y + (amp if k % 2 else -amp) + rng.uniform(-2, 2)) for k in range(5)]
            d = smooth_open(pts)
            width = rng.uniform(2.2, 5.5) * (0.6 + t)
            target = light if rng.random() < 0.62 else dark
            colour = pal.paper if target is light else pal.deep
            target.append(f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="{width:.1f}" stroke-linecap="round"/>')
    return (
        f'<g filter="url(#soft)" opacity="0.5">{"".join(light)}</g>'
        f'<g filter="url(#soft)" style="mix-blend-mode:multiply" opacity="0.3">{"".join(dark)}</g>'
    )


def _moon(rng: random.Random, cx: float, cy: float, r: float, pal: Palette, *, sun: bool = False) -> str:
    fill = pal.glow if sun else pal.paper
    craters = ""
    if not sun:
        spots = [
            blob(
                rng,
                cx + rng.uniform(-0.45, 0.45) * r,
                cy + rng.uniform(-0.45, 0.45) * r,
                r * rng.uniform(0.1, 0.24),
                r * rng.uniform(0.1, 0.2),
                points=7,
                wobble=0.25,
            )
            for _ in range(4)
        ]
        marks = "".join(f'<path d="{d}" fill="{pal.wash}"/>' for d in spots)
        craters = f'<g filter="url(#soft)" style="mix-blend-mode:multiply" opacity="0.2">{marks}</g>'
    disc = circle_path(cx, cy, r)
    return (
        f'<g filter="url(#halo)" opacity="0.5"><path d="{circle_path(cx, cy, r * 1.25)}" fill="{fill}"/></g>'
        f'<g filter="url(#soft)" opacity="0.96"><path d="{disc}" fill="{fill}"/></g>{craters}'
    )


def _dots(rng: random.Random, count: int, top: float, bottom: float, r_min: float, r_max: float, pal: Palette, opacity: float) -> str:
    dots = "".join(
        f'<path d="{circle_path(rng.uniform(MARGIN + 30, W - MARGIN - 30), rng.uniform(top, bottom), rng.uniform(r_min, r_max))}" fill="{pal.paper}"/>'
        for _ in range(count)
    )
    return f'<g filter="url(#soft)" opacity="{opacity:.2f}">{dots}</g>'


def _splatter(rng: random.Random, pal: Palette) -> str:
    cx = rng.choice([rng.uniform(90, 250), rng.uniform(W - 250, W - 90)])
    cy = rng.uniform(120, H - 140)
    dots = []
    for _ in range(rng.randint(14, 24)):
        t = rng.uniform(0, math.tau)
        dist = abs(rng.gauss(0, 46))
        dots.append(f'<path d="{circle_path(cx + math.cos(t) * dist, cy + math.sin(t) * dist, rng.uniform(0.9, 3.4))}" fill="{pal.deep}"/>')
    return f'<g style="mix-blend-mode:multiply" opacity="0.42">{"".join(dots)}</g>'


def render_scene(spec: SceneSpec) -> str:
    """Returns a self-contained SVG document, 800 by 1000."""
    rng = random.Random(spec.seed)
    pal = palette_for(spec.moods)
    symbols = sorted(spec.symbols, key=lambda s: (-s.salience, s.name))

    def of_zone(*zones: str) -> list[tuple[SceneSymbol, Glyph]]:
        return [(s, GLYPHS[s.glyph]) for s in symbols if s.glyph in GLYPHS and GLYPHS[s.glyph].zone in zones]

    has = {s.glyph for s in symbols if s.glyph}
    water = "water" in has
    horizon = rng.uniform(0.56, 0.63) * H if water else rng.uniform(0.6, 0.68) * H
    parts: list[str] = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">',
        _defs(spec.seed, pal),
        f'<rect width="{W}" height="{H}" fill="{pal.paper}"/>',
    ]

    # Sky and ground go through the paint filter together: one pass over the
    # canvas instead of three, which is most of the render time.
    sky_bottom = H - MARGIN - 10
    ground_top = horizon + rng.uniform(-6, 6)
    washes = [
        f'<path d="{band(rng, MARGIN, W - MARGIN, MARGIN, sky_bottom)}" fill="url(#skyfade)" opacity="0.66"/>',
        f'<path d="{band(rng, MARGIN + 30, W - MARGIN - 20, MARGIN + 26, horizon + 40, wobble=30)}" fill="url(#skyfade)" opacity="0.42"/>',
        f'<path d="{band(rng, MARGIN - 6, W - MARGIN + 6, ground_top, H - MARGIN - 4, wobble=10)}" fill="url(#groundfade)" opacity="{0.92 if water else 0.6:.2f}"/>',
    ]
    parts.append(f'<g filter="url(#wash)" style="mix-blend-mode:multiply">{"".join(washes)}</g>')
    # Blooms: places where water pushed the pigment away.
    blooms = [
        f'<path d="{blob(rng, rng.uniform(140, W - 140), rng.uniform(110, horizon - 120), rng.uniform(70, 150), rng.uniform(40, 80), wobble=0.3)}" fill="{pal.paper}" opacity="{rng.uniform(0.2, 0.34):.2f}"/>'
        for _ in range(rng.randint(2, 3))
    ]
    parts.append(f'<g filter="url(#bloom)">{"".join(blooms)}</g>')

    # Decide who is the hero before placing anything, so the sky can leave room.
    cast = of_zone("ground", "float")
    hero = cast[0] if cast else None
    hero_x = rng.choice([0.35, 0.65]) * W if hero else None

    # Sky furniture.
    if "star" in has:
        parts.append(_dots(rng, rng.randint(34, 52), MARGIN + 30, horizon - 60, 1.0, 3.0, pal, 0.85))
        spark = GLYPHS["star"]
        for _ in range(3):
            parts.append(paint_glyph(spark, Affine.place(rng.uniform(120, W - 120), rng.uniform(140, horizon - 120), rng.uniform(26, 54)), pal))
    celestial = of_zone("celestial")
    for i, (sym, glyph) in enumerate(celestial[:2]):
        big = sym.salience >= 0.6 or len(symbols) <= 3
        r = rng.uniform(96, 150) if big else rng.uniform(52, 84)
        if hero_x is not None:
            cx = (W - hero_x) + rng.uniform(-40, 40)
        else:
            cx = rng.uniform(0.3, 0.7) * W
        cx = min(max(cx + i * 190, MARGIN + r + 30), W - MARGIN - r - 30)
        if glyph.key == "sun":
            parts.append(_moon(rng, cx, horizon - r * rng.uniform(0.1, 0.5), r * 0.9, pal, sun=True))
        else:
            parts.append(_moon(rng, cx, max(rng.uniform(0.17, 0.29) * H + i * 60, MARGIN + r + 34), r, pal))
    moon_x = None
    if celestial and celestial[0][1].key == "moon":
        moon_x = min(max(((W - hero_x) if hero_x is not None else W / 2), 180), W - 180)

    for sym, glyph in of_zone("sky")[:3]:
        # Keep the sky's furniture on the side the hero is not standing on.
        side = rng.uniform(0.18, 0.4) if (hero_x or 0) > W / 2 else rng.uniform(0.6, 0.82)
        cx, cy = (side if hero_x is not None else rng.uniform(0.2, 0.8)) * W, rng.uniform(0.14, 0.34) * H
        if glyph.key == "bird":
            for k in range(rng.randint(3, 5)):
                size = glyph.size * rng.uniform(0.6, 1.5) * (1.5 if k == 0 else 1)
                m = Affine.place(cx + k * rng.uniform(44, 80) * rng.choice([-1, 1]), cy + rng.uniform(-70, 90), size, rotate=rng.uniform(-16, 16))
                parts.append(paint_glyph(glyph, m, pal))
        elif glyph.key == "cloud":
            for _ in range(2):
                m = Affine.place(rng.uniform(0.2, 0.8) * W, rng.uniform(0.16, 0.36) * H, glyph.size * rng.uniform(1.1, 2.0))
                parts.append(paint_glyph(glyph, m, pal, opacity=0.8))
        elif glyph.key == "kite":
            size = glyph.size * rng.uniform(1.3, 1.9)
            base = cy + size
            parts.append(paint_glyph(glyph, Affine.place(cx, base, size, rotate=rng.uniform(-24, 24)), pal))
            string = smooth_open([(cx, base), (cx + rng.uniform(-60, 60), (base + horizon) / 2), (cx + rng.uniform(-120, 120), horizon + 20)])
            parts.append(
                f'<g filter="url(#soft)" style="mix-blend-mode:multiply" opacity="0.6"><path d="{string}" fill="none" stroke="{pal.deep}" stroke-width="1.6"/></g>'
            )
        else:
            parts.append(paint_glyph(glyph, Affine.place(cx, cy + glyph.size, glyph.size * rng.uniform(1.2, 1.9), rotate=rng.uniform(-10, 10)), pal))

    # Backdrop: wide, pale, sitting on the horizon.
    for sym, glyph in of_zone("backdrop")[:2]:
        width = rng.uniform(0.62, 0.9) * (W - 2 * MARGIN)
        tall = glyph.size * rng.uniform(1.1, 1.9)
        if glyph.key == "bridge":
            width, tall = W - 2 * MARGIN - 20, glyph.size * rng.uniform(1.0, 1.4)
        cx = rng.uniform(MARGIN + width / 2 + 10, W - MARGIN - width / 2 - 10)
        m = Affine.place(cx, horizon + 14, width, squash=tall / width)
        parts.append(paint_glyph(glyph, m, pal, opacity=0.8 if glyph.key != "bridge" else 0.95))

    # Water gets its surface; land is left as the wash.
    if water:
        parts.append(_waves(rng, ground_top + 16, H - MARGIN - 40, pal))
        if moon_x is not None:
            dashes = []
            for k in range(9):
                y = ground_top + 26 + k * rng.uniform(22, 34)
                half = rng.uniform(16, 60) * (1 + k * 0.12)
                dashes.append(
                    f'<path d="M{moon_x - half + rng.uniform(-14, 14):.1f},{y:.1f} H{moon_x + half + rng.uniform(-14, 14):.1f}" fill="none" stroke="{pal.paper}" stroke-width="{rng.uniform(3, 7):.1f}" stroke-linecap="round"/>'
                )
            parts.append(f'<g filter="url(#ripple)" opacity="0.62">{"".join(dashes)}</g>')
    if "road" in has:
        vx = (hero_x if hero_x is not None else W / 2) + rng.uniform(-60, 60)
        bx = W / 2 + rng.uniform(-120, 120)
        left = smooth_open([(bx - 130, H - MARGIN), (bx - 40 + (vx - bx) * 0.4, (H + ground_top) / 2), (vx - 5, ground_top + 8)])
        right_pts = [(vx + 5, ground_top + 8), (bx + 60 + (vx - bx) * 0.4, (H + ground_top) / 2), (bx + 130, H - MARGIN)]
        right = smooth_open(right_pts).replace("M", "L", 1)
        parts.append(f'<g filter="url(#soft)" opacity="0.55"><path d="{left}{right}Z" fill="{pal.paper}"/></g>')
    if "snow" in has:
        parts.append(_dots(rng, rng.randint(70, 100), MARGIN + 20, H - MARGIN - 20, 1.4, 4.4, pal, 0.8))

    # The cast. One hero, painted far too large; the rest ordinary or tiny.
    painted: list[tuple[float, str]] = []
    occupied: list[tuple[float, float]] = []

    def claim(width: float) -> float:
        """An x for something this wide, overlapping what already stands there as little as possible."""
        half = width / 2
        low, high = MARGIN + 34 + half, W - MARGIN - 34 - half
        options = [low + (high - low) * k / 11 for k in range(12)] if high > low else [W / 2]
        rng.shuffle(options)

        def overlap(x: float) -> float:
            return sum(max(0.0, min(x + half, b) - max(x - half, a)) for a, b in occupied)

        best = min(options, key=overlap)
        occupied.append((best - half - 16, best + half + 16))
        return best

    if hero is not None and hero_x is not None:
        sym, glyph = hero
        size = min(max(glyph.size * rng.uniform(2.1, 2.9), 250), 0.56 * H)
        if glyph.zone == "float":
            size = min(size, 380)
            base = ground_top - rng.uniform(40, 120)
            hx = W / 2 + (hero_x - W / 2) * 0.5
            m = Affine.place(hx, base, size, rotate=rng.uniform(-14, 14))
            shadow = blob(rng, hx, ground_top + 70, size * 0.42, 16, wobble=0.2)
            painted.append(
                (base - 2, f'<g filter="url(#wash)" style="mix-blend-mode:multiply" opacity="0.3"><path d="{shadow}" fill="{pal.deep}"/></g>')
            )
        else:
            base = ground_top + rng.uniform(34, 70)
            hx = hero_x
            m = Affine.place(hx, base, size, flip=rng.random() < 0.5)
            if water:
                painted.append((base - 1, paint_glyph(glyph, Affine.place(hx, base, size, squash=-0.7), pal, reflection=True)))
        occupied.append((hx - size * 0.4, hx + size * 0.4))
        painted.append((base, paint_glyph(glyph, m, pal)))

    supporting = [c for c in cast if hero is None or c[0] is not hero[0]][:4]
    for i, (sym, glyph) in enumerate(supporting):
        shrink = 0.5 if i == len(supporting) - 1 and len(supporting) > 1 else rng.uniform(0.7, 1.05)
        size = glyph.size * shrink
        x = claim(size * 0.8)
        if glyph.zone == "float":
            base = rng.uniform(0.3, 0.52) * H + size / 2
            m = Affine.place(x, base, size, rotate=rng.uniform(-24, 24), flip=rng.random() < 0.5)
        else:
            base = ground_top + rng.uniform(4, 30) + (0 if water else i * 6)
            m = Affine.place(x, base, size, flip=rng.random() < 0.5)
            if water:
                painted.append((base - 1, paint_glyph(glyph, Affine.place(x, base, size, squash=-0.7), pal, reflection=True)))
        painted.append((base, paint_glyph(glyph, m, pal)))

    # People are never drawn. A person in the dream becomes a standing shape.
    for sym, glyph in of_zone("presence")[:3]:
        size = glyph.size * rng.uniform(0.7, 1.25)
        px = claim(size * 0.42)
        base = ground_top + rng.uniform(10, 46)
        painted.append((base, paint_glyph(glyph, Affine.place(px, base, size), pal, opacity=0.62)))

    unknown = [s for s in symbols if not s.glyph][:3]
    for i, sym in enumerate(unknown):
        cx = (0.2, 0.8, 0.5)[i] * W + rng.uniform(-50, 50)
        cy = rng.uniform(0.3, 0.52) * H
        painted.append((-1.0, _lantern(sym.name, cx, cy, pal)))

    parts.extend(svg for _, svg in sorted(painted, key=lambda t: t[0]))
    parts.append(_splatter(rng, pal))
    parts.append(f'<rect width="{W}" height="{H}" filter="url(#paper)" style="mix-blend-mode:multiply" opacity="0.5"/>')
    parts.append("</svg>")
    return "".join(parts)


def render_swatch(glyph_key: str, mood: str = "calm", seed: int = 1) -> str:
    """One glyph on a small wash. Used for the contact sheet and for tests."""
    pal = palette_for([mood])
    rng = random.Random(seed)
    glyph = GLYPHS[glyph_key]
    size = 200
    body = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" width="{size}" height="{size}">'
        + _defs(seed, pal)
        + f'<rect width="{size}" height="{size}" fill="{pal.paper}"/>'
        + _wash(blob(rng, size / 2, size / 2, 78, 72, wobble=0.1), pal.wash, 0.6)
        + paint_glyph(glyph, Affine.place(size / 2, 160, 120), pal)
        + "</svg>"
    )
    return body
