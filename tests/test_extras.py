import subprocess
from pathlib import Path

import pytest
from PIL import Image

from histposts import licensing, video
from histposts.compose import FORMATS, compose
from histposts.pipeline import PostSpec, default_alt, series_counters
from histposts.review import build_review

from .conftest import make_photo


@pytest.mark.parametrize(
    ("year", "died", "expected"),
    [
        (1913, 1927, "yes"),
        (1936, 1965, "no"),  # US-government work, but the author's term runs on abroad
        (1890, "anonymous", "yes"),
        (1912, "anonymous", "unknown"),
        (1990, "anonymous", "unknown"),
        (1900, None, "unknown"),
    ],
)
def test_worldwide(year, died, expected):
    assert licensing.worldwide(year, died, now=2026)[0] == expected


def test_series_counters_only_for_series_members():
    specs = [
        PostSpec("a", "a.jpg", "A", "i", series="s"),
        PostSpec("b", "b.jpg", "B", "i"),
        PostSpec("c", "c.jpg", "C", "i", series="s"),
    ]
    assert series_counters(specs) == {"a": "01 / 02", "c": "02 / 02"}


def test_default_alt_mentions_title_place_year():
    alt = default_alt(PostSpec("a", "a.jpg", "Başlık", "i", year="1900", place="Paris"))
    assert "Başlık" in alt and "Paris" in alt and "1900" in alt


def test_counter_and_bright_photo_render():
    bright = Image.new("RGB", (1600, 1200), (245, 245, 245))
    out = compose(bright, "Başlık", "Metin.", "1900", FORMATS["4x5"], place="Paris", counter="03 / 10")
    assert out.size == FORMATS["4x5"]


def test_review_page_lists_posts(tmp_path: Path):
    folder = tmp_path / "01-demo"
    folder.mkdir()
    (folder / "license_evidence.json").write_text(
        '{"level": "safe", "reasons": ["ok"], "license": "Public domain", "source_url": "https://x"}'
    )
    (folder / "caption.txt").write_text("caption <b>")
    page = build_review(tmp_path).read_text(encoding="utf-8")
    assert "01-demo" in page and "caption &lt;b&gt;" in page


def test_video_reports_missing_ffmpeg(tmp_path, monkeypatch):
    monkeypatch.setattr(video.shutil, "which", lambda _: None)
    with pytest.raises(video.VideoError, match="ffmpeg"):
        video.make_video(tmp_path / "a.jpg", tmp_path / "a.mp4")


def test_video_is_written_when_ffmpeg_exists(tmp_path):
    if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0:
        pytest.skip("ffmpeg not installed")
    img = tmp_path / "a.jpg"
    make_photo(1080, 1920).save(img)
    out = video.make_video(img, tmp_path / "a.mp4", seconds=1, fps=10)
    assert out.stat().st_size > 1000
