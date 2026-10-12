"""Decodes whatever the browser recorded into 16 kHz mono float32.

Chrome records WebM/Opus and Safari records MP4/AAC. PyAV ships its own FFmpeg
libraries, so no ffmpeg binary is needed. This is done here and not left to
faster-whisper because faster-whisper 1.2.1 calls ``av.open`` with a keyword
that PyAV 19 removed, which fails before a single sample is read.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import av
import numpy as np
from numpy.typing import NDArray

SAMPLE_RATE = 16_000


class AudioDecodeError(ValueError):
    pass


def decode_audio(path: Path) -> NDArray[np.float32]:
    chunks: list[NDArray[Any]] = []
    try:
        with av.open(str(path)) as container:
            if not container.streams.audio:
                raise AudioDecodeError("the upload has no audio track")
            resampler = av.AudioResampler(format="s16", layout="mono", rate=SAMPLE_RATE)
            for frame in container.decode(audio=0):
                for out in resampler.resample(frame):
                    chunks.append(out.to_ndarray().reshape(-1))
            for out in resampler.resample(None):
                chunks.append(out.to_ndarray().reshape(-1))
    except AudioDecodeError:
        raise
    except Exception as exc:  # PyAV raises a family of FFmpeg errors
        raise AudioDecodeError(f"could not decode audio: {exc}") from exc
    if not chunks:
        raise AudioDecodeError("the recording is empty")
    return np.concatenate(chunks).astype(np.float32) / 32768.0
