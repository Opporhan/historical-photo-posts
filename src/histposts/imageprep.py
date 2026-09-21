"""Pre-processing: trim scan borders before enhancement."""

from __future__ import annotations

import numpy as np
from PIL import Image

MAX_TRIM = 0.06  # never remove more than 6% per side
MIN_TRIM = 0.004


def _uniform(line: np.ndarray) -> bool:
    return line.std() < 10 and (line.mean() < 25 or line.mean() > 240)


def _trim(gray: np.ndarray, axis_len: int, get_line) -> int:
    limit = int(axis_len * MAX_TRIM)
    n = 0
    while n < limit and _uniform(get_line(n)):
        n += 1
    return n if n >= max(2, int(axis_len * MIN_TRIM)) else 0


def autocrop_borders(img: Image.Image) -> Image.Image:
    """Remove near-uniform black/white bands (scanner or glass-plate borders) from the image edges."""
    gray = np.asarray(img.convert("L"), dtype=np.float32)
    h, w = gray.shape
    top = _trim(gray, h, lambda i: gray[i, :])
    bottom = _trim(gray, h, lambda i: gray[h - 1 - i, :])
    left = _trim(gray, w, lambda i: gray[:, i])
    right = _trim(gray, w, lambda i: gray[:, w - 1 - i])
    if not (top or bottom or left or right):
        return img
    return img.crop((left, top, w - right, h - bottom))


def crop_fractions(img: Image.Image, box: tuple[float, float, float, float]) -> Image.Image:
    """Crop by (left, top, right, bottom) fractions of the image size."""
    w, h = img.size
    return img.crop((int(box[0] * w), int(box[1] * h), int(box[2] * w), int(box[3] * h)))
