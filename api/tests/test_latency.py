"""PRD acceptance test: stop-recording to saved entry in under 20 seconds for a
60 second clip, with the real models.

What is timed: one HTTP request that uploads the recording and returns once the
entry is in Postgres with its transcript, symbols, embeddings and picture. The
server is warm (the models are loaded by a short request first), which is the
state a running app is in. The clip is synthetic speech from the macOS ``say``
command at a slow dictation pace with pauses; real morning speech is harder for
Whisper to get right but no slower to process.
"""

from __future__ import annotations

import difflib
import platform
import re
import statistics
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dreamlog.audio import decode_audio
from dreamlog.main import create_app

from .conftest import AUDIO, make_settings

BUDGET_S = 20.0


@pytest.mark.model
def test_sixty_second_clip_is_saved_within_twenty_seconds(tmp_path: Path) -> None:
    clip = AUDIO / "clip-60s.m4a"
    seconds = len(decode_audio(clip)) / 16_000
    assert 60.0 <= seconds <= 63.0, "the acceptance test is about a 60 second clip"

    settings = make_settings(tmp_path, transcriber="faster-whisper", embedder="fastembed")
    with TestClient(create_app(settings, warm=False)) as client:
        client.delete("/api/all", params={"confirm": "delete-everything"})
        with (AUDIO / "clip-short.m4a").open("rb") as fh:  # loads both models
            assert client.post("/api/entries/audio", files={"file": ("warm.m4a", fh, "audio/mp4")}).status_code == 201

        runs: list[float] = []
        stages: dict[str, int] = {}
        entry: dict[str, object] = {}
        for _ in range(3):
            with clip.open("rb") as fh:
                started = time.perf_counter()
                response = client.post("/api/entries/audio", files={"file": ("dream.m4a", fh, "audio/mp4")})
                runs.append(time.perf_counter() - started)
            assert response.status_code == 201, response.text
            entry = response.json()
            stages = entry["timings_ms"]  # type: ignore[assignment]

        saved = client.get(f"/api/entries/{entry['id']}").json()
        assert saved["image_url"] and client.get(saved["image_url"]).status_code == 200
        assert saved["engines"]["transcriber"].startswith("faster-whisper") and saved["engines"]["embedder"].startswith("fastembed")
        assert saved["has_audio"] is False

        def words(text: str) -> list[str]:
            return re.findall(r"[a-z']+", text.lower())

        match = difflib.SequenceMatcher(None, words(clip.with_suffix(".txt").read_text()), words(saved["transcript"])).ratio()
        names = {s["name"] for s in saved["symbols"]}
        print(
            f"\n{seconds:.1f} s clip, stop-to-saved over 3 warm runs: "
            f"median {statistics.median(runs):.2f} s, slowest {max(runs):.2f} s (budget {BUDGET_S:.0f} s)"
            f"\nlast run by stage (ms): {stages}"
            f"\nmodel {saved['engines']['transcriber']}, machine: {platform.platform()} {platform.machine()}"
            f"\nword match with the script: {match:.3f}; symbols: {sorted(names)}"
        )
        assert max(runs) < BUDGET_S
        assert match > 0.9
        assert {"door", "moon", "key"} <= names
