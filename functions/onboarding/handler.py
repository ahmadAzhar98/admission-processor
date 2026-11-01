"""OpenFaaS entry point for onboarding.

``POST`` a JSON body with ``tenant_id``, ``display_name``,
``admission_cycle``, ``checklist`` and ``samples``. Each sample has OCR
``text`` or a base64 ``image`` to OCR here. Requires ``X-Admin-Key``
matching the hashed ``platform-admin-key`` secret. The draft is stored
under the tenant's ``onboarding/`` prefix and returned for admin review;
it is never written to the active tenant configs.
"""

import base64
import binascii
import hmac
from typing import Any

from common.auth import ChainSecretSource, EnvSecretSource, FileSecretSource, hash_api_key
from common.errors import AuthenticationError, InvalidRequestError
from common.http import HttpEvent, Response, header, http_handler, json_response, parse_body
from common.repositories import AuditEntry
from common.runtime import Runtime, get_runtime
from common.schemas.documents import DocumentType
from common.settings import OPENFAAS_SECRETS_DIR
from common.storage import tenant_key
from common.tenant import RequestContext, bind_context
from pydantic import BaseModel, Field

from .drafting import DraftRequest, Sample, draft_config, to_json

ADMIN_SECRET = "platform-admin-key"  # noqa: S105 - name of the secret, not its value


class UploadedSample(BaseModel):
    """A sample as sent by the admin: OCR text, or an image to OCR."""

    document_type: DocumentType | None = None
    text: str | None = None
    image: str | None = Field(default=None, description="base64-encoded PNG/JPEG")


class OnboardingRequest(BaseModel):
    """Request body; samples may carry images instead of text."""

    tenant_id: str
    display_name: str
    admission_cycle: str
    checklist: str
    samples: list[UploadedSample] = Field(default_factory=list, max_length=20)


def require_admin(api_key: str | None) -> None:
    """Check the platform admin key.

    Raises:
        AuthenticationError: If the key is missing or wrong.
    """
    secrets = ChainSecretSource(FileSecretSource(OPENFAAS_SECRETS_DIR), EnvSecretSource())
    expected = secrets.read(ADMIN_SECRET)
    if not api_key or not expected or not hmac.compare_digest(hash_api_key(api_key), expected):
        raise AuthenticationError("invalid admin credentials")


def to_samples(rt: Runtime, uploaded: list[UploadedSample]) -> list[Sample]:
    """OCR image samples so the drafter only sees text."""
    samples = []
    for item in uploaded:
        text = item.text
        if text is None and item.image is not None:
            try:
                data = base64.b64decode(item.image, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise InvalidRequestError("sample image is not valid base64") from exc
            text = rt.get_ocr().recognize(data).text
        if text:
            samples.append(Sample(document_type=item.document_type, text=text))
    return samples


@http_handler
def handle(event: HttpEvent, context: Any) -> Response:
    """Draft, validate and store a pending tenant config."""
    require_admin(header(event, "X-Admin-Key"))
    body = parse_body(event, OnboardingRequest)
    rt = get_runtime()
    request = DraftRequest.model_validate(
        {**body.model_dump(exclude={"samples"}), "samples": to_samples(rt, body.samples)}
    )
    with bind_context(RequestContext(tenant_id=request.tenant_id)):
        result = draft_config(rt.get_llm(), request)
        key = tenant_key(request.tenant_id, "onboarding", "draft.json")
        rt.storage.put(key, to_json(result).encode("utf-8"), "application/json")
        rt.audit.record(
            AuditEntry(
                tenant_id=request.tenant_id,
                document_id=None,
                actor="onboarding",
                action="config_drafted",
                to_status="pending_approval",
                details={"valid": result.valid, "errors": len(result.errors)},
            )
        )
    return json_response(200, {**result.model_dump(), "stored_at": key})
