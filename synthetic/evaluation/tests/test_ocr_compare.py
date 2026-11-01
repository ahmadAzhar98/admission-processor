from pathlib import Path

from common.errors import UpstreamServiceError
from common.ocr.label import LabelOcrEngine
from common.tenant_config.loader import TenantRegistry

from synthetic.evaluation.ocr_compare import compare_engine, flatten
from synthetic.generate import generate

TENANTS = Path(__file__).resolve().parents[3] / "tenants"


def test_flatten():
    assert flatten("Name:  Ali\n Khan ") == "Name: Ali Khan"


def test_perfect_engine_scores_zero_and_groups_by_profile(tmp_path):
    labels = generate(TenantRegistry(TENANTS), ["uni-c"], 1, seed=8, out_dir=tmp_path)
    engine = LabelOcrEngine()
    for label in labels:
        engine.register((tmp_path / str(label.image_path)).read_bytes(), label.text)
    report = compare_engine(engine, labels, tmp_path)
    assert report["available"] is True
    assert report["all"]["cer"] == 0.0 and report["all"]["documents"] == len(labels)
    assert any(key.startswith("profile:") for key in report)


def test_missing_engine_is_reported_unavailable(tmp_path):
    labels = generate(TenantRegistry(TENANTS), ["uni-c"], 1, seed=8, out_dir=tmp_path)

    class Missing:
        name = "missing"

        def recognize(self, image):
            raise UpstreamServiceError("not installed")

    assert compare_engine(Missing(), labels, tmp_path)["available"] is False
