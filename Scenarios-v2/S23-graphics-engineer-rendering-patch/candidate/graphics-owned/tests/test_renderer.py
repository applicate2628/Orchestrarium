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

from graphics_pipeline import frame_to_hex_grid, render_scene


def load_cases():
    payload = json.loads(
        (BUNDLE_ROOT / "oracle" / "frame-oracle.json").read_text(encoding="utf-8")
    )
    return payload["cases"]


class RenderingPipelineTests(unittest.TestCase):
    def test_frame_oracle_cases(self):
        for case in load_cases():
            with self.subTest(case=case["id"]):
                actual = frame_to_hex_grid(render_scene(case["scene"]))
                self.assertEqual(actual, case["expected_frame"])


if __name__ == "__main__":
    unittest.main()
