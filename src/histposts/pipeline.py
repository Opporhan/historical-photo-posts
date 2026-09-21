from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path

import cv2
import numpy as np
import yaml
from PIL import Image

from . import licensing, verify
from .compose import FORMATS, compose
from .enhance import before_after, enhance
from .http import get_bytes, polite_pause
from .imageprep import autocrop_borders, crop_fractions
from .models import Candidate
from .photocheck import is_monochrome
from .sources import wikimedia
from .video import make_video

DISCLOSURE = "Görsel dijital olarak iyileştirilmiştir."


class SpecError(ValueError):
    pass


@dataclass
class PostSpec:
    name: str
    file: str
    title: str
    info: str
    year: str = ""
    tags: list[str] = field(default_factory=list)
    crop: tuple[float, float, float, float] | None = None
    place: str = ""  # shown next to the top label, e.g. "Paris"
    story: str = ""  # longer text for caption.txt; falls back to ``info``
    focus: tuple[float, float] = (0.5, 0.5)  # (x, y) fractions kept in frame when the photo is cropped
    author_qid: str = ""  # Wikidata Q-id of the author; the death year is read from there
    author_died: int | str | None = None  # manual death year or "anonymous" (needs rights_source)
    rights_source: str = ""  # URL(s) backing a manual author_died / anonymity claim
    credit: str = ""  # author line for caption.txt when the Commons author is not the photographer
    title_en: str = ""  # English title/story for caption_en.txt (optional)
    story_en: str = ""
    series: str = ""  # posts sharing a series get a "03 / 10" counter
    alt_text: str = ""  # image description for accessibility; a default is generated when empty


@dataclass
class BuildResult:
    name: str
    level: str
    method: str = ""
    note: str = ""
    skipped: bool = False
    path: Path | None = None


