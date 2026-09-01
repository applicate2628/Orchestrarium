from __future__ import annotations

import sys
import unittest
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PACK_ROOT / "Tooling"))

from validate_calibration import validate_calibration  # noqa: E402


class ValidationHarnessTests(unittest.TestCase):
    def test_harness_proves_spread_monotonicity_paraphrase_and_replay(self) -> None:
        summary = validate_calibration(PACK_ROOT)
        aggregate = summary["aggregate"]
        self.assertEqual(aggregate["root_count"], 4)
        self.assertEqual(aggregate["monotonic_comparisons_passed"], aggregate["monotonic_comparisons_total"])
        self.assertGreaterEqual(aggregate["score_spread"], 90)
        self.assertGreaterEqual(aggregate["intermediate_score_count"], 12)
        self.assertLessEqual(aggregate["max_paraphrase_delta"], 2)
        self.assertEqual(aggregate["deterministic_replays_passed"], aggregate["deterministic_replays_total"])
        self.assertEqual(aggregate["adapter_checks_passed"], 4)
        self.assertTrue(aggregate["integrity_probe_passed"])
        self.assertEqual(aggregate["one_atom_locality_checks_passed"], 4)
        self.assertEqual(aggregate["threshold_neighborhood_checks_passed"], 4)


if __name__ == "__main__":
    unittest.main()
