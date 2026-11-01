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