def load_specs(path: str | Path) -> list[PostSpec]:
    path = Path(path)
    if not path.is_file():
        raise SpecError(f"spec file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    posts = data.get("posts")
    if not isinstance(posts, list) or not posts:
        raise SpecError(f"{path}: expected a non-empty 'posts:' list")
    specs, seen = [], set()
    for i, raw in enumerate(posts, 1):
        missing = [k for k in ("name", "file", "title", "info") if not raw.get(k)]
        if missing:
            raise SpecError(f"{path}: post #{i} is missing {', '.join(missing)}")
        if raw["name"] in seen:
            raise SpecError(f"{path}: duplicate post name {raw['name']!r}")
        seen.add(raw["name"])
        crop = raw.get("crop")
        if crop is not None and (len(crop) != 4 or not all(0 <= v <= 1 for v in crop)):
            raise SpecError(f"{path}: post {raw['name']!r}: crop must be 4 fractions between 0 and 1")
        focus = raw.get("focus", (0.5, 0.5))
        if len(focus) != 2 or not all(0 <= v <= 1 for v in focus):
            raise SpecError(f"{path}: post {raw['name']!r}: focus must be 2 fractions between 0 and 1")
        specs.append(
            PostSpec(
                name=raw["name"],
                file=raw["file"],
                title=raw["title"],
                info=raw["info"],
                year=str(raw.get("year", "")),
                tags=list(raw.get("tags", [])),
                crop=tuple(crop) if crop else None,
                place=str(raw.get("place", "")),
                story=str(raw.get("story", "")),
                focus=tuple(focus),
                author_qid=str(raw.get("author_qid", "")),
                author_died=raw.get("author_died"),
                rights_source=str(raw.get("rights_source", "")),
                credit=str(raw.get("credit", "")),
                title_en=str(raw.get("title_en", "")),
                story_en=str(raw.get("story_en", "")),
                series=str(raw.get("series", "")),
                alt_text=str(raw.get("alt_text", "")),
            )
        )
    return specs


def _download(url: str, cache_dir: Path | None) -> bytes:
    if cache_dir is None:
        data = get_bytes(url)
        polite_pause()
        return data
    cache_dir.mkdir(parents=True, exist_ok=True)
    target = cache_dir / hashlib.sha1(url.encode()).hexdigest()
    if not target.exists():
        target.write_bytes(get_bytes(url))
        polite_pause()
    return target.read_bytes()


def series_counters(specs: list[PostSpec]) -> dict[str, str]:
    """Post name -> "03 / 10" for posts that belong to a series."""
    members: dict[str, list[str]] = {}
    for spec in specs:
        if spec.series:
            members.setdefault(spec.series, []).append(spec.name)
    return {
        name: f"{i:02d} / {len(names):02d}" for names in members.values() for i, name in enumerate(names, 1)
    }


def default_alt(spec: PostSpec) -> str:
    where = f", {spec.place}" if spec.place else ""
    when = f" ({spec.year})" if spec.year else ""
    return f"Siyah-beyaz tarihi fotoğraf: {spec.title}{where}{when}."


def credit_line(c: Candidate, override: str = "") -> str:
    author = (override or c.author).strip()
    if not author or author.lower().startswith("unknown"):
        return ""
    return f"Fotoğraf: {author}\n"


def image_credit(spec: PostSpec, c: Candidate) -> str:
    """Small source line printed on the image: author, source, license."""
    author = (spec.credit or c.author).strip()
    parts = [f"Fotoğraf: {author}"] if author and not author.lower().startswith("unknown") else []
    cc0 = "cc-zero" in c.extra.get("templates", "").lower()
    return " · ".join([*parts, c.source, "CC0" if cc0 else "Kamu malı"])


def caption_en_text(spec: PostSpec, c: Candidate) -> str:
    author = (spec.credit or c.author).strip()
    credit = f"Photo: {author}\n" if author and not author.lower().startswith("unknown") else ""
    tags = " ".join(dict.fromkeys(t if t.startswith("#") else f"#{t}" for t in spec.tags))
    return (
        f"{spec.title_en or spec.title}\n\n{spec.story_en}\n\n{tags} #history #vintagephotography\n\n"
        "Image digitally enhanced.\n\n"
        f"{credit}Source: {c.source} — {c.source_url}\nLicense: {c.license}\n"
    )


def caption_text(spec: PostSpec, c: Candidate) -> str:
    wanted = [t if t.startswith("#") else f"#{t}" for t in [*spec.tags, "#tarih", "#tarihifotoğraf"]]
    tags = " ".join(dict.fromkeys(wanted))
    return (
        f"{spec.title}\n\n{spec.story or spec.info}\n\n{tags}\n\n{DISCLOSURE}\n\n"
        f"{credit_line(c, spec.credit)}Kaynak: {c.source} — {c.source_url}\nLisans: {c.license}\n\n"
        f"Alt metin: {spec.alt_text or default_alt(spec)}\n"
    )


def build_post(
    spec: PostSpec,
    folder: Path,
    mode: str = "auto",
    strict: bool = False,
    cache_dir: Path | None = None,
    counter: str = "",
    allow_unverified: bool = False,
    video: bool = False,
) -> BuildResult:
    candidate = wikimedia.fetch_by_title(spec.file)
    verdict = licensing.classify(candidate)
    if verdict.level == licensing.BLOCKED or (strict and verdict.level != licensing.SAFE):
        shutil.rmtree(folder, ignore_errors=True)
        return BuildResult(spec.name, verdict.level, skipped=True, note="; ".join(verdict.reasons))

    rights = verify.verify(candidate, spec.author_qid, spec.author_died, spec.rights_source)
    if not allow_unverified and rights.status != verify.VERIFIED:
        shutil.rmtree(folder, ignore_errors=True)  # never leave an older build of a post that now fails
        return BuildResult(
            spec.name,
            verdict.level,
            skipped=True,
            note=f"rights {rights.status}: " + "; ".join(rights.problems),
        )

    original = Image.open(BytesIO(_download(candidate.thumb or candidate.url, cache_dir))).convert("RGB")
    if not is_monochrome(cv2.cvtColor(np.asarray(original), cv2.COLOR_RGB2BGR)):
        return BuildResult(
            spec.name, verdict.level, skipped=True, note="renkli fotoğraf (yalnızca siyah-beyaz set)"
        )
    original_size = original.size
    if spec.crop:
        original = crop_fractions(original, spec.crop)
    original = autocrop_borders(original)
    enhanced = enhance(original, mode)

    if folder.exists():
        shutil.rmtree(folder)
    folder.mkdir(parents=True)
    for label, size in (("instagram_4x5", FORMATS["4x5"]), ("tiktok_9x16", FORMATS["9x16"])):
        compose(
            enhanced.image,
            spec.title,
            spec.info,
            spec.year,
            size,
            place=spec.place,
            focus=spec.focus,
            counter=counter,
            credit=image_credit(spec, candidate),
        ).save(folder / f"{label}.jpg", quality=95)
    before_after(original, enhanced.image).save(folder / "before_after.jpg", quality=90)
    (folder / "caption.txt").write_text(caption_text(spec, candidate), encoding="utf-8")
    evidence = licensing.evidence_record(candidate, verdict)
    evidence["enhancement"] = enhanced.method
    evidence["rights"] = rights.to_dict()
    evidence["source_size"] = list(original_size)
    if spec.story_en:
        (folder / "caption_en.txt").write_text(caption_en_text(spec, candidate), encoding="utf-8")
    if video:
        make_video(folder / "tiktok_9x16.jpg", folder / "reels_tiktok.mp4")
    (folder / "license_evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return BuildResult(
        spec.name, verdict.level, enhanced.method, enhanced.note or "; ".join(rights.basis), path=folder
    )
