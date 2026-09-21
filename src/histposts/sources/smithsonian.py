from __future__ import annotations

import os

from ..http import get_json
from ..models import Candidate


def search(query: str, limit: int = 15) -> list[Candidate]:
    key = os.environ.get("SMITHSONIAN_KEY", "DEMO_KEY")
    data = get_json(
        "https://api.si.edu/openaccess/api/v1.0/search",
        q=f'{query} AND online_media_type:"Images"',
        rows=limit,
        api_key=key,
    )
    out = []
    for row in data.get("response", {}).get("rows", []):
        content = row.get("content", {})
        desc = content.get("descriptiveNonRepeating", {})
        media = [
            m
            for m in desc.get("online_media", {}).get("media", [])
            if m.get("type") == "Images" and m.get("usage", {}).get("access") == "CC0"
        ]
        if not media:
            continue
        names = content.get("freetext", {}).get("name") or [{}]
        out.append(
            Candidate(
                source="Smithsonian",
                url=media[0]["content"],
                thumb=media[0]["content"],
                title=row.get("title", ""),
                author=names[0].get("content", ""),
                license="CC0 (Smithsonian Open Access)",
                source_url=desc.get("record_link", ""),
                extra={"license_url": "https://creativecommons.org/publicdomain/zero/1.0/"},
            )
        )
    return out
