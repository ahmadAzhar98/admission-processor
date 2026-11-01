from pathlib import Path

from common.schemas.documents import DocumentStatus, DocumentType
from common.schemas.results import RuleOutcome
from common.tenant_config.loader import TenantRegistry

from functions.decide.policy import DocumentEvidence, Outcome, decide

REGISTRY = TenantRegistry(Path(__file__).resolve().parents[3] / "tenants")
UNI_C_TYPES = ["cnic", "matric_result", "fsc_result", "fee_challan"]


def _docs(confidence=0.97, types=UNI_C_TYPES, **overrides):
    docs = []
    for i, doc_type in enumerate(types):
        fields = {
            "document_id": f"d{i}",
            "document_type": DocumentType(doc_type),
            "status": DocumentStatus.VALIDATED,
            "extraction_confidence": confidence,
        }
        fields.update(overrides.get(doc_type, {}))
        docs.append(DocumentEvidence(**fields))
    return docs


def _fail(rule_id, severity="review"):
    return RuleOutcome(rule_id=rule_id, passed=False, severity=severity, message="m")


def test_clean_application_is_approved():
    decision = decide(REGISTRY.get("uni-c"), _docs(), [])
    assert decision.outcome is Outcome.APPROVED


def test_missing_required_document_is_incomplete():
    decision = decide(REGISTRY.get("uni-c"), _docs(types=["cnic", "fsc_result"]), [])
    assert decision.outcome is Outcome.INCOMPLETE
    assert decision.reasons == ["missing:matric_result", "missing:fee_challan"]


def test_b_form_satisfies_cnic_requirement():
    types = ["b_form", "matric_result", "fsc_result", "fee_challan"]
    assert decide(REGISTRY.get("uni-c"), _docs(types=types), []).outcome is Outcome.APPROVED


def test_same_confidence_approved_by_one_tenant_reviewed_by_another():
    types_a = ["cnic", "matric_result", "fsc_result", "entry_test", "fee_challan"]
    a = decide(REGISTRY.get("uni-a"), _docs(0.9, types_a), [])
    c = decide(REGISTRY.get("uni-c"), _docs(0.9), [])
    assert a.outcome is Outcome.NEEDS_REVIEW and "low_confidence" in a.reasons
    assert c.outcome is Outcome.APPROVED


def test_reject_rule_rejects_only_when_reading_is_confident():
    failing = {"fsc_result": {"failures": [_fail("fsc-min-45", "reject")]}}
    confident = decide(REGISTRY.get("uni-c"), _docs(0.97, **failing), [])
    unsure = decide(
        REGISTRY.get("uni-c"),
        _docs(0.97, **{"fsc_result": {**failing["fsc_result"], "extraction_confidence": 0.5}}),
        [],
    )
    assert confident.outcome is Outcome.REJECTED and confident.reasons == ["rule:fsc-min-45"]
    assert unsure.outcome is Outcome.NEEDS_REVIEW
    assert unsure.review_documents["d2"] == ["low_confidence", "rule:fsc-min-45"]


def test_cross_check_failure_reviews_the_involved_documents():
    decision = decide(REGISTRY.get("uni-c"), _docs(), [_fail("crosscheck:full_name")])
    assert decision.outcome is Outcome.NEEDS_REVIEW
    assert set(decision.review_documents) == {"d0", "d1", "d2"}  # not the fee challan


def test_reupload_and_unclassified_documents():
    reupload = _docs(**{"fee_challan": {"status": DocumentStatus.REUPLOAD_REQUIRED}})
    assert decide(REGISTRY.get("uni-c"), reupload, []).outcome is Outcome.INCOMPLETE
    unclassified = _docs(**{"fee_challan": {"status": DocumentStatus.NEEDS_REVIEW}})
    decision = decide(REGISTRY.get("uni-c"), unclassified, [])
    assert decision.review_documents == {"d3": ["unclassified_or_not_accepted"]}
