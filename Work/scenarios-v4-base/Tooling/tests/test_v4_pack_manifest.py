from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml


PACK_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = PACK_ROOT / "Planning" / "v4-pack-manifest.json"

PILOT_FIXTURES = (
    {
        "scenario_id": "V4L09B-pre-pr-review",
        "root": "Fixtures/V4L09B-pre-pr-review",
        "lane": "L09",
        "form": "base",
    },
    {
        "scenario_id": "V4L09F-pre-pr-review",
        "root": "Fixtures/V4L09F-pre-pr-review",
        "lane": "L09",
        "form": "frontier",
    },
)

FORBIDDEN_METADATA_TOKENS = (
    "expected-winner",
    "expected_winner",
    "expected winner",
    "expected-rank",
    "expected_rank",
    "expected rank",
    "desired-ranking",
    "desired_ranking",
    "desired ranking",
    "target-ranking",
    "target_ranking",
    "target ranking",
    "discrimination",
    "discriminator",
    "model-label",
    "model_label",
    "model label",
    "provider-label",
    "provider_label",
    "provider label",
)


class V4PackManifestTests(unittest.TestCase):
    def test_pilot_manifest_lists_exact_l09_pair_and_resolves_roots(self) -> None:
        self.assertTrue(MANIFEST.is_file(), f"missing manifest: {MANIFEST.relative_to(PACK_ROOT)}")
        manifest_text = MANIFEST.read_text(encoding="utf-8")
        manifest = json.loads(manifest_text)

        self.assertEqual(manifest.get("schema_version"), "scenarios-v4-pack-manifest-1")
        self.assertEqual(manifest.get("status"), "pilot")
        self.assertFalse(manifest.get("frozen"))
        self.assertEqual(manifest.get("target_evaluation_root_count"), 26)
        self.assertEqual(tuple(manifest.get("fixtures", ())), PILOT_FIXTURES)

        for entry in manifest["fixtures"]:
            root = PACK_ROOT / entry["root"]
            self.assertTrue(root.is_dir(), f"manifest root does not resolve: {entry['root']}")
            scenario = yaml.safe_load((root / "scenario.yaml").read_text(encoding="utf-8"))
            self.assertEqual(scenario.get("scenario_id"), entry["scenario_id"])
            self.assertEqual(scenario.get("lane"), entry["lane"])
            self.assertEqual(scenario.get("form"), entry["form"])

        lowered = manifest_text.lower()
        for token in FORBIDDEN_METADATA_TOKENS:
            self.assertNotIn(token, lowered, f"manifest contains forbidden metadata token {token!r}")


if __name__ == "__main__":
    unittest.main()
