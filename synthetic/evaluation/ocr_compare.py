"""Compare OCR engines on the synthetic dataset.

Usage::

    python -m synthetic.evaluation.ocr_compare --dataset synthetic/output \
        --engine tesseract --engine paddle

Reports mean character and word error rate and seconds per page for each
engine, overall and per degradation profile and language. Text is
compared line-insensitively (whitespace collapsed), since layouts differ
in how engines order table cells. An engine that is not installed is
reported as unavailable instead of failing the run.
"""

import argparse
import json
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from common.errors import UpstreamServiceError
from common.ocr import OcrEngine
from common.ocr.fallback import build_ocr_engine
from common.settings import Settings

from synthetic.evaluation.metrics import character_error_rate, word_error_rate
from synthetic.labels import GroundTruth, read_manifest


def flatten(text: str) -> str:
    """Collapse all whitespace so line breaks and spacing do not count."""
    return " ".join(text.split())


def compare_engine(engine: OcrEngine, labels: list[GroundTruth], dataset: Path) -> dict[str, Any]:
    """Run ``engine`` over every labelled image and aggregate error rates."""
    groups: dict[str, list[tuple[float, float, float]]] = defaultdict(list)
    for label in labels:
        data = (dataset / str(label.image_path)).read_bytes()
        started = time.perf_counter()
        try:
            text = engine.recognize(data).text
        except UpstreamServiceError as exc:
            return {"available": False, "error": str(exc)}
        seconds = time.perf_counter() - started
        cer = character_error_rate(flatten(label.text), flatten(text))
        wer = word_error_rate(flatten(label.text), flatten(text))
        for key in ("all", f"profile:{label.profile}", f"language:{label.language}"):
            groups[key].append((cer, wer, seconds))

    def summary(values: list[tuple[float, float, float]]) -> dict[str, float]:
        return {
            "documents": len(values),
            "cer": round(statistics.mean(v[0] for v in values), 4),
            "wer": round(statistics.mean(v[1] for v in values), 4),
            "seconds_per_page": round(statistics.mean(v[2] for v in values), 3),
        }

    return {"available": True, **{k: summary(v) for k, v in sorted(groups.items())}}


def main(argv: list[str] | None = None) -> None:
    """Command-line entry point; writes JSON to ``--out``."""
    parser = argparse.ArgumentParser(description="OCR engine comparison on synthetic data")
    parser.add_argument("--dataset", type=Path, default=Path("synthetic/output"))
    parser.add_argument("--engine", action="append", choices=["tesseract", "paddle"])
    parser.add_argument("--limit", type=int, default=0, help="first N documents only")
    parser.add_argument("--out", type=Path, default=Path("results/ocr_compare.json"))
    args = parser.parse_args(argv)
    labels = read_manifest(args.dataset)
    if args.limit:
        labels = labels[: args.limit]
    report = {
        name: compare_engine(build_ocr_engine(Settings(ocr_engine=name)), labels, args.dataset)
        for name in args.engine or ["tesseract", "paddle"]
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
