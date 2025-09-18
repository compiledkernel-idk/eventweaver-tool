# EventWeaver Architecture

EventWeaver is a Python 3.13+ command line companion for fusing heterogeneous log streams into a single temporal narrative. It tries to feel like an observability Swiss army knife while staying dependency-light and hackable.

## Goals

- **Multi-source ingestion:** Support JSON Lines, regex-based text logs, and CSV feeds with a single configuration file.
- **Temporal fusion:** Merge events from multiple sources into a strictly ordered timeline that tolerates clock skew and missing data.
- **Embedded heuristics:** Provide anomaly detectors (time gaps, traffic bursts, severity regressions) that surface likely problem areas automatically.
- **Expressive filtering:** Allow analysts to slice fused timelines with a safe, Pythonic expression DSL that can reference event metadata.
- **Extensibility hooks:** Let power users inject custom enrichers through import paths without editing EventWeaver's source.

## High-level Flow

1. **Configuration** is loaded from a TOML file into strong dataclasses with validation (sources, semantics, heuristics, enrichers).
2. **Source loaders** stream events concurrently using `asyncio.to_thread` to avoid blocking on slow disks.
3. **Parsers** normalise raw records into the internal `Event` dataclass, attaching structured tags and extra metadata.
4. The **fusion engine** chronologically merges the normalised generators, compensating for clock skew with configurable tolerance windows.
5. **Heuristic analyzers** walk the fused stream to emit `Insight` objects that describe anomalies or contextual metrics.
6. The **CLI** renders timelines, insights, and metrics as rich text tables or JSON, and can export slices with the expression DSL.

## Modules

- `config`: dataclasses + loaders for TOML configuration, handles validation and defaults.
- `sources`: parser classes for JSONL, regex-text, and CSV sources; includes helper utilities to register extra parser types at runtime.
- `timeline`: fusion logic and skew handling; houses the `Event` dataclass and chronological merge routines.
- `analysis`: anomaly detection heuristics producing structured `Insight` entries.
- `dsl`: safe expression compiler that translates user expressions into callables evaluated on `Event` instances.
- `cli`: argparse-powered command definitions: `fuse`, `insights`, `export`, `explain`.

## Extensibility

The config allows optional `enrichers = ["module:callable"]`. At runtime EventWeaver imports each callable, checks its signature `(event) -> event`, and applies it during normalisation, making it easy to append extra metadata or tag events.

## Advanced Behaviours

- **Clock skew tolerance:** Each source can declare a `skew_ms` tolerance. The fusion engine holds a small frontier buffer so a source running slightly behind does not get unfairly interleaved.
- **Burst detection:** Uses sliding windows with deque-based accounting to avoid reprocessing large spans.
- **Severity regression heuristic:** Detects when the overall severity trend worsens within an adjustable horizon.

## Testing Strategy

- Fast unit tests validate parsers, fusion ordering, DSL evaluation, and heuristic outputs on curated fixtures.
- Property-style checks ensure the DSL rejects unsafe syntax.
- End-to-end smoke test runs the CLI against the example config to verify the wiring.

