from pathlib import Path

import pytest
from common.runtime import InMemoryRuntime, in_memory_runtime
from common.schemas.documents import Document, DocumentStatus, DocumentType
from common.schemas.results import ExtractedField, ExtractionResult

TENANTS = Path(__file__).resolve().parents[3] / "tenants"


@pytest.fixture
def rt() -> InMemoryRuntime:
    """Runtime with one uni-b domicile document waiting for review."""
    runtime = in_memory_runtime(TENANTS)
    key = runtime.tenant_storage("uni-b").put(("applications", "a1", "d1.png"), b"PNG", "image/png")
    runtime.documents.add(
        Document(
            tenant_id="uni-b",
            document_id="d1",
            application_id="a1",
            object_key=key,
            content_type="image/png",
            sha256="6" * 64,
            size_bytes=3,
        )
    )
    runtime.documents.set_status(
        "uni-b",
        "d1",
        DocumentStatus.NEEDS_REVIEW,
        actor="decide",
        document_type=DocumentType.DOMICILE,
    )
    extraction = ExtractionResult(
        tenant_id="uni-b",
        document_id="d1",
        document_type=DocumentType.DOMICILE,
        fields=[
            ExtractedField(name="district", value="Lahor", confidence=0.4),
            ExtractedField(name="issue_date", value="2025-05-12", confidence=0.9),
        ],
    )
    runtime.results.save(
        "uni-b", "d1", "extract", {**extraction.model_dump(mode="json"), "llm_used": True}
    )
    runtime.results.save("uni-b", "d1", "ocr", {"text": "District: Lahor", "lines": []})
    runtime.reviews.open("uni-b", "d1", ["low_confidence"])
    return runtime
