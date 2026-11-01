"""Fictional applicants with format-valid identity numbers."""

import random
from dataclasses import dataclass
from datetime import date, timedelta

MALE_NAMES = (
    "Ahmed",
    "Ali",
    "Bilal",
    "Faisal",
    "Hamza",
    "Haris",
    "Imran",
    "Junaid",
    "Kashif",
    "Usman",
    "Omar",
    "Saad",
    "Talha",
    "Zain",
    "Danish",
    "Fahad",
    "Arslan",
    "Shahzaib",
)
FEMALE_NAMES = (
    "Ayesha",
    "Fatima",
    "Hira",
    "Iqra",
    "Maham",
    "Mariam",
    "Noor",
    "Rabia",
    "Sana",
    "Zainab",
    "Amna",
    "Areeba",
    "Laiba",
    "Mahnoor",
    "Sidra",
    "Kinza",
    "Anam",
    "Esha",
)
FAMILY_NAMES = (
    "Khan",
    "Ahmed",
    "Malik",
    "Butt",
    "Chaudhry",
    "Qureshi",
    "Sheikh",
    "Raza",
    "Siddiqui",
    "Hussain",
    "Iqbal",
    "Javed",
    "Mirza",
    "Rana",
    "Bhatti",
    "Awan",
    "Abbasi",
    "Gill",
)
# Punjab division and district codes form the first digits of a CNIC.
PUNJAB_LOCALITY_PREFIXES = ("35201", "35202", "35102", "33100", "34101", "36302", "37405")


@dataclass(frozen=True)
class Applicant:
    """A fictional applicant and their identity details."""

    full_name: str
    father_name: str
    gender: str
    date_of_birth: date
    cnic_number: str
    district: str


def cnic_number(rng: random.Random, gender: str) -> str:
    """Return a CNIC-format number ``#####-#######-#``.

    The last digit is odd for male and even for female holders, as on
    real cards; the rest is random, so the number is valid in format only.
    """
    locality = rng.choice(PUNJAB_LOCALITY_PREFIXES)
    serial = f"{rng.randrange(10**7):07d}"
    last = rng.choice((1, 3, 5, 7, 9) if gender == "male" else (2, 4, 6, 8))
    return f"{locality}-{serial}-{last}"


def make_applicant(rng: random.Random, districts: tuple[str, ...]) -> Applicant:
    """Draw one fictional applicant aged roughly 16 to 22 in 2026."""
    gender = rng.choice(("male", "female"))
    given = rng.choice(MALE_NAMES if gender == "male" else FEMALE_NAMES)
    family = rng.choice(FAMILY_NAMES)
    father = f"{rng.choice(MALE_NAMES)} {family}"
    dob = date(2004, 1, 1) + timedelta(days=rng.randrange(6 * 365))
    return Applicant(
        full_name=f"{given} {family}",
        father_name=father,
        gender=gender,
        date_of_birth=dob,
        cnic_number=cnic_number(rng, gender),
        district=rng.choice(districts),
    )
