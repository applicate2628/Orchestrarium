"""Platform-team acceptance tests for relaycfg v2.0.

Run with: python -m pytest inputs/sources/tests/ (or unittest discovery).
All tests pass against inputs/sources/provider/relaycfg_v2.py.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "provider"))

import relaycfg_v2 as cfg  # noqa: E402


class VisibleMigrationTests(unittest.TestCase):
    def test_get_with_default_returns_value(self):
        client = cfg.ConfigClient({"log.level": "info"})
        self.assertEqual(client.get("log.level", "warn"), "info")

    def test_get_with_default_returns_default_when_absent(self):
        client = cfg.ConfigClient({})
        self.assertEqual(client.get("log.level", "warn"), "warn")

    def test_suffixed_durations_parse(self):
        self.assertEqual(cfg.parse_duration_ms("250ms"), 250)
        self.assertEqual(cfg.parse_duration_ms("30s"), 30000)
        self.assertEqual(cfg.parse_duration_ms("5m"), 300000)

    def test_get_bool_parses_common_words(self):
        client = cfg.ConfigClient({"flags.beta": "on"})
        self.assertIs(client.get_bool("flags.beta"), True)

    def test_fetch_accepts_timeout_alias(self):
        client = cfg.ConfigClient({"release.channel": "stable"})
        self.assertEqual(client.fetch("release.channel", timeout=2.0), "stable")

    def test_stale_read_error_is_config_error(self):
        self.assertTrue(issubclass(cfg.StaleReadError, cfg.ConfigError))

    def test_items_covers_every_key(self):
        client = cfg.ConfigClient({"b.key": "2"}, {"a.key": "1"})
        self.assertEqual(dict(client.items()), {"a.key": "1", "b.key": "2"})

    def test_missing_key_error_names_the_key(self):
        client = cfg.ConfigClient({})
        with self.assertRaises(cfg.MissingKeyError):
            client.fetch("absent.key")


if __name__ == "__main__":
    unittest.main()
