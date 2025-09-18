from __future__ import annotations

import unittest
from pathlib import Path

from eventweaver.config import Config
from eventweaver.timeline import collect_events


FIXTURE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = FIXTURE_DIR / "examples" / "configs" / "synthetic.toml"


class TimelineTests(unittest.TestCase):
    def test_collect_events_sorted(self) -> None:
        config = Config.load(CONFIG_PATH)
        events = collect_events(config)
        self.assertTrue(events, "expected events to be returned")
        timestamps = [event.timestamp for event in events]
        self.assertEqual(timestamps, sorted(timestamps))
        self.assertTrue(any(event.severity == 3 for event in events))

    def test_expression_filter_by_source(self) -> None:
        config = Config.load(CONFIG_PATH)
        events = collect_events(config, expression="source == 'auth-service'")
        self.assertTrue(events)
        self.assertTrue(all(event.source == "auth-service" for event in events))


if __name__ == "__main__":
    unittest.main()
