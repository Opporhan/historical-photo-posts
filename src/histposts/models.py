from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class CaptionError(RuntimeError):
    pass


@dataclass
class Candidate:
    """A photograph found in one of the open-access sources."""

    source: str
    url: str
    title: str
    source_url: str
    license: str
    thumb: str = ""
    width: int = 0
    date: str = ""
    author: str = ""
    description: str = ""
    # License evidence as reported by the source (license URL, usage terms, credit line, ...).
    extra: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Candidate:
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})
