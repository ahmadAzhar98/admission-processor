from pathlib import Path

from common.llm import FakeLlmClient
from common.ocr import StaticOcrEngine
from common.runtime import in_memory_runtime
from common.schemas.documents import Document, DocumentStatus
from common.schemas.events import PipelineEvent, PipelineStep

from functions.classify.service import process

TENANTS = Path(__file__).resolve().parents[3] / "tenants"
DOMICILE_TEXT = "Office of the District Officer, Lahore\nDomicile Certificate\nDistrict: Lahore"


def _setup(tenant_id, text, declared=None, llm=None):
    rt = in_memory_runtime(TENANTS)
    rt.ocr = StaticOcrEngine(text)
    rt.llm = llm or FakeLlmClient(lambda p: {"document_type": "unknown", "confidence": 0.1})
    key = rt.tenant_storage(tenant_id).put(("applications", "a1", "d1.png"), b"img", "image/png")
    rt.documents.add(
        Document(
            tenant_id=tenant_id,
            document_id="d1",
            application_id="a1",
            object_key=key,
            content_type="image/png",
            sha256="2" * 64,
            size_bytes=3,
            declared_type=declared,
        )
    )
    event = PipelineEvent(
        tenant_id=tenant_id, application_id="a1", document_id="d1", step="classify"
    )
    return rt, event


def test_accepted_type_goes_to_extract_and_ocr_is_stored():
    rt, event = _setup("uni-b", DOMICILE_TEXT, declared="domicile")
    process(event, rt)
    assert rt.documents.get("uni-b", "d1").status is DocumentStatus.CLASSIFIED
    [nxt] = rt.publisher.events
    assert nxt.step is PipelineStep.EXTRACT
    assert nxt.payload["document_type"] == "domicile"
    assert nxt.payload["declared_mismatch"] is False
    ocr = rt.results.get("uni-b", "d1", "ocr")
    assert ocr is not None and "Domicile" in ocr["text"]


def test_type_not_required_by_tenant_goes_to_review():
    rt, event = _setup("uni-c", DOMICILE_TEXT)
    process(event, rt)
    assert rt.documents.get("uni-c", "d1").status is DocumentStatus.NEEDS_REVIEW
    [nxt] = rt.publisher.events
    assert nxt.step is PipelineStep.DECIDE
    assert nxt.payload == {"reasons": ["document_type_not_accepted"]}


def test_llm_is_consulted_only_when_rules_are_unsure():
    llm = FakeLlmClient(lambda p: {"document_type": "fee_challan", "confidence": 0.9})
    rt, event = _setup("uni-a", "smudged text with no cues", llm=llm)
    process(event, rt)
    assert len(llm.prompts) == 1
    result = rt.results.get("uni-a", "d1", "classify")
    assert result is not None and result["method"] == "llm"

    llm_clear = FakeLlmClient()
    rt2, event2 = _setup("uni-b", DOMICILE_TEXT, llm=llm_clear)
    process(event2, rt2)
    assert llm_clear.prompts == []


def test_declared_type_mismatch_is_flagged():
    rt, event = _setup("uni-b", DOMICILE_TEXT, declared="cnic")
    process(event, rt)
    assert rt.publisher.events[0].payload["declared_mismatch"] is True
