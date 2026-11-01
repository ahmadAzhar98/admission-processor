"""Document content: ground-truth field values and the lines printed.

Builders return a :class:`DocumentContent` holding the canonical values
(ISO dates, integers) used as labels, and the label/value lines as they
appear on paper (local date formats, English or Urdu captions). The
renderer draws the lines; the evaluator compares against the fields.
"""

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta

from common.schemas.documents import DocumentType

from synthetic.identities import Applicant

FieldValue = str | int | float

LABELS: dict[str, tuple[str, str]] = {
    "cnic_number": ("Identity Number", "شناختی نمبر"),
    "b_form_number": ("Registration No.", "رجسٹریشن نمبر"),
    "full_name": ("Name", "نام"),
    "father_name": ("Father Name", "والد کا نام"),
    "date_of_birth": ("Date of Birth", "تاریخ پیدائش"),
    "gender": ("Gender", "جنس"),
    "district": ("District", "ضلع"),
    "certificate_number": ("Certificate No.", "سرٹیفکیٹ نمبر"),
    "issue_date": ("Date of Issue", "تاریخ اجراء"),
    "roll_number": ("Roll No.", "رول نمبر"),
    "board": ("Board", "بورڈ"),
    "passing_year": ("Session", "سیشن"),
    "group": ("Group", "گروپ"),
    "obtained_marks": ("Marks Obtained", "حاصل کردہ نمبر"),
    "total_marks": ("Total Marks", "کل نمبر"),
    "test_name": ("Test", "ٹیسٹ"),
    "score": ("Score", "اسکور"),
    "total_score": ("Out of", "کل اسکور"),
    "test_date": ("Test Date", "ٹیسٹ کی تاریخ"),
    "challan_number": ("Challan No.", "چالان نمبر"),
    "amount": ("Amount (Rs.)", "رقم (روپے)"),
    "paid_date": ("Date of Payment", "تاریخ ادائیگی"),
    "bank": ("Bank", "بینک"),
}
"""English and Urdu captions per field."""


@dataclass(frozen=True)
class DocumentContent:
    """Everything needed to render one document and grade its extraction."""

    document_type: DocumentType
    title: str
    issuer: str
    language: str
    layout: str
    fields: dict[str, FieldValue]
    lines: list[tuple[str, str]] = field(default_factory=list)

    @property
    def text(self) -> str:
        """The document as plain text, as a perfect OCR engine would read it."""
        body = "\n".join(f"{label}: {value}" for label, value in self.lines)
        return f"{self.issuer}\n{self.title}\n{body}"


def format_date(value: date, style: str) -> str:
    """Render a date the way local documents print it."""
    if style == "slash":
        return value.strftime("%d/%m/%Y")
    if style == "long":
        return value.strftime("%d %b %Y")
    return value.strftime("%d-%m-%Y")


def label(name: str, language: str, rng: random.Random) -> str:
    """Return the caption for ``name``; ``mixed`` picks a language per line."""
    en, ur = LABELS[name]
    if language == "mixed":
        return rng.choice((en, ur))
    return ur if language == "ur" else en


def _lines(
    values: dict[str, FieldValue], display: dict[str, str], language: str, rng: random.Random
) -> list[tuple[str, str]]:
    return [(label(k, language, rng), display.get(k, str(v))) for k, v in values.items()]


def cnic(applicant: Applicant, rng: random.Random, language: str) -> DocumentContent:
    """Build a national identity card."""
    style = rng.choice(("dash", "dot"))
    dob = applicant.date_of_birth
    fields: dict[str, FieldValue] = {
        "full_name": applicant.full_name,
        "father_name": applicant.father_name,
        "gender": "M" if applicant.gender == "male" else "F",
        "cnic_number": applicant.cnic_number,
        "date_of_birth": dob.isoformat(),
    }
    display = {"date_of_birth": dob.strftime("%d.%m.%Y" if style == "dot" else "%d-%m-%Y")}
    return DocumentContent(
        document_type=DocumentType.CNIC,
        title="National Identity Card" if language != "ur" else "قومی شناختی کارڈ",
        issuer="ISLAMIC REPUBLIC OF PAKISTAN",
        language=language,
        layout="card",
        fields=fields,
        lines=_lines(fields, display, language, rng),
    )


