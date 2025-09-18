from __future__ import annotations

import unittest
from pathlib import Path

from eventweaver.config import Config, SourceConfig


FIXTURE_DIR = Path(__file__).resolve().parents[1]
CONFIG_PATH = FIXTURE_DIR / "examples" / "configs" / "synthetic.toml"


class ConfigTests(unittest.TestCase):
    def test_config_loads_example(self) -> None:
        config = Config.load(CONFIG_PATH)
        self.assertEqual(config.title, "Synthetic Incident")
        self.assertEqual(len(config.sources), 3)
        api_source = next(src for src in config.sources if src.name == "api-gateway")
        self.assertTrue(api_source.path.is_absolute())
        self.assertEqual(api_source.merged_severity_map(config.defaults)["ERROR"], 3)

    def test_invalid_source_kind(self) -> None:
        bogus = SourceConfig(name="bad", path=FIXTURE_DIR, kind="xml")
        with self.assertRaises(ValueError):
            bogus.validate()


if __name__ == "__main__":
    unittest.main()
