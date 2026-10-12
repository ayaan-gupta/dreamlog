"""Speech to text behind one small interface."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .audio import SAMPLE_RATE, decode_audio


@dataclass(frozen=True)
class Transcript:
    text: str
    duration_s: float
    engine: str


class Transcriber(Protocol):
    name: str

    def transcribe(self, path: Path) -> Transcript: ...


class FasterWhisperTranscriber:
    """Local Whisper through CTranslate2. Nothing leaves the machine."""

    def __init__(self, model: str, compute_type: str, cache_dir: Path) -> None:
        self.name = f"faster-whisper:{model}"
        self._model_name = model
        self._compute_type = compute_type
        self._cache_dir = cache_dir
        self._model: Any = None
        self._lock = threading.Lock()

    def load(self) -> None:
        with self._lock:
            if self._model is None:
                from faster_whisper import WhisperModel

                self._cache_dir.mkdir(parents=True, exist_ok=True)
                self._model = WhisperModel(
                    self._model_name, device="cpu", compute_type=self._compute_type, download_root=str(self._cache_dir / "whisper")
                )

    def transcribe(self, path: Path) -> Transcript:
        self.load()
        samples = decode_audio(path)
        language = "en" if self._model_name.endswith(".en") else None
        with self._lock:  # one transcription at a time; the model is not re-entrant
            segments, _info = self._model.transcribe(samples, beam_size=5, language=language, vad_filter=True)
            text = " ".join(segment.text.strip() for segment in segments)
        return Transcript(text=" ".join(text.split()), duration_s=len(samples) / SAMPLE_RATE, engine=self.name)


class FakeTranscriber:
    """For unit tests: decodes the audio for real, then returns a fixed script.

    Decoding is kept so that a broken upload fails the same way it would with
    the real model, and so the reported duration is true.
    """

    name = "fake"

    def __init__(self, script: str = "I was walking by the sea and found a door.") -> None:
        self.script = script

    def transcribe(self, path: Path) -> Transcript:
        samples = decode_audio(path)
        return Transcript(text=self.script, duration_s=len(samples) / SAMPLE_RATE, engine=self.name)
