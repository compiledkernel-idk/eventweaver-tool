[README.md](https://github.com/user-attachments/files/22414728/README.md)
# EventWeaver

EventWeaver is an analyst-focused command line tool that fuses heterogeneous log files into a coherent timeline, runs contextual anomaly heuristics, and lets you slice the resulting event stream with a safe expression language.

It is designed for incident responders who constantly jump between JSON APIs, legacy text logs, and CSV exports. EventWeaver pulls those strands together and highlights the interesting bits automatically.

## Features

- **Multi-source ingestion**: JSON Lines, regex-based plaintext logs, and CSV are supported out of the box.
- **Temporal fusion**: Events from every source are merged into a single, stable timeline with per-source clock skew normalisation.
- **Heuristic insights**: Built-in detectors surface long quiet gaps, suspicious bursts, and worsening severity trends.
- **Expression DSL**: Filter and export slices with a Pythonic expression language that is statically analysed for safety (no eval).
- **Runtime enrichers**: Plug in custom enrichment callables from any import path to annotate events on the fly.

## Quick Start

```bash
# Create a virtual environment (optional but recommended)
python3 -m venv .venv
source .venv/bin/activate

# Install EventWeaver in editable mode
pip install -e .

# Run fusion against the synthetic example configuration
weave fuse --config examples/configs/synthetic.toml
```

### Insight run

```bash
weave insights --config examples/configs/synthetic.toml --format table
```

### Export only authentication related errors to JSON

```bash
weave export --config examples/configs/synthetic.toml --query "severity >= 2 and 'auth' in message" --output auth.json
```

## Configuration

EventWeaver expects a TOML configuration file. The synthetic example is heavily commented at `examples/configs/synthetic.toml`.

Key sections:

- `title` (optional): Free-form label used in CLI output.
- `defaults`: Shared defaults like `skew_ms` and severity field names.
- `sources`: One table per source describing type, file path, timestamp semantics, and severity mapping.
- `heuristics`: Thresholds for time gap, burst, and severity regression insights.
- `enrichers`: Optional list of import paths (`package.module:function`) that receive each `Event` and can mutate or return a new one.

## Advanced Expression DSL

The `--query` flag lets you filter events using a safe subset of Python expressions. Supported operations:

- Comparisons (`==`, `!=`, `>`, `<`, `>=`, `<=`)
- Boolean logic (`and`, `or`, `not`)
- Membership (`in`, `not in`)
- String literals and numeric literals
- Metadata access (`metadata['user_id']`)

Attempting to use unsupported syntax (function calls, attribute access, comprehensions, etc.) raises a friendly validation error.

## Architecture Overview

See `docs/ARCHITECTURE.md` for module-level details.

## Testing

```bash
pip install -e "[test]"
pytest
```

## Roadmap

- Allow streaming ingest from HTTP endpoints
- Persist timeline snapshots to SQLite for long running investigations
- Ship optional heuristics for user-defined markers (e.g., login/logout pairing)

## License

MIT
