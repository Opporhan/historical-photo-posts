import pytest
import responses

from histposts.sources import wikimedia

API = wikimedia.API


def page(title, license_name="Public domain", mime="image/jpeg", **meta):
    extmetadata = {"LicenseShortName": {"value": license_name}, **{k: {"value": v} for k, v in meta.items()}}
    return {
        "title": f"File:{title}",
        "imageinfo": [
            {
                "url": f"https://upload.test/{title}",
                "thumburl": f"https://upload.test/t/{title}",
                "descriptionurl": f"https://commons.test/File:{title}",
                "width": 2000,
                "mime": mime,
                "extmetadata": extmetadata,
            }
        ],
    }


@responses.activate
def test_search_keeps_only_public_domain_images():
    pages = {
        "1": page("a.jpg"),
        "2": page("b.jpg", "CC BY-SA 4.0"),
        "3": page("c.png", mime="image/png"),
        "4": page("d.jpg", "CC0", DateTimeOriginal="1900-01-01date QS:P571,+1900"),
    }
    responses.add(responses.GET, API, json={"query": {"pages": pages}})
    found = wikimedia.search("anything")
    assert [c.title for c in found] == ["a.jpg", "d.jpg"]
    assert found[1].date == "1900-01-01"  # Wikidata artefact removed


@responses.activate
def test_fetch_by_title_returns_non_pd_files_so_they_can_be_classified():
    responses.add(
        responses.GET,
        API,
        json={
            "query": {
                "pages": {
                    "1": page(
                        "x.jpg",
                        "CC BY 4.0",
                        LicenseUrl="https://cc/by",
                        Credit="Somebody",
                        Artist="<b>Jane</b>",
                    )
                }
            }
        },
    )
    c = wikimedia.fetch_by_title("x.jpg")
    assert c.license == "CC BY 4.0" and c.author == "Jane"
    assert c.extra["license_url"] == "https://cc/by" and c.extra["credit"] == "Somebody"
    assert "titles=File%3Ax.jpg" in responses.calls[0].request.url


@responses.activate
def test_fetch_by_title_missing_file():
    responses.add(
        responses.GET, API, json={"query": {"pages": {"-1": {"title": "File:nope.jpg", "missing": ""}}}}
    )
    with pytest.raises(LookupError):
        wikimedia.fetch_by_title("nope.jpg")


@responses.activate
def test_build_metadata_asks_for_a_standard_sized_thumbnail():
    responses.add(responses.GET, API, json={"query": {"pages": {"1": page("y.jpg")}}})
    wikimedia.fetch_by_title("y.jpg")
    assert f"iiurlwidth={wikimedia.BUILD_WIDTH}" in responses.calls[0].request.url
    assert wikimedia.BUILD_WIDTH in (1920, 2560, 3840)  # sizes Wikimedia serves from cache
