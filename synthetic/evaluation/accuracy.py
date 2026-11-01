"""Measure quality-check, classification and extraction accuracy.

Usage::

    make synthetic APPLICATIONS=10
    python -m synthetic.evaluation.accuracy --dataset synthetic/output --ocr tesseract
    python -m synthetic.evaluation.accuracy --ocr paddle --llm ollama --corrections 0.5

Extraction is scored per field, exact match after normalisation, grouped
by tenant and document type. With ``--llm ollama`` and ``--corrections``,
applications are split by index: the ground truth of the first share is
stored as tenant few-shot examples (as reviewer corrections would be), and
the remaining applications are extracted before and after, so "after"
measures the effect of corrections on unseen documents. Without an LLM the
examples cannot influence extraction, so no "after" figure is produced.
"""

import argparse
import json
import logging
import time
from pathlib import Path
from typing import Any

from common.llm import FakeLlmClient, LlmClient, OllamaClient
from common.log import configure_logging
from common.ocr import OcrEngine
from common.ocr.fallback import build_ocr_engine
from common.ocr.label import LabelOcrEngine
from common.repositories.examples import FewShotExample
from common.runtime import InMemoryRuntime, in_memory_runtime
from common.settings import Settings
from common.tenant_config.loader import TenantRegistry

from functions.classify.classifier import classify_text
from functions.extract.service import extract
from functions.quality_check.service import assess
from synthetic.evaluation.metrics import Confusion, Tally, normalise_for_compare
from synthetic.labels import GroundTruth, read_manifest

logger = logging.getLogger(__name__)


def make_ocr(name: str, labels: list[GroundTruth], dataset: Path) -> OcrEngine:
    """Ground-truth text lookup, or a real engine from settings."""
    if name == "ground-truth":
        engine = LabelOcrEngine()
        for label in labels:
            engine.register((dataset / str(label.image_path)).read_bytes(), label.text)
        return engine
    return build_ocr_engine(Settings(ocr_engine=name))


def make_llm(name: str) -> LlmClient:
    """No-op client, or Ollama configured from AP_* settings."""
    if name == "none":
        return FakeLlmClient(lambda prompt: {})
    settings = Settings()
    return OllamaClient(settings.ollama_url, settings.llm_model, settings.embedding_model, 120.0)


def score_extraction(
    rt: InMemoryRuntime,
    registry: TenantRegistry,
    label: GroundTruth,
    text: str,
    lines: Any,
    tally: Tally,
) -> None:
    """Extract with the document's true type and count field matches."""
    config = registry.get(label.tenant_id)
    result, _ = extract(rt, config, label.document_type, label.document_id, text, lines)
    requirement = config.requirement(label.document_type)
    declared = {spec.name for spec in requirement.fields} if requirement else set()
    for name, expected in label.fields.items():
        if name in declared:
            tally.add(
                (label.tenant_id, label.document_type.value),
                normalise_for_compare(result.value(name)) == normalise_for_compare(expected),
            )


def evaluate(args: argparse.Namespace) -> dict[str, Any]:
    """Run the evaluation and return a JSON-serialisable report."""
    labels = read_manifest(args.dataset)
    registry = TenantRegistry(args.tenants_dir)
    ocr = make_ocr(args.ocr, labels, args.dataset)
    rt = in_memory_runtime(args.tenants_dir)
    rt.llm = make_llm(args.llm)
    quality, classification = Confusion(), Tally()
    before, after = Tally(), Tally()
    apps = sorted({(lbl.tenant_id, lbl.application_id) for lbl in labels})
    train = set(apps[: int(len(apps) * args.corrections)]) if args.llm != "none" else set()
    readings: dict[str, tuple[str, Any]] = {}
    ocr_seconds = 0.0
    for label in labels:
        data = (args.dataset / str(label.image_path)).read_bytes()
        config = registry.get(label.tenant_id)
        report = assess(data, config.quality)
        quality.add(not report.accepted, label.expected_reupload)
        started = time.perf_counter()
        reading = ocr.recognize(data)
        ocr_seconds += time.perf_counter() - started
        readings[label.document_id] = (reading.text, reading.lines)
        predicted = classify_text(reading.text, report.width, report.height).document_type
        classification.add(
            (label.tenant_id, label.document_type.value), predicted == label.document_type
        )
        if (label.tenant_id, label.application_id) not in train:
            score_extraction(rt, registry, label, reading.text, reading.lines, before)
    if train:
        for label in labels:
            if (label.tenant_id, label.application_id) in train:
                text = readings[label.document_id][0]
                example = FewShotExample(
                    tenant_id=label.tenant_id,
                    document_type=label.document_type,
                    source_document_id=label.document_id,
                    ocr_text=text,
                    fields=label.fields,
                )
                rt.examples.add(example, rt.get_llm().embed(text))
        for label in labels:
            if (label.tenant_id, label.application_id) not in train:
                text, lines = readings[label.document_id]
                score_extraction(rt, registry, label, text, lines, after)

    def rows(tally: Tally) -> list[dict[str, Any]]:
        return [
            {
                "tenant": k[0],
                "document_type": k[1],
                "correct": c,
                "total": t,
                "accuracy": round(r, 4),
            }
            for k, c, t, r in tally.rows()
        ]

    return {
        "settings": {
            "dataset": str(args.dataset),
            "ocr": args.ocr,
            "llm": args.llm,
            "corrections_share": args.corrections if train else 0.0,
            "documents": len(labels),
        },
        "ocr_seconds_per_document": round(ocr_seconds / max(len(labels), 1), 3),
        "quality": {
            "tp": quality.tp,
            "fp": quality.fp,
            "tn": quality.tn,
            "fn": quality.fn,
            "precision": round(quality.precision, 4),
            "recall": round(quality.recall, 4),
        },
        "classification": {
            "overall": round(classification.overall(), 4),
            "rows": rows(classification),
        },
        "extraction_before": {"overall": round(before.overall(), 4), "rows": rows(before)},
        "extraction_after": (
            {"overall": round(after.overall(), 4), "rows": rows(after)} if train else None
        ),
    }


def main(argv: list[str] | None = None) -> None:
    """Command-line entry point; writes JSON to ``--out``."""
    parser = argparse.ArgumentParser(description="Accuracy evaluation on synthetic data")
    parser.add_argument("--dataset", type=Path, default=Path("synthetic/output"))
    parser.add_argument("--tenants-dir", type=Path, default=Path("tenants"))
    parser.add_argument(
        "--ocr",
        default="ground-truth",
        choices=["ground-truth", "tesseract", "paddle", "paddle+tesseract"],
    )
    parser.add_argument("--llm", default="none", choices=["none", "ollama"])
    parser.add_argument("--corrections", type=float, default=0.5)
    parser.add_argument("--out", type=Path, default=Path("results/accuracy.json"))
    args = parser.parse_args(argv)
    configure_logging("WARNING")
    report = evaluate(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.warning("evaluation written", extra={"out": str(args.out)})


if __name__ == "__main__":
    main()
