from __future__ import annotations

import re

from ..http import get_json
from ..models import Candidate

API = "https://commons.wikimedia.org/w/api.php"
PD_LICENSE = re.compile(r"^(public domain|pd\b|cc0|cc-zero)", re.I)
IMAGE_MIMES = ("image/jpeg", "image/tiff")
INFO_PROPS = "url|size|extmetadata|mime"
# Wikimedia asks clients to fetch standard thumbnail sizes instead of huge originals.
SEARCH_THUMB = 960
BUILD_WIDTH = 2560


def _text(meta: dict, key: str) -> str:
    return re.sub(r"<[^>]+>", "", meta.get(key, {}).get("value", "")).strip()


def clean_author(text: str) -> str:
    """Commons repeats some names ("Unknown authorUnknown author"); collapse that and stray whitespace."""
    text = re.sub(r"\s+", " ", text).strip()
    half = len(text) // 2
    if len(text) % 2 == 0 and half and text[:half] == text[half:]:
        return text[:half]
    match = re.fullmatch(r"(.+?)\1", text)
    return match.group(1) if match else text


def _parse_page(page: dict, require_pd: bool = True) -> Candidate | None:
    info = (page.get("imageinfo") or [{}])[0]
    meta = info.get("extmetadata", {})
    license_name = _text(meta, "LicenseShortName")
    if not info.get("url") or info.get("mime") not in IMAGE_MIMES:
        return None
    if require_pd and not PD_LICENSE.match(license_name):
        return None
    return Candidate(
        source="Wikimedia Commons",
        url=info["url"],
        thumb=info.get("thumburl", info["url"]),
        width=info.get("width", 0),
        title=page["title"].removeprefix("File:"),
        date=re.sub(r"date QS.*", "", _text(meta, "DateTimeOriginal")),
        author=clean_author(_text(meta, "Artist")),
        description=_text(meta, "ImageDescription"),
        license=license_name,
        source_url=info.get("descriptionurl", ""),
        extra={
            "license_url": _text(meta, "LicenseUrl"),
            "usage_terms": _text(meta, "UsageTerms"),
            "credit": _text(meta, "Credit"),
        },
    )


def _files_in(category: str, depth: int, limit: int) -> list[str]:
    """File titles in a category, descending into sub-categories up to ``depth`` levels."""
    titles: list[str] = []
    subs: list[str] = []
    data = get_json(
        API,
        action="query",
        list="categorymembers",
        cmtitle=f"Category:{category}",
        cmtype="file|subcat",
        cmlimit=50,
        format="json",
    )
    for member in data["query"]["categorymembers"]:
        (titles if member["ns"] == 6 else subs).append(member["title"])
    for sub in subs[:8] if depth else []:
        if len(titles) >= limit:
            break
        titles += _files_in(sub.removeprefix("Category:"), depth - 1, limit)
    return titles[:limit]


def _query_pages(width: int = SEARCH_THUMB, **params) -> list[dict]:
    data = get_json(
        API, action="query", prop="imageinfo", iiprop=INFO_PROPS, iiurlwidth=width, format="json", **params
    )
    return list(data.get("query", {}).get("pages", {}).values())


def search(query: str, limit: int = 15, category: str | None = None) -> list[Candidate]:
    limit = min(limit, 50)
    if category:
        titles = _files_in(category, 2, limit)
        pages = _query_pages(titles="|".join(titles)) if titles else []
    else:
        pages = _query_pages(
            generator="search", gsrsearch=f"{query} filetype:bitmap", gsrnamespace=6, gsrlimit=limit
        )
    return [c for c in (_parse_page(p) for p in pages) if c]


def fetch_by_title(file_title: str, width: int = BUILD_WIDTH) -> Candidate:
    """Metadata for one Commons file (by file name, with or without the ``File:`` prefix).

    Unlike :func:`search`, non-public-domain licenses are returned too, so the caller can classify them.
    """
    title = file_title if file_title.startswith("File:") else f"File:{file_title}"
    for page in _query_pages(width, titles=title):
        candidate = _parse_page(page, require_pd=False)
        if candidate:
            candidate.extra["templates"] = "|".join(templates_of(title))
            return candidate
    raise LookupError(f"Wikimedia Commons file not found or not a JPEG/TIFF: {file_title!r}")


def templates_of(file_title: str) -> list[str]:
    """Names of the templates used on a Commons file page (PD-old-70-expired, PD-USGov-FSA, Cc-zero, ...)."""
    data = get_json(API, action="query", titles=file_title, prop="templates", tllimit=500, format="json")
    names: list[str] = []
    for page in data.get("query", {}).get("pages", {}).values():
        names += [t["title"].removeprefix("Template:") for t in page.get("templates", [])]
    return names
