from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


SUPPORTED_KINDS = {"jsonl", "regex", "csv"}


@dataclass
class Defaults:
    severity_field: Optional[str] = None
    message_field: Optional[str] = None
    timestamp_field: Optional[str] = None
    timestamp_format: Optional[str] = None
    skew_ms: int = 0
    severity_map: Dict[str, float] = field(default_factory=dict)


@dataclass
class SourceConfig:
    name: str
    path: Path
    kind: str
    timestamp_field: Optional[str] = None
    timestamp_format: Optional[str] = None
    regex: Optional[str] = None
    csv_delimiter: str = ","
    csv_has_header: bool = True
    message_field: Optional[str] = None
    severity_field: Optional[str] = None
    severity_map: Dict[str, float] = field(default_factory=dict)
    metadata_fields: List[str] = field(default_factory=list)
    skew_ms: int = 0

    def merged_severity_map(self, defaults: Defaults) -> Dict[str, float]:
        result = dict(defaults.severity_map)
        result.update(self.severity_map)
        return result

    def effective_severity_field(self, defaults: Defaults) -> Optional[str]:
        return self.severity_field or defaults.severity_field

    def effective_message_field(self, defaults: Defaults) -> Optional[str]:
        return self.message_field or defaults.message_field

    def effective_timestamp_field(self, defaults: Defaults) -> Optional[str]:
        return self.timestamp_field or defaults.timestamp_field

    def effective_timestamp_format(self, defaults: Defaults) -> Optional[str]:
        return self.timestamp_format or defaults.timestamp_format

    def validate(self) -> None:
        if self.kind not in SUPPORTED_KINDS:
            raise ValueError(f"Unsupported source kind '{self.kind}' for {self.name}")
        if not self.path:
            raise ValueError(f"Source {self.name} is missing path")
        if self.kind == "jsonl":
            if not self.timestamp_field:
                raise ValueError(f"jsonl source {self.name} must define timestamp_field")
        if self.kind == "regex":
            if not self.regex:
                raise ValueError(f"regex source {self.name} must define regex pattern")
        if self.kind == "csv":
            if not self.timestamp_field:
                raise ValueError(f"csv source {self.name} must define timestamp_field")


@dataclass
class HeuristicsConfig:
    gap_ms: Optional[int] = None
    burst_window_ms: Optional[int] = None
    burst_threshold: Optional[int] = None
    severity_horizon: Optional[int] = None
    severity_delta: float = 0.5


@dataclass
class Config:
    title: Optional[str]
    defaults: Defaults
    sources: List[SourceConfig]
    heuristics: HeuristicsConfig
    enrichers: List[str]

    @classmethod
    def load(cls, path: Path | str) -> "Config":
        path = Path(path)
        with path.open("rb") as fh:
            data = tomllib.load(fh)
        return cls.from_dict(data, base_dir=path.parent)

    @classmethod
    def from_dict(cls, data: Dict[str, Any], base_dir: Path | None = None) -> "Config":
        base_dir = base_dir or Path.cwd()
        defaults = parse_defaults(data.get("defaults", {}))
        sources = [parse_source(item, defaults, base_dir) for item in data.get("sources", [])]
        if not sources:
            raise ValueError("At least one source must be configured")
        heuristics = parse_heuristics(data.get("heuristics", {}))
        enrichers = list(map(str, data.get("enrichers", [])))
        title = data.get("title")
        for src in sources:
            src.validate()
        return cls(title=title, defaults=defaults, sources=sources, heuristics=heuristics, enrichers=enrichers)


def parse_defaults(raw: Dict[str, Any]) -> Defaults:
    severity_map = {str(k): float(v) for k, v in raw.get("severity_map", {}).items()}
    return Defaults(
        severity_field=raw.get("severity_field"),
        message_field=raw.get("message_field"),
        timestamp_field=raw.get("timestamp_field"),
        timestamp_format=raw.get("timestamp_format"),
        skew_ms=int(raw.get("skew_ms", 0)),
        severity_map=severity_map,
    )


def parse_source(raw: Dict[str, Any], defaults: Defaults, base_dir: Path) -> SourceConfig:
    name = raw.get("name")
    if not name:
        raise ValueError("Each source must have a name")
    path = Path(raw.get("path", "")).expanduser()
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    kind = raw.get("kind", "").lower()

    severity_map = {str(k): float(v) for k, v in raw.get("severity_map", {}).items()}
    metadata_fields = [str(f) for f in raw.get("metadata_fields", [])]

    cfg = SourceConfig(
        name=name,
        path=path,
        kind=kind,
        timestamp_field=raw.get("timestamp_field", defaults.timestamp_field),
        timestamp_format=raw.get("timestamp_format", defaults.timestamp_format),
        regex=raw.get("regex"),
        csv_delimiter=raw.get("csv_delimiter", ","),
        csv_has_header=bool(raw.get("csv_has_header", True)),
        message_field=raw.get("message_field", defaults.message_field),
        severity_field=raw.get("severity_field", defaults.severity_field),
        severity_map=severity_map,
        metadata_fields=metadata_fields,
        skew_ms=int(raw.get("skew_ms", defaults.skew_ms)),
    )
    return cfg


def parse_heuristics(raw: Dict[str, Any]) -> HeuristicsConfig:
    gap = raw.get("gap", raw.get("gap_ms"))
    if isinstance(gap, dict):
        gap_ms = gap.get("threshold_ms") or gap.get("ms")
    else:
        gap_ms = gap
    burst = raw.get("burst", {})
    severity = raw.get("severity_regression", {})

    return HeuristicsConfig(
        gap_ms=int(gap_ms) if gap_ms is not None else None,
        burst_window_ms=_optional_int(burst.get("window_ms")),
        burst_threshold=_optional_int(burst.get("threshold") or burst.get("count")),
        severity_horizon=_optional_int(severity.get("horizon")),
        severity_delta=float(severity.get("delta", 0.5)) if severity else 0.5,
    )


def _optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    return int(value)
