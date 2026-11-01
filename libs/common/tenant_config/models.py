"""The root tenant configuration model and its cross-reference checks."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from common.schemas.documents import DocumentType, TenantId
from common.tenant_config.fields import DocumentRequirement
from common.tenant_config.notifications import NotificationSettings
from common.tenant_config.rules import Rule, Severity


class ConfigStatus(StrEnum):
    """Whether a config may be used to process documents."""

    ACTIVE = "active"
    PENDING_APPROVAL = "pending_approval"
    """Drafted (for example by the onboarding assistant); an admin must approve."""


class QualityThresholds(BaseModel):
    """Image-quality limits below which a re-upload is requested.

    Units follow the quality-check measures: ``min_blur_score`` is the
    contrast-normalised Laplacian variance, brightness is the mean and
    contrast the 1st-99th percentile spread of the 1000 px grayscale page.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    min_width: int = Field(default=800, gt=0)
    min_height: int = Field(default=600, gt=0)
    min_blur_score: float = Field(default=60.0, ge=0)
    max_skew_degrees: float = Field(default=5.0, ge=0, le=45)
    min_brightness: float = Field(default=60.0, ge=0, le=255)
    max_brightness: float = Field(default=252.0, ge=0, le=255)
    min_contrast: float = Field(default=40.0, ge=0, le=255)


class DecisionThresholds(BaseModel):
    """Confidence levels that drive automation versus human review."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    classification_min_confidence: float = Field(default=0.7, ge=0, le=1)
    """Below this the classifier falls back to the LLM."""

    auto_approve_min_confidence: float = Field(default=0.9, ge=0, le=1)
    """Extraction confidence needed to approve without a human."""

    few_shot_examples: int = Field(default=3, ge=0, le=10)
    """How many past corrections to include in extraction prompts."""


class CrossCheck(BaseModel):
    """A field that must agree across several documents."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    field: str
    documents: list[DocumentType] = Field(min_length=2)
    method: Literal["exact", "fuzzy"] = "exact"
    min_similarity: float = Field(default=0.9, ge=0, le=1)
    severity: Severity = Severity.REVIEW


class AuthSettings(BaseModel):
    """Where the tenant's intake credential is stored."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    api_key_secret: str = Field(pattern=r"^[a-z0-9][a-z0-9-]*$")
    """OpenFaaS secret holding the SHA-256 hash of the tenant's API key."""

    staff_api_key_secret: str | None = Field(default=None, pattern=r"^[a-z0-9][a-z0-9-]*$")
    """Secret holding the hash of the staff key for the review API.

    Kept separate from the upload key so a leaked portal credential cannot
    read or change review decisions. Without it, staff endpoints refuse
    every request for the tenant.
    """


class TenantConfig(BaseModel):
    """Everything that distinguishes one university's admission process."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tenant_id: TenantId
    display_name: str = Field(min_length=1)
    profile: str = ""
    admission_cycle: str = Field(pattern=r"^\d{4}$")
    status: ConfigStatus = ConfigStatus.ACTIVE
    auth: AuthSettings
    documents: list[DocumentRequirement] = Field(min_length=1)
    rules: list[Rule] = Field(default_factory=list)
    cross_checks: list[CrossCheck] = Field(default_factory=list)
    quality: QualityThresholds = QualityThresholds()
    decision: DecisionThresholds = DecisionThresholds()
    notifications: NotificationSettings
    retention_days: int = Field(default=365, gt=0)

    def requirement(self, document_type: DocumentType) -> DocumentRequirement | None:
        """Return the requirement for ``document_type``, including alternatives."""
        for req in self.documents:
            if req.type == document_type:
                return req
        return None

    @property
    def accepted_types(self) -> set[DocumentType]:
        """All document types this tenant has a field spec for."""
        return {req.type for req in self.documents}

    @model_validator(mode="after")
    def _references_resolve(self) -> "TenantConfig":
        types = [req.type for req in self.documents]
        if len(types) != len(set(types)):
            raise ValueError("each document type may be declared only once")
        for req in self.documents:
            for alt in req.alternatives:
                if alt not in types:
                    raise ValueError(f"{req.type}: alternative {alt} has no field spec")
        rule_ids = [rule.id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("rule ids must be unique")
        for rule in self.rules:
            self._require_fields(rule.document, rule.referenced_fields(), f"rule {rule.id}")
        for check in self.cross_checks:
            for doc_type in check.documents:
                self._require_fields(doc_type, [check.field], f"cross-check {check.field}")
        return self

    def _require_fields(self, doc_type: DocumentType, names: list[str], where: str) -> None:
        req = self.requirement(doc_type)
        if req is None:
            raise ValueError(f"{where}: document {doc_type} is not declared")
        for name in names:
            if req.field(name) is None:
                raise ValueError(f"{where}: field {name} not declared for {doc_type}")
