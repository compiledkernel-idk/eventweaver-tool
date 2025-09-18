from __future__ import annotations

import unittest
from pathlib import Path

from eventweaver.config import Config
from eventweaver.timeline import generate_insights


FIXTURE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = FIXTURE_DIR / "examples" / "configs" / "synthetic.toml"


class AnalysisTests(unittest.TestCase):
    def test_generate_insights_emits_expected_kinds(self) -> None:
        config = Config.load(CONFIG_PATH)
        insights = generate_insights(config)
        kinds = {insight.kind for insight in insights}
        self.assertIn("time_gap", kinds)
        self.assertIn("burst", kinds)
        self.assertIn("severity_regression", kinds)


if __name__ == "__main__":
    unittest.main()