def b_form(applicant: Applicant, rng: random.Random, language: str) -> DocumentContent:
    """Build a child registration certificate (B-form)."""
    dob = applicant.date_of_birth
    fields: dict[str, FieldValue] = {
        "b_form_number": applicant.cnic_number,
        "full_name": applicant.full_name,
        "father_name": applicant.father_name,
        "date_of_birth": dob.isoformat(),
    }
    display = {"date_of_birth": format_date(dob, rng.choice(("dash", "slash")))}
    return DocumentContent(
        document_type=DocumentType.B_FORM,
        title="Child Registration Certificate" if language != "ur" else "ب فارم",
        issuer="National Database and Registration Authority (synthetic)",
        language=language,
        layout="certificate",
        fields=fields,
        lines=_lines(fields, display, language, rng),
    )


def domicile(applicant: Applicant, rng: random.Random, language: str) -> DocumentContent:
    """Build a district domicile certificate."""
    issued = date(2025, 1, 1) + timedelta(days=rng.randrange(500))
    fields: dict[str, FieldValue] = {
        "certificate_number": f"DOM-{rng.randrange(10**6):06d}",
        "full_name": applicant.full_name,
        "father_name": applicant.father_name,
        "district": applicant.district,
        "issue_date": issued.isoformat(),
    }
    display = {"issue_date": format_date(issued, rng.choice(("dash", "long")))}
    return DocumentContent(
        document_type=DocumentType.DOMICILE,
        title="Domicile Certificate" if language != "ur" else "ڈومیسائل سرٹیفکیٹ",
        issuer=f"Office of the District Officer, {applicant.district}",
        language=language,
        layout="certificate",
        fields=fields,
        lines=_lines(fields, display, language, rng),
    )


BOARDS = (
    "BISE Lahore",
    "BISE Gujranwala",
    "BISE Faisalabad",
    "BISE Rawalpindi",
    "BISE Multan",
    "BISE Sargodha",
    "Federal Board",
)
RESULT_LAYOUTS = ("table", "card", "certificate")
"""Board styles: a marks table, a compact result card, an ornate certificate."""

FSC_GROUPS = ("Pre-Engineering", "Pre-Medical", "ICS", "Humanities")


