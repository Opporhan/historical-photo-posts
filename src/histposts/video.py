"""Short vertical MP4 (slow zoom) from a finished 9:16 image, for Reels/TikTok. Needs ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class VideoError(RuntimeError):
    pass


def make_video(image: Path, out: Path, seconds: int = 8, fps: int = 30) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise VideoError("ffmpeg not found; install it (e.g. `brew install ffmpeg`) to use --video")
    frames = seconds * fps
    # Upscale first so zoompan's integer cropping does not jitter, then zoom from 1.0 to 1.08.
    zoom = f"scale=2160:3840,zoompan=z='1+0.08*on/{frames}':d={frames}:s=1080x1920:fps={fps}"
    cmd = [
        ffmpeg, "-y", "-loglevel", "error", "-i", str(image), "-vf", zoom,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-movflags", "+faststart", str(out),
    ]  # fmt: skip
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise VideoError(proc.stderr.strip() or "ffmpeg failed")
    return out
