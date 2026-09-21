import pytest

from histposts import verify
from histposts.sources import wikidata
from histposts.sources.wikimedia import clean_author

from .conftest import candidate


def person_died(year):
    return lambda qid: wikidata.Person(qid, "Someone", year, f"https://wd/{qid}")


def cand(date="1913", templates="PD-old|PD-Layout"):
    return candidate(license="Public domain", date=date, extra={"templates": templates})


def test_verified_needs_template_us_status_and_finished_life_term():
    r = verify.verify(cand(), author_qid="Q1", person=person_died(1927), now=2026)
    assert r.status == verify.VERIFIED and r.author_died == 1927


def test_recent_author_is_us_only_not_verified():
    r = verify.verify(cand("1936", "PD-USGov-FSA"), author_qid="Q1", person=person_died(1965), now=2026)
    assert r.status == verify.US_ONLY and any("protected" in p for p in r.problems)


def test_no_author_evidence_is_unverified_or_us_only_never_verified():
    r = verify.verify(cand(), now=2026)
    assert r.status != verify.VERIFIED and r.problems


def test_manual_claim_requires_a_source_url():
    assert verify.verify(cand(), author_died=1920, now=2026).status != verify.VERIFIED
    ok = verify.verify(cand(), author_died=1920, rights_source="https://example.org/record", now=2026)
    assert ok.status == verify.VERIFIED


def test_anonymous_work_with_source_is_verified_only_when_old_enough():
    old = verify.verify(cand("1890"), author_died="anonymous", rights_source="https://x", now=2026)
    new = verify.verify(cand("1990"), author_died="anonymous", rights_source="https://x", now=2026)
    assert old.status == verify.VERIFIED and new.status != verify.VERIFIED


def test_missing_public_domain_template_blocks_verification():
    r = verify.verify(cand(templates="Some-other"), author_qid="Q1", person=person_died(1927), now=2026)
    assert r.status != verify.VERIFIED


def test_photo_after_us_cutoff_is_not_verified_even_if_author_is_old():
    r = verify.verify(cand("1940"), author_qid="Q1", person=person_died(1940), now=2026)
    assert r.status != verify.VERIFIED


@pytest.mark.parametrize(
    ("raw", "clean"),
    [("Unknown authorUnknown author", "Unknown author"), ("Lewis Hine", "Lewis Hine"), (" A  B ", "A B")],
)
def test_clean_author(raw, clean):
    assert clean_author(raw) == clean


def test_any_pd_template_counts_but_author_checks_still_decide():
    r = verify.verify(cand("1909", "PD-NCLC"), author_qid="Q1", person=person_died(1940), now=2026)
    assert r.status == verify.VERIFIED
    unknown = verify.verify(cand("1909", "PD-Australia"), now=2026)
    assert unknown.status != verify.VERIFIED
