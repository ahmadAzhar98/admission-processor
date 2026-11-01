"""Normalise printed values into canonical field values.

Documents print dates as ``05-03-2007``, ``05/03/2007`` or ``05 Mar 2007``
and amounts as ``5,000/-``. Extraction stores ISO dates, plain integers
and floats so validation rules and cross-checks compare like with like.
"""

import re
from datetime import date, datetime

from common.tenant_config.fields import FieldType

FieldValue = str | int | float

DATE_FORMATS = ("%d-%m-%Y", "%d/%m/%Y", "%d.%m.%Y", "%d %b %Y", "%d %B %Y", "%Y-%m-%d")
_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def normalise_string(raw: str) -> str:
    """Collapse whitespace and trim separators left over from the caption."""
    return re.sub(r"\s+", " ", raw).strip(" :-|\t")


def normalise_date(raw: str) -> str | None:
    """Return an ISO date for any known printed format, else ``None``."""
    text = normalise_string(raw).replace(",", "")
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _digits(raw: str) -> str:
    return raw.replace(",", "").replace("/-", "").replace(" ", "")


def normalise_integer(raw: str) -> int | None:
    """Parse ``5,000/-`` or ``Rs. 950`` as an integer; ``None`` if absent."""
    match = _NUMBER.search(_digits(raw))
    if match is None:
        return None
    return int(float(match.group()))


def normalise_number(raw: str) -> float | None:
    """Parse a decimal number such as ``132.5``; ``None`` if absent."""
    match = _NUMBER.search(_digits(raw))
    return float(match.group()) if match else None


def coerce(raw: str, field_type: FieldType) -> FieldValue | None:
    """Convert printed text to the canonical value for ``field_type``."""
    if field_type is FieldType.DATE:
        return normalise_date(raw)
    if field_type is FieldType.INTEGER:
        return normalise_integer(raw)
    if field_type is FieldType.NUMBER:
        return normalise_number(raw)
    text = normalise_string(raw)
    return text or None


def parse_iso_date(value: FieldValue | None) -> date | None:
    """Parse a canonical ISO date value back into a ``date``."""
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
