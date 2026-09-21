import pytest

from histposts.compose import FONT_DIR, FONT_FILES, FORMATS, ComposeWarning, Layout, compose, turkish_upper

from .conftest import make_photo

TITLE = "Şişli'de Ağır İşçi Çocuğu Üçüncü Öğle Yemeği"
INFO = (
    "1913'te İstanbul'da çekilen bu karede ğüşıöç harflerini içeren uzun bir açıklama metni yer alıyor. " * 2
)


def test_bundled_fonts_exist():
    for name in FONT_FILES.values():
        assert (FONT_DIR / name).is_file()


@pytest.mark.parametrize("fmt", ["4x5", "9x16"])
def test_output_sizes(fmt):
    out = compose(make_photo(), TITLE, INFO, "1913", FORMATS[fmt])
    assert out.size == FORMATS[fmt]


def test_portrait_and_landscape_photos_fit():
    for size in ((600, 1400), (1600, 400)):
        out = compose(make_photo(*size), "Başlık", "Metin.", "", FORMATS["4x5"])
        assert out.size == FORMATS["4x5"]


def test_layout_is_configurable():
    tight = compose(make_photo(), "T", "I", "1900", FORMATS["9x16"], Layout(top_tall=100, bottom_tall=100))
    assert tight.size == FORMATS["9x16"]


def test_turkish_upper_keeps_dotted_and_dotless_i():
    assert turkish_upper("işçi ılık Şişli") == "İŞÇİ ILIK ŞİŞLİ"


def test_place_and_focus_are_accepted():
    out = compose(
        make_photo(1600, 900), "Başlık", "Metin.", "1900", FORMATS["4x5"], place="Paris", focus=(0.2, 0.5)
    )
    assert out.size == FORMATS["4x5"]


def test_very_long_text_warns_instead_of_silently_cutting():
    with pytest.warns(ComposeWarning):
        compose(make_photo(), "Başlık", "kelime " * 400, "", FORMATS["4x5"])
