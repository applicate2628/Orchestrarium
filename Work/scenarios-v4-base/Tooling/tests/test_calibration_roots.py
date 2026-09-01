from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import jsonschema


PACK_ROOT = Path(__file__).resolve().parents[2]
TOOLING_ROOT = PACK_ROOT / "Tooling"
sys.path.insert(0, str(TOOLING_ROOT))

from v4_rubric.cli import score_root  # noqa: E402
from v4_rubric.contracts import validate_rubric  # noqa: E402


CALIBRATION_ROOTS = [
    "V4C01-source-bound-advice",
    "V4C02-numeric-reasoning",
    "V4C03-implementation-runtime",
    "V4C04-findings-review",
]


class CalibrationRootContractTests(unittest.TestCase):
    def test_four_roots_have_complete_visible_and_hidden_contracts(self) -> None:
        for root_name in CALIBRATION_ROOTS:
            with self.subTest(root=root_name):
                root = PACK_ROOT / "Fixtures" / root_name
                for relative in [
                    "README.md",
                    "scenario.yaml",
                    "inputs/task.md",
                    "inputs/output-schema.json",
                    "candidate/README.md",
                    "oracle/rubric.json",
                    "oracle/reference-answer.json",
                    "oracle/synthetic-answers.json",
                    "verifiers/score.py",
                    "verifiers/verifier-contract.md",
                ]:
                    self.assertTrue((root / relative).is_file(), f"missing {root_name}/{relative}")
                schema = json.loads((root / "inputs" / "output-schema.json").read_text(encoding="utf-8"))
                self.assertEqual(schema["type"], "object")
                self.assertFalse(schema["additionalProperties"])
                validate_rubric(json.loads((root / "oracle" / "rubric.json").read_text(encoding="utf-8")))

    def test_each_synthetic_ladder_is_monotonic_and_paraphrase_robust(self) -> None:
        for root_name in CALIBRATION_ROOTS:
            with self.subTest(root=root_name):
                root = PACK_ROOT / "Fixtures" / root_name
                corpus = json.loads((root / "oracle" / "synthetic-answers.json").read_text(encoding="utf-8"))
                scores = {
                    answer_id: score_root(root, root / "oracle" / "synthetic" / f"{answer_id}.json")["score"]
                    for answer_id in corpus["monotonic_order"]
                }
                ordered = [scores[answer_id] for answer_id in corpus["monotonic_order"]]
                self.assertEqual(ordered, sorted(ordered, reverse=True))
                self.assertGreaterEqual(ordered[0], 95)
                self.assertLessEqual(ordered[-1], 10)
                self.assertTrue(any(10 < score < 90 for score in ordered))
                self.assertLessEqual(abs(scores["reference"] - scores["paraphrase"]), 2)

    def test_reference_answer_scores_at_least_95(self) -> None:
        for root_name in CALIBRATION_ROOTS:
            with self.subTest(root=root_name):
                root = PACK_ROOT / "Fixtures" / root_name
                report = score_root(root, root / "oracle" / "reference-answer.json")
                self.assertTrue(report["scoreable"])
                self.assertGreaterEqual(report["score"], 95)

    def test_reference_and_paraphrase_are_valid_visible_schema_variants(self) -> None:
        for root_name in CALIBRATION_ROOTS:
            with self.subTest(root=root_name):
                root = PACK_ROOT / "Fixtures" / root_name
                schema = json.loads((root / "inputs" / "output-schema.json").read_text(encoding="utf-8"))
                jsonschema.Draft202012Validator.check_schema(schema)
                for answer in [
                    root / "oracle" / "reference-answer.json",
                    root / "oracle" / "synthetic" / "paraphrase.json",
                ]:
                    jsonschema.validate(json.loads(answer.read_text(encoding="utf-8")), schema)


if __name__ == "__main__":
    unittest.main()
