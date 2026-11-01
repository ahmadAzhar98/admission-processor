import pytest
from pydantic import TypeAdapter, ValidationError

from common.tenant_config.rules import (
    AgeRule,
    MinPercentageRule,
    RangeRule,
    Rule,
    Severity,
)

adapter: TypeAdapter[Rule] = TypeAdapter(Rule)


def test_rules_are_selected_by_type():
    rule = adapter.validate_python(
        {
            "id": "fsc-min",
            "description": "FSc at least 60%",
            "document": "fsc_result",
            "type": "min_percentage",
            "obtained_field": "obtained_marks",
            "total_field": "total_marks",
            "min_percent": 60,
        }
    )
    assert isinstance(rule, MinPercentageRule)
    assert rule.severity is Severity.REVIEW
    assert rule.referenced_fields() == ["obtained_marks", "total_marks"]


def test_unknown_rule_type_is_rejected():
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {"id": "x1", "description": "", "document": "cnic", "type": "python_expr"}
        )


def test_range_needs_consistent_bounds():
    base = {"id": "r1", "description": "", "document": "entry_test", "type": "range"}
    with pytest.raises(ValidationError):
        RangeRule.model_validate({**base, "field": "score"})
    with pytest.raises(ValidationError):
        RangeRule.model_validate({**base, "field": "score", "min": 10, "max": 5})
    assert RangeRule.model_validate({**base, "field": "score", "min": 50}).max is None


def test_age_rule_needs_a_bound():
    with pytest.raises(ValidationError):
        AgeRule.model_validate(
            {
                "id": "age",
                "description": "",
                "document": "cnic",
                "type": "age",
                "field": "date_of_birth",
                "reference_date": "2026-09-01",
            }
        )
