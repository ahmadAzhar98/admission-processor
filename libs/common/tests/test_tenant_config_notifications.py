import pytest
from pydantic import ValidationError

from common.tenant_config.notifications import (
    Language,
    NotificationEvent,
    NotificationSettings,
    NotificationTemplate,
)


def _template():
    return NotificationTemplate(
        en="{university}: application {application_id} approved.",
        ur="{university}: درخواست {application_id} منظور ہو گئی ہے۔",
    )


def test_render_in_both_languages():
    t = _template()
    values = {"university": "University A", "application_id": "app-1"}
    assert t.render(Language.EN, values) == "University A: application app-1 approved."
    assert "منظور" in t.render(Language.UR, values)


def test_missing_value_renders_empty():
    assert _template().render(Language.EN, {}) == ": application  approved."


def test_pii_placeholders_are_rejected():
    with pytest.raises(ValidationError):
        NotificationTemplate(en="Dear {applicant_name}", ur="محترم")


def test_every_event_needs_a_template():
    with pytest.raises(ValidationError):
        NotificationSettings(templates={NotificationEvent.APPROVED: _template()})
    full = NotificationSettings(templates={e: _template() for e in NotificationEvent})
    assert full.default_language is Language.EN
