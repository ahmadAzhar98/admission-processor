"""Evaluate tenant validation rules against an extraction result.

Each rule type has one small evaluator. Rules come from the tenant config,
so two tenants can judge the same document differently with no code
difference between them.
"""

import re
from collections.abc import Callable
from datetime import date

from common.schemas.documents import DocumentType
from common.schemas.results import ExtractionResult, FieldValue, RuleOutcome
from common.tenant_config.models import TenantConfig
from common.tenant_config.rules import (
    AgeRule,
    AllowedValuesRule,
    DateWindowRule,
    MinPercentageRule,
    RangeRule,
    Severity,
)

Evaluator = Callable[..., tuple[bool, str]]


def _number(value: FieldValue) -> float | None:
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _date(value: FieldValue) -> date | None:
    try:
        return date.fromisoformat(str(value))
    except ValueError:
        return None


def age_on(birth: date, reference: date) -> int:
    """Whole years between ``birth`` and ``reference``."""
    before_birthday = (reference.month, reference.day) < (birth.month, birth.day)
    return reference.year - birth.year - int(before_birthday)


def _min_percentage(rule: MinPercentageRule, result: ExtractionResult) -> tuple[bool, str]:
    obtained = _number(result.value(rule.obtained_field))
    total = _number(result.value(rule.total_field))
    if obtained is None or not total:
        return False, "marks could not be read"
    percent = obtained / total * 100
    return percent >= rule.min_percent, f"{percent:.1f}% against minimum {rule.min_percent:g}%"


def _range(rule: RangeRule, result: ExtractionResult) -> tuple[bool, str]:
    value = _number(result.value(rule.field))
    if value is None:
        return False, f"{rule.field} could not be read"
    low_ok = rule.min is None or value >= rule.min
    high_ok = rule.max is None or value <= rule.max
    return low_ok and high_ok, f"{rule.field} {value:g} against [{rule.min}, {rule.max}]"


def _allowed_values(rule: AllowedValuesRule, result: ExtractionResult) -> tuple[bool, str]:
    value = result.value(rule.field)
    if value is None:
        return False, f"{rule.field} could not be read"
    allowed = rule.values if rule.case_sensitive else [v.casefold() for v in rule.values]
    candidate = str(value).strip() if rule.case_sensitive else str(value).strip().casefold()
    ok = candidate in allowed
    return ok, f"{rule.field} {'is' if ok else 'is not'} an allowed value"


def _age(rule: AgeRule, result: ExtractionResult) -> tuple[bool, str]:
    birth = _date(result.value(rule.field))
    if birth is None:
        return False, f"{rule.field} could not be read"
    years = age_on(birth, rule.reference_date)
    ok = (rule.min_years is None or years >= rule.min_years) and (
        rule.max_years is None or years <= rule.max_years
    )
    return ok, f"age {years} on {rule.reference_date.isoformat()}"


def _date_window(rule: DateWindowRule, result: ExtractionResult) -> tuple[bool, str]:
    value = _date(result.value(rule.field))
    if value is None:
        return False, f"{rule.field} could not be read"
    ok = (rule.not_before is None or value >= rule.not_before) and (
        rule.not_after is None or value <= rule.not_after
    )
    return ok, f"{rule.field} {'inside' if ok else 'outside'} the allowed window"


EVALUATORS: dict[type, Evaluator] = {
    MinPercentageRule: _min_percentage,
    RangeRule: _range,
    AllowedValuesRule: _allowed_values,
    AgeRule: _age,
    DateWindowRule: _date_window,
}


def field_checks(config: TenantConfig, result: ExtractionResult) -> list[RuleOutcome]:
    """Check required fields are present and values match declared patterns."""
    requirement = config.requirement(result.document_type)
    if requirement is None:
        return []
    outcomes = []
    for spec in requirement.fields:
        value = result.value(spec.name)
        if value is None:
            if spec.required:
                outcomes.append(
                    RuleOutcome(
                        rule_id=f"required:{spec.name}",
                        passed=False,
                        severity=Severity.REVIEW,
                        message=f"{spec.name} is missing",
                    )
                )
            continue
        if spec.pattern and not re.fullmatch(spec.pattern, str(value)):
            outcomes.append(
                RuleOutcome(
                    rule_id=f"pattern:{spec.name}",
                    passed=False,
                    severity=Severity.REVIEW,
                    message=f"{spec.name} does not match the expected format",
                )
            )
    return outcomes


def applicable_types(config: TenantConfig, document_type: DocumentType) -> set[DocumentType]:
    """Document types whose rules apply to ``document_type``."""
    types = {document_type}
    types.update(req.type for req in config.documents if document_type in req.alternatives)
    return types


def evaluate(config: TenantConfig, result: ExtractionResult) -> list[RuleOutcome]:
    """Run field checks and every tenant rule that applies to this document type.

    A rule declared for a document's primary type also applies to its
    alternatives (e.g. an age rule on the CNIC applies to a B-form).
    """
    applicable = applicable_types(config, result.document_type)
    outcomes = field_checks(config, result)
    for rule in config.rules:
        if rule.document not in applicable:
            continue
        if rule.document != result.document_type and any(
            result.get(name) is None for name in rule.referenced_fields()
        ):
            continue  # an alternative document without this field: not applicable
        passed, message = EVALUATORS[type(rule)](rule, result)
        outcomes.append(
            RuleOutcome(rule_id=rule.id, passed=passed, severity=rule.severity, message=message)
        )
    return outcomes
