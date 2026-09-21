from __future__ import annotations

import warnings
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageStat

FONT_DIR = Path(__file__).parent / "assets" / "fonts"
FONT_FILES = {
    "title": "PlayfairDisplay-Variable.ttf",
    "body": "Lato-Regular.ttf",
    "label": "Lato-Bold.ttf",
}
TITLE_WEIGHT = 600
FORMATS = {"4x5": (1080, 1350), "9x16": (1080, 1920)}
DEFAULT_LABEL = "TARİHTEN KARELER"
# Below this share of the photo kept by a cover crop, the whole photo is shown instead (blurred fill).
MIN_COVER_KEEP = 0.72


class ComposeWarning(UserWarning):
    pass


@lru_cache(maxsize=32)
def font(kind: str, size: int) -> ImageFont.FreeTypeFont:
    fnt = ImageFont.truetype(str(FONT_DIR / FONT_FILES[kind]), size)
    if kind == "title":
        fnt.set_variation_by_axes([TITLE_WEIGHT])
    return fnt


@dataclass(frozen=True)
class Layout:
    """Safe-area settings in pixels. The tall (9:16) values keep clear of TikTok/Reels UI overlays."""

    pad: int = 75
    top: int = 66
    bottom: int = 90
    top_tall: int = 230
    bottom_tall: int = 330


def turkish_upper(text: str) -> str:
    return text.replace("i", "İ").replace("ı", "I").upper()


