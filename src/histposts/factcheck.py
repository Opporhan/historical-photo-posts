"""Keyless fact check against Wikipedia (MediaWiki API, no account or paid API needed).

``facts.yaml`` lists, per post, the claims that go beyond the photo's own record, the Wikipedia article that
should back them and the key tokens (dates, numbers, names) that must appear in that article. A claim passes
when every token is found in the article text. This catches wrong dates, numbers and names; it is not a
sentence-level proof, so a passing check means "consistent with Wikipedia", not "true".
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .http import get_json


@dataclass
class Check:
    post: str
    claim: str
    article: str
    ok: bool
    missing: list[str] = field(default_factory=list)
    note: str = ""


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    return re.sub(r"\s+", " ", text.replace(" ", " ").replace("–", "-").replace("’", "'"))


def article_text(title: str, lang: str = "en") -> str:
    data = get_json(
        f"https://{lang}.wikipedia.org/w/api.php",
        action="query",
        prop="extracts",
        explaintext=1,
        redirects=1,
        titles=title,
        format="json",
    )
    pages = data.get("query", {}).get("pages", {})
    return " ".join(p.get("extract", "") for p in pages.values())


def load_facts(path: str | Path) -> dict[str, list[dict]]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {name: list(items) for name, items in data.items()}


def run(facts: dict[str, list[dict]], fetch=article_text) -> list[Check]:
    cache: dict[tuple[str, str], str] = {}
    results: list[Check] = []
    for post, items in facts.items():
        for item in items:
            lang, wiki = item.get("lang", "en"), item["wiki"]
            key = (lang, wiki)
            if key not in cache:
                cache[key] = _norm(fetch(wiki, lang))
            text = cache[key]
            label = f"{lang}.wikipedia: {wiki}"
            if not text:
                results.append(Check(post, item["claim"], label, False, note="article not found"))
                continue
            missing = [t for t in item["expect"] if _norm(str(t)) not in text]
            results.append(Check(post, item["claim"], label, not missing, missing))
    return results
