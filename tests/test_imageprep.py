from PIL import Image, ImageOps

from histposts.imageprep import autocrop_borders, crop_fractions

from .conftest import make_photo


def test_black_border_is_removed():
    framed = ImageOps.expand(make_photo(1000, 800), border=30, fill=(0, 0, 0))
    out = autocrop_borders(framed)
    assert framed.width - out.width >= 40  # both side borders trimmed
    assert out.width <= 1010 and out.height <= 810


def test_photo_without_border_is_untouched():
    photo = make_photo(1000, 800)
    assert autocrop_borders(photo).size == photo.size


def test_trim_is_capped():
    mostly_black = Image.new("RGB", (1000, 800), (0, 0, 0))
    out = autocrop_borders(mostly_black)
    assert out.width >= 1000 * (1 - 2 * 0.06) - 1


def test_crop_fractions():
    out = crop_fractions(Image.new("RGB", (1000, 500)), (0.1, 0.2, 0.9, 0.8))
    assert out.size == (800, 300)