def _wrap(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines: list[str] = []
    cur = ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return [*lines, cur] if cur else lines


def _fit(draw, text, kind, start, minimum, max_lines, max_w, what):
    """Largest font size in [minimum, start] whose wrapped text fits max_lines; warns if none does."""
    for size in range(start, minimum - 1, -2):
        fnt = font(kind, size)
        lines = _wrap(draw, text, fnt, max_w)
        if len(lines) <= max_lines:
            return fnt, lines
    warnings.warn(
        f"{what} needs more than {max_lines} lines at {minimum}px; shorten it", ComposeWarning, stacklevel=3
    )
    return fnt, lines


def _tracked(draw, xy, text, fnt, fill, tracking, anchor_right=False):
    """Draw letter-spaced text; with anchor_right the text ends at x."""
    x, y = xy
    width = sum(draw.textlength(ch, font=fnt) + tracking for ch in text) - tracking
    if anchor_right:
        x -= width
    for ch in text:
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += draw.textlength(ch, font=fnt) + tracking


def _cover(photo: Image.Image, size: tuple[int, int], focus: tuple[float, float]) -> Image.Image:
    cw, ch = size
    scale = max(cw / photo.width, ch / photo.height)
    resized = photo.resize((round(photo.width * scale), round(photo.height * scale)), Image.LANCZOS)
    left = min(max(round(focus[0] * resized.width - cw / 2), 0), resized.width - cw)
    top = min(max(round(focus[1] * resized.height - ch / 2), 0), resized.height - ch)
    return resized.crop((left, top, left + cw, top + ch))


def _background(photo: Image.Image, size: tuple[int, int], focus: tuple[float, float]) -> Image.Image:
    """Blurred, darkened cover of the photo: fills the space a 'contain' placement leaves free."""
    return _cover(photo, size, focus).filter(ImageFilter.GaussianBlur(60)).point(lambda v: int(v * 0.38))


def _gradient(size: tuple[int, int], start: int, end: int, top_to_bottom_alpha=(0, 235)) -> Image.Image:
    """Vertical black-alpha ramp between rows start and end (alpha grows downwards)."""
    cw, ch = size
    a0, a1 = top_to_bottom_alpha
    mask = Image.new("L", (1, ch), 0)
    px = mask.load()
    for y in range(ch):
        if y >= end:
            px[0, y] = a1
        elif y > start:
            t = (y - start) / max(end - start, 1)
            px[0, y] = round(a0 + (a1 - a0) * t * t * (3 - 2 * t))  # smoothstep
        else:
            px[0, y] = a0
    return mask.resize((cw, ch))


def _feather(size: tuple[int, int], top: bool, bottom: bool, edge: int = 110) -> Image.Image:
    """Alpha mask that softens a pasted photo's top/bottom edges so it melts into the fill."""
    w, h = size
    mask = Image.new("L", (1, h), 255)
    px = mask.load()
    for y in range(min(edge, h // 2)):
        v = round(255 * y / edge)
        if top:
            px[0, y] = v
        if bottom:
            px[0, h - 1 - y] = v
    return mask.resize((w, h))


def compose(
    photo: Image.Image,
    title: str,
    info: str,
    year: str,
    size: tuple[int, int],
    layout: Layout | None = None,
    label: str = DEFAULT_LABEL,
    place: str = "",
    focus: tuple[float, float] = (0.5, 0.5),
    counter: str = "",
    credit: str = "",
) -> Image.Image:
    layout = layout or Layout()
    cw, ch = size
    tall = ch > 1500
    pad = layout.pad
    max_w = cw - 2 * pad
    photo = photo.convert("RGB")

    # --- text block, laid out from the bottom up so the photo gets whatever is left ---
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    title_fnt, title_lines = _fit(probe, turkish_upper(title), "title", 60, 36, 2, max_w, "title")
    body_fnt, body_lines = _fit(probe, info, "body", 31, 25, 6 if tall else 5, max_w, "info")
    title_lh, body_lh = round(title_fnt.size * 1.16), round(body_fnt.size * 1.5)
    bottom = ch - (layout.bottom_tall if tall else layout.bottom)
    body_top = bottom - body_lh * len(body_lines)
    title_top = body_top - 14 - title_lh * len(title_lines)
    rule_y = title_top - 30

    # --- photo: cover crop when little is lost, otherwise the whole photo over a blurred fill ---
    pa, ca = photo.width / photo.height, cw / ch
    scrim_start = rule_y - 260
    if min(pa / ca, ca / pa) >= MIN_COVER_KEEP:
        canvas = _cover(photo, size, focus)
    else:
        canvas = _background(photo, size, focus)
        area_h = max(rule_y - 40, 200)
        scale = min(cw / photo.width, area_h / photo.height)
        fitted = photo.resize((round(photo.width * scale), round(photo.height * scale)), Image.LANCZOS)
        y = max((area_h - fitted.height) // 2, 0) if tall or fitted.width < cw * 0.999 else 0
        if tall:  # keep the label clear of the photo edge
            y = max(y, layout.top_tall + 50)
        canvas.paste(
            fitted, ((cw - fitted.width) // 2, y), _feather(fitted.size, y > 0, y + fitted.height < ch)
        )
        scrim_start = min(scrim_start, y + fitted.height - 240)

    # --- scrims: bottom ramp for the text, a light one at the top for the label ---
    black = Image.new("RGB", size, (0, 0, 0))
    canvas = Image.composite(black, canvas, _gradient(size, scrim_start, ch - 20, (0, 235)))
    # The label sits on the photo: the brighter the top of the picture, the stronger its scrim.
    top_lum = ImageStat.Stat(canvas.crop((0, 0, cw, 260)).convert("L")).mean[0]
    top_alpha = round(70 + 120 * top_lum / 255)
    top_ramp = _gradient(size, 0, 260, (0, top_alpha)).point(lambda v: top_alpha - v)
    canvas = Image.composite(black, canvas, top_ramp)

    draw = ImageDraw.Draw(canvas)
    parts = [label, place, str(year) if counter and year else ""]
    label_text = turkish_upper(" · ".join(p for p in parts if p))
    top = layout.top_tall if tall else layout.top
    small = font("label", 22)
    _tracked(draw, (pad, top), label_text, small, (255, 255, 255), 3.2)
    corner = counter or (str(year) if year else "")
    if corner:
        _tracked(draw, (cw - pad, top), turkish_upper(corner), font("body", 24), (255, 255, 255), 1.5, True)

    draw.rectangle((pad, rule_y, pad + 46, rule_y + 3), fill=(255, 255, 255))
    y = title_top
    for line in title_lines:
        draw.text((pad, y), line, font=title_fnt, fill="white")
        y += title_lh
    y = body_top
    for line in body_lines:
        draw.text((pad, y), line, font=body_fnt, fill=(240, 240, 240))
        y += body_lh
    if credit:  # small source line under the text block
        size = 20
        while size > 14 and draw.textlength(credit, font=font("body", size)) > max_w:
            size -= 1
        draw.text((pad, bottom + 26), credit, font=font("body", size), fill=(170, 170, 170))
    return canvas
