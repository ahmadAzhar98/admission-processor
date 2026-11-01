"""Field and document-requirement specifications."""

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from common.schemas.documents import DocumentType

FIELD_NAME = r"^[a-z][a-z0-9_]{0,63}$"


class FieldType(StrEnum):
    """Value types an extracted field may have."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    DATE = "date"


class FieldSpec(BaseModel):
    """One field to extract from a document type.

    ``labels`` lists the printed captions the field appears under (for
    example "Roll No." or "رول نمبر"); they guide both the OCR heuristics
    and the LLM prompt. ``pii`` marks values that must be masked in logs.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(pattern=FIELD_NAME)
    type: FieldType = FieldType.STRING
    required: bool = True
    description: str = ""
    labels: list[str] = Field(default_factory=list)
    pattern: str | None = None
    pii: bool = False

    @field_validator("pattern")
    @classmethod
    def _pattern_compiles(cls, value: str | None) -> str | None:
        if value is not None:
            try:
                re.compile(value)
            except re.error as exc:
                raise ValueError(f"invalid regex {value!r}: {exc}") from exc
        return value


class DocumentRequirement(BaseModel):
    """A document type the tenant accepts, and the fields to extract from it.

    ``alternatives`` lists types that satisfy the requirement instead (for
    example a B-form in place of a CNIC for applicants under 18).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    type: DocumentType
    required: bool = True
    alternatives: list[DocumentType] = Field(default_factory=list)
    fields: list[FieldSpec] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique_field_names(self) -> "DocumentRequirement":
        names = [f.name for f in self.fields]
        duplicates = {n for n in names if names.count(n) > 1}
        if duplicates:
            raise ValueError(f"duplicate fields in {self.type}: {sorted(duplicates)}")
        if self.type in self.alternatives or DocumentType.UNKNOWN in self.alternatives:
            raise ValueError(f"invalid alternatives for {self.type}")
        return self

    def field(self, name: str) -> FieldSpec | None:
        """Return the spec of field ``name`` or ``None``."""
        return next((f for f in self.fields if f.name == name), None)
