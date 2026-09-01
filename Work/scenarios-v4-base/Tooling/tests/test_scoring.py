from __future__ import annotations

import json
import math
import sys
import tempfile
import unittest
from pathlib import Path


TOOLING_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLING_ROOT))

from v4_rubric.contracts import ContractError, validate_rubric  # noqa: E402
from v4_rubric.cli import score_root  # noqa: E402
from v4_rubric.scoring import canonical_report_bytes, score_candidate  # noqa: E402
from v4_rubric.signals import (  # noqa: E402
    findings_f1,
    numeric_credit,
    source_ranking_credit,
    weighted_f1,
)


def minimal_rubric() -> dict:
    return {
        "schema_version": "v4-rubric-1",
        "scenario_id": "TEST",
        "score": {
            "max_points": 100,
            "pass_threshold": 80,
            "partial_threshold": 50,
            "integrity_penalty_cap": 15,
        },
        "components": [
            {
                "id": "decision",
                "weight": 50,
                "semantic": True,
                "atoms": [
                    {
                        "id": f"route-{index}",
                        "type": "categorical",
                        "weight": 1,
                        "candidate_path": f"decision.route-{index}",
                        "expected": "SAFE",
                    }
                    for index in range(1, 6)
                ],
            },
            {
                "id": "measurement",
                "weight": 50,
                "semantic": True,
                "atoms": [
                    {
                        "id": f"latency-{index}",
                        "type": "numeric",
                        "weight": 1,
                        "candidate_path": f"measurements.latency-{index}",
                        "expected": 10,
                        "unit": "ms",
                        "full_tolerance": 0,
                        "zero_tolerance": 10,
                    }
                    for index in range(1, 6)
                ],
            },
        ],
        "integrity_events": [],
    }


def minimal_candidate(*, route: str = "SAFE", value: int = 10, unit: str = "ms") -> dict:
    return {
        "decision": {f"route-{index}": route for index in range(1, 6)},
        "measurements": {
            f"latency-{index}": {"value": value, "unit": unit}
            for index in range(1, 6)
        },
    }


class SignalTests(unittest.TestCase):
    def test_weighted_f1_retains_partial_precision_and_recall(self) -> None:
        result = weighted_f1(tp=2, fp=1, fn=2)
        self.assertAlmostEqual(result["precision"], 2 / 3)
        self.assertAlmostEqual(result["recall"], 1 / 2)
        self.assertAlmostEqual(result["f1"], 4 / 7)

    def test_numeric_credit_is_continuous_and_unit_checked(self) -> None:
        self.assertEqual(numeric_credit(10, 10, "ms", "ms", 1, 5), 1)
        self.assertEqual(numeric_credit(13, 10, "ms", "ms", 1, 5), 0.5)
        self.assertEqual(numeric_credit(20, 10, "ms", "ms", 1, 5), 0)
        self.assertEqual(numeric_credit(10, 10, "s", "ms", 1, 5), 0)
        self.assertEqual(numeric_credit(math.nan, 10, "ms", "ms", 1, 5), 0)

    def test_findings_matching_is_one_to_one_and_duplicate_is_false_positive(self) -> None:
        expected = [
            {"id": "A", "file": "src/a.py", "symbol": "load", "severity": "high"},
            {"id": "B", "file": "src/b.py", "symbol": "save", "severity": "medium"},
        ]
        reported = [
            {"id": "r1", "file": "SRC/A.PY", "symbol": "LOAD", "severity": "high"},
            {"id": "r2", "file": "src/a.py", "symbol": "load", "severity": "high"},
        ]
        result = findings_f1(
            expected,
            reported,
            match_fields=["file", "symbol"],
            severity_weights={"high": 3, "medium": 2, "low": 1},
            casefold_fields=["file", "symbol"],
        )
        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["unmatched_reported_count"], 1)
        self.assertEqual(result["unmatched_expected_count"], 1)
        self.assertGreater(result["f1"], 0)
        self.assertLess(result["f1"], 1)

    def test_source_ranking_loses_only_inverted_pairs(self) -> None:
        expected = ["current", "runtime", "stale"]
        perfect = source_ranking_credit(expected, expected)
        one_inversion = source_ranking_credit(expected, ["runtime", "current", "stale"])
        self.assertEqual(perfect["credit"], 1)
        self.assertGreater(one_inversion["credit"], 0)
        self.assertLess(one_inversion["credit"], 1)


