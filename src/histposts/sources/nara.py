from __future__ import annotations

import os

from ..http import request
from ..models import Candidate

REQUIRES_KEY = "NARA_KEY"


def search(query: str, limit: int = 15) -> list[Candidate]:
    response = request(
        "https://catalog.archives.gov/api/v2/records/search",
        params={
            "q": query,
            "limit": limit,
            "availableOnline": "true",
            "typeOfMaterials": "Photographs and other Graphic Materials",
        },
        headers={"x-api-key": os.environ[REQUIRES_KEY]},
    )
    out = []
    for hit in response.json().get("body", {}).get("hits", {}).get("hits", []):
        record = hit["_source"]["record"]
        objects = record.get("digitalObjects", [])
        restriction = str(record.get("useRestriction", "")).lower()
        if not objects or ("restriction" in restriction and "unrestricted" not in restriction):
            continue
        out.append(
            Candidate(
                source="NARA",
                url=objects[0]["objectUrl"],
                thumb=objects[0]["objectUrl"],
                title=record.get("title", ""),
                description=record.get("scopeAndContentNote", ""),
                license="Public Domain (NARA)",
                source_url=f"https://catalog.archives.gov/id/{record.get('naId')}",
                extra={"credit": "National Archives and Records Administration"},
            )
        )
    return out
