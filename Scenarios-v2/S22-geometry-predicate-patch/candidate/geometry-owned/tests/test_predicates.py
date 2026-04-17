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

from geometry.predicates import orientation, segments_intersect


def load_cases():
    payload = json.loads(
        (BUNDLE_ROOT / "inputs" / "failing-cases.json").read_text(encoding="utf-8")
    )
    return payload["cases"]


class GeometryPredicateTests(unittest.TestCase):
    def test_failing_case_packet(self):
        for case in load_cases():
            with self.subTest(case=case["id"]):
                if case["kind"] == "orientation":
                    actual = orientation(*[tuple(point) for point in case["points"]])
                    self.assertEqual(actual, case["expected_orientation"])
                elif case["kind"] == "segment_intersection":
                    segment_a = tuple(tuple(point) for point in case["segment_a"])
                    segment_b = tuple(tuple(point) for point in case["segment_b"])
                    actual = segments_intersect(
                        segment_a[0],
                        segment_a[1],
                        segment_b[0],
                        segment_b[1],
                    )
                    self.assertEqual(actual, case["expected_intersects"])
                else:
                    self.fail(f"Unknown case kind: {case['kind']}")


if __name__ == "__main__":
    unittest.main()
