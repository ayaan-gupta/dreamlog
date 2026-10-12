"""The hand-drawn glyph library.

Each glyph is a handful of shapes in a 100 by 100 box whose bottom edge is the
ground. Shapes are deliberately plain: the paint filters roughen every edge, so
a careful outline would be wasted. Tones say what a shape is painted with:

    deep   the darkest value of the mood colour (silhouettes)
    mid    a middle value (distant things, foliage)
    paper  unpainted paper showing through (moons, sails, pages, teeth)
    glow   warm light (windows, flames, an open door)

``words`` lists what a glyph can stand for. A symbol that is not listed can
still pick up a glyph through embedding similarity to one of these words (see
``matcher.py``); a symbol with no glyph is painted as an abstract mark.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from .geometry import circle_path

Tone = Literal["deep", "mid", "paper", "glow"]
Zone = Literal["celestial", "sky", "backdrop", "ground", "float", "water", "scatter", "path", "presence"]


@dataclass(frozen=True)
class Shape:
    tone: Tone
    d: str
    stroke: float = 0.0
    """Stroke width in box units. Zero means the shape is filled."""


@dataclass(frozen=True)
class Glyph:
    key: str
    zone: Zone
    size: float
    """Natural height in pixels on the 800 by 1000 canvas, before distortion."""
    shapes: tuple[Shape, ...]
    words: tuple[str, ...] = ()


def _p(tone: Tone, d: str) -> Shape:
    return Shape(tone, d)


def _s(tone: Tone, d: str, width: float) -> Shape:
    return Shape(tone, d, width)


def _c(tone: Tone, cx: float, cy: float, r: float, ry: float | None = None) -> Shape:
    return Shape(tone, circle_path(cx, cy, r, ry))


def _ring(tone: Tone, cx: float, cy: float, r: float, width: float) -> Shape:
    return Shape(tone, circle_path(cx, cy, r), width)


def _rect(tone: Tone, x: float, y: float, w: float, h: float) -> Shape:
    return Shape(tone, f"M{x},{y} H{x + w} V{y + h} H{x} Z")


_TOOTH = (
    "M20,22 C28,6 44,12 50,14 C56,12 72,6 80,22 C90,40 78,58 74,90 C71,100 62,98 60,74 C58,60 42,60 40,74 C38,98 29,100 26,90 C22,58 10,40 20,22 Z"
)
_EYE = "M4,50 C26,22 74,22 96,50 C74,78 26,78 4,50 Z"
_SPARK = "M50,6 C52,36 64,48 94,50 C64,52 52,64 50,94 C48,64 36,52 6,50 C36,48 48,36 50,6 Z"

_GLYPHS: tuple[Glyph, ...] = (
    Glyph(
        "door",
        "ground",
        170,
        (
            _p("deep", "M20,100 V16 C20,6 30,2 50,2 C70,2 80,6 80,16 V100 Z"),
            _p("glow", "M55,100 V21 L71,16 V100 Z"),
            _c("paper", 47, 62, 2.2),
        ),
        ("door", "gate", "doorway", "exit", "entrance"),
    ),
    Glyph(
        "stairs",
        "ground",
        170,
        (
            _p("deep", "M0,100 V86 H14 V72 H28 V58 H42 V44 H56 V30 H70 V16 H84 V2 H100 V100 Z"),
            _s("paper", "M1,86 H14 M15,72 H28 M29,58 H42 M43,44 H56 M57,30 H70 M71,16 H84 M85,2 H100", 1.5),
        ),
        ("stairs", "staircase", "steps", "escalator", "ladder"),
    ),
    Glyph(
        "house",
        "ground",
        150,
        (
            _p("deep", "M64,32 V8 H75 V42 Z"),
            _p("deep", "M14,100 V50 L50,18 L86,50 V100 Z"),
            _p("deep", "M5,55 L50,12 L95,55 L89,60 L50,23 L11,60 Z"),
            _rect("glow", 25, 62, 17, 17),
            _rect("glow", 58, 62, 17, 17),
            _c("glow", 50, 42, 4.5),
        ),
        ("house", "home", "cabin", "cottage", "apartment", "roof"),
    ),
    Glyph(
        "window",
        "float",
        130,
        (
            _rect("deep", 14, 6, 72, 88),
            _rect("glow", 22, 14, 24, 32),
            _rect("glow", 54, 14, 24, 32),
            _rect("glow", 22, 54, 24, 32),
            _rect("glow", 54, 54, 24, 32),
        ),
        ("window",),
    ),
    Glyph(
        "tree",
        "ground",
        190,
        (
            _p("deep", "M45,100 C47,82 46,68 43,54 L50,58 L57,54 C54,68 53,82 55,100 Z"),
            _p("mid", "M50,2 C72,0 92,16 88,38 C98,54 80,70 60,62 C48,72 22,70 18,52 C2,40 16,8 50,2 Z"),
        ),
        ("tree",),
    ),
    Glyph(
        "forest",
        "backdrop",
        150,
        (
            _p("mid", "M14,40 L26,100 H2 Z"),
            _p("mid", "M32,18 L48,100 H16 Z"),
            _p("mid", "M52,34 L66,100 H38 Z"),
            _p("mid", "M72,8 L90,100 H54 Z"),
            _p("mid", "M90,44 L100,100 H80 Z"),
        ),
        ("forest", "woods", "jungle"),
    ),
    Glyph(
        "mountain",
        "backdrop",
        190,
        (
            _p("mid", "M0,100 L22,46 L34,62 L56,8 L74,48 L84,36 L100,100 Z"),
            _p("paper", "M56,8 L65,28 L59,24 L54,33 L48,24 Z"),
        ),
        ("mountain", "hill", "cliff", "hillside"),
    ),
    Glyph(
        "bridge",
        "backdrop",
        150,
        (
            _p("deep", "M0,56 H100 V64 H0 Z"),
            _p("deep", "M24,20 H30 V100 H24 Z"),
            _p("deep", "M70,20 H76 V100 H70 Z"),
            _s("deep", "M0,54 Q14,50 27,22 Q50,66 73,22 Q86,50 100,54", 1.6),
        ),
        ("bridge",),
    ),
    Glyph(
        "moon",
        "celestial",
        150,
        (
            _c("paper", 50, 50, 46),
            _c("mid", 36, 38, 8),
            _c("mid", 60, 60, 11),
            _c("mid", 63, 30, 5),
        ),
        ("moon",),
    ),
    Glyph("sun", "celestial", 150, (_c("glow", 50, 50, 40), _ring("glow", 50, 50, 48, 1.5)), ("sun", "sunlight")),
    Glyph(
        "star",
        "scatter",
        90,
        (_p("paper", _SPARK), _c("paper", 14, 18, 3), _c("paper", 84, 78, 2.4), _c("paper", 80, 16, 1.8)),
        ("star",),
    ),
    Glyph(
        "snow",
        "scatter",
        90,
        tuple(
            _c("paper", x, y, r)
            for x, y, r in ((16, 14, 4), (48, 8, 3), (80, 20, 5), (30, 40, 5), (64, 46, 3.5), (88, 58, 3), (12, 66, 3), (44, 74, 5), (74, 86, 4))
        ),
        ("snow", "ice"),
    ),
    Glyph(
        "cloud",
        "sky",
        90,
        (_c("paper", 30, 62, 18), _c("paper", 52, 48, 24), _c("paper", 74, 62, 17), _rect("paper", 30, 60, 44, 20)),
        ("cloud", "fog", "smoke", "mist"),
    ),
    Glyph(
        "bird",
        "sky",
        46,
        (_p("deep", "M0,38 C16,22 34,24 50,46 C66,24 84,22 100,38 C82,36 66,42 50,62 C34,42 18,36 0,38 Z"),),
        ("bird", "crow", "owl"),
    ),
    Glyph(
        "swarm",
        "sky",
        130,
        tuple(
            _c("deep", x, y, r, r * 0.7)
            for x, y, r in (
                (12, 40, 2.6),
                (22, 62, 2.2),
                (30, 28, 3),
                (38, 50, 2.4),
                (44, 72, 2),
                (50, 36, 3.2),
                (56, 58, 2.6),
                (62, 22, 2.2),
                (68, 44, 3),
                (72, 68, 2.4),
                (80, 34, 2.6),
                (86, 54, 2.2),
                (92, 42, 1.8),
                (34, 84, 1.8),
                (58, 86, 2.2),
                (18, 20, 1.8),
            )
        ),
        ("bee", "swarm", "insect", "spider"),
    ),
    Glyph(
        "kite",
        "sky",
        130,
        (
            _p("glow", "M50,2 L80,36 L50,82 L20,36 Z"),
            _s("deep", "M50,2 V82 M20,36 H80", 1.4),
            _s("deep", "M50,82 C40,88 62,92 52,100", 1.6),
        ),
        ("kite", "balloon"),
    ),
    Glyph(
        "fish",
        "float",
        80,
        (
            _p("deep", "M4,50 C24,26 60,24 78,50 C60,76 24,74 4,50 Z"),
            _p("deep", "M72,50 L98,30 L91,50 L98,70 Z"),
            _c("paper", 22, 46, 3),
        ),
        ("fish", "crab"),
    ),
    Glyph(
        "whale",
        "float",
        150,
        (
            _p("deep", "M2,56 C8,32 44,24 70,40 C80,46 86,54 90,48 L100,30 L99,58 C90,76 60,86 34,80 C16,76 4,68 2,56 Z"),
            _c("paper", 20, 54, 2),
            _s("paper", "M8,64 C24,72 44,74 60,70", 1.2),
        ),
        ("whale", "shark"),
    ),
    Glyph(
        "dog",
        "ground",
        110,
        (
            _p(
                "deep",
                "M6,40 L18,30 L24,18 L31,30 C36,34 40,40 44,42 L78,40 C86,40 90,46 92,52 L98,40 L99,46 L93,60 "
                "L92,100 H84 L82,74 C74,78 60,78 50,76 L48,100 H40 L38,72 C32,68 28,62 26,54 L12,50 Z",
            ),
            _p("deep", "M52,74 L55,100 H61 L59,74 Z"),
            _p("deep", "M72,74 L70,100 H77 L80,74 Z"),
        ),
        ("dog", "wolf", "fox"),
    ),
    Glyph(
        "cat",
        "ground",
        90,
        (
            _p("deep", "M30,100 C20,80 26,56 38,46 L33,20 L45,32 H55 L67,20 L62,46 C74,56 80,80 70,100 Z"),
            _s("deep", "M70,94 C90,96 94,76 84,64", 5),
            _c("glow", 44, 42, 2.2),
            _c("glow", 56, 42, 2.2),
        ),
        ("cat",),
    ),
    Glyph(
        "snake",
        "ground",
        80,
        (_s("deep", "M8,92 C40,96 22,62 50,60 C78,58 60,28 84,24", 8), _c("deep", 86, 22, 6.5), _c("paper", 88, 20, 1.3)),
        ("snake",),
    ),
    Glyph(
        "key",
        "float",
        120,
        (
            _ring("deep", 28, 28, 17, 8),
            _p("deep", "M38,44 L44,38 L94,88 L88,94 Z"),
            _p("deep", "M72,78 L64,86 L70,92 L78,84 Z"),
            _p("deep", "M60,66 L52,74 L58,80 L66,72 Z"),
        ),
        ("key", "lock", "keyhole"),
    ),
    Glyph("tooth", "float", 110, (_p("paper", _TOOTH), _s("deep", _TOOTH, 3)), ("tooth",)),
    Glyph(
        "eye",
        "float",
        90,
        (_p("paper", _EYE), _s("deep", _EYE, 3), _c("deep", 50, 50, 15), _c("paper", 45, 45, 4)),
        ("eye",),
    ),
    Glyph(
        "clock",
        "float",
        120,
        (
            _c("paper", 50, 50, 42),
            _ring("deep", 50, 50, 42, 5),
            _s("deep", "M50,50 L50,22 M50,50 L70,60", 4),
            _c("deep", 50, 50, 3),
        ),
        ("clock", "watch"),
    ),
    Glyph(
        "book",
        "float",
        100,
        (
            _p("deep", "M2,30 C20,20 38,22 50,34 C62,22 80,20 98,30 V86 C80,76 62,78 50,90 C38,78 20,76 2,86 Z"),
            _p("paper", "M9,36 C22,29 36,31 46,40 V80 C36,72 22,71 9,77 Z"),
            _p("paper", "M91,36 C78,29 64,31 54,40 V80 C64,72 78,71 91,77 Z"),
        ),
        ("book", "page", "letter", "notebook"),
    ),
    Glyph(
        "mirror",
        "ground",
        150,
        (
            _c("deep", 50, 40, 30, 38),
            _p("deep", "M46,76 H54 V94 H66 V100 H34 V94 H46 Z"),
            _c("paper", 50, 40, 24, 32),
        ),
        ("mirror", "reflection"),
    ),
    Glyph(
        "bed",
        "ground",
        90,
        (
            _p("deep", "M2,100 V38 H10 V62 H90 C96,62 98,66 98,72 V100 H90 V88 H10 V100 Z"),
            _p("paper", "M14,52 C14,46 34,46 34,52 V61 H14 Z"),
        ),
        ("bed", "bedroom", "pillow"),
    ),
    Glyph(
        "fire",
        "ground",
        110,
        (
            _p("deep", "M14,95 H86 V100 H14 Z"),
            _p("glow", "M50,4 C58,30 84,44 78,72 C74,92 60,99 50,99 C38,99 22,92 22,72 C22,56 34,50 37,32 C43,42 47,36 50,4 Z"),
            _p("paper", "M50,46 C54,60 64,66 62,80 C60,92 54,96 50,96 C44,96 38,90 38,80 C38,70 46,64 50,46 Z"),
        ),
        ("fire", "flame", "candle"),
    ),
    Glyph(
        "boat",
        "ground",
        110,
        (
            _p("deep", "M4,66 H96 L82,92 H20 Z"),
            _s("deep", "M48,66 V8", 2.5),
            _p("paper", "M52,12 L86,58 H52 Z"),
            _p("paper", "M44,22 L20,58 H44 Z"),
        ),
        ("boat", "ship"),
    ),
    Glyph(
        "car",
        "ground",
        70,
        (
            _p("deep", "M2,78 V60 L18,56 L30,36 H66 L82,56 L98,62 V78 Z"),
            _c("deep", 26, 80, 11),
            _c("deep", 76, 80, 11),
            _p("glow", "M34,42 H48 V56 H26 Z"),
            _p("glow", "M52,42 H63 L74,56 H52 Z"),
            _c("paper", 26, 80, 3.5),
            _c("paper", 76, 80, 3.5),
            _c("glow", 95, 66, 2.5),
        ),
        ("car", "bus", "truck", "taxi"),
    ),
    Glyph(
        "train",
        "ground",
        90,
        (
            _p("deep", "M2,84 V26 H32 V44 H70 V30 H80 V44 H90 V84 Z"),
            _p("deep", "M90,84 L100,84 L90,64 Z"),
            _c("deep", 16, 86, 10),
            _c("deep", 44, 88, 8),
            _c("deep", 62, 88, 8),
            _c("deep", 80, 88, 8),
            _rect("glow", 8, 34, 18, 16),
            _c("paper", 75, 20, 7),
            _c("paper", 66, 10, 9),
            _c("paper", 52, 6, 6),
        ),
        ("train", "railway", "carriage", "platform"),
    ),
    Glyph(
        "bicycle",
        "ground",
        80,
        (
            _ring("deep", 22, 76, 21, 3.4),
            _ring("deep", 78, 76, 21, 3.4),
            _s("deep", "M22,76 L42,42 H68 L78,76 M42,42 L52,76 H22 M52,76 L68,42 M36,36 H48 M66,32 L68,42 M60,32 H72", 3.4),
        ),
        ("bicycle", "bike"),
    ),
    Glyph(
        "tower",
        "ground",
        200,
        (
            _p("deep", "M36,100 L41,26 H59 L64,100 Z"),
            _p("deep", "M34,26 H66 V20 H34 Z"),
            _p("deep", "M38,8 L50,0 L62,8 Z"),
            _rect("glow", 41, 8, 18, 12),
            _rect("paper", 47, 50, 6, 8),
        ),
        ("tower", "lighthouse", "windmill"),
    ),
    Glyph(
        "building",
        "ground",
        150,
        (
            _p("deep", "M6,100 V36 H94 V100 Z"),
            _p("deep", "M2,37 L50,10 L98,37 Z"),
            *(_rect("glow", x, y, 9, 12) for y in (46, 66) for x in (16, 36, 56, 76)),
            _rect("glow", 44, 84, 12, 16),
        ),
        ("school", "hotel", "museum", "office", "hospital", "supermarket", "station", "airport", "church", "library"),
    ),
    Glyph(
        "suitcase",
        "ground",
        70,
        (
            _p("deep", "M8,38 C8,35 10,34 13,34 H87 C90,34 92,35 92,38 V94 C92,97 90,98 87,98 H13 C10,98 8,97 8,94 Z"),
            _s("deep", "M36,34 V22 H64 V34", 5),
            _s("paper", "M28,36 V96 M72,36 V96", 2),
        ),
        ("suitcase", "bag", "luggage", "backpack"),
    ),
    Glyph(
        "feather",
        "float",
        110,
        (_p("paper", "M50,4 C74,26 72,64 52,92 C30,66 28,26 50,4 Z"), _s("deep", "M50,10 C52,50 52,80 54,100", 1.8)),
        ("feather", "leaf"),
    ),
    Glyph(
        "flower",
        "ground",
        120,
        (
            _s("deep", "M50,100 C48,80 52,60 50,42", 3),
            _p("mid", "M50,76 C62,62 74,64 78,58 C74,72 62,80 50,80 Z"),
            *(_c("glow", 50 + 15 * math.cos(i * math.tau / 8), 28 + 15 * math.sin(i * math.tau / 8), 8) for i in range(8)),
            _c("deep", 50, 28, 9),
        ),
        ("flower", "sunflower", "garden"),
    ),
    Glyph(
        "presence",
        "presence",
        120,
        (_p("mid", "M36,100 C28,72 30,42 38,22 C43,6 57,6 62,22 C70,42 72,72 64,100 Z"),),
        (),
    ),
    Glyph(
        "water",
        "water",
        90,
        (
            _s("deep", "M4,30 C20,18 30,42 50,30 C70,18 80,42 96,30", 4),
            _s("mid", "M4,52 C20,40 30,64 50,52 C70,40 80,64 96,52", 4),
            _s("deep", "M4,74 C20,62 30,86 50,74 C70,62 80,86 96,74", 4),
        ),
        ("water", "ocean", "sea", "lake", "river", "pool", "swimming pool", "flood", "wave", "pond"),
    ),
    Glyph(
        "road",
        "path",
        120,
        (_p("mid", "M30,100 C44,70 40,40 49,6 H51 C52,40 62,70 74,100 Z"),),
        ("road", "street", "path", "corridor", "hallway"),
    ),
)

GLYPHS: dict[str, Glyph] = {g.key: g for g in _GLYPHS}


def word_index() -> dict[str, str]:
    """Every listed word mapped to its glyph key."""
    return {word: g.key for g in _GLYPHS for word in g.words}
