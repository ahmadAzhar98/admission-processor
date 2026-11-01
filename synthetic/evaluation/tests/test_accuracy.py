import argparse
from pathlib import Path

from common.tenant_config.loader import TenantRegistry

from synthetic.evaluation.accuracy import evaluate
from synthetic.generate import generate

TENANTS = Path(__file__).resolve().parents[3] / "tenants"


def test_ground_truth_run_produces_a_complete_report(tmp_path):
    generate(TenantRegistry(TENANTS), ["uni-c"], 2, seed=3, out_dir=tmp_path)
    args = argparse.Namespace(
        dataset=tmp_path,
        tenants_dir=TENANTS,
        ocr="ground-truth",
        llm="none",
        corrections=0.5,
        out=tmp_path / "r.json",
    )
    report = evaluate(args)
    assert report["classification"]["overall"] == 1.0
    assert report["extraction_before"]["overall"] >= 0.95
    assert report["extraction_after"] is None  # needs an LLM
    assert {"precision", "recall"} <= set(report["quality"])
