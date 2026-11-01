from collections import Counter
from pathlib import Path

from common.ocr import OcrLine, StaticOcrEngine
from common.tenant_config.fields import DocumentRequirement, FieldSpec
from common.tenant_config.loader import TenantRegistry

from functions.extract.heuristic import extract_fields
from synthetic.generate import generate

REGISTRY = TenantRegistry(Path(__file__).resolve().parents[3] / "tenants")

REQ = DocumentRequirement(
    type="fsc_result",
    fields=[
        FieldSpec(name="full_name", labels=["Name", "نام"]),
        FieldSpec(name="father_name", labels=["Father Name"]),
        FieldSpec(name="obtained_marks", type="integer", labels=["Marks Obtained"]),
        FieldSpec(name="roll_number", labels=["Roll No."], pattern=r"\d{6}"),
    ],
)


def _lines(*texts, confidence=0.9):
    return [OcrLine(t, confidence, (0, i * 40, 100, i * 40 + 30)) for i, t in enumerate(texts)]


def test_longest_caption_wins():
    fields = {
        f.name: f
        for f in extract_fields(REQ, _lines("Father Name: Talha Butt", "Name: Usman Butt"))
    }
    assert fields["full_name"].value == "Usman Butt"
    assert fields["father_name"].value == "Talha Butt"


def test_values_are_typed_and_urdu_captions_work():
    fields = {
        f.name: f for f in extract_fields(REQ, _lines("نام: Usman Butt", "Marks Obtained 1,050"))
    }
    assert fields["full_name"].value == "Usman Butt"
    assert fields["obtained_marks"].value == 1050


def test_pattern_failure_lowers_confidence():
    [field] = extract_fields(REQ, _lines("Roll No.: 12AB"))
    assert field.value == "12AB"
    assert field.confidence < 0.9


def test_caption_must_be_a_whole_word():
    assert extract_fields(REQ, _lines("Names of subjects: Physics")) == []


def test_value_on_the_same_row_is_paired_with_its_caption():
    # Box layout as Tesseract returns a two-column result card.
    lines = [
        OcrLine("Name", 0.96, (82, 328, 154, 348)),
        OcrLine("Marks Obtained", 0.93, (80, 408, 244, 434)),
        OcrLine("Usman Butt", 0.95, (542, 326, 697, 349)),
        OcrLine("1,050", 0.9, (541, 406, 639, 434)),
        OcrLine("Roll No.", 0.94, (81, 488, 225, 508)),
    ]
    fields = {f.name: f for f in extract_fields(REQ, lines)}
    assert fields["full_name"].value == "Usman Butt"
    assert fields["obtained_marks"].value == 1050
    assert fields["obtained_marks"].confidence == 0.9
    assert "roll_number" not in fields  # no value on that row


def test_recall_on_synthetic_ground_truth_text():
    labels = generate(REGISTRY, ["uni-a", "uni-b", "uni-c"], 30, seed=21, out_dir=None)
    total, correct = 0, 0
    missing: Counter[tuple[str, str]] = Counter()
    for label in labels:
        requirement = REGISTRY.get(label.tenant_id).requirement(label.document_type)
        assert requirement is not None
        lines = StaticOcrEngine(label.text).recognize(b"").lines
        got = {f.name: f.value for f in extract_fields(requirement, lines)}
        for spec in requirement.fields:
            if spec.name not in label.fields:
                continue
            total += 1
            if got.get(spec.name) == label.fields[spec.name]:
                correct += 1
            else:
                missing[(label.document_type.value, spec.name)] += 1
    assert correct / total >= 0.98, missing.most_common(10)
