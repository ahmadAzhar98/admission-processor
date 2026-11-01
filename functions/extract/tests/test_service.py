from pathlib import Path

from common.llm import FakeLlmClient
from common.ocr import StaticOcrEngine
from common.repositories.examples import FewShotExample
from common.runtime import in_memory_runtime
from common.schemas.documents import Document, DocumentStatus, DocumentType
from common.schemas.events import PipelineEvent, PipelineStep

from functions.extract.service import process

TENANTS = Path(__file__).resolve().parents[3] / "tenants"
DOMICILE = (
    "Office of the District Officer, Lahore\nDomicile Certificate\n"
    "Certificate No.: DOM-123456\nName: Ayesha Khan\nFather Name: Bilal Khan\n"
    "District: Lahore\nDate of Issue: 12-05-2025"
)


def _setup(text, llm=None):
    rt = in_memory_runtime(TENANTS)
    rt.ocr = StaticOcrEngine(text)
    rt.llm = llm or FakeLlmClient()
    key = rt.tenant_storage("uni-b").put(("applications", "a1", "d1.png"), b"x", "image/png")
    rt.documents.add(
        Document(
            tenant_id="uni-b",
            document_id="d1",
            application_id="a1",
            object_key=key,
            content_type="image/png",
            sha256="4" * 64,
            size_bytes=1,
        )
    )
    rt.documents.set_status(
        "uni-b", "d1", DocumentStatus.CLASSIFIED, actor="t", document_type=DocumentType.DOMICILE
    )
    event = PipelineEvent(
        tenant_id="uni-b",
        application_id="a1",
        document_id="d1",
        step="extract",
        payload={"document_type": "domicile"},
    )
    return rt, event


def test_clean_document_is_extracted_without_llm():
    llm = FakeLlmClient()
    rt, event = _setup(DOMICILE, llm)
    summary = process(event, rt)
    assert summary["llm_used"] is False and llm.prompts == []
    stored = rt.results.get("uni-b", "d1", "extract")
    assert stored is not None
    values = {f["name"]: f["value"] for f in stored["fields"]}
    assert values["issue_date"] == "2025-05-12"
    assert values["district"] == "Lahore"
    assert rt.documents.get("uni-b", "d1").status is DocumentStatus.EXTRACTED
    assert rt.publisher.events[0].step is PipelineStep.VALIDATE


def test_missing_field_triggers_llm_with_tenant_examples():
    text = DOMICILE.replace("District: Lahore\n", "Lahore\n")
    llm = FakeLlmClient(lambda p: {"district": {"value": "Lahore", "confidence": 0.8}})
    rt, event = _setup(text, llm)
    rt.examples.add(
        FewShotExample(
            tenant_id="uni-b",
            document_type="domicile",
            source_document_id="old",
            ocr_text=DOMICILE,
            fields={"district": "Lahore"},
        ),
        llm.embed(DOMICILE),
    )
    summary = process(event, rt)
    assert summary["llm_used"] is True and summary["examples_used"] == 1
    assert "Verified fields" in llm.prompts[0]


def test_required_field_missing_everywhere_zeroes_confidence():
    text = DOMICILE.replace("District: Lahore\n", "")
    rt, event = _setup(text, FakeLlmClient(lambda p: {}))
    summary = process(event, rt)
    assert summary["confidence"] == 0.0
