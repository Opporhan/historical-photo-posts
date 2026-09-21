"""HTTP helpers that follow the Wikimedia API etiquette.

* meaningful ``User-Agent`` (contact taken from ``HISTPOSTS_CONTACT``; never hard-coded),
* at most :data:`MAX_CONCURRENCY` requests in flight,
* retry with exponential backoff on 429/5xx, honouring ``Retry-After``.
"""

from __future__ import annotations

import os
import random
import sys
import threading
import time
from typing import Any

import requests

from . import __version__

MAX_CONCURRENCY = 3
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})

_gate = threading.BoundedSemaphore(MAX_CONCURRENCY)
_warned = False
_sleep = time.sleep  # replaced in tests


def user_agent() -> str:
    global _warned
    contact = os.environ.get("HISTPOSTS_CONTACT", "").strip()
    if not contact and not _warned:
        _warned = True
        print(
            "note: set HISTPOSTS_CONTACT (an e-mail or URL) so that servers such as Wikimedia can reach you "
            "if your client misbehaves.",
            file=sys.stderr,
        )
    return f"histposts/{__version__} ({contact or 'contact not set'}) python-requests/{requests.__version__}"


def _delay(response: requests.Response | None, attempt: int) -> float:
    if response is not None:
        retry_after = response.headers.get("Retry-After", "")
        if retry_after.isdigit():
            return min(float(retry_after), 60.0)
    return min(4.0 * 2.0**attempt + random.uniform(0, 1), 60.0)


def request(
    url: str,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    retries: int = 5,
    timeout: float = 60,
) -> requests.Response:
    merged = {"User-Agent": user_agent(), **(headers or {})}
    for attempt in range(retries + 1):
        response: requests.Response | None = None
        try:
            with _gate:
                response = requests.get(url, params=params, headers=merged, timeout=timeout)
        except requests.RequestException:
            if attempt == retries:
                raise
        if response is not None:
            if response.status_code not in RETRY_STATUSES or attempt == retries:
                response.raise_for_status()
                return response
        _sleep(_delay(response, attempt))
    raise RuntimeError("unreachable")  # pragma: no cover


def get_json(url: str, **params: Any) -> Any:
    return request(url, params=params).json()


def get_bytes(url: str) -> bytes:
    return request(url, timeout=120).content


def polite_pause(seconds: float = 1.0) -> None:
    """Short pause between large downloads so bulk builds stay well below server rate limits."""
    _sleep(seconds)
