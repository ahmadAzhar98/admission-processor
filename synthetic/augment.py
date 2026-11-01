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


def _perspective_coeffs(
    src: list[tuple[float, float]], dst: list[tuple[float, float]]
) -> list[float]:
    """Solve for PIL perspective coefficients mapping ``dst`` points to ``src``."""
    rows = []
    for (x, y), (u, v) in zip(dst, src, strict=True):
        rows.append([x, y, 1, 0, 0, 0, -u * x, -u * y])
        rows.append([0, 0, 0, x, y, 1, -v * x, -v * y])
    a = np.array(rows, dtype=np.float64)
    b = np.array(src, dtype=np.float64).reshape(8)
    return [float(c) for c in np.linalg.solve(a, b)]


def phone_photo(image: Image.Image, rng: random.Random) -> tuple[Image.Image, Params]:
    """Imitate a phone photo of a page lying on a desk.

    The page is shrunk onto a desk-coloured background, warped by a random
    perspective, lit unevenly from one side, and slightly softened.
    """
    width, height = image.size
    scale = rng.uniform(0.78, 0.92)
    jitter = 0.06
    w, h = width * scale, height * scale
    x0, y0 = (width - w) / 2, (height - h) / 2
    corners = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h), (x0, y0 + h)]
    warped = [
        (x + rng.uniform(-jitter, jitter) * width, y + rng.uniform(-jitter, jitter) * height)
        for x, y in corners
    ]
    src = [(0.0, 0.0), (float(width), 0.0), (float(width), float(height)), (0.0, float(height))]
    desk = (rng.randint(90, 160), rng.randint(70, 120), rng.randint(40, 90))
    photo = Image.new("RGB", (width, height), desk)
    page = image.convert("RGB").transform(
        (width, height),
        Image.Transform.PERSPECTIVE,
        _perspective_coeffs(src, warped),
        resample=Image.Resampling.BICUBIC,
    )
    mask = Image.new("L", (width, height), 255).transform(
        (width, height), Image.Transform.PERSPECTIVE, _perspective_coeffs(src, warped)
    )
    photo.paste(page, (0, 0), mask)
    strength = rng.uniform(0.25, 0.55)
    gradient = np.linspace(1.0 - strength, 1.0, width, dtype=np.float32)
    if rng.random() < 0.5:
        gradient = gradient[::-1]
    lit = np.asarray(photo, dtype=np.float32) * gradient[None, :, None]
    photo = Image.fromarray(np.clip(lit, 0, 255).astype(np.uint8))
    photo = photo.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 1.0)))
    return photo, {"scale": round(scale, 3), "shadow": round(strength, 3)}


AUGMENTATIONS: dict[str, Augmentation] = {
    "skew": skew,
    "blur": blur,
    "noise": noise,
    "low_contrast": low_contrast,
    "jpeg": jpeg,
    "phone_photo": phone_photo,
}

PROFILES = ("clean", "mild", "phone", "severe")


def choose_augmentations(rng: random.Random) -> tuple[str, list[str]]:
    """Draw a degradation profile and its augmentation sequence.

    Roughly 30% clean scans, 45% mildly degraded, 15% phone photos and 10%
    severely degraded uploads, which is a plausible mix for a deadline-night
    upload burst.
    """
    roll = rng.random()
    if roll < 0.30:
        return "clean", []
    if roll < 0.75:
        options = ["skew", "noise", "jpeg", "low_contrast"]
        return "mild", rng.sample(options, k=rng.randint(1, 2))
    if roll < 0.90:
        return "phone", ["phone_photo", "jpeg"]
    return "severe", ["blur", rng.choice(["skew", "low_contrast", "noise"])]


def is_severe(applied: list[Params]) -> bool:
    """Heuristically decide whether the degradation should trigger a re-upload.

    Used as the expected label when evaluating the quality check; the cut
    points match the default tenant quality thresholds, not ground truth
    about human readability.
    """
    for params in applied:
        name = params["name"]
        if name == "blur" and params["radius"] >= 2.5:
            return True
        if name == "skew" and abs(params["angle"]) >= 7:
            return True
        if name == "low_contrast" and params["factor"] <= 0.35:
            return True
        if name == "noise" and params["sigma"] >= 25:
            return True
    return False


def apply(
    image: Image.Image, rng: random.Random, names: list[str]
) -> tuple[Image.Image, list[Params]]:
    """Apply augmentations ``names`` in order, returning recorded parameters."""
    applied: list[Params] = []
    for name in names:
        image, params = AUGMENTATIONS[name](image, rng)
        applied.append({"name": name, **params})
    return image, applied
