import random

import numpy as np
import pytest

from synthetic import documents
from synthetic.identities import make_applicant
from synthetic.render import SIZES, render

APPLICANT = make_applicant(random.Random(4), ("Lahore",))


@pytest.mark.parametrize("document_type", sorted(documents.BUILDERS))
def test_every_document_renders_at_layout_size(document_type):
    content = documents.build_document(document_type, APPLICANT, random.Random(1), "mixed")
    image = render(content, random.Random(1))
    assert image.size == SIZES[content.layout]
    pixels = np.asarray(image.convert("L"))
    assert pixels.min() < 100  # some ink was drawn
    assert pixels.mean() > 180  # mostly paper


def test_rendering_is_deterministic():
    content = documents.cnic(APPLICANT, random.Random(2), "en")
    a = render(content, random.Random(9))
    b = render(content, random.Random(9))
    assert a.tobytes() == b.tobytes()
