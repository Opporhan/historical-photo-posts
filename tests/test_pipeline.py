import json

import pytest
import responses
from PIL import Image

from histposts import pipeline
from histposts.pipeline import PostSpec, SpecError, build_post, load_specs
from histposts.sources import wikimedia

from .conftest import jpeg_bytes, make_photo
from .test_wikimedia import page


def mock_commons(license_name="Public domain", date="1900"):
    responses.add(
        responses.GET,
        wikimedia.API,
        json={
            "query": {
                "pages": {
                    "1": page(
                        "photo.jpg",
                        license_name,
                        DateTimeOriginal=date,
                        LicenseUrl="https://pd",
                        Artist="Anon",
                    )
                }
            }
        },
    )
    responses.add(
        responses.GET,
        "https://upload.test/t/photo.jpg",
        body=jpeg_bytes(make_photo(1800, 1300)),
        content_type="image/jpeg",
    )


SPEC = PostSpec(
    name="demo",
    file="photo.jpg",
    title="Örnek Başlık",
    info="Kısa bir açıklama.",
    year="1900",
    tags=["#tarih", "demo"],
)


@responses.activate
def test_build_post_writes_everything(tmp_path):
    mock_commons()
    result = build_post(SPEC, tmp_path / "01-demo", mode="gentle", allow_unverified=True)
    assert result.level == "safe" and not result.skipped
    folder = tmp_path / "01-demo"
    assert Image.open(folder / "instagram_4x5.jpg").size == (1080, 1350)
    assert Image.open(folder / "tiktok_9x16.jpg").size == (1080, 1920)
    assert (folder / "before_after.jpg").exists()
    caption = (folder / "caption.txt").read_text(encoding="utf-8")
    assert "Örnek Başlık" in caption and pipeline.DISCLOSURE in caption and "#demo" in caption
    evidence = json.loads((folder / "license_evidence.json").read_text(encoding="utf-8"))
    assert evidence["level"] == "safe" and evidence["license_url"] == "https://pd"


@responses.activate
def test_strict_skips_review_posts(tmp_path):
    mock_commons(date="1950")
    result = build_post(SPEC, tmp_path / "x", mode="gentle", strict=True)
    assert result.skipped and result.level == "review" and not (tmp_path / "x").exists()


@responses.activate
def test_blocked_licenses_are_never_built(tmp_path):
    mock_commons(license_name="CC BY-SA 4.0")
    result = build_post(SPEC, tmp_path / "x", mode="gentle")
    assert result.skipped and result.level == "blocked"


@responses.activate
def test_download_cache_is_used(tmp_path):
    mock_commons()
    cache = tmp_path / "cache"
    build_post(SPEC, tmp_path / "a", mode="gentle", cache_dir=cache, allow_unverified=True)
    build_post(SPEC, tmp_path / "b", mode="gentle", cache_dir=cache, allow_unverified=True)
    image_calls = [c for c in responses.calls if c.request.url.startswith("https://upload.test/")]
    assert len(image_calls) == 1


def write(tmp_path, text):
    path = tmp_path / "posts.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_specs_ok(tmp_path):
    specs = load_specs(
        write(tmp_path, "posts:\n- {name: a, file: a.jpg, title: T, info: I, crop: [0, 0, 1, 0.9]}\n")
    )
    assert specs[0].crop == (0, 0, 1, 0.9) and specs[0].year == ""


@pytest.mark.parametrize(
    "text",
    [
        "posts: []",
        "{}",
        "posts:\n- {name: a, file: a.jpg, title: T}\n",
        "posts:\n- {name: a, file: a.jpg, title: T, info: I}\n- {name: a, file: b.jpg, title: T, info: I}\n",
        "posts:\n- {name: a, file: a.jpg, title: T, info: I, crop: [0, 0, 2, 1]}\n",
    ],
)
def test_load_specs_errors(tmp_path, text):
    with pytest.raises(SpecError):
        load_specs(write(tmp_path, text))


def test_load_specs_missing_file(tmp_path):
    with pytest.raises(SpecError, match="not found"):
        load_specs(tmp_path / "nope.yaml")


def test_repository_posts_yaml_is_valid():
    from pathlib import Path

    specs = load_specs(Path(__file__).resolve().parents[1] / "posts.yaml")
    assert len(specs) == 19 and len({s.file for s in specs}) == 19
    assert all(s.place and s.story for s in specs)


@responses.activate
def test_unverified_post_is_skipped_and_its_old_folder_removed(tmp_path):
    mock_commons()
    stale = tmp_path / "01-demo"
    stale.mkdir()
    (stale / "instagram_4x5.jpg").write_bytes(b"old")
    result = build_post(SPEC, stale, mode="gentle")  # no templates, no author evidence -> unverified
    assert result.skipped and "unverified" in result.note
    assert not stale.exists()


def test_credit_line_skips_unknown_authors():
    from histposts.pipeline import credit_line

    from .conftest import candidate

    assert credit_line(candidate(author="Unknown author")) == ""
    assert credit_line(candidate(author="Lewis Hine")) == "Fotoğraf: Lewis Hine\n"


def test_caption_hashtags_are_not_duplicated():
    from histposts.pipeline import caption_text

    from .conftest import candidate

    text = caption_text(PostSpec("a", "a.jpg", "T", "i", tags=["#tarih", "demo"]), candidate())
    assert text.count("#tarih ") + text.count("#tarih\n") == 1 and "#demo" in text


def test_image_credit_names_author_source_and_license():
    from histposts.pipeline import image_credit

    from .conftest import candidate

    text = image_credit(PostSpec("a", "a.jpg", "T", "i"), candidate(author="Lewis Hine"))
    assert "Lewis Hine" in text and "Wikimedia Commons" in text and "Kamu malı" in text
    assert "Fotoğraf" not in image_credit(
        PostSpec("a", "a.jpg", "T", "i"), candidate(author="Unknown author")
    )
