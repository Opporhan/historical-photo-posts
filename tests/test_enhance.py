import pytest
from PIL import Image

from histposts import enhance as enh

from .conftest import make_photo


def test_gentle_upscales_small_images():
    out = enh.enhance(make_photo(800, 600), "gentle")
    assert out.method == "gentle"
    assert max(out.image.size) >= 2000


def test_gentle_limits_huge_images():
    out = enh.enhance(Image.new("RGB", (4000, 3000), (120, 120, 120)), "gentle")
    assert max(out.image.size) <= enh.MAX_LONG_SIDE


def test_unknown_mode():
    with pytest.raises(ValueError):
        enh.enhance(make_photo(), "magic")


def test_esrgan_mode_requires_binary(monkeypatch):
    monkeypatch.setattr(enh, "find_binary", lambda: None)
    with pytest.raises(enh.EnhanceError, match="install"):
        enh.enhance(make_photo(800, 600), "esrgan")


def test_auto_falls_back_to_gentle_with_note(monkeypatch):
    monkeypatch.setattr(enh, "find_binary", lambda: None)
    out = enh.enhance(make_photo(800, 600), "auto")
    assert out.method == "gentle" and "not installed" in out.note


def test_auto_does_not_use_esrgan_for_large_sources(monkeypatch):
    def boom():
        raise AssertionError("binary lookup must not happen for large sources")

    monkeypatch.setattr(enh, "find_binary", boom)
    assert enh.enhance(make_photo(1800, 1200), "auto").method == "gentle"


def test_auto_survives_a_failing_binary(monkeypatch, tmp_path):
    fake = tmp_path / "realesrgan-ncnn-vulkan"
    fake.write_text("#!/bin/sh\nexit 3\n")
    fake.chmod(0o755)
    monkeypatch.setattr(enh, "find_binary", lambda: fake)
    out = enh.enhance(make_photo(800, 600), "auto")
    assert out.method == "gentle" and "failed" in out.note
    with pytest.raises(enh.EnhanceError):
        enh.enhance(make_photo(800, 600), "esrgan")


def test_before_after_is_side_by_side():
    sheet = enh.before_after(make_photo(800, 600), make_photo(1600, 1200), height=300)
    assert sheet.height == 300 + 56 and sheet.width > 2 * 300
