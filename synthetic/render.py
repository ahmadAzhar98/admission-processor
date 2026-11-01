"""Draw :class:`~synthetic.documents.DocumentContent` as a scanned page.

Three layouts approximate the families of real documents: ``card`` (ID
cards, scorecards: landscape with a photo box), ``table`` (marks sheets,
challans: ruled label/value grid) and ``certificate`` (domicile, B-form,
some board certificates: portrait with a double border and a seal).
"""

import random

from PIL import Image, ImageDraw

from synthetic.documents import DocumentContent
from synthetic.fonts import is_urdu, load_font

SIZES = {"card": (1400, 880), "table": (1240, 1600), "certificate": (1240, 1754)}
INK = (25, 25, 35)
RULE = (120, 120, 130)


def _text(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, size: int) -> None:
    urdu = is_urdu(text)
    font = load_font(size, urdu=urdu)
    try:
        draw.text(xy, text, font=font, fill=INK, direction="rtl" if urdu else None)
    except (KeyError, ValueError, OSError):
        # Basic layout (no libraqm) cannot set direction; draw unshaped.
        draw.text(xy, text, font=font, fill=INK)


def _paper(size: tuple[int, int], rng: random.Random) -> Image.Image:
    tint = rng.randint(238, 252)
    return Image.new("RGB", size, (tint, tint, max(0, tint - rng.randint(0, 10))))


def _header(draw: ImageDraw.ImageDraw, content: DocumentContent, width: int, top: int) -> int:
    _text(draw, (60, top), content.issuer, 30)
    _text(draw, (60, top + 50), content.title, 40)
    draw.line((60, top + 110, width - 60, top + 110), fill=RULE, width=3)
    return top + 140


def _render_card(content: DocumentContent, rng: random.Random) -> Image.Image:
    image = _paper(SIZES["card"], rng)
    draw = ImageDraw.Draw(image)
    width, height = image.size
    draw.rounded_rectangle((20, 20, width - 20, height - 20), radius=30, outline=RULE, width=4)
    y = _header(draw, content, width, 50)
    draw.rectangle((width - 330, y, width - 70, y + 320), outline=RULE, width=3)
    _text(draw, (width - 260, y + 140), "PHOTO", 28)
    for label_text, value in content.lines:
        _text(draw, (70, y), f"{label_text}:", 26)
        _text(draw, (420, y), value, 30)
        y += 70
    return image


def _render_table(content: DocumentContent, rng: random.Random) -> Image.Image:
    image = _paper(SIZES["table"], rng)
    draw = ImageDraw.Draw(image)
    width, _ = image.size
    y = _header(draw, content, width, 80)
    row_height = 80
    split = 520
    for label_text, value in content.lines:
        draw.rectangle((60, y, width - 60, y + row_height), outline=RULE, width=2)
        draw.line((split, y, split, y + row_height), fill=RULE, width=2)
        _text(draw, (80, y + 22), label_text, 28)
        _text(draw, (split + 20, y + 20), value, 32)
        y += row_height
    return image


def _render_certificate(content: DocumentContent, rng: random.Random) -> Image.Image:
    image = _paper(SIZES["certificate"], rng)
    draw = ImageDraw.Draw(image)
    width, height = image.size
    draw.rectangle((30, 30, width - 30, height - 30), outline=RULE, width=6)
    draw.rectangle((50, 50, width - 50, height - 50), outline=RULE, width=2)
    y = _header(draw, content, width, 110) + 40
    for label_text, value in content.lines:
        _text(draw, (100, y), f"{label_text}:", 30)
        _text(draw, (520, y), value, 34)
        y += 95
    cx, cy = width - 260, height - 300
    draw.ellipse((cx - 110, cy - 110, cx + 110, cy + 110), outline=(150, 40, 40), width=5)
    _text(draw, (cx - 55, cy - 18), "SEAL", 32)
    return image


RENDERERS = {"card": _render_card, "table": _render_table, "certificate": _render_certificate}


def render(content: DocumentContent, rng: random.Random) -> Image.Image:
    """Render ``content`` with its layout on lightly tinted paper."""
    return RENDERERS[content.layout](content, rng)
