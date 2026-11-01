from datetime import date
from pathlib import Path

import pytest
from common.schemas.results import ExtractedField, ExtractionResult
from common.tenant_config.loader import TenantRegistry

from functions.validate.engine import age_on, evaluate

REGISTRY = TenantRegistry(Path(__file__).resolve().parents[3] / "tenants")


def _result(tenant_id, document_type, **values):
    return ExtractionResult(
        tenant_id=tenant_id,
        document_id="d1",
        document_type=document_type,
        fields=[ExtractedField(name=k, value=v, confidence=0.95) for k, v in values.items()],
    )


FSC_65 = {
    "full_name": "Ali Khan",
    "father_name": "Omar Khan",
    "roll_number": "123456",
    "board": "BISE Lahore",
    "passing_year": 2025,
    "obtained_marks": 715,
    "total_marks": 1100,
}


def _by_id(outcomes):
    return {o.rule_id: o for o in outcomes}


def test_same_marks_pass_one_tenant_and_fail_another():
    a = _by_id(evaluate(REGISTRY.get("uni-a"), _result("uni-a", "fsc_result", **FSC_65)))
    b = _by_id(evaluate(REGISTRY.get("uni-b"), _result("uni-b", "fsc_result", **FSC_65)))
    c = _by_id(evaluate(REGISTRY.get("uni-c"), _result("uni-c", "fsc_result", **FSC_65)))
    assert a["fsc-min-70"].passed is False and a["fsc-min-70"].severity == "reject"
    assert b["fsc-min-60"].passed is True
    assert c["fsc-min-45"].passed is True
    assert "65.0%" in a["fsc-min-70"].message


def test_allowed_values_is_case_insensitive_and_hides_value():
    config = REGISTRY.get("uni-b")
    ok = _by_id(evaluate(config, _result("uni-b", "domicile", district="lahore")))
    bad = _by_id(evaluate(config, _result("uni-b", "domicile", district="Karachi South")))
    assert ok["punjab-domicile"].passed
    assert not bad["punjab-domicile"].passed
    assert "Karachi" not in bad["punjab-domicile"].message


def test_missing_and_malformed_fields_are_reported():
    config = REGISTRY.get("uni-a")
    outcomes = _by_id(
        evaluate(config, _result("uni-a", "cnic", cnic_number="3520-12", full_name="A B"))
    )
    assert not outcomes["pattern:cnic_number"].passed
    assert not outcomes["required:date_of_birth"].passed
    assert not outcomes["age-limit"].passed  # cannot be evaluated without a date


def test_cnic_rule_applies_to_b_form_alternative():
    config = REGISTRY.get("uni-c")
    young = _result(
        "uni-c",
        "b_form",
        b_form_number="35202-1234567-2",
        full_name="A B",
        father_name="C B",
        date_of_birth="2012-01-01",
    )
    assert not _by_id(evaluate(config, young))["minimum-age"].passed


def test_date_window_and_range():
    config = REGISTRY.get("uni-a")
    outcomes = _by_id(
        evaluate(
            config,
            _result(
                "uni-a", "fee_challan", challan_number="1", amount=4000, paid_date="2026-09-01"
            ),
        )
    )
    assert not outcomes["fee-paid-in-window"].passed
    assert not outcomes["fee-amount"].passed


@pytest.mark.parametrize(
    ("birth", "expected"),
    [(date(2002, 9, 1), 24), (date(2002, 9, 2), 23), (date(2008, 2, 29), 18)],
)
def test_age_on(birth, expected):
    assert age_on(birth, date(2026, 9, 1)) == expected
