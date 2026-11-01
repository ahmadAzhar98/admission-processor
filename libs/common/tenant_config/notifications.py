"""English/Urdu notification templates with checked placeholders."""

from enum import StrEnum
from string import Formatter

from pydantic import BaseModel, ConfigDict, Field, model_validator

ALLOWED_PLACEHOLDERS = frozenset(
    {"university", "application_id", "document_type", "reasons", "portal_url"}
)
"""Values a template may reference. Deliberately excludes names and CNICs:
messages go to channels outside our control, so they must not carry PII."""


class Language(StrEnum):
    """Supported notification languages."""

    EN = "en"
    UR = "ur"


class NotificationEvent(StrEnum):
    """Moments at which an applicant is notified."""

    RECEIVED = "received"
    REUPLOAD_REQUIRED = "reupload_required"
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"


def placeholders(template: str) -> set[str]:
    """Return the field names referenced by a ``str.format`` template."""
    return {name for _, name, _, _ in Formatter().parse(template) if name}


class NotificationTemplate(BaseModel):
    """The same message in English and Urdu."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    en: str = Field(min_length=1)
    ur: str = Field(min_length=1)

    @model_validator(mode="after")
    def _known_placeholders(self) -> "NotificationTemplate":
        unknown = (placeholders(self.en) | placeholders(self.ur)) - ALLOWED_PLACEHOLDERS
        if unknown:
            raise ValueError(f"unknown template placeholders: {sorted(unknown)}")
        return self

    def render(self, language: Language, values: dict[str, str]) -> str:
        """Fill the template for ``language``; missing values render empty."""
        text = self.ur if language is Language.UR else self.en
        filled = {name: values.get(name, "") for name in placeholders(text)}
        return text.format_map(filled)


class NotificationSettings(BaseModel):
    """How and in which language a tenant notifies applicants."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    default_language: Language = Language.EN
    channel: str = Field(default="log", pattern=r"^[a-z][a-z0-9_-]*$")
    portal_url: str = ""
    templates: dict[NotificationEvent, NotificationTemplate]

    @model_validator(mode="after")
    def _all_events_covered(self) -> "NotificationSettings":
        missing = set(NotificationEvent) - set(self.templates)
        if missing:
            raise ValueError(f"missing notification templates: {sorted(missing)}")
        return self
