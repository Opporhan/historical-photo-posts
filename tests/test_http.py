import pytest
import requests
import responses

from histposts import http


@responses.activate
def test_retries_on_429_and_honours_retry_after(monkeypatch):
    sleeps = []
    monkeypatch.setattr(http, "_sleep", sleeps.append)
    responses.add(responses.GET, "https://api.test/x", status=429, headers={"Retry-After": "7"})
    responses.add(responses.GET, "https://api.test/x", json={"ok": True})
    assert http.get_json("https://api.test/x") == {"ok": True}
    assert sleeps == [7.0]


@responses.activate
def test_gives_up_after_retries():
    responses.add(responses.GET, "https://api.test/y", status=503)
    with pytest.raises(requests.HTTPError):
        http.request("https://api.test/y", retries=2)
    assert len(responses.calls) == 3


@responses.activate
def test_client_errors_are_not_retried():
    responses.add(responses.GET, "https://api.test/z", status=404)
    with pytest.raises(requests.HTTPError):
        http.request("https://api.test/z")
    assert len(responses.calls) == 1


@responses.activate
def test_user_agent_uses_contact_from_environment(monkeypatch):
    monkeypatch.setenv("HISTPOSTS_CONTACT", "me@example.org")
    responses.add(responses.GET, "https://api.test/ua", json={})
    http.get_json("https://api.test/ua")
    agent = responses.calls[0].request.headers["User-Agent"]
    assert agent.startswith("histposts/") and "me@example.org" in agent


def test_contact_is_never_hard_coded(monkeypatch):
    monkeypatch.delenv("HISTPOSTS_CONTACT", raising=False)
    assert "@" not in http.user_agent()


def test_concurrency_is_capped_at_three():
    assert http.MAX_CONCURRENCY <= 3


@responses.activate
def test_default_backoff_grows(monkeypatch):
    sleeps = []
    monkeypatch.setattr(http, "_sleep", sleeps.append)
    responses.add(responses.GET, "https://api.test/b", status=503)
    responses.add(responses.GET, "https://api.test/b", status=503)
    responses.add(responses.GET, "https://api.test/b", json={"ok": 1})
    assert http.get_json("https://api.test/b") == {"ok": 1}
    assert len(sleeps) == 2 and sleeps[0] >= 4 and sleeps[1] >= 8
