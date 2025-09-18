from __future__ import annotations

import csv
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Callable

from .config import Defaults, SourceConfig
from .models import Event


class SourceLoader:
    """Load events from a source according to its configuration."""

    def __init__(
        self,
        config: SourceConfig,
        defaults: Defaults,
        enrichers: Sequence[Callable[[Event], Event | None]] | None = None,
    ) -> None:
        self.config = config
        self.defaults = defaults
        self.enrichers: List[Callable[[Event], Event | None]] = list(enrichers or [])
        self._severity_map = config.merged_severity_map(defaults)

    def iter_events(self) -> Iterator[Event]:
        if not self.config.path.exists():
            raise FileNotFoundError(f"Source file not found: {self.config.path}")

        if self.config.kind == "jsonl":
            yield from self._iter_jsonl()
        elif self.config.kind == "regex":
            yield from self._iter_regex()
        elif self.config.kind == "csv":
            yield from self._iter_csv()
        else:
            raise ValueError(f"Unsupported source kind '{self.config.kind}'")

    # region helpers
    def _apply_enrichers(self, event: Event) -> Event:
        for enricher in self.enrichers:
            updated = enricher(event)
            if updated is not None:
                event = updated
        return event

    def _normalise_timestamp(self, raw_value: Any) -> datetime:
        if isinstance(raw_value, datetime):
            dt = raw_value
        elif isinstance(raw_value, (int, float)):
            dt = datetime.fromtimestamp(float(raw_value))
        elif isinstance(raw_value, str):
            fmt = self.config.effective_timestamp_format(self.defaults)
            dt = parse_timestamp(raw_value, fmt)
        else:
            raise ValueError(f"Unsupported timestamp value: {raw_value!r}")

        if self.config.skew_ms:
            dt = dt - timedelta(milliseconds=self.config.skew_ms)
        return dt

    def _normalise_severity(self, raw_value: Any) -> Optional[float]:
        if raw_value is None:
            return None
        if isinstance(raw_value, (int, float)):
            return float(raw_value)
        text = str(raw_value).strip()
        if text in self._severity_map:
            return self._severity_map[text]
        try:
            return float(text)
        except ValueError:
            return None

    def _extract_message(self, record: Dict[str, Any], fallback: str) -> str:
        field = self.config.effective_message_field(self.defaults)
        if field and field in record:
            return str(record[field])
        return fallback

    # endregion

    def _iter_jsonl(self) -> Iterator[Event]:
        timestamp_field = self.config.effective_timestamp_field(self.defaults)
        if not timestamp_field:
            raise ValueError(f"jsonl source {self.config.name} missing timestamp_field")

        severity_field = self.config.effective_severity_field(self.defaults)

        with self.config.path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Invalid JSON on line {line_no} in {self.config.path}") from exc

                if timestamp_field not in payload:
                    raise ValueError(
                        f"Missing timestamp_field '{timestamp_field}' in {self.config.name} line {line_no}"
                    )
                timestamp = self._normalise_timestamp(payload[timestamp_field])
                severity = self._normalise_severity(payload.get(severity_field)) if severity_field else None
                message = self._extract_message(payload, fallback=json.dumps(payload, ensure_ascii=False))

                metadata = {key: payload.get(key) for key in self.config.metadata_fields}
                event = Event(
                    timestamp=timestamp,
                    source=self.config.name,
                    severity=severity,
                    message=message,
                    metadata={k: v for k, v in metadata.items() if v is not None},
                    raw=payload,
                )
                yield self._apply_enrichers(event)

    def _iter_regex(self) -> Iterator[Event]:
        if not self.config.regex:
            raise ValueError(f"regex source {self.config.name} missing pattern")
        pattern = re.compile(self.config.regex)
        severity_field = self.config.effective_severity_field(self.defaults)

        with self.config.path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                match = pattern.search(line)
                if not match:
                    continue
                groups = match.groupdict(default=None)
                timestamp_token = groups.get("timestamp")
                if not timestamp_token:
                    raise ValueError(
                        f"Regex source {self.config.name} must define a 'timestamp' named capture group"
                    )
                timestamp = self._normalise_timestamp(timestamp_token)

                severity_token = groups.get("severity")
                if severity_token is None and severity_field and severity_field in groups:
                    severity_token = groups.get(severity_field)
                severity = self._normalise_severity(severity_token)

                message_token = groups.get("message") or line.strip()
                message = self._extract_message(groups, fallback=message_token)

                metadata = {key: groups.get(key) for key in self.config.metadata_fields}
                event = Event(
                    timestamp=timestamp,
                    source=self.config.name,
                    severity=severity,
                    message=message,
                    metadata={k: v for k, v in metadata.items() if v is not None},
                    raw={"line": line.rstrip("\n"), "groups": groups},
                )
                yield self._apply_enrichers(event)

    def _iter_csv(self) -> Iterator[Event]:
        timestamp_field = self.config.effective_timestamp_field(self.defaults)
        if not timestamp_field:
            raise ValueError(f"csv source {self.config.name} missing timestamp_field")
        severity_field = self.config.effective_severity_field(self.defaults)

        with self.config.path.open("r", encoding="utf-8", newline="") as handle:
            reader: Iterable[Dict[str, Any]]
            if self.config.csv_has_header:
                reader = csv.DictReader(handle, delimiter=self.config.csv_delimiter)
            else:
                if not isinstance(timestamp_field, str):
                    raise ValueError("timestamp_field must be column name when csv_has_header is False")
                headers = [timestamp_field]
                if severity_field:
                    headers.append(severity_field)
                headers.extend(self.config.metadata_fields)
                reader = csv.DictReader(handle, fieldnames=headers, delimiter=self.config.csv_delimiter)

            for row in reader:
                if timestamp_field not in row:
                    raise ValueError(
                        f"csv source {self.config.name} missing timestamp column '{timestamp_field}'"
                    )
                timestamp = self._normalise_timestamp(row[timestamp_field])
                severity = self._normalise_severity(row.get(severity_field)) if severity_field else None
                message = self._extract_message(row, fallback=",".join(str(v) for v in row.values()))
                metadata = {key: row.get(key) for key in self.config.metadata_fields}
                event = Event(
                    timestamp=timestamp,
                    source=self.config.name,
                    severity=severity,
                    message=message,
                    metadata={k: v for k, v in metadata.items() if v is not None},
                    raw=row,
                )
                yield self._apply_enrichers(event)


def parse_timestamp(value: str, fmt: Optional[str]) -> datetime:
    value = value.strip()
    if fmt:
        return datetime.strptime(value, fmt)
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"Could not parse timestamp '{value}'") from exc
