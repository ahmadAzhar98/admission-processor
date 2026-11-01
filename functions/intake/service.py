"""Intake logic: validate an upload, store it once, enqueue quality check."""

import hashlib
import logging

from common.errors import InvalidRequestError, PayloadTooLargeError
from common.runtime import Runtime
from common.schemas.documents import Document, DocumentStatus, DocumentType, Identifier, TenantId
from common.schemas.events import PipelineEvent, PipelineStep
from pydantic import BaseModel

logger = logging.getLogger(__name__)

EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/tiff": "tiff"}


class UploadRequest(BaseModel):
    """Metadata accompanying an uploaded file."""

    tenant_id: TenantId
    application_id: Identifier
    content_type: str
    declared_type: DocumentType | None = None


class UploadResult(BaseModel):
    """What the applicant portal gets back."""

    document_id: str
    status: DocumentStatus
    duplicate: bool


def document_id_for(application_id: str, sha256: str) -> str:
    """Derive a stable document ID from the application and file content.

    Re-uploading the same bytes for the same application yields the same
    ID, which makes intake idempotent end to end.
    """
    return hashlib.sha256(f"{application_id}:{sha256}".encode()).hexdigest()[:24]


def accept_upload(rt: Runtime, request: UploadRequest, data: bytes) -> UploadResult:
    """Store an upload and enqueue it for the quality check.

    Raises:
        InvalidRequestError: For an empty body or unsupported content type.
        PayloadTooLargeError: If the body exceeds ``max_upload_bytes``.
    """
    content_type = request.content_type.split(";")[0].strip().lower()
    extension = EXTENSIONS.get(content_type)
    if extension is None:
        raise InvalidRequestError(f"unsupported content type {content_type!r}")
    if not data:
        raise InvalidRequestError("empty upload")
    if len(data) > rt.settings.max_upload_bytes:
        raise PayloadTooLargeError(f"upload of {len(data)} bytes exceeds limit")

    sha256 = hashlib.sha256(data).hexdigest()
    document_id = document_id_for(request.application_id, sha256)
    storage = rt.tenant_storage(request.tenant_id)
    object_key = storage.put(
        ("applications", request.application_id, f"{document_id}.{extension}"),
        data,
        content_type,
    )
    record, created = rt.documents.add(
        Document(
            tenant_id=request.tenant_id,
            document_id=document_id,
            application_id=request.application_id,
            object_key=object_key,
            content_type=content_type,
            sha256=sha256,
            size_bytes=len(data),
            declared_type=request.declared_type,
        )
    )
    if created:
        rt.publisher.publish(
            PipelineEvent(
                tenant_id=request.tenant_id,
                application_id=request.application_id,
                document_id=document_id,
                step=PipelineStep.QUALITY_CHECK,
                payload={"object_key": object_key},
            )
        )
    logger.info("upload accepted", extra={"duplicate": not created, "size_bytes": len(data)})
    return UploadResult(
        document_id=record.document.document_id, status=record.status, duplicate=not created
    )
