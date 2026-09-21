"""Author life dates from Wikidata (a person is looked up by an explicit Q-id, never by fuzzy name search)."""

from __future__ import annotations

from dataclasses import dataclass

from ..http import get_json

ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"


@dataclass
class Person:
    qid: str
    label: str
    died: int | None
    url: str


def _year(claims: dict, prop: str) -> int | None:
    try:
        return int(claims[prop][0]["mainsnak"]["datavalue"]["value"]["time"][1:5])
    except (KeyError, IndexError, ValueError):
        return None


def person(qid: str) -> Person:
    entity = get_json(ENTITY.format(qid=qid))["entities"][qid]
    label = entity.get("labels", {}).get("en", {}).get("value", "")
    return Person(qid, label, _year(entity.get("claims", {}), "P570"), f"https://www.wikidata.org/wiki/{qid}")
