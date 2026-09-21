"""Faithful restoration: no colorization, no face reconstruction, no inpainting.

``gentle``  classical OpenCV: mild denoise, soft local contrast, light unsharp mask.
``esrgan``  Real-ESRGAN (x4plus) for low-resolution sources, blended with the gentle result so that
            invented detail stays limited.
``auto``    ``esrgan`` when the long side is below ``min_long_side`` and the binary is installed,
            otherwise ``gentle``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw

from .compose import font

MAX_LONG_SIDE = 2800
ESRGAN_BLEND = 0.6
BINARY_NAME = "realesrgan-ncnn-vulkan"
INSTALL_HINT = "run scripts/install_realesrgan.sh or set HISTPOSTS_REALESRGAN to the binary path"


class EnhanceError(RuntimeError):
    pass


@dataclass
class Enhanced:
    image: Image.Image
    method: str  # "gentle" | "esrgan"
    note: str = ""


def find_binary() -> Path | None:
    env = os.environ.get("HISTPOSTS_REALESRGAN")
    candidates = [Path(env)] if env else []
    candidates.append(Path(__file__).resolve().parents[2] / "tools" / "realesrgan" / BINARY_NAME)
    found = shutil.which(BINARY_NAME)
    if found:
        candidates.append(Path(found))
    return next((p for p in candidates if p.is_file() and os.access(p, os.X_OK)), None)


def _limit(img: np.ndarray, long_side: int) -> np.ndarray:
    h, w = img.shape[:2]
    if max(h, w) <= long_side:
        return img
    s = long_side / max(h, w)
    return cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)


def gentle(img_bgr: np.ndarray, min_long_side: int = 2000) -> np.ndarray:
    img = _limit(img_bgr, MAX_LONG_SIDE)
    h, w = img.shape[:2]
    if max(h, w) < min_long_side:
        s = min_long_side / max(h, w)
        img = cv2.resize(img, None, fx=s, fy=s, interpolation=cv2.INTER_LANCZOS4)
    img = cv2.fastNlMeansDenoisingColored(img, None, 3, 3, 7, 21)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l_chan, a_chan, b_chan = cv2.split(lab)
    l_chan = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8)).apply(l_chan)
    img = cv2.cvtColor(cv2.merge([l_chan, a_chan, b_chan]), cv2.COLOR_LAB2BGR)
    blur = cv2.GaussianBlur(img, (0, 0), 1.5)
    return np.clip(cv2.addWeighted(img, 1.35, blur, -0.35, 0), 0, 255).astype(np.uint8)


def _run_esrgan(img_bgr: np.ndarray, binary: Path) -> np.ndarray:
    with tempfile.TemporaryDirectory() as tmp:
        src, dst = Path(tmp, "in.png"), Path(tmp, "out.png")
        cv2.imwrite(str(src), img_bgr)
        proc = subprocess.run(
            [str(binary), "-i", str(src), "-o", str(dst), "-n", "realesrgan-x4plus"],
            capture_output=True,
            text=True,
            cwd=binary.parent,
            timeout=900,
        )
        if proc.returncode != 0 or not dst.exists():
            raise EnhanceError(f"Real-ESRGAN failed (exit {proc.returncode}): {proc.stderr.strip()[-300:]}")
        out = cv2.imread(str(dst))
    if out is None:
        raise EnhanceError("Real-ESRGAN produced an unreadable image")
    return out


def enhance(img: Image.Image, mode: str = "auto", min_long_side: int = 1600) -> Enhanced:
    if mode not in {"auto", "gentle", "esrgan"}:
        raise ValueError(f"unknown enhance mode: {mode!r}")
    bgr = cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR)
    small = max(bgr.shape[:2]) < min_long_side
    use_esrgan = mode == "esrgan" or (mode == "auto" and small)
    note = ""

    if use_esrgan:
        binary = find_binary()
        if binary is None:
            if mode == "esrgan":
                raise EnhanceError(f"Real-ESRGAN binary not found; {INSTALL_HINT}")
            note = (
                f"low-resolution source but Real-ESRGAN is not installed ({INSTALL_HINT}); used gentle mode"
            )
            use_esrgan = False
    if use_esrgan:
        try:
            big = _limit(_run_esrgan(bgr, binary), MAX_LONG_SIDE)
            base = cv2.resize(gentle(bgr), (big.shape[1], big.shape[0]), interpolation=cv2.INTER_LANCZOS4)
            out = cv2.addWeighted(big, ESRGAN_BLEND, base, 1 - ESRGAN_BLEND, 0)
            return Enhanced(Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB)), "esrgan", note)
        except (EnhanceError, subprocess.SubprocessError, OSError) as exc:
            if mode == "esrgan":
                raise EnhanceError(str(exc)) from exc
            note = f"Real-ESRGAN failed ({exc}); used gentle mode"
    out = gentle(bgr)
    return Enhanced(Image.fromarray(cv2.cvtColor(out, cv2.COLOR_BGR2RGB)), "gentle", note)


def before_after(original: Image.Image, enhanced: Image.Image, height: int = 900) -> Image.Image:
    """Side-by-side comparison image (original left, enhanced right) at the same display size."""

    def fit(im: Image.Image) -> Image.Image:
        return im.convert("RGB").resize((max(1, round(im.width * height / im.height)), height), Image.LANCZOS)

    left, right = fit(original), fit(enhanced)
    gap, bar = 12, 56
    sheet = Image.new("RGB", (left.width + right.width + gap, height + bar), (18, 18, 18))
    sheet.paste(left, (0, bar))
    sheet.paste(right, (left.width + gap, bar))
    draw = ImageDraw.Draw(sheet)
    label = font("label", 30)
    draw.text((16, 10), "Original", font=label, fill=(235, 235, 235))
    draw.text((left.width + gap + 16, 10), "Enhanced", font=label, fill=(230, 190, 90))
    return sheet
