"""A very small path toolkit.

Glyphs are written by hand in a 100 by 100 box using only absolute M, L, H, V,
C, Q and Z commands. They are placed by transforming the coordinates here
instead of with an SVG transform attribute, because filter noise is defined in
user space: a glyph scaled four times by a transform would get paint texture
four times too coarse.
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass

_TOKEN = re.compile(r"[MLHVCQZ]|-?\d*\.?\d+")
_ARITY = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "Q": 4, "Z": 0}

Point = tuple[float, float]
Segment = tuple[str, tuple[Point, ...]]


@dataclass(frozen=True)
class Affine:
    """x' = a*x + c*y + e, y' = b*x + d*y + f."""

    a: float = 1.0
    b: float = 0.0
    c: float = 0.0
    d: float = 1.0
    e: float = 0.0
    f: float = 0.0

    def apply(self, p: Point) -> Point:
        x, y = p
        return (self.a * x + self.c * y + self.e, self.b * x + self.d * y + self.f)

    @staticmethod
    def place(
        cx: float,
        base_y: float,
        height: float,
        *,
        rotate: float = 0.0,
        flip: bool = False,
        squash: float = 1.0,
    ) -> Affine:
        """Maps the glyph box so (50, 100) lands on (cx, base_y) at the given height.

        ``rotate`` is in degrees about the box centre. ``squash`` scales y only,
        and a negative value mirrors the glyph below its baseline (reflections).
        """
        s = height / 100.0
        sx = -s if flip else s
        sy = s * squash
        t = math.radians(rotate)
        cos, sin = math.cos(t), math.sin(t)
        # p' = S * (R * (p - centre) + centre) + T, with T chosen so the
        # unrotated baseline midpoint (50, 100) lands on (cx, base_y).
        e = sx * (50 - 50 * cos + 50 * sin) + cx - sx * 50
        f = sy * (50 - 50 * sin - 50 * cos) + base_y - sy * 100
        return Affine(sx * cos, sy * sin, -sx * sin, sy * cos, e, f)


def parse_path(d: str) -> list[Segment]:
    """Parses absolute path data into segments of absolute points."""
    tokens = _TOKEN.findall(d)
    out: list[Segment] = []
    i = 0
    cmd = ""
    cur: Point = (0.0, 0.0)
    while i < len(tokens):
        tok = tokens[i]
        if tok in _ARITY:
            cmd = tok
            i += 1
            if cmd == "Z":
                out.append(("Z", ()))
                continue
        n = _ARITY[cmd]
        vals = [float(v) for v in tokens[i : i + n]]
        if len(vals) != n:
            raise ValueError(f"bad path data near token {i}: {d!r}")
        i += n
        if cmd == "H":
            cur = (vals[0], cur[1])
            out.append(("L", (cur,)))
        elif cmd == "V":
            cur = (cur[0], vals[0])
            out.append(("L", (cur,)))
        else:
            pts = tuple((vals[k], vals[k + 1]) for k in range(0, n, 2))
            cur = pts[-1]
            out.append((cmd, pts))
            if cmd == "M":
                cmd = "L"  # implicit lineto after a moveto
    return out


def emit(segments: list[Segment], m: Affine) -> str:
    parts: list[str] = []
    for cmd, pts in segments:
        if cmd == "Z":
            parts.append("Z")
        else:
            parts.append(cmd + " ".join(f"{x:.1f},{y:.1f}" for x, y in map(m.apply, pts)))
    return "".join(parts)


def circle_path(cx: float, cy: float, r: float, ry: float | None = None) -> str:
    """A circle or ellipse as four cubic curves, so it survives any affine map."""
    ry = r if ry is None else ry
    k = 0.5523

    def n(v: float) -> str:
        return f"{v:.2f}"

    return (
        f"M{n(cx - r)},{n(cy)}"
        f"C{n(cx - r)},{n(cy - k * ry)} {n(cx - k * r)},{n(cy - ry)} {n(cx)},{n(cy - ry)}"
        f"C{n(cx + k * r)},{n(cy - ry)} {n(cx + r)},{n(cy - k * ry)} {n(cx + r)},{n(cy)}"
        f"C{n(cx + r)},{n(cy + k * ry)} {n(cx + k * r)},{n(cy + ry)} {n(cx)},{n(cy + ry)}"
        f"C{n(cx - k * r)},{n(cy + ry)} {n(cx - r)},{n(cy + k * ry)} {n(cx - r)},{n(cy)}Z"
    )


def smooth_closed(points: list[Point]) -> str:
    """A closed Catmull-Rom spline through the points, as cubic curves."""
    n = len(points)
    out = [f"M{points[0][0]:.1f},{points[0][1]:.1f}"]
    for i in range(n):
        p0, p1, p2, p3 = points[i - 1], points[i], points[(i + 1) % n], points[(i + 2) % n]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        out.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return "".join(out) + "Z"


def smooth_open(points: list[Point]) -> str:
    """An open Catmull-Rom spline through the points."""
    n = len(points)
    out = [f"M{points[0][0]:.1f},{points[0][1]:.1f}"]
    for i in range(n - 1):
        p0 = points[max(i - 1, 0)]
        p1, p2 = points[i], points[i + 1]
        p3 = points[min(i + 2, n - 1)]
        c1 = (p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6)
        c2 = (p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6)
        out.append(f"C{c1[0]:.1f},{c1[1]:.1f} {c2[0]:.1f},{c2[1]:.1f} {p2[0]:.1f},{p2[1]:.1f}")
    return "".join(out)


def blob(rng: random.Random, cx: float, cy: float, rx: float, ry: float, *, points: int = 11, wobble: float = 0.16) -> str:
    """An organic closed shape around an ellipse."""
    pts: list[Point] = []
    phase = rng.uniform(0, math.tau)
    for i in range(points):
        t = phase + math.tau * i / points
        k = 1 + rng.uniform(-wobble, wobble)
        pts.append((cx + math.cos(t) * rx * k, cy + math.sin(t) * ry * k))
    return smooth_closed(pts)


def band(rng: random.Random, left: float, right: float, top: float, bottom: float, *, wobble: float = 14, steps: int = 7) -> str:
    """A roughly rectangular wash with wandering edges."""
    pts: list[Point] = []
    for i in range(steps + 1):
        x = left + (right - left) * i / steps
        pts.append((x, top + rng.uniform(-wobble, wobble)))
    side = max(2, round(steps * (bottom - top) / max(right - left, 1)))
    for i in range(1, side):
        y = top + (bottom - top) * i / side
        pts.append((right + rng.uniform(-wobble, wobble), y))
    for i in range(steps + 1):
        x = right - (right - left) * i / steps
        pts.append((x, bottom + rng.uniform(-wobble, wobble)))
    for i in range(1, side):
        y = bottom - (bottom - top) * i / side
        pts.append((left + rng.uniform(-wobble, wobble), y))
    return smooth_closed(pts)
