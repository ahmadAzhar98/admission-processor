"""LLM-assisted drafting of tenant configurations.

An admissions office describes its requirements in plain language ("FSc
at least 60%, Punjab domicile required, fee by 31 August") and supplies
sample documents. The LLM proposes a config. The draft is then forced
into a safe shape (status ``pending_approval``, derived secret names) and
validated against the real schema. Validation errors go back to the
model once for repair. The result is never active until an administrator
approves it.
"""

import json
import logging
from typing import Any

from common.errors import TenantConfigError
from common.llm import LlmClient
from common.schemas.documents import DocumentType
from common.tenant_config.loader import parse_config
from common.tenant_config.models import ConfigStatus, TenantConfig
from common.tenant_config.notifications import NotificationEvent
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

MAX_SAMPLE_CHARS = 1500

DEFAULT_TEMPLATES: dict[str, dict[str, str]] = {
    NotificationEvent.RECEIVED: {
        "en": "{university}: {document_type} received for application {application_id}.",
        "ur": "{university}: درخواست {application_id} کے لیے {document_type} موصول ہو گیا۔",
    },
    NotificationEvent.REUPLOAD_REQUIRED: {
        "en": "{university}: please re-upload your {document_type} ({reasons}) at {portal_url}.",
        "ur": "{university}: براہ کرم اپنا {document_type} دوبارہ اپ لوڈ کریں ({reasons})۔",
    },
    NotificationEvent.NEEDS_REVIEW: {
        "en": "{university}: application {application_id} is being reviewed.",
        "ur": "{university}: درخواست {application_id} کا جائزہ لیا جا رہا ہے۔",
    },
    NotificationEvent.APPROVED: {
        "en": "{university}: documents for application {application_id} are verified.",
        "ur": "{university}: درخواست {application_id} کے کاغذات کی تصدیق ہو گئی ہے۔",
    },
    NotificationEvent.REJECTED: {
        "en": "{university}: application {application_id} does not meet requirements ({reasons}).",
        "ur": "{university}: درخواست {application_id} شرائط پر پوری نہیں اترتی ({reasons})۔",
    },
}
"""Neutral bilingual templates used when the draft omits some."""


class Sample(BaseModel):
    """A sample document: its OCR text and, if known, its type."""

    document_type: DocumentType | None = None
    text: str = Field(min_length=1)


class DraftRequest(BaseModel):
    """What an admissions office provides to start onboarding."""

    tenant_id: str = Field(pattern=r"^[a-z][a-z0-9-]{1,30}[a-z0-9]$")
    display_name: str = Field(min_length=1, max_length=120)
    admission_cycle: str = Field(pattern=r"^\d{4}$")
    checklist: str = Field(min_length=10, max_length=8000)
    samples: list[Sample] = Field(default_factory=list, max_length=20)


class DraftResult(BaseModel):
    """The proposed config and whether it passed schema validation."""

    valid: bool
    config: dict[str, Any]
    errors: list[str] = Field(default_factory=list)
    attempts: int


def build_prompt(request: DraftRequest, errors: list[str] | None = None) -> str:
    """Prompt with the checklist, samples, schema summary and any errors to fix."""
    samples = "\n".join(
        f"--- sample ({s.document_type.value if s.document_type else 'type unknown'}) ---\n"
        f"{s.text[:MAX_SAMPLE_CHARS]}"
        for s in request.samples
    )
    types = ", ".join(t.value for t in DocumentType if t is not DocumentType.UNKNOWN)
    repair = ""
    if errors:
        repair = (
            "\nYour previous draft failed validation. Fix exactly these errors:\n- "
            + "\n- ".join(errors)
        )
    return (
        "Draft an admission-document configuration for a Pakistani university.\n"
        f"Document types: {types}.\n"
        "For each required document list the fields to extract (snake_case names, "
        "type string|integer|number|date, printed captions as labels, pii true for "
        "names and identity numbers).\n"
        "Rules must use only these types: min_percentage (obtained_field, total_field, "
        "min_percent), range (field, min, max), allowed_values (field, values), age "
        "(field, reference_date, min_years, max_years), date_window (field, not_before, "
        "not_after); each has id, description, document, severity review|reject, and "
        "may only reference fields declared for its document.\n"
        "Cross-checks compare a field (e.g. full_name) across documents.\n"
        f"Admissions checklist:\n<<<\n{request.checklist}\n>>>\n"
        f"Sample documents:\n{samples or '(none)'}\n{repair}"
    )


def enforce_safe_shape(request: DraftRequest, draft: dict[str, Any]) -> dict[str, Any]:
    """Overwrite fields the model must not choose, and fill required gaps.

    Identity, status and secret names are set here, never by the model, so a
    draft can never activate itself or point at another tenant's secrets.
    """
    shaped = dict(draft)
    shaped.update(
        {
            "tenant_id": request.tenant_id,
            "display_name": request.display_name,
            "admission_cycle": request.admission_cycle,
            "status": ConfigStatus.PENDING_APPROVAL.value,
            "auth": {
                "api_key_secret": f"{request.tenant_id}-api-key",
                "staff_api_key_secret": f"{request.tenant_id}-staff-key",
            },
        }
    )
    notifications = dict(shaped.get("notifications") or {})
    templates = {**DEFAULT_TEMPLATES, **(notifications.get("templates") or {})}
    notifications["templates"] = {str(k): v for k, v in templates.items()}
    shaped["notifications"] = notifications
    return shaped


def _schema() -> dict[str, Any]:
    return TenantConfig.model_json_schema()


def draft_config(llm: LlmClient, request: DraftRequest, max_attempts: int = 2) -> DraftResult:
    """Ask the LLM for a draft, validate it, and allow one repair round.

    Raises:
        UpstreamServiceError: If the LLM cannot be reached at all.
    """
    errors: list[str] = []
    shaped: dict[str, Any] = {}
    for attempt in range(1, max_attempts + 1):
        raw = llm.complete_json(build_prompt(request, errors or None), _schema())
        shaped = enforce_safe_shape(request, raw)
        try:
            parse_config(shaped, f"draft:{request.tenant_id}")
        except TenantConfigError as exc:
            errors = [e.strip() for e in str(exc).split(":", 1)[-1].split(";") if e.strip()]
            logger.info("draft invalid", extra={"attempt": attempt, "errors": len(errors)})
            continue
        return DraftResult(valid=True, config=shaped, attempts=attempt)
    return DraftResult(valid=False, config=shaped, errors=errors, attempts=max_attempts)


def to_json(result: DraftResult) -> str:
    """Pretty JSON of the draft config for storage and admin review."""
    return json.dumps(result.config, indent=2, ensure_ascii=False, default=str)
