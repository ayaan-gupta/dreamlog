"""One dominant colour per mood.

Every illustration is painted in the colours of the entry's first mood. The
same wash colour is what the web app uses for that mood's dot, so a timeline of
pictures and a timeline of mood chips tell the same story.
"""

from __future__ import annotations

from dataclasses import dataclass

PAPER = "#f7f2e8"
GLOW = "#f8dc9c"


@dataclass(frozen=True)
class Palette:
    mood: str
    wash: str
    """The dominant colour: sky and large washes."""
    ground: str
    """A deeper neighbour of the wash, for land or water."""
    mid: str
    """Middle value for distant shapes."""
    deep: str
    """Darkest value, for silhouettes."""
    paper: str = PAPER
    glow: str = GLOW


_MOODS: dict[str, tuple[str, str, str, str]] = {
    # mood: (wash, ground, mid, deep)
    "calm": ("#6fa8b4", "#4f8c9c", "#2f6675", "#173f4c"),
    "joyful": ("#eebf5b", "#dba33f", "#a8731f", "#6b430d"),
    "anxious": ("#b9b565", "#9e9a47", "#6f6b28", "#3d3b12"),
    "fearful": ("#5a5f9e", "#41467f", "#2c3066", "#161838"),
    "sad": ("#8a9bb3", "#6d809b", "#465a75", "#243042"),
    "nostalgic": ("#cfa77c", "#b78a5c", "#8a5f38", "#4f321a"),
    "awed": ("#9478bd", "#775aa3", "#553b85", "#2c1b4d"),
    "confused": ("#93b592", "#74a077", "#477152", "#22402a"),
    "angry": ("#cf6b5c", "#b34d40", "#8c3329", "#4f1712"),
    "tender": ("#e7a6b0", "#d4848f", "#a35465", "#5e2433"),
    "neutral": ("#b3adbd", "#958fa3", "#635d75", "#322e40"),
}

MOODS: tuple[str, ...] = tuple(_MOODS)

# Warm washes need a paler light source than the amber used on cool ones.
_WARM = {"joyful", "anxious", "nostalgic", "angry", "tender"}


def palette_for(moods: list[str]) -> Palette:
    mood = next((m for m in moods if m in _MOODS), "neutral")
    wash, ground, mid, deep = _MOODS[mood]
    glow = "#fff1c9" if mood in _WARM else GLOW
    return Palette(mood=mood, wash=wash, ground=ground, mid=mid, deep=deep, glow=glow)


def mood_colours() -> dict[str, str]:
    """Mood name to its dominant colour, for the client."""
    return {mood: colours[0] for mood, colours in _MOODS.items()}
