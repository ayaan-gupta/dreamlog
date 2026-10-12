"""Chooses the canonicalisation threshold from hand-labelled symbol pairs.

    .venv/bin/python scripts/calibrate_threshold.py

The rule, fixed before looking at the result: take the threshold that
maximises F1 on the labelled pairs, and if a range of thresholds ties, take the
lowest of them rounded to two decimals. The pair water/ocean is not among the
labelled pairs. It is reported at the end as a held-out check.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from dreamlog.config import get_settings  # noqa: E402
from dreamlog.embed import FastEmbedEmbedder, symbol_text  # noqa: E402

PAIRS = json.loads((ROOT / "api" / "dreamlog" / "data" / "calibration_pairs.json").read_text())


def evaluate(embedder: FastEmbedEmbedder, phrase) -> dict[str, object]:  # type: ignore[no-untyped-def]
    words = sorted({w for key in ("merge", "distinct") for pair in PAIRS[key] for w in pair} | {"water", "ocean", "sea", "lake", "river"})
    vectors = dict(zip(words, embedder.embed([phrase(w) for w in words]), strict=True))

    def sim(a: str, b: str) -> float:
        return float(vectors[a] @ vectors[b])

    merge = [sim(a, b) for a, b in PAIRS["merge"]]
    distinct = [sim(a, b) for a, b in PAIRS["distinct"]]
    auc = float(np.mean([(m > d) + 0.5 * (m == d) for m in merge for d in distinct]))
    curve = []
    for t in np.arange(0.30, 0.951, 0.01):
        tp = sum(m >= t for m in merge)
        fp = sum(d >= t for d in distinct)
        precision = tp / (tp + fp) if tp + fp else 1.0
        recall = tp / len(merge)
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        curve.append((round(float(t), 2), precision, recall, f1))
    best = max(c[3] for c in curve)
    plateau = [c for c in curve if c[3] >= best - 1e-9]
    return {"auc": auc, "curve": curve, "best": plateau[0], "plateau": (plateau[0][0], plateau[-1][0]), "sim": sim}


def main() -> None:
    settings = get_settings()
    embedder = FastEmbedEmbedder(settings.embedding_model, settings.model_cache_dir)
    print(f"model: {settings.embedding_model}")
    print(f"pairs: {len(PAIRS['merge'])} merge, {len(PAIRS['distinct'])} distinct\n")
    for label, phrase in (("bare word", lambda w: w), ("with article (used)", symbol_text)):
        result = evaluate(embedder, phrase)
        threshold, precision, recall, f1 = result["best"]  # type: ignore[misc]
        lo, hi = result["plateau"]  # type: ignore[misc]
        print(f"{label}: AUC {result['auc']:.3f}, best F1 {f1:.3f} at {threshold:.2f} (precision {precision:.2f}, recall {recall:.2f}), F1 plateau {lo:.2f} to {hi:.2f}")
        if phrase is symbol_text:
            sim = result["sim"]
            print("\n threshold  precision  recall  F1")
            for t, p, r, f in result["curve"]:  # type: ignore[union-attr]
                if 0.5 <= t <= 0.72:
                    print(f"   {t:.2f}      {p:.2f}      {r:.2f}   {f:.3f}{'   <- chosen' if t == threshold else ''}")
            print(f"\nchosen threshold: {threshold:.2f}  (configured default: {settings.canonical_threshold:.2f})")
            print("wrongly merged at that threshold:", ", ".join(f"{a}/{b} {sim(a, b):.2f}" for a, b in PAIRS["distinct"] if sim(a, b) >= threshold))  # type: ignore[operator]
            print("wrongly kept apart:", ", ".join(f"{a}/{b} {sim(a, b):.2f}" for a, b in PAIRS["merge"] if sim(a, b) < threshold))  # type: ignore[operator]
            print("\nheld out, not used above:")
            for other in ("ocean", "sea", "lake", "river"):
                print(f"  water / {other}: {sim('water', other):.3f}")  # type: ignore[operator]


if __name__ == "__main__":
    main()
