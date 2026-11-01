import random
import re

from synthetic.identities import cnic_number, make_applicant

CNIC = re.compile(r"^\d{5}-\d{7}-\d$")
DISTRICTS = ("Lahore", "Kasur")


def test_cnic_format_and_gender_digit():
    rng = random.Random(1)
    for _ in range(200):
        male = cnic_number(rng, "male")
        female = cnic_number(rng, "female")
        assert CNIC.fullmatch(male) and CNIC.fullmatch(female)
        assert int(male[-1]) % 2 == 1
        assert int(female[-1]) % 2 == 0


def test_applicants_are_reproducible_from_seed():
    a = [make_applicant(random.Random(7), DISTRICTS) for _ in range(3)]
    assert a[0] == a[1] == a[2]
    assert make_applicant(random.Random(8), DISTRICTS) != a[0]


def test_applicant_is_plausible():
    applicant = make_applicant(random.Random(3), DISTRICTS)
    assert applicant.full_name.split()[-1] == applicant.father_name.split()[-1]
    assert 2004 <= applicant.date_of_birth.year <= 2008
    assert applicant.district in DISTRICTS
