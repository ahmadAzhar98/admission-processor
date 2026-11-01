"""Ground-truth label schema and dataset manifest helpers."""

import json
from pathlib import Path
from typing import Any

from common.schemas.documents import DocumentType
from pydantic import BaseModel, Field

FieldValue = str | int | float


class InjectedMismatch(BaseModel):
    """A deliberate inconsistency planted to test the cross-check step."""

    document_type: DocumentType
    field: str
    original: str
    altered: str


class GroundTruth(BaseModel):
    """Everything known about one synthetic document image."""

    tenant_id: str
    application_id: str
    document_id: str
    document_type: DocumentType
    language: str
    layout: str
    fields: dict[str, FieldValue]
    text: str = Field(description="Clean text as printed; ideal OCR output")
    profile: str
    augmentations: list[dict[str, Any]] = Field(default_factory=list)
    expected_reupload: bool = False
    injected_mismatch: InjectedMismatch | None = None
    image_path: str | None = None


MANIFEST_NAME = "manifest.jsonl"


def write_manifest(labels: list[GroundTruth], out_dir: Path) -> Path:
    """Write one JSON label per line to ``out_dir/manifest.jsonl``."""
    path = out_dir / MANIFEST_NAME
    with path.open("w", encoding="utf-8") as handle:
        for label in labels:
            handle.write(label.model_dump_json() + "\n")
    return path


def read_manifest(path: Path) -> list[GroundTruth]:
    """Read labels from a manifest file (or a dataset directory)."""
    if path.is_dir():
        path = path / MANIFEST_NAME
    with path.open(encoding="utf-8") as handle:
        return [GroundTruth.model_validate(json.loads(line)) for line in handle if line.strip()]
