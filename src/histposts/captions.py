"""Grounded Turkish caption drafts with the Claude API.

Two calls: (1) draft title/info/hashtags plus the list of factual claims and where each one comes from,
(2) an independent check of the metadata-based claims against the source metadata. Claims that rest on
general knowledge are always flagged, so a human reviews them before anything is published.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from .models import Candidate, CaptionError

DEFAULT_MODEL = "claude-opus-5"
TITLE_MAX = 40
INFO_MAX = 300


class Claim(BaseModel):
    text: str
    basis: Literal["metadata", "general_knowledge"]


class CaptionDraft(BaseModel):
    title: str
    info: str
    hashtags: list[str]
    claims: list[Claim]


class ClaimCheck(BaseModel):
    claim: str
    supported: bool
    note: str


class Verification(BaseModel):
    checks: list[ClaimCheck]


@dataclass
class CaptionResult:
    draft: CaptionDraft
    needs_review: list[str]


DRAFT_SYSTEM = f"""You write short Turkish captions for historical-photo social media posts.

Rules:
- Base every statement on the metadata provided (title, description, date, place, source). Do not invent
  names, dates, numbers or causes. If something is uncertain or missing, leave it out or say it is unknown.
- You may add at most one sentence of widely documented background. Mark such a claim with basis
  "general_knowledge"; everything taken from the metadata has basis "metadata".
- Never name the photographer, the archive or the collection in the text.
- Do not describe things you cannot know from the metadata (people's thoughts, unseen details).
- title: Turkish, at most {TITLE_MAX} characters, no trailing period.
- info: Turkish, 2-3 sentences, at most {INFO_MAX} characters, neutral tone.
- hashtags: 3-6 lowercase Turkish or English hashtags including '#'.
- claims: every factual statement in title+info, one entry each.
"""

VERIFY_SYSTEM = """You fact-check claims against source metadata. For each claim answer whether the metadata
explicitly supports it. Be strict: a claim that goes beyond the metadata is not supported."""


def _client():
    import anthropic

    try:
        return anthropic.Anthropic()
    except anthropic.AnthropicError as exc:
        raise CaptionError(
            "No Anthropic credentials found. Export ANTHROPIC_API_KEY (or run `ant auth login`)."
        ) from exc


def _metadata(c: Candidate, topic: str | None) -> str:
    data = {
        "topic": topic or "",
        "title": c.title,
        "date": c.date,
        "description": c.description[:1500],
        "source": c.source,
        "license": c.license,
    }
    return json.dumps(data, ensure_ascii=False, indent=1)


def _parse(client, model: str, system: str, content: str, schema):
    import anthropic

    try:
        response = client.messages.parse(
            model=model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": content}],
            output_format=schema,
        )
    except anthropic.AuthenticationError as exc:
        raise CaptionError("Anthropic rejected the API key (authentication failed).") from exc
    except anthropic.APIError as exc:
        raise CaptionError(f"Claude API error: {exc}") from exc
    if response.stop_reason == "refusal":
        raise CaptionError("The model declined to write this caption.")
    if response.parsed_output is None:
        raise CaptionError("The model returned no structured output (try again).")
    return response.parsed_output


def generate_caption(
    candidate: Candidate, topic: str | None = None, client=None, model: str | None = None
) -> CaptionResult:
    model = model or os.environ.get("HISTPOSTS_MODEL", DEFAULT_MODEL)
    client = client or _client()
    meta = _metadata(candidate, topic)
    draft: CaptionDraft = _parse(client, model, DRAFT_SYSTEM, f"Photo metadata:\n{meta}", CaptionDraft)

    needs_review: list[str] = []
    if len(draft.title) > TITLE_MAX:
        needs_review.append(f"title is {len(draft.title)} characters (max {TITLE_MAX})")
    if len(draft.info) > INFO_MAX:
        needs_review.append(f"info is {len(draft.info)} characters (max {INFO_MAX})")

    from_metadata = [c.text for c in draft.claims if c.basis == "metadata"]
    needs_review += [
        f"general knowledge, verify: {c.text}" for c in draft.claims if c.basis == "general_knowledge"
    ]
    if from_metadata:
        request = f"Metadata:\n{meta}\n\nClaims to check:\n" + "\n".join(f"- {t}" for t in from_metadata)
        result: Verification = _parse(client, model, VERIFY_SYSTEM, request, Verification)
        needs_review += [
            f"not supported by metadata: {ck.claim} ({ck.note})" for ck in result.checks if not ck.supported
        ]
    return CaptionResult(draft=draft, needs_review=needs_review)
