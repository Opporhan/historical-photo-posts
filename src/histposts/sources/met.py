from __future__ import annotations

from ..http import get_json
from ..models import Candidate

BASE = "https://collectionapi.metmuseum.org/public/collection/v1"


def search(query: str, limit: int = 15) -> list[Candidate]:
    """The Met's Open Access photographs (CC0). No API key needed."""
    found = get_json(f"{BASE}/search", q=query, hasImages="true", isPublicDomain="true", medium="Photographs")
    out = []
    for object_id in (found.get("objectIDs") or [])[:limit]:
        obj = get_json(f"{BASE}/objects/{object_id}")
        if not obj.get("isPublicDomain") or not obj.get("primaryImage"):
            continue
        out.append(
            Candidate(
                source="The Met",
                url=obj["primaryImage"],
                thumb=obj.get("primaryImageSmall") or obj["primaryImage"],
                title=obj.get("title", ""),
                date=obj.get("objectDate", ""),
                author=obj.get("artistDisplayName", ""),
                description=obj.get("medium", ""),
                license="CC0 (The Met Open Access)",
                source_url=obj.get("objectURL", ""),
                extra={"license_url": "https://creativecommons.org/publicdomain/zero/1.0/"},
            )
        )
    return out
