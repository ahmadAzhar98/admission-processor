from common.errors import UpstreamServiceError
from common.llm import FakeLlmClient
from common.repositories.examples import FewShotExample
from common.tenant_config.fields import DocumentRequirement, FieldSpec

from functions.extract.llm_extract import (
    answer_model,
    build_prompt,
    extract_with_llm,
    response_schema,
)

REQ = DocumentRequirement(
    type="domicile",
    fields=[
        FieldSpec(name="district", labels=["District", "ضلع"]),
        FieldSpec(name="issue_date", type="date"),
        FieldSpec(name="certificate_number", pattern=r"DOM-\d{6}"),
    ],
)
EXAMPLE = FewShotExample(
    tenant_id="uni-b",
    document_type="domicile",
    source_document_id="d0",
    ocr_text="District: Kasur",
    fields={"district": "Kasur"},
)


def test_schema_and_model_follow_tenant_fields():
    schema = response_schema(REQ)
    assert schema["required"] == ["district", "issue_date", "certificate_number"]
    assert schema["properties"]["issue_date"]["properties"]["value"]["type"] == ["string", "null"]
    model = answer_model(REQ)
    assert set(model.model_fields) == {"district", "issue_date", "certificate_number"}


def test_prompt_contains_examples_and_captions():
    prompt = build_prompt(REQ, "District: Lahore", [EXAMPLE])
    assert "Verified fields" in prompt and "Kasur" in prompt
    assert "printed as District, ضلع" in prompt
    assert "YYYY-MM-DD" in prompt


def test_answers_are_normalised_and_checked():
    llm = FakeLlmClient(
        lambda p: {
            "district": {"value": "Lahore", "confidence": 0.9},
            "issue_date": {"value": "12/05/2025", "confidence": 0.8},
            "certificate_number": {"value": "DOM-12", "confidence": 0.9},
        }
    )
    fields = {f.name: f for f in extract_with_llm(llm, REQ, "text", []) or []}
    assert fields["issue_date"].value == "2025-05-12"
    assert fields["district"].source == "llm"
    assert fields["certificate_number"].confidence < 0.9


def test_null_values_are_omitted():
    llm = FakeLlmClient(lambda p: {"district": {"value": None, "confidence": 0.0}})
    assert extract_with_llm(llm, REQ, "text", []) == []


def test_failures_return_none():
    def boom(prompt):
        raise UpstreamServiceError("down")

    assert extract_with_llm(FakeLlmClient(boom), REQ, "t", []) is None
    bad = FakeLlmClient(lambda p: {"district": {"value": "x", "confidence": 7}})
    assert extract_with_llm(bad, REQ, "t", []) is None
