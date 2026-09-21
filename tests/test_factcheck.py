from histposts import factcheck


def test_claim_passes_only_when_every_token_is_in_the_article():
    facts = {"a": [{"claim": "c", "wiki": "X", "expect": ["1878", "Palo Alto"]}]}
    ok = factcheck.run(facts, fetch=lambda t, lang: "Shot at Palo Alto in 1878.")
    bad = factcheck.run(facts, fetch=lambda t, lang: "Shot in 1878.")
    assert ok[0].ok and not bad[0].ok and bad[0].missing == ["Palo Alto"]


def test_missing_article_fails_with_a_note():
    result = factcheck.run({"a": [{"claim": "c", "wiki": "X", "expect": ["1"]}]}, fetch=lambda t, lang: "")
    assert not result[0].ok and result[0].note == "article not found"


def test_matching_ignores_case_dashes_and_nbsp():
    facts = {"a": [{"claim": "c", "wiki": "X", "expect": ["1871-1874", "Wheeler"]}]}
    assert factcheck.run(facts, fetch=lambda t, lang: "From 1871–1874 with WHEELER.")[0].ok
