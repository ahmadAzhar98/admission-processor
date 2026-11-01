"""Masking of personal data before it reaches logs or error messages.

Two layers are applied: known identifier formats (CNIC/B-form numbers,
Pakistani mobile numbers, e-mail addresses) are masked wherever they
appear in free text, and values stored under sensitive keys (names,
dates of birth, roll numbers, ...) are masked regardless of content.
"""

import re
from collections.abc import Mapping
from typing import Any

SENSITIVE_KEYS = frozenset(
    {
        "address",
        "applicant_name",
        "b_form_number",
        "cnic",
        "cnic_number",
        "date_of_birth",
        "email",
        "father_name",
        "full_name",
        "guardian_name",
        "name",
        "phone",
        "roll_number",
    }
)

_CNIC = re.compile(r"(?<!\d)\d{5}-?\d{7}-?(\d)(?!\d)")
_PHONE = re.compile(r"(?<!\d)(?:\+92|0092|0)3\d{2}-?\d{4}(\d{3})(?!\d)")
_EMAIL = re.compile(r"\b([A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")


def mask_text(text: str) -> str:
    """Mask identifier patterns inside free text.

    CNIC and B-form numbers keep only their check digit, phone numbers keep
    their last three digits, and e-mail addresses keep their first character
    and domain, which is enough to correlate log lines without exposing the
    person.
    """
    text = _CNIC.sub(r"*****-*******-\1", text)
    text = _PHONE.sub(r"03**-****\1", text)
    return _EMAIL.sub(r"\1***@\2", text)


def mask_value(value: Any) -> str:
    """Fully mask a sensitive value, keeping only a length hint."""
    rendered = str(value)
    if not rendered:
        return ""
    return f"{rendered[0]}***({len(rendered)})"


def mask_data(data: Any, sensitive_keys: frozenset[str] = SENSITIVE_KEYS) -> Any:
    """Return a copy of ``data`` with sensitive keys and patterns masked.

    Mappings and sequences are walked recursively; strings under other keys
    still go through :func:`mask_text`.
    """
    if isinstance(data, Mapping):
        return {
            key: mask_value(value)
            if str(key).lower() in sensitive_keys and value is not None
            else mask_data(value, sensitive_keys)
            for key, value in data.items()
        }
    if isinstance(data, list | tuple):
        return [mask_data(item, sensitive_keys) for item in data]
    if isinstance(data, str):
        return mask_text(data)
    return data
