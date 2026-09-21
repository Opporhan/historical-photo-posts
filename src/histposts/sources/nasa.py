from __future__ import annotations

from ..http import get_json
from ..models import Candidate


def search(query: str, limit: int = 15) -> list[Candidate]:
    data = get_json("https://images-api.nasa.gov/search", q=query, media_type="image")
    out = []
    for item in data["collection"]["items"][:limit]:
        meta = item["data"][0]
        thumb = next((link["href"] for link in item.get("links", []) if link.get("rel") == "preview"), None)
        if not thumb:
            continue
        out.append(
            Candidate(
                source="NASA",
                thumb=thumb,
                url=thumb.replace("~thumb", "~large"),
                title=meta.get("title", ""),
                date=meta.get("date_created", "")[:10],
                author=meta.get("photographer") or meta.get("center", "NASA"),
                description=meta.get("description", ""),
                license="Public Domain (NASA)",
                source_url=f"https://images.nasa.gov/details/{meta['nasa_id']}",
                extra={"credit": "NASA"},
            )
        )
    return out
