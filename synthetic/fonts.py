"""Locate fonts for Latin and Urdu text on the host system.

Fonts are not vendored. The generator prefers fonts named in
``AP_SYNTHETIC_FONT`` / ``AP_SYNTHETIC_URDU_FONT``, then common system
fonts on Linux and macOS, and finally Pillow's built-in font (which has
no Urdu glyphs). Ground-truth labels do not depend on the font; rendered
pixels do, so image bytes are reproducible per machine, not across them.
"""

import os
from functools import lru_cache
from pathlib import Path

from PIL import ImageFont

Font = ImageFont.FreeTypeFont | ImageFont.ImageFont

LATIN_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
)
URDU_CANDIDATES = (
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoNaskhArabic-Regular.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/GeezaPro.ttc",
)


def _first_existing(env_var: str, candidates: tuple[str, ...]) -> Path | None:
    override = os.environ.get(env_var)
    for name in ((override,) if override else ()) + candidates:
        if name and Path(name).is_file():
            return Path(name)
    return None


@lru_cache(maxsize=64)
def load_font(size: int, urdu: bool = False) -> Font:
    """Return a font of ``size`` pixels suitable for Latin or Urdu text."""
    path = (
        _first_existing("AP_SYNTHETIC_URDU_FONT", URDU_CANDIDATES)
        if urdu
        else _first_existing("AP_SYNTHETIC_FONT", LATIN_CANDIDATES)
    )
    if path is None:
        return ImageFont.load_default(size)
    return ImageFont.truetype(str(path), size)


def is_urdu(text: str) -> bool:
    """Return whether ``text`` contains Arabic-script characters."""
    return any("؀" <= ch <= "ۿ" for ch in text)
