import responses

from histposts import sources
from histposts.sources import europeana, met, nasa


@responses.activate
def test_nasa_parsing():
    responses.add(
        responses.GET,
        "https://images-api.nasa.gov/search",
        json={
            "collection": {
                "items": [
                    {
                        "data": [
                            {
                                "title": "Apollo",
                                "nasa_id": "A1",
                                "date_created": "1969-07-16T00:00:00Z",
                                "center": "JSC",
                            }
                        ],
                        "links": [{"rel": "preview", "href": "https://x/A1~thumb.jpg"}],
                    }
                ]
            }
        },
    )
    (c,) = nasa.search("apollo")
    assert c.url.endswith("~large.jpg") and c.date == "1969-07-16" and c.source_url.endswith("/A1")


@responses.activate
def test_met_only_public_domain_photographs():
    base = met.BASE
    responses.add(responses.GET, f"{base}/search", json={"objectIDs": [1, 2]})
    responses.add(
        responses.GET,
        f"{base}/objects/1",
        json={
            "isPublicDomain": True,
            "primaryImage": "https://m/1.jpg",
            "title": "Street",
            "objectDate": "1900",
            "objectURL": "u",
        },
    )
    responses.add(
        responses.GET, f"{base}/objects/2", json={"isPublicDomain": False, "primaryImage": "https://m/2.jpg"}
    )
    (c,) = met.search("street")
    assert c.title == "Street" and c.license.startswith("CC0")


def test_key_gated_sources_are_skipped_with_a_note(monkeypatch):
    monkeypatch.delenv("EUROPEANA_KEY", raising=False)
    monkeypatch.delenv("NARA_KEY", raising=False)
    assert europeana.REQUIRES_KEY == "EUROPEANA_KEY"
    found, notes = sources.search_all("x", names=["europeana", "nara"])
    assert found == []
    assert any("EUROPEANA_KEY" in n for n in notes) and any("NARA_KEY" in n for n in notes)


def test_one_failing_source_does_not_stop_the_search(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(sources.nasa, "search", boom)
    found, notes = sources.search_all("x", names=["nasa"])
    assert found == [] and any("nasa: failed" in n for n in notes)
