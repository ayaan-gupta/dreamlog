"""Decodes any audio file to 48 kHz mono 16-bit WAV.

    .venv/bin/python scripts/to_wav.py in.m4a out.wav [seconds of silence to append]

Chromium's fake microphone only reads WAV, and it loops the file, so the demo
recorder pads the clip with silence instead of letting it start again.
"""

from __future__ import annotations

import sys
import wave

import av
import numpy as np


def main(source: str, target: str, pad_s: float = 0.0) -> None:
    chunks = []
    with av.open(source) as container:
        resampler = av.AudioResampler(format="s16", layout="mono", rate=48_000)
        for frame in container.decode(audio=0):
            chunks.extend(out.to_ndarray().reshape(-1) for out in resampler.resample(frame))
        chunks.extend(out.to_ndarray().reshape(-1) for out in resampler.resample(None))
    samples = np.concatenate([*chunks, np.zeros(int(pad_s * 48_000), dtype=np.int16)]).astype(np.int16)
    with wave.open(target, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(48_000)
        out.writeframes(samples.tobytes())
    print(f"{target}: {len(samples) / 48_000:.1f} s")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 0.0)
