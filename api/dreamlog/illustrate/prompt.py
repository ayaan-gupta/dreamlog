"""Builds the text prompt a hosted image model would be given.

The built-in painter does not read it; it works from the same symbols and mood
directly. The prompt is still built for every entry so that switching
``DREAMLOG_ILLUSTRATOR`` to the API changes nothing else. Only symbol names and
the mood are included, never the transcript.
"""

from __future__ import annotations

STYLE_BIBLE = (
    "Soft watercolour on cold-pressed paper, wet-on-wet washes with visible pigment granulation and an unpainted "
    "paper border. Dreamlike scale distortions: one object far too large, another far too small. One dominant "
    "colour for the whole picture. No text, no letters, no numbers, no people, no faces, no figures."
)

MOOD_COLOUR: dict[str, str] = {
    "calm": "muted teal",
    "joyful": "warm golden yellow",
    "anxious": "sour olive green",
    "fearful": "deep indigo",
    "sad": "slate blue-grey",
    "nostalgic": "faded sepia",
    "awed": "violet",
    "confused": "sage green",
    "angry": "brick red",
    "tender": "dusty rose",
    "neutral": "warm grey-lilac",
}


def build_prompt(symbols: list[tuple[str, str]], moods: list[str]) -> str:
    """``symbols`` is (name, kind), most salient first."""
    mood = moods[0] if moods else "neutral"
    things = [name for name, kind in symbols if kind != "person"][:6]
    people = sum(1 for _name, kind in symbols if kind == "person")
    parts = [STYLE_BIBLE, f"Dominant colour: {MOOD_COLOUR.get(mood, MOOD_COLOUR['neutral'])}. Mood: {mood}."]
    if things:
        parts.append(f"The scene contains: {', '.join(things)}. The first of these is enormous.")
    if people:
        parts.append("Where the dream had people, paint tall standing stones instead.")
    return " ".join(parts)
