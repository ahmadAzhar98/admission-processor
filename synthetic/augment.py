"""Image degradations that imitate real uploads, with recorded parameters.

Each augmentation takes an image and a seeded RNG and returns the new
image plus the parameters it drew, so every output image comes with an
exact description of how it was degraded.
"""

import io
import random
from collections.abc import Callable
from typing import Any

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

Params = dict[str, Any]
Augmentation = Callable[[Image.Image, random.Random], tuple[Image.Image, Params]]


def _fill(image: Image.Image) -> tuple[int, ...]:
    corner = image.convert("RGB").getpixel((0, 0))
    return tuple(corner) if isinstance(corner, tuple) else (int(corner or 0),) * 3


def skew(image: Image.Image, rng: random.Random) -> tuple[Image.Image, Params]:
    """Rotate by 1-10 degrees either way, as from a crooked scan."""
    angle = round(rng.uniform(1, 10) * rng.choice((-1, 1)), 2)
    rotated = image.rotate(angle, resample=Image.Resampling.BICUBIC, fillcolor=_fill(image))
    return rotated, {"angle": angle}


def blur(image: Image.Image, rng: random.Random) -> tuple[Image.Image, Params]:
    """Gaussian blur with radius 0.8-4, as from an out-of-focus camera."""
    radius = round(rng.uniform(0.8, 4.0), 2)
    return image.filter(ImageFilter.GaussianBlur(radius)), {"radius": radius}


def noise(image: Image.Image, rng: random.Random) -> tuple[Image.Image, Params]:
    """Additive Gaussian sensor noise with sigma 5-30."""
    sigma = round(rng.uniform(5, 30), 2)
    gen = np.random.default_rng(rng.randrange(2**32))
    pixels = np.asarray(image, dtype=np.float32)
    noisy = np.clip(pixels + gen.normal(0, sigma, pixels.shape), 0, 255).astype(np.uint8)
    return Image.fromarray(noisy), {"sigma": sigma}


def low_contrast(image: Image.Image, rng: random.Random) -> tuple[Image.Image, Params]:
    """Flatten contrast (factor 0.25-0.7) and shift brightness, as a faded copy."""
    factor = round(rng.uniform(0.25, 0.7), 2)
    brightness = round(rng.uniform(0.85, 1.15), 2)
    faded = ImageEnhance.Contrast(image).enhance(factor)
    return ImageEnhance.Brightness(faded).enhance(brightness), {
        "factor": factor,
        "brightness": brightness,
    }


def jpeg(image: Image.Image, rng: random.Random) -> tuple[Image.Image, Params]:
    """Re-encode as JPEG with quality 20-70, as messaging apps do."""
    quality = rng.randint(20, 70)
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=quality)
    buffer.seek(0)
    return Image.open(buffer).convert("RGB"), {"quality": quality}


AUGMENTATIONS: dict[str, Augmentation] = {
    "skew": skew,
    "blur": blur,
    "noise": noise,
    "low_contrast": low_contrast,
    "jpeg": jpeg,
}


def apply(
    image: Image.Image, rng: random.Random, names: list[str]
) -> tuple[Image.Image, list[Params]]:
    """Apply augmentations ``names`` in order, returning recorded parameters."""
    applied: list[Params] = []
    for name in names:
        image, params = AUGMENTATIONS[name](image, rng)
        applied.append({"name": name, **params})
    return image, applied
