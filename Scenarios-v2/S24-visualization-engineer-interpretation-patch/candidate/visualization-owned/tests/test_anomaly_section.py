from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
BUNDLE_ROOT = THIS_FILE.parents[3]
SRC_ROOT = THIS_FILE.parents[1] / "src"

if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from visualization_owned import build_anomaly_section


def load_cases():
    packet_payload = json.loads(
        (BUNDLE_ROOT / "inputs" / "section-cases.json").read_text(encoding="utf-8")
    )
    oracle_payload = json.loads(
        (BUNDLE_ROOT / "oracle" / "encoding-oracle.json").read_text(encoding="utf-8")
    )
    expected_by_id = {
        case["id"]: case["expected_spec"] for case in oracle_payload["cases"]
    }
    return [
        {
            "id": case["id"],
            "packet": case["packet"],
            "expected_spec": expected_by_id[case["id"]],
        }
        for case in packet_payload["cases"]
    ]


class VisualizationInterpretationTests(unittest.TestCase):
    def test_section_encoding_cases(self):
        for case in load_cases():
            with self.subTest(case=case["id"]):
                actual = build_anomaly_section(case["packet"])
                self.assertEqual(actual, case["expected_spec"])


if __name__ == "__main__":
    unittest.main()
