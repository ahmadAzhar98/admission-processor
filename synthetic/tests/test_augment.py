import random

import numpy as np
import pytest
from PIL import Image, ImageDraw

from synthetic import augment


def _page():
    image = Image.new("RGB", (400, 300), (245, 245, 240))
    draw = ImageDraw.Draw(image)
    for y in range(40, 260, 30):
        draw.rectangle((40, y, 360, y + 8), fill=(20, 20, 20))
    return image


def _sharpness(image):
    gray = np.asarray(image.convert("L"), dtype=np.float32)
    return float(np.var(np.diff(gray, axis=0)))


@pytest.mark.parametrize("name", sorted(augment.AUGMENTATIONS))
def test_augmentations_keep_size_and_record_params(name):
    out, params = augment.AUGMENTATIONS[name](_page(), random.Random(1))
    assert out.size == (400, 300)
    assert params


def test_blur_reduces_sharpness():
    out, _ = augment.blur(_page(), random.Random(2))
    assert _sharpness(out) < _sharpness(_page())


def test_low_contrast_narrows_range():
    out, _ = augment.low_contrast(_page(), random.Random(3))
    gray = np.asarray(out.convert("L"))
    assert int(gray.max()) - int(gray.min()) < 200


def test_apply_is_reproducible():
    names = ["skew", "noise", "jpeg"]
    a, pa = augment.apply(_page(), random.Random(5), names)
    b, pb = augment.apply(_page(), random.Random(5), names)
    assert pa == pb
    assert [p["name"] for p in pa] == names
    assert a.tobytes() == b.tobytes()


def test_phone_photo_shows_desk_at_edges():
    out, params = augment.phone_photo(_page(), random.Random(7))
    corner = out.getpixel((2, 2))
    assert corner != (245, 245, 240)
    assert 0.78 <= params["scale"] <= 0.92


def test_profiles_cover_all_kinds():
    rng = random.Random(0)
    seen = {augment.choose_augmentations(rng)[0] for _ in range(400)}
    assert seen == set(augment.PROFILES)


@pytest.mark.parametrize(
    ("applied", "severe"),
    [
        ([], False),
        ([{"name": "blur", "radius": 3.0}], True),
        ([{"name": "blur", "radius": 1.0}], False),
        ([{"name": "skew", "angle": -8.0}], True),
        ([{"name": "jpeg", "quality": 20}], False),
    ],
)
def test_is_severe(applied, severe):
    assert augment.is_severe(applied) is severe
