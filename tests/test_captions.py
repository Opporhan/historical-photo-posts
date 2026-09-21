from types import SimpleNamespace

import pytest

from histposts import captions
from histposts.captions import CaptionDraft, CaptionError, Claim, ClaimCheck, Verification, generate_caption

from .conftest import candidate


class FakeMessages:
    def __init__(self, outputs, stop_reason="end_turn"):
        self.outputs, self.calls, self.stop_reason = list(outputs), [], stop_reason

    def parse(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(parsed_output=self.outputs.pop(0), stop_reason=self.stop_reason)


def fake_client(*outputs, stop_reason="end_turn"):
    return SimpleNamespace(messages=FakeMessages(outputs, stop_reason))


def draft(**kw):
    base = dict(
        title="Titanic Yola Çıkıyor",
        info="10 Nisan 1912'de gemi Southampton'dan ayrıldı.",
        hashtags=["#titanic"],
        claims=[Claim(text="departed 10 April 1912", basis="metadata")],
    )
    base.update(kw)
    return CaptionDraft(**base)


def test_clean_caption_needs_no_review():
    client = fake_client(
        draft(),
        Verification(checks=[ClaimCheck(claim="departed 10 April 1912", supported=True, note="date")]),
    )
    result = generate_caption(
        candidate(title="Titanic", date="1912-04-10"), "titanic", client=client, model="m"
    )
    assert result.needs_review == []
    assert [c["model"] for c in client.messages.calls] == ["m", "m"]
    assert client.messages.calls[0]["output_format"] is CaptionDraft


def test_general_knowledge_and_unsupported_claims_are_flagged():
    d = draft(
        claims=[
            Claim(text="sank on 15 April", basis="general_knowledge"),
            Claim(text="carried 2,224 people", basis="metadata"),
        ]
    )
    v = Verification(
        checks=[ClaimCheck(claim="carried 2,224 people", supported=False, note="not in metadata")]
    )
    result = generate_caption(candidate(), client=fake_client(d, v), model="m")
    assert any("general knowledge" in r for r in result.needs_review)
    assert any("not supported" in r for r in result.needs_review)


def test_length_limits_are_flagged():
    d = draft(title="x" * 60, info="y" * 400, claims=[])
    result = generate_caption(candidate(), client=fake_client(d), model="m")
    assert len(result.needs_review) == 2


def test_refusal_becomes_a_friendly_error():
    with pytest.raises(CaptionError, match="declined"):
        generate_caption(candidate(), client=fake_client(draft(), stop_reason="refusal"), model="m")


def test_missing_credentials_message(monkeypatch):
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", "/nonexistent")
    try:
        client = captions._client()
    except CaptionError as exc:
        assert "ANTHROPIC_API_KEY" in str(exc)
    else:  # SDK resolves credentials lazily: the error then surfaces on the first request
        with pytest.raises(Exception, match="(?i)api_key|auth|credential"):
            client.messages.count_tokens(model="claude-opus-5", messages=[{"role": "user", "content": "hi"}])


def test_default_model_is_opus_5():
    assert captions.DEFAULT_MODEL == "claude-opus-5"
