"""Static HTML page that shows every built post next to its license evidence, for a final human check."""

from __future__ import annotations

import html
import json
from pathlib import Path

CSS = (
    "body{font-family:system-ui,sans-serif;background:#111;color:#eee;margin:0;padding:24px}"
    "h1{font-weight:500}article{display:grid;grid-template-columns:270px 1fr;gap:20px;margin:24px 0;"
    "padding:16px;background:#1b1b1b;border-radius:8px}img{width:270px;border-radius:4px}"
    ".safe{color:#7ddc8a}.review{color:#f0c060}.blocked{color:#f07070}pre{white-space:pre-wrap;color:#ccc}"
    "a{color:#8ab4ff}"
)


def build_review(out_dir: Path) -> Path:
    cards = []
    for folder in sorted(p for p in out_dir.iterdir() if p.is_dir()):
        evidence_file = folder / "license_evidence.json"
        if not evidence_file.exists():
            continue
        ev = json.loads(evidence_file.read_text(encoding="utf-8"))
        caption = (
            (folder / "caption.txt").read_text(encoding="utf-8") if (folder / "caption.txt").exists() else ""
        )
        rows = "".join(
            f"<li><b>{html.escape(k)}:</b> {html.escape(str(ev.get(k, '')))}</li>"
            for k in ("license", "author", "date", "worldwide", "worldwide_basis", "enhancement")
            if ev.get(k)
        )
        cards.append(
            f"<article><a href='{folder.name}/instagram_4x5.jpg'>"
            f"<img src='{folder.name}/instagram_4x5.jpg'></a>"
            f"<div><h2>{html.escape(folder.name)} <span class='{ev['level']}'>{ev['level']}</span></h2>"
            f"<p class='{ev['level']}'>{html.escape('; '.join(ev.get('reasons', [])))}</p><ul>{rows}</ul>"
            f"<p><a href='{html.escape(ev.get('source_url', ''))}'>source page</a></p>"
            f"<pre>{html.escape(caption)}</pre></div></article>"
        )
    page = out_dir / "index.html"
    page.write_text(
        f"<!doctype html><meta charset='utf-8'><title>histposts review</title><style>{CSS}</style>"
        f"<h1>Review ({len(cards)} posts)</h1>{''.join(cards)}",
        encoding="utf-8",
    )
    return page
