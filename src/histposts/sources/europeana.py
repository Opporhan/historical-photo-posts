from __future__ import annotations

import os

from ..http import get_json
from ..models import Candidate

REQUIRES_KEY = "EUROPEANA_KEY"


def search(query: str, limit: int = 15) -> list[Candidate]:
    data = get_json(
        "https://api.europeana.eu/record/v2/search.json",
        wskey=os.environ[REQUIRES_KEY],
        query=query,
        rows=limit,
        media="true",
        qf="TYPE:IMAGE",
        reusability="open",
    )
    out = []
    for item in data.get("items", []):
        rights = (item.get("rights") or [""])[0]
        if ("publicdomain" not in rights and "/zero/" not in rights) or not item.get("edmIsShownBy"):
            continue
        out.append(
            Candidate(
                source="Europeana",
                url=item["edmIsShownBy"][0],
                thumb=item["edmIsShownBy"][0],
                title=(item.get("title") or [""])[0],
                date=(item.get("year") or [""])[0],
                author=(item.get("dcCreator") or [""])[0],
                description=(item.get("dcDescription") or [""])[0],
                license="Public Domain / CC0 (Europeana)",
                source_url=item.get("guid", ""),
                extra={"license_url": rights},
            )
        )
    return out
