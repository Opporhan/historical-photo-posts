import pytest

from histposts import licensing
from histposts.licensing import BLOCKED, REVIEW, SAFE, classify, latest_year

from .conftest import candidate


@pytest.mark.parametrize(
    ("kwargs", "level"),
    [
        (dict(license="CC0", date="2020"), SAFE),
        (dict(license="Public domain", date="1903-12-17"), SAFE),
        (dict(license="Public domain", date="between 1880 and 1893"), SAFE),
        (
            dict(license="Public domain", date="1936-04", description="Farm Security Administration photo"),
            SAFE,
        ),
        (dict(license="Public domain", date="1969-07-20", extra={"credit": "NASA"}), SAFE),
        (dict(license="Public domain", date="1931"), REVIEW),
        (dict(license="Public domain", date="between 1914 and 1953"), REVIEW),
        (dict(license="Public domain", date=""), REVIEW),
        (dict(license="Public domain", date="1912", extra={"credit": "Associated Press"}), REVIEW),
        (dict(license="Public domain", date="1912", extra={"usage_terms": "PD-US-no-notice"}), REVIEW),
        (dict(license="CC BY-SA 4.0", date="1900"), BLOCKED),
        (dict(license="", date="1900"), BLOCKED),
        (dict(license="GFDL", date="1900"), BLOCKED),
    ],
)
def test_levels(kwargs, level):
    assert classify(candidate(**kwargs), now=2026).level == level


def test_reasons_are_always_given():
    assert classify(candidate(license="Public domain", date="1950")).reasons


def test_latest_year_takes_the_most_recent():
    assert latest_year("between 1880 and 1893") == 1893
    assert latest_year("unknown") is None


def test_evidence_record_contains_proof_fields():
    c = candidate(date="1900", extra={"license_url": "https://example/pd", "credit": "Archive"})
    record = licensing.evidence_record(c, classify(c))
    for key in ("level", "reasons", "license", "license_url", "credit", "source_url", "retrieved_at"):
        assert key in record
    assert record["license_url"] == "https://example/pd"


def test_us_cutoff_moves_with_the_year():
    assert classify(candidate(license="Public domain", date="1930"), now=2026).level == SAFE
    assert classify(candidate(license="Public domain", date="1930"), now=2025).level == REVIEW


def test_getty_research_institute_open_content_is_not_a_press_agency():
    ok = candidate(
        license="Public domain", date="1886", extra={"credit": "Getty Research Institute open content"}
    )
    assert classify(ok, now=2026).level == SAFE
    agency = candidate(license="Public domain", date="1886", extra={"credit": "Getty Images"})
    assert classify(agency, now=2026).level == REVIEW
