"""Evidence-based rights check that is stricter than ``licensing.classify``.

A post is ``verified`` only when all of these hold:

1. Commons (or the holding institution) tags the file as public domain / CC0 (template evidence).
2. The author's life+70 term has ended: the death year comes from Wikidata (looked up by an explicit Q-id),
   or from the spec together with a ``rights_source`` URL, or the work is anonymous
   (``author_died: anonymous`` plus a ``rights_source``) and at least 126 years old.
3. It is also public domain in the US: CC0, or created/published at least 96 years ago.

``us-only`` means public domain in the US but not provably elsewhere (e.g. US-government photographs by
authors who died recently). Everything else is ``unverified``. This is evidence-gathering, not legal advice.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from . import licensing
from .models import Candidate
from .sources import wikidata

VERIFIED, US_ONLY, UNVERIFIED = "verified", "us-only", "unverified"
# Any "PD-*" / CC0 / PD-mark template counts as "someone tags this as public domain"; the author and US checks
# below decide whether that claim holds worldwide.
_PD_TEMPLATE = re.compile(r"^(PD-|PD$|Cc-zero|Cc-pd-mark)", re.I)
_USGOV_TEMPLATE = re.compile(r"^PD-USGov", re.I)


@dataclass
class Rights:
    status: str
    basis: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)
    author_died: int | None = None
    sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "basis": self.basis,
            "problems": self.problems,
            "author_died": self.author_died,
            "sources": self.sources,
        }


def _templates(c: Candidate) -> list[str]:
    return [t for t in c.extra.get("templates", "").split("|") if t]


def verify(
    c: Candidate,
    author_qid: str = "",
    author_died: int | str | None = None,
    rights_source: str = "",
    person: Callable[[str], wikidata.Person] = wikidata.person,
    now: int | None = None,
) -> Rights:
    now = now or datetime.now(UTC).year
    templates = _templates(c)
    pd_templates = [t for t in templates if _PD_TEMPLATE.match(t)]
    year = licensing.latest_year(c.date)
    rights = Rights(UNVERIFIED, sources=[c.source_url] if c.source_url else [])

    if not pd_templates:
        rights.problems.append("no public-domain/CC0 template found on the source page")
    else:
        rights.basis.append("source tags: " + ", ".join(pd_templates[:5]))
    cc0 = any(t.lower() == "cc-zero" for t in templates)

    us_ok = cc0 or (year is not None and year < licensing.us_pd_before(now))
    if not us_ok:
        rights.problems.append(f"US status not established (date {c.date or 'unknown'})")

    world_ok = False
    if author_qid:
        who = person(author_qid)
        rights.sources.append(who.url)
        rights.author_died = who.died
        if who.died is None:
            rights.problems.append(f"Wikidata {author_qid} ({who.label}) has no death year")
        elif who.died <= now - licensing.PD_LIFE_PLUS - 1:
            world_ok = True
            rights.basis.append(f"author {who.label} died {who.died} (Wikidata {author_qid})")
        else:
            rights.problems.append(f"author {who.label} died {who.died}: protected in life+70 countries")
    elif author_died is not None and rights_source:
        rights.sources.append(rights_source)
        status, why = licensing.worldwide(year, author_died, now)
        world_ok = status == licensing.WORLDWIDE_YES
        (rights.basis if world_ok else rights.problems).append(f"{why} (source: {rights_source})")
        rights.author_died = author_died if isinstance(author_died, int) else None
    else:
        rights.problems.append(
            "author's death year / anonymity not established (set author_qid or rights_source)"
        )

    if pd_templates and us_ok and world_ok:
        rights.status = VERIFIED
    elif any(_USGOV_TEMPLATE.match(t) for t in templates) or (pd_templates and us_ok):
        rights.status = US_ONLY
    return rights
