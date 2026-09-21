import cv2
import numpy as np
from PIL import Image

from histposts.photocheck import is_monochrome, looks_like_photo

from .conftest import make_photo


def bgr(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def test_photo_like_image_passes():
    ok, why = looks_like_photo(bgr(make_photo()), "Street in Paris")
    assert ok, why


def test_flat_logo_is_rejected():
    logo = np.full((800, 800, 3), 255, np.uint8)
    cv2.circle(logo, (400, 400), 200, (0, 0, 200), -1)
    ok, _ = looks_like_photo(logo, "Company")
    assert not ok


def test_low_resolution_is_rejected():
    ok, why = looks_like_photo(bgr(make_photo(150, 120)), "Tiny")
    assert not ok and "çözünürlük" in why


def test_non_photo_titles_are_rejected():
    for title in ("Map of Europe", "Menu of the day", "Coat of arms", "Colorized portrait"):
        ok, _ = looks_like_photo(bgr(make_photo()), title)
        assert not ok, title


def test_extreme_aspect_ratio_is_rejected():
    ok, _ = looks_like_photo(bgr(make_photo(2400, 500)), "Panorama")
    assert not ok


def test_grey_and_sepia_are_monochrome_but_colour_is_not():
    grey = np.asarray(make_photo().convert("L").convert("RGB"), dtype=np.float32)
    sepia = np.clip(grey * np.array([1.0, 0.88, 0.7]), 0, 255).astype(np.uint8)
    colour = np.asarray(make_photo(seed=1), dtype=np.float32) * np.array([1.0, 0.3, 1.0])
    colour[..., 1] = np.clip(colour[..., 1] + 90, 0, 255)
    assert is_monochrome(bgr(Image.fromarray(grey.astype(np.uint8))))
    assert is_monochrome(bgr(Image.fromarray(sepia)))
    assert not is_monochrome(bgr(Image.fromarray(np.clip(colour, 0, 255).astype(np.uint8))))
