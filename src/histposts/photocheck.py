"""Heuristics to reject non-photographs (logos, diagrams, maps, text scans, posters, screenshots)."""

import re

import cv2
import numpy as np

BAD_WORDS = re.compile(
    r"\b(logo|map|diagram|flag|coat of arms|poster|intertitle|screenshot|icon|chart|graph|"
    r"stamp|emblem|banner|infographic|cover|document|letter|newspaper|drawing|sketch|painting|"
    r"illustration|render|schematic|plan|patch|seal|signature|montage|collage|menu|ticket|postcard|"
    r"colou?rized|colou?rised|ai[- ]enhanced)\b",
    re.I,
)


def looks_like_photo(img_bgr, title=""):
    """Returns (ok, reason)."""
    if BAD_WORDS.search(title):
        return False, "başlık: fotoğraf değil gibi"
    h, w = img_bgr.shape[:2]
    if min(h, w) < 200:
        return False, f"çözünürlük düşük ({w}x{h})"
    if max(h, w) / min(h, w) > 3:
        return False, "aşırı uzun/panorama oran"
    small = cv2.resize(img_bgr, (160, 160), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
    if (gray > 235).mean() > 0.6:
        return False, "çoğunlukla beyaz (belge/çizim)"
    q = (small // 8).reshape(-1, 3)
    uniq = len({tuple(x) for x in q})
    if uniq < 120 and len(set(map(int, gray.ravel() // 8))) < 12:
        return False, "renk/ton çeşitliliği düşük (logo/grafik)"
    lap = cv2.Laplacian(gray, cv2.CV_64F)
    if (np.abs(lap) < 0.5).mean() > 0.75:
        return False, "düz alanlar baskın (grafik)"
    hist = np.bincount(gray.ravel(), minlength=256) / gray.size
    ent = -(hist[hist > 0] * np.log2(hist[hist > 0])).sum()
    if ent < 3.5:
        return False, f"tonal entropi düşük ({ent:.1f})"
    return True, "ok"


def is_monochrome(img_bgr, max_mean_chroma=20.0, max_p95_chroma=35.0):
    """True for black-and-white, toned (sepia, cyanotype) or faded photos; False for colour photographs.

    Uses CIELAB chroma of the non-dark pixels: toning stays low and uniform, real colour does not.
    """
    small = cv2.resize(img_bgr, (200, 200), interpolation=cv2.INTER_AREA)
    lab = cv2.cvtColor(small, cv2.COLOR_BGR2LAB).astype(np.float32)
    lit = lab[..., 0] > 40
    if not lit.any():
        return True
    chroma = np.hypot(lab[..., 1] - 128, lab[..., 2] - 128)[lit]
    return bool(chroma.mean() <= max_mean_chroma and np.percentile(chroma, 95) <= max_p95_chroma)
