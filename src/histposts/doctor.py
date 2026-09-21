"""Pre-publication checklist over the built posts (files, rights evidence, text lengths, resolution)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .pipeline import PostSpec

REQUIRED = (
    "instagram_4x5.jpg",
    "tiktok_9x16.jpg",
    "before_after.jpg",
    "caption.txt",
    "license_evidence.json",
)
MIN_SOURCE_LONG_SIDE = 1600
INFO_RANGE, STORY_MIN = (100, 330), 300


@dataclass
class Finding:
    post: str
    level: str  # "error" | "warn"
    message: str


def check(specs: list[PostSpec], out_dir: Path) -> list[Finding]:
    findings: list[Finding] = []

    def add(post: str, level: str, message: str) -> None:
        findings.append(Finding(post, level, message))

    expected = {f"{n:02d}-{spec.name}": spec for n, spec in enumerate(specs, 1)}
    for folder in sorted(p for p in out_dir.iterdir() if p.is_dir()) if out_dir.is_dir() else []:
        if re.match(r"\d\d-", folder.name) and folder.name not in expected:
            add(folder.name, "error", "folder is not in the spec (stale output): delete it before publishing")

    for name, spec in expected.items():
        folder = out_dir / name
        if not folder.is_dir():
            add(name, "error", "not built")
            continue
        for filename in REQUIRED:
            if not (folder / filename).exists():
                add(name, "error", f"missing {filename}")
        evidence_file = folder / "license_evidence.json"
        if evidence_file.exists():
            evidence = json.loads(evidence_file.read_text(encoding="utf-8"))
            status = evidence.get("rights", {}).get("status")
            if status != "verified":
                add(name, "error", f"rights are '{status}', not verified")
            if max(evidence.get("source_size", [0])) < MIN_SOURCE_LONG_SIDE:
                add(name, "warn", f"source is small ({evidence.get('source_size')}); image may look soft")
        caption = folder / "caption.txt"
        if caption.exists():
            text = caption.read_text(encoding="utf-8")
            for needle in ("Kaynak:", "Lisans:", "Alt metin:"):
                if needle not in text:
                    add(name, "error", f"caption.txt lacks '{needle}'")
        if not INFO_RANGE[0] <= len(spec.info) <= INFO_RANGE[1]:
            add(
                name, "warn", f"info is {len(spec.info)} characters (aim for {INFO_RANGE[0]}-{INFO_RANGE[1]})"
            )
        if len(spec.story) < STORY_MIN:
            add(name, "warn", f"story is {len(spec.story)} characters (aim for {STORY_MIN}+)")
        if spec.story_en and not (folder / "caption_en.txt").exists():
            add(name, "error", "story_en is set but caption_en.txt is missing")
        if not spec.story_en:
            add(name, "warn", "no English text (story_en)")
        if not (folder / "reels_tiktok.mp4").exists():
            add(name, "warn", "no video (build with --video)")
    return findings
