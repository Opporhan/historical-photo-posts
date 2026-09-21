from __future__ import annotations

from io import BytesIO

import numpy as np
import pytest
from PIL import Image, ImageFilter

from histposts.models import Candidate


def make_photo(width: int = 1200, height: int = 900, seed: int = 0) -> Image.Image:
    """Synthetic 'photograph': smooth structure plus grain, with a wide tonal range."""
    rng = np.random.default_rng(seed)
    base = rng.random((height // 20, width // 20)).astype(np.float32)
    base = np.asarray(
        Image.fromarray((base * 255).astype(np.uint8)).resize((width, height), Image.BICUBIC),
        dtype=np.float32,
    )
    grain = rng.normal(0, 12, (height, width)).astype(np.float32)
    gray = np.clip(base + grain, 0, 255).astype(np.uint8)
    img = Image.fromarray(gray).convert("RGB")
    return img.filter(ImageFilter.GaussianBlur(0.6))


def jpeg_bytes(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


@pytest.fixture
def photo() -> Image.Image:
    return make_photo()


@pytest.fixture(autouse=True)
def _no_real_sleep(monkeypatch):
    monkeypatch.setattr("histposts.http._sleep", lambda s: None)


def candidate(**kw) -> Candidate:
    base = dict(
        source="Wikimedia Commons",
        url="https://upload.example/x.jpg",
        title="X.jpg",
        source_url="https://commons.example/File:X.jpg",
        license="Public domain",
    )
    base.update(kw)
    extra = base.pop("extra", {})
    return Candidate(**base, extra=extra)