class ContractAndScoringTests(unittest.TestCase):
    def test_contract_rejects_non_100_total_and_large_ordinary_atom(self) -> None:
        rubric = minimal_rubric()
        rubric["components"][0]["weight"] = 60
        with self.assertRaises(ContractError):
            validate_rubric(rubric)

        rubric = minimal_rubric()
        rubric["components"][0]["atoms"][0]["commitment"] = True
        with self.assertRaisesRegex(ContractError, "wrong_commitment_cap"):
            validate_rubric(rubric)

        rubric["score"]["wrong_commitment_cap"] = 50
        with self.assertRaisesRegex(ContractError, "below the partial threshold"):
            validate_rubric(rubric)

        rubric = minimal_rubric()
        rubric["components"][0]["weight"] = 20
        rubric["components"][1]["weight"] = 80
        with self.assertRaises(ContractError):
            validate_rubric(rubric)

    def test_score_has_no_global_floor_or_ceiling_and_status_is_diagnostic(self) -> None:
        report = score_candidate(
            minimal_rubric(),
            minimal_candidate(value=20),
        )
        self.assertEqual(report["raw_score"], 50)
        self.assertEqual(report["score"], 50)
        self.assertEqual(report["status"], "PARTIAL")
        self.assertEqual(report["components"][0]["score"], 50)
        self.assertEqual(report["components"][1]["score"], 0)

        commitment_rubric = minimal_rubric()
        commitment_rubric["score"]["wrong_commitment_cap"] = 40
        for atom in commitment_rubric["components"][0]["atoms"]:
            atom["commitment"] = True
        wrong_report = score_candidate(
            commitment_rubric,
            minimal_candidate(route="UNSAFE"),
        )
        self.assertEqual(wrong_report["raw_score"], 50)
        self.assertEqual(wrong_report["score"], 40)
        self.assertEqual(wrong_report["status"], "FAIL-COMMITMENT")
        self.assertEqual(len(wrong_report["commitment_violations"]), 5)

        omission_candidate = minimal_candidate()
        omission_candidate["decision"] = {}
        omission_report = score_candidate(commitment_rubric, omission_candidate)
        self.assertEqual(omission_report["raw_score"], 50)
        self.assertEqual(omission_report["score"], 50)
        self.assertEqual(omission_report["status"], "PARTIAL")
        self.assertEqual(omission_report["commitment_violations"], [])

    def test_map_and_list_collections_normalize_to_same_structured_score(self) -> None:
        rubric = minimal_rubric()
        rubric["components"] = [
            {
                "id": "cases",
                "weight": 100,
                "semantic": True,
                "atoms": [
                    {
                        "id": f"case-{index}",
                        "type": "case_fraction",
                        "weight": 1,
                        "candidate_path": "cases",
                        "id_field": "case_id",
                        "value_field": "outcome",
                        "expected": {f"C{index}": "ALLOW" if index % 2 else "DENY"},
                    }
                    for index in range(1, 11)
                ],
            }
        ]
        cases = {
            f"c{index}": {"outcome": "ALLOW" if index % 2 else "DENY"}
            for index in range(1, 11)
        }
        list_report = score_candidate(
            rubric,
            {"cases": [{"case_id": case_id, **value} for case_id, value in cases.items()]},
        )
        map_report = score_candidate(
            rubric,
            {"cases": dict(reversed(list(cases.items())))},
        )
        self.assertEqual(list_report["score"], 100)
        self.assertEqual(canonical_report_bytes(list_report), canonical_report_bytes(map_report))

    def test_direct_scoring_uses_precanonicalized_candidate_ids_once(self) -> None:
        rubric = minimal_rubric()
        rubric["components"] = [
            {
                "id": "cases",
                "weight": 100,
                "semantic": True,
                "atoms": [
                    {
                        "id": f"case-{index}",
                        "type": "case_fraction",
                        "weight": 1,
                        "candidate_path": "cases",
                        "id_field": "case_id",
                        "value_field": "outcome",
                        "expected": {f"C{index}": "ALLOW" if index % 2 else "DENY"},
                    }
                    for index in range(1, 11)
                ],
            }
        ]
        canonical_candidate = {
            "cases": [
                {"case_id": f"c{index}", "outcome": "ALLOW" if index % 2 else "DENY"}
                for index in range(1, 11)
            ]
        }
        unnormalized_candidate = {
            "cases": [
                {"case_id": f" C{index} ", "outcome": "ALLOW" if index % 2 else "DENY"}
                for index in range(1, 11)
            ]
        }

        self.assertEqual(score_candidate(rubric, canonical_candidate)["score"], 100)
        self.assertEqual(score_candidate(rubric, unnormalized_candidate)["score"], 0)

    def test_integrity_zero_is_local_and_penalty_is_bounded(self) -> None:
        rubric = minimal_rubric()
        rubric["integrity_events"] = [
            {
                "id": "unsafe-claim",
                "type": "forbidden_value",
                "candidate_path": "claims.safe_to_delete",
                "forbidden_values": [True],
                "zero_atoms": ["decision.route-1"],
                "penalty": 7,
            }
        ]
        report = score_candidate(
            rubric,
            {**minimal_candidate(), "claims": {"safe_to_delete": True}},
        )
        self.assertEqual(report["raw_score"], 100)
        self.assertEqual(report["adjusted_components"]["decision"], 40)
        self.assertEqual(report["adjusted_components"]["measurement"], 50)
        self.assertEqual(report["penalty"], 7)
        self.assertEqual(report["score"], 83)
        self.assertEqual(report["status"], "FAIL-INTEGRITY")

    def test_report_serialization_is_byte_deterministic(self) -> None:
        report = score_candidate(
            minimal_rubric(),
            minimal_candidate(value=12),
        )
        encoded = canonical_report_bytes(report)
        self.assertEqual(encoded, canonical_report_bytes(json.loads(encoded)))

    def test_invalid_candidate_is_distinct_from_scorer_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "oracle").mkdir()
            (root / "candidate").mkdir()
            (root / "inputs").mkdir()
            (root / "oracle" / "rubric.json").write_text(
                json.dumps({**minimal_rubric(), "candidate_artifact": "answer.json"}),
                encoding="utf-8",
            )
            (root / "inputs" / "output-schema.json").write_text(
                json.dumps({"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}),
                encoding="utf-8",
            )
            (root / "candidate" / "answer.json").write_text("{broken", encoding="utf-8")
            candidate_report = score_root(root)
            self.assertTrue(candidate_report["scoreable"])
            self.assertEqual(candidate_report["status"], "INVALID-CANDIDATE")
            self.assertEqual(candidate_report["score"], 0)
            self.assertEqual(candidate_report["candidate_diagnostics"][0]["code"], "CANDIDATE-INVALID-JSON")

            (root / "candidate" / "answer.json").unlink()
            missing_report = score_root(root)
            self.assertEqual(missing_report["status"], "INVALID-CANDIDATE")
            self.assertEqual(missing_report["candidate_diagnostics"][0]["path"], "answer.json")

            (root / "oracle" / "rubric.json").write_text("{}", encoding="utf-8")
            scorer_report = score_root(root)
            self.assertFalse(scorer_report["scoreable"])
            self.assertEqual(scorer_report["status"], "SCORER-ERROR")
            self.assertIsNone(scorer_report["score"])

            missing_rubric_report = score_root(root / "missing-root")
            self.assertEqual(missing_rubric_report["status"], "SCORER-ERROR")
            self.assertNotIn(root.name, missing_rubric_report["error"]["message"])


if __name__ == "__main__":
    unittest.main()
