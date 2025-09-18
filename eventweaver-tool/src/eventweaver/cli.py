from __future__ import annotations

import argparse
import json
import sys
import textwrap
from pathlib import Path
from typing import Iterable, List, Optional

from .config import Config
from .models import Event, Insight
from .timeline import collect_events, generate_insights


def _default_config_path() -> Optional[Path]:
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    if not pyproject.exists():
        return None
    try:
        import tomllib

        with pyproject.open("rb") as fh:
            data = tomllib.load(fh)
        path_str = data.get("tool", {}).get("eventweaver", {}).get("default_config")
        if path_str:
            candidate = (pyproject.parent / path_str).resolve()
            return candidate
    except Exception:
        return None
    return None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="weave", description="Fuse heterogeneous logs into a shared timeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    default_config = _default_config_path()

    fuse = subparsers.add_parser("fuse", help="Print fused timeline")
    fuse.add_argument("--config", type=Path, default=default_config, help="Path to TOML config file")
    fuse.add_argument("--query", type=str, help="Expression DSL filter", default=None)
    fuse.add_argument("--limit", type=int, help="Limit number of events shown")
    fuse.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="Output format",
    )
    fuse.set_defaults(handler=_handle_fuse)

    insights = subparsers.add_parser("insights", help="Run anomaly heuristics")
    insights.add_argument("--config", type=Path, default=default_config, help="Path to TOML config file")
    insights.add_argument("--query", type=str, help="Expression DSL filter", default=None)
    insights.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="Output format",
    )
    insights.set_defaults(handler=_handle_insights)

    export = subparsers.add_parser("export", help="Export fused events to JSON file")
    export.add_argument("--config", type=Path, default=default_config, help="Path to TOML config file")
    export.add_argument("--query", type=str, help="Expression DSL filter", default=None)
    export.add_argument("--output", type=Path, required=True, help="File to write JSON events to")
    export.add_argument("--indent", type=int, default=2, help="JSON indentation")
    export.set_defaults(handler=_handle_export)

    return parser


def _load_config(path: Optional[Path]) -> Config:
    if not path:
        raise SystemExit("A --config path must be provided (no default available)")
    if not path.exists():
        raise SystemExit(f"Config file not found: {path}")
    return Config.load(path)


def _handle_fuse(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    events = collect_events(config, expression=args.query)
    if args.limit is not None:
        events = events[: args.limit]
    if args.format == "json":
        print(json.dumps([event.to_dict() for event in events], indent=2))
    else:
        print(render_event_table(events))
    return 0


def _handle_insights(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    insights = generate_insights(config, expression=args.query)
    if args.format == "json":
        print(json.dumps([insight.to_dict() for insight in insights], indent=2))
    else:
        print(render_insight_table(insights))
    return 0


def _handle_export(args: argparse.Namespace) -> int:
    config = _load_config(args.config)
    events = collect_events(config, expression=args.query)
    payload = [event.to_dict() for event in events]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=args.indent))
    print(f"Wrote {len(events)} events to {args.output}")
    return 0


def render_event_table(events: Iterable[Event]) -> str:
    rows = [
        (
            event.timestamp.isoformat(timespec="seconds"),
            event.source,
            f"{event.severity:.2f}" if event.severity is not None else "-",
            textwrap.shorten(event.message.replace("\n", " "), width=80, placeholder="…"),
        )
        for event in events
    ]
    headers = ("timestamp", "source", "severity", "message")
    return _render_table(headers, rows)


def render_insight_table(insights: Iterable[Insight]) -> str:
    rows = [
        (
            insight.kind,
            insight.start.isoformat(timespec="seconds"),
            insight.end.isoformat(timespec="seconds"),
            textwrap.shorten(insight.summary, width=80, placeholder="…"),
        )
        for insight in insights
    ]
    headers = ("kind", "start", "end", "summary")
    if not rows:
        return "(no insights found)"
    return _render_table(headers, rows)


def _render_table(headers: Iterable[str], rows: Iterable[Iterable[str]]) -> str:
    headers = tuple(headers)
    rows = [tuple(str(cell) for cell in row) for row in rows]
    if not rows:
        return "(no data)"

    widths = [len(header) for header in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    def format_row(row: Iterable[str]) -> str:
        return " | ".join(cell.ljust(widths[idx]) for idx, cell in enumerate(row))

    separator = "-+-".join("-" * width for width in widths)
    lines = [format_row(headers), separator]
    lines.extend(format_row(row) for row in rows)
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
