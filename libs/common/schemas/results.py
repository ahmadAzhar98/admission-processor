"""Outputs of the pipeline steps, each carrying confidence scores."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from common.schemas.documents import Confidence, DocumentType, Identifier, TenantId

FieldValue = str | int | float | None


class FieldSource(StrEnum):
    """Where an extracted value came from."""

    OCR = "ocr"
    LLM = "llm"
    HUMAN = "human"


class QualityReport(BaseModel):
    """Image-quality measurements and the accept/re-upload verdict."""

    accepted: bool
    width: int = Field(ge=0)
    height: int = Field(ge=0)
    blur_score: float = Field(ge=0.0, description="Variance of the Laplacian; higher is sharper")
    skew_degrees: float
    brightness: float = Field(ge=0.0, le=255.0)
    contrast: float = Field(ge=0.0)
    issues: list[str] = Field(default_factory=list)


class ClassificationResult(BaseModel):
    """Predicted document type."""

    document_type: DocumentType
    confidence: Confidence
    method: str = Field(description="Which classifier decided, e.g. 'keywords' or 'llm'")


class ExtractedField(BaseModel):
    """One extracted value with its confidence and provenance."""

    name: str
    value: FieldValue
    confidence: Confidence
    source: FieldSource = FieldSource.OCR


class ExtractionResult(BaseModel):
    """All fields extracted from one document."""

    model_config = ConfigDict(frozen=True)

    tenant_id: TenantId
    document_id: Identifier
    document_type: DocumentType
    fields: list[ExtractedField] = Field(default_factory=list)

    def get(self, name: str) -> ExtractedField | None:
        """Return the field called ``name``, or ``None`` if absent."""
        return next((f for f in self.fields if f.name == name), None)

    def value(self, name: str) -> FieldValue:
        """Return the value of field ``name``, or ``None`` if absent."""
        found = self.get(name)
        return found.value if found else None

    @property
    def confidence(self) -> float:
        """Weakest-link confidence: the minimum over all fields, 0 if none."""
        return min((f.confidence for f in self.fields), default=0.0)
