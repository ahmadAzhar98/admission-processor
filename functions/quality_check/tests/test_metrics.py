import io
import random

import pytest
from common.errors import InvalidRequestError
from common.schemas.documents import DocumentType
from PIL import Image, ImageEnhance, ImageFilter

from functions.quality_check import metrics
from synthetic import documents
from synthetic.identities import make_applicant
from synthetic.render import render

APPLICANT = make_applicant(random.Random(1), ("Lahore",))


def _page(document_type="fsc_result"):
    content = documents.build_document(
        DocumentType(document_type), APPLICANT, random.Random(2), "en"
    )
    return render(content, random.Random(1))


def _gray(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return metrics.normalise(metrics.decode_gray(buffer.getvalue()))


def test_undecodable_bytes_are_rejected():
    with pytest.raises(InvalidRequestError):
        metrics.decode_gray(b"not an image")


def test_normalise_scales_longer_side():
    assert max(_gray(_page()).shape) == metrics.NORMALISED_SIDE


@pytest.mark.parametrize("document_type", ["cnic", "fsc_result", "fee_challan"])
def test_blur_separates_sharp_from_blurred(document_type):
    page = _page(document_type)
    sharp = metrics.blur_score(_gray(page))
    blurred = metrics.blur_score(_gray(page.filter(ImageFilter.GaussianBlur(3))))
    assert sharp > 150 > 60 > blurred


def test_faded_page_has_low_contrast_but_is_not_blurry():
    faded = ImageEnhance.Contrast(_page()).enhance(0.2)
    gray = _gray(faded)
    assert metrics.contrast(gray) < 40 < metrics.contrast(_gray(_page()))
    assert metrics.blur_score(gray) > 150


@pytest.mark.parametrize("angle", [-8.0, -3.0, 0.0, 4.5])
def test_skew_estimate_matches_rotation(angle):
    page = _page()
    rotated = page.rotate(angle, resample=Image.Resampling.BICUBIC, fillcolor=(245, 245, 240))
    assert abs(abs(metrics.skew_degrees(_gray(rotated))) - abs(angle)) < 0.5


def test_blank_page_has_no_skew():
    blank = Image.new("RGB", (800, 600), (250, 250, 250))
    assert metrics.skew_degrees(_gray(blank)) == 0.0
