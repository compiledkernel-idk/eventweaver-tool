from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


@dataclass(order=True)
class Event:
    """Normalized event emitted by EventWeaver."""

    sort_index: datetime = field(init=False, repr=False)
    timestamp: datetime
    source: str
    severity: Optional[float]
    message: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.sort_index = self.timestamp

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "severity": self.severity,
            "message": self.message,
            "metadata": self.metadata,
            "raw": self.raw,
        }


@dataclass
class Insight:
    """Structured insight produced by heuristics."""

    kind: str
    summary: str
    start: datetime
    end: datetime
    evidence: List[Event] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "summary": self.summary,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "metadata": self.metadata,
            "evidence": [event.to_dict() for event in self.evidence],
        }


def iter_event_dicts(events: Iterable[Event]) -> Iterable[Dict[str, Any]]:
    for event in events:
        yield event.to_dict()
