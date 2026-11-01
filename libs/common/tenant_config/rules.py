"""Declarative validation rules.

Rules are a closed set of typed models selected by their ``type`` key,
never free-form expressions. That keeps tenant files safe to load (no
``eval``), lets the loader check that every referenced field exists, and
gives the validation engine one small function per rule type.
"""

from datetime import date
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from common.schemas.documents import DocumentType

RULE_ID = r"^[a-z][a-z0-9-]{1,63}$"


class Severity(StrEnum):
    """What happens when a rule fails."""

    REVIEW = "review"
    """Send the application to a human reviewer."""

    REJECT = "reject"
    """The application cannot be accepted as submitted."""


class _RuleBase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(pattern=RULE_ID)
    description: str
    document: DocumentType
    severity: Severity = Severity.REVIEW

    def referenced_fields(self) -> list[str]:
        """Return the field names this rule reads from ``document``."""
        raise NotImplementedError


class MinPercentageRule(_RuleBase):
    """``obtained / total * 100`` must be at least ``min_percent``."""

    type: Literal["min_percentage"]
    obtained_field: str
    total_field: str
    min_percent: float = Field(ge=0, le=100)

    def referenced_fields(self) -> list[str]:
        """Return the obtained and total fields."""
        return [self.obtained_field, self.total_field]


class RangeRule(_RuleBase):
    """A numeric field must lie within ``[min, max]`` (either bound optional)."""

    type: Literal["range"]
    field: str
    min: float | None = None
    max: float | None = None

    @model_validator(mode="after")
    def _has_bound(self) -> "RangeRule":
        if self.min is None and self.max is None:
            raise ValueError(f"rule {self.id}: range needs min or max")
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError(f"rule {self.id}: min greater than max")
        return self

    def referenced_fields(self) -> list[str]:
        """Return the checked field."""
        return [self.field]


class AllowedValuesRule(_RuleBase):
    """A field's value must be one of ``values`` (case-insensitive by default)."""

    type: Literal["allowed_values"]
    field: str
    values: list[str] = Field(min_length=1)
    case_sensitive: bool = False

    def referenced_fields(self) -> list[str]:
        """Return the checked field."""
        return [self.field]


class AgeRule(_RuleBase):
    """Age computed from a date field on ``reference_date`` must be in range."""

    type: Literal["age"]
    field: str
    reference_date: date
    min_years: int | None = Field(default=None, ge=0)
    max_years: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _has_bound(self) -> "AgeRule":
        if self.min_years is None and self.max_years is None:
            raise ValueError(f"rule {self.id}: age needs min_years or max_years")
        return self

    def referenced_fields(self) -> list[str]:
        """Return the date-of-birth field."""
        return [self.field]


class DateWindowRule(_RuleBase):
    """A date field must fall on or between ``not_before`` and ``not_after``."""

    type: Literal["date_window"]
    field: str
    not_before: date | None = None
    not_after: date | None = None

    @model_validator(mode="after")
    def _has_bound(self) -> "DateWindowRule":
        if self.not_before is None and self.not_after is None:
            raise ValueError(f"rule {self.id}: date_window needs a bound")
        return self

    def referenced_fields(self) -> list[str]:
        """Return the checked field."""
        return [self.field]


Rule = Annotated[
    MinPercentageRule | RangeRule | AllowedValuesRule | AgeRule | DateWindowRule,
    Field(discriminator="type"),
]
"""Any validation rule, selected by its ``type`` key."""