def _result(
    applicant: Applicant,
    rng: random.Random,
    language: str,
    document_type: DocumentType,
    year: int,
) -> DocumentContent:
    board = rng.choice(BOARDS)
    total = 1100 if year < 2025 else 1200
    # Skewed towards passing, with a tail below every tenant's minimum.
    obtained = min(total - 5, max(total // 3, int(rng.gauss(0.72, 0.13) * total)))
    fields: dict[str, FieldValue] = {
        "full_name": applicant.full_name,
        "father_name": applicant.father_name,
        "roll_number": f"{rng.randrange(100000, 999999)}",
        "board": board,
        "passing_year": year,
    }
    if document_type is DocumentType.FSC_RESULT:
        fields["group"] = rng.choice(FSC_GROUPS)
    fields["obtained_marks"] = obtained
    fields["total_marks"] = total
    is_fsc = document_type is DocumentType.FSC_RESULT
    title_en = "Higher Secondary School Certificate" if is_fsc else "Secondary School Certificate"
    title_ur = "انٹرمیڈیٹ نتیجہ کارڈ" if is_fsc else "میٹرک نتیجہ کارڈ"
    return DocumentContent(
        document_type=document_type,
        title=title_ur if language == "ur" else f"{title_en} Examination {year}",
        issuer=f"Board of Intermediate and Secondary Education ({board})",
        language=language,
        layout=rng.choice(RESULT_LAYOUTS),
        fields=fields,
        lines=_lines(fields, {}, language, rng),
    )


def matric_result(applicant: Applicant, rng: random.Random, language: str) -> DocumentContent:
    """Build a Matric (SSC) result card two years before FSc."""
    year = applicant.date_of_birth.year + 16
    return _result(applicant, rng, language, DocumentType.MATRIC_RESULT, year)


def fsc_result(applicant: Applicant, rng: random.Random, language: str) -> DocumentContent:
    """Build an FSc (HSSC) result card."""
    year = applicant.date_of_birth.year + 18
    return _result(applicant, rng, language, DocumentType.FSC_RESULT, year)


ENTRY_TESTS = (("University Admission Test", 100.0), ("Engineering Entry Test", 400.0))
BANKS = ("Bank A (synthetic)", "Bank B (synthetic)", "Bank C (synthetic)")


def entry_test(applicant: Applicant, rng: random.Random, language: str) -> DocumentContent:
    """Build an entry-test scorecard; the scale depends on the test."""
    name, out_of = rng.choice(ENTRY_TESTS)
    score = round(min(out_of, max(0.0, rng.gauss(0.55, 0.18) * out_of)), 1)
    taken = date(2026, 7, 1) + timedelta(days=rng.randrange(45))
    fields: dict[str, FieldValue] = {
        "test_name": name,
        "full_name": applicant.full_name,
        "cnic_number": applicant.cnic_number,
        "score": score,
        "total_score": out_of,
        "test_date": taken.isoformat(),
    }
    display = {"test_date": format_date(taken, "long")}
    return DocumentContent(
        document_type=DocumentType.ENTRY_TEST,
        title="Result Card" if language != "ur" else "نتیجہ کارڈ",
        issuer=f"{name} - Testing Service (synthetic)",
        language=language,
        layout="card",
        fields=fields,
        lines=_lines(fields, display, language, rng),
    )


def fee_challan(applicant: Applicant, rng: random.Random, language: str) -> DocumentContent:
    """Build a paid bank fee challan."""
    paid = date(2026, 6, 1) + timedelta(days=rng.randrange(100))
    fields: dict[str, FieldValue] = {
        "challan_number": f"{rng.randrange(10**9, 10**10)}",
        "full_name": applicant.full_name,
        "amount": rng.choice((2500, 3000, 5000, 5000, 6000)),
        "paid_date": paid.isoformat(),
        "bank": rng.choice(BANKS),
    }
    display = {"paid_date": format_date(paid, "slash"), "amount": f"{fields['amount']:,}/-"}
    return DocumentContent(
        document_type=DocumentType.FEE_CHALLAN,
        title="Fee Challan - Paid" if language != "ur" else "فیس چالان",
        issuer=str(fields["bank"]),
        language=language,
        layout="table",
        fields=fields,
        lines=_lines(fields, display, language, rng),
    )


Builder = Callable[[Applicant, random.Random, str], DocumentContent]

BUILDERS: dict[DocumentType, Builder] = {
    DocumentType.CNIC: cnic,
    DocumentType.B_FORM: b_form,
    DocumentType.MATRIC_RESULT: matric_result,
    DocumentType.FSC_RESULT: fsc_result,
    DocumentType.DOMICILE: domicile,
    DocumentType.ENTRY_TEST: entry_test,
    DocumentType.FEE_CHALLAN: fee_challan,
}
"""Builder for every classifiable document type."""


def build_document(
    document_type: DocumentType, applicant: Applicant, rng: random.Random, language: str
) -> DocumentContent:
    """Build content for ``document_type``.

    Raises:
        KeyError: For ``DocumentType.UNKNOWN``, which has no builder.
    """
    return BUILDERS[document_type](applicant, rng, language)
