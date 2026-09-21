"""License risk classification.

Three levels, deliberately conservative:

``safe``     CC0/Public Domain Mark, works of US federal agencies (NASA, FSA/OWI), or works published
             published before the US 95-year cut-off (1931 in 2026).
``review``   Tagged "public domain" but the legal basis is unclear (later than 1929, unknown date,
             press agencies, "no notice"/"not renewed" arguments). A human should check the source page.
``blocked``  Attribution / share-alike / non-commercial licenses or an unknown license.

This is a risk filter, not legal advice: copyright terms differ by country.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .models import Candidate

SAFE, REVIEW, BLOCKED = "safe", "review", "blocked"
US_TERM = 95  # US works published 1931+ are protected for 95 years; the term ends with the year


def us_pd_before(now: int | None = None) -> int:
    """First publication year that is NOT yet public domain in the US (2026 -> 1931: up to 1930 is free)."""
    return (now or datetime.now(UTC).year) - US_TERM


_RESTRICTED = re.compile(
    r"\bcc[- ]?by\b|\bby-sa\b|\bsa\b 4|share ?alike|non-?commercial|\bgfdl\b|\bcc[- ]by", re.I
)
_CC0 = re.compile(r"\bcc0\b|cc[- ]zero|public domain mark|publicdomain/(zero|mark)", re.I)
_GOV = re.compile(r"\bnasa\b|\bfsa\b|farm security administration|office of war information|\bowi\b", re.I)
_AGENCY = re.compile(
    r"associated press|\bap\b photo|getty images|gettyimages|reuters|keystone|bettmann|corbis|\bafp\b"
    r"|ullstein"
    r"|\blook magazine\b",
    re.I,
)
_NO_NOTICE = re.compile(r"no[- ]notice|not renewed|non-?renewed|pd-us-no", re.I)
_YEAR = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b")


@dataclass
class Verdict:
    level: str
    reasons: list[str] = field(default_factory=list)


def latest_year(date_text: str) -> int | None:
    """Latest year mentioned in a free-form date ("between 1880 and 1893" -> 1893)."""
    years = [int(y) for y in _YEAR.findall(date_text or "")]
    return max(years) if years else None


def classify(c: Candidate, now: int | None = None) -> Verdict:
    us_limit = us_pd_before(now)
    evidence = " ".join([c.license, c.extra.get("usage_terms", ""), c.extra.get("license_url", "")])
    context = " ".join([evidence, c.extra.get("credit", ""), c.author, c.description, c.title])
    year = latest_year(c.date)

    if not c.license.strip():
        return Verdict(BLOCKED, ["no license information"])
    if _RESTRICTED.search(evidence):
        return Verdict(BLOCKED, [f"license requires attribution/share-alike or restricts use: {c.license}"])
    if _CC0.search(evidence):
        return Verdict(SAFE, ["CC0 / Public Domain Mark"])

    review: list[str] = []
    if _AGENCY.search(context):
        review.append(
            "credit or description mentions a press agency or magazine; such photos are often still protected"
        )
    if _NO_NOTICE.search(evidence):
        review.append("public-domain claim rests on 'no notice'/'not renewed' (US-only argument)")
    if review:
        return Verdict(REVIEW, review)

    if _GOV.search(context):
        return Verdict(SAFE, ["work of a US federal agency (NASA / FSA / OWI)"])
    if year is not None and year < us_limit:
        return Verdict(
            SAFE,
            [
                f"published by {year}: public domain in the US (before {us_limit}); "
                "other countries depend on the author's death date"
            ],
        )
    if year is None:
        return Verdict(REVIEW, ["no date available; cannot verify the public-domain basis"])
    return Verdict(
        REVIEW,
        [f"dated {year} (after {us_limit - 1}): public-domain basis unclear, check the source page"],
    )


PD_LIFE_PLUS = 70  # most countries, including EU states and Turkey
# Anonymous/corporate works are only accepted when so old that even an unidentified author would have had to
# live 55+ years after creating them to still be protected (also covers the US 120-year rule).
ANON_MIN_AGE = 126
WORLDWIDE_YES, WORLDWIDE_NO, WORLDWIDE_UNKNOWN = "yes", "no", "unknown"


def worldwide(year: int | None, author_died: int | str | None, now: int | None = None) -> tuple[str, str]:
    """Is the work also public domain in life+70 countries? Returns (status, basis).

    ``author_died`` is the author's death year, ``"anonymous"`` for anonymous/corporate works (term counted
    from publication), or ``None`` when unknown. A US-government or pre-cut-off status alone says
    nothing about countries such as Turkey or the EU, so it is deliberately not used here.
    """
    now = now or datetime.now(UTC).year
    limit = now - PD_LIFE_PLUS - 1  # died in or before this year -> term has ended
    if isinstance(author_died, int):
        if author_died <= limit:
            return WORLDWIDE_YES, f"author died {author_died}; life+{PD_LIFE_PLUS} has ended"
        return WORLDWIDE_NO, f"author died {author_died}; protected in life+{PD_LIFE_PLUS} countries"
    if author_died == "anonymous":
        if year is not None and year <= now - ANON_MIN_AGE:
            return WORLDWIDE_YES, f"anonymous/corporate work dated {year} (over {ANON_MIN_AGE} years old)"
        return WORLDWIDE_UNKNOWN, f"anonymous work, not provably older than {ANON_MIN_AGE} years"
    return WORLDWIDE_UNKNOWN, "author's death year not recorded (set author_died in posts.yaml)"


def evidence_record(c: Candidate, verdict: Verdict) -> dict:
    """Everything needed to justify the license decision later."""
    return {
        "level": verdict.level,
        "reasons": verdict.reasons,
        "title": c.title,
        "source": c.source,
        "source_url": c.source_url,
        "license": c.license,
        "license_url": c.extra.get("license_url", ""),
        "usage_terms": c.extra.get("usage_terms", ""),
        "credit": c.extra.get("credit", ""),
        "author": c.author,
        "date": c.date,
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
