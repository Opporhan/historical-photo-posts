"""Open-access photo sources. Every module exposes ``search(query, limit=15, **kw) -> list[Candidate]``."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from types import ModuleType

from ..models import Candidate
from . import europeana, met, nara, nasa, smithsonian, wikimedia

SOURCES: dict[str, ModuleType] = {
    "wikimedia": wikimedia,
    "nasa": nasa,
    "smithsonian": smithsonian,
    "met": met,
    "europeana": europeana,
    "nara": nara,
}


def search_all(
    query: str, limit: int = 15, category: str | None = None, names: list[str] | None = None
) -> tuple[list[Candidate], list[str]]:
    """Search every source; returns (candidates, notes about skipped/failed sources)."""
    notes: list[str] = []
    selected = [n for n in SOURCES if not names or n in names]
    if category:  # category crawling is a Wikimedia Commons feature
        selected = ["wikimedia"]

    def run(name: str) -> list[Candidate]:
        module = SOURCES[name]
        key = getattr(module, "REQUIRES_KEY", None)
        if key and not os.environ.get(key):
            notes.append(f"{name}: skipped (set {key} to enable)")
            return []
        try:
            if name == "wikimedia":
                return module.search(query, limit=limit, category=category)
            return module.search(query, limit=limit)
        except Exception as exc:  # one broken source must not stop the search
            notes.append(f"{name}: failed ({type(exc).__name__}: {exc})")
            return []

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(run, selected))
    return [c for group in results for c in group], notes
