from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PACK_ROOT = Path(__file__).resolve().parents[2]
TOOLING_ROOT = PACK_ROOT / "Tooling"
CANDIDATE_ROOT = Path(__file__).resolve().parent / "adversarial_candidates"
sys.path.insert(0, str(TOOLING_ROOT))

from v4_rubric.cli import score_root  # noqa: E402
from v4_rubric.contracts import ContractError  # noqa: E402
from v4_rubric.scoring import canonical_report_bytes, score_candidate  # noqa: E402


def fixture_root(name: str) -> Path:
    return PACK_ROOT / "Fixtures" / name


def candidate(name: str) -> Path:
    return CANDIDATE_ROOT / name


def identity_rubric() -> dict:
    atoms = [
        {
            "id": "case",
            "type": "case_fraction",
            "weight": 1,
            "candidate_path": "cases",
            "id_field": "case_id",
            "value_field": "outcome",
            "casefold_values": True,
            "expected": {"Case One": "PASS"},
        },
        {
            "id": "claim",
            "type": "source_binding_f1",
            "weight": 1,
            "candidate_path": "claims",
            "id_field": "id",
            "source_ids_field": "source_ids",
            "casefold_sources": True,
            "expected": [{"id": "Cafe\u0301", "source_ids": ["SRC-1"]}],
        },
        {
            "id": "finding",
            "type": "findings_f1",
            "weight": 1,
            "candidate_path": "findings.correctness",
            "match_fields": ["file", "symbol"],
            "casefold_fields": ["file", "symbol"],
            "severity_weights": {"high": 3, "medium": 2, "low": 1},
            "expected": [{"id": "F1", "file": "src/a.py", "symbol": "load", "severity": "high"}],
        },
    ]
    atoms.extend(
        {
            "id": f"filler-{index}",
            "type": "categorical",
            "weight": 1,
            "candidate_path": f"sentinel.filler_{index}",
            "expected": "ok",
        }
        for index in range(1, 8)
    )
    return {
        "schema_version": "v4-rubric-1",
        "scenario_id": "TEST-identity-ingestion",
        "score": {
            "max_points": 100,
            "pass_threshold": 80,
            "partial_threshold": 50,
            "integrity_penalty_cap": 15,
        },
        "components": [{"id": "identity", "weight": 100, "semantic": True, "atoms": atoms}],
        "integrity_events": [],
    }


def ambiguous_id_field_rubric() -> dict:
    rubric = identity_rubric()
    rubric["components"][0]["atoms"][0] = {
        "id": "case-primary-id",
        "type": "case_fraction",
        "weight": 1,
        "candidate_path": "cases",
        "id_field": "case_id",
        "value_field": "outcome",
        "expected": {"A": "PASS"},
    }
    rubric["components"][0]["atoms"][1] = {
        "id": "case-other-id",
        "type": "case_fraction",
        "weight": 1,
        "candidate_path": "cases",
        "id_field": "other_id",
        "value_field": "outcome",
        "expected": {"B": "PASS"},
    }
    return rubric


def permissive_schema() -> dict:
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}


def score_with_temporary_root(rubric: dict, schema: dict, candidate_name: str) -> dict:
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        (root / "oracle").mkdir()
        (root / "inputs").mkdir()
        (root / "oracle" / "rubric.json").write_text(json.dumps(rubric), encoding="utf-8")
        (root / "inputs" / "output-schema.json").write_text(json.dumps(schema), encoding="utf-8")
        return score_root(root, candidate(candidate_name))


def diagnostic_codes(report: dict) -> set[str]:
    return {diagnostic["code"] for diagnostic in report["candidate_diagnostics"]}


class AdversarialRegressionTests(unittest.TestCase):
    def assert_invalid_candidate(self, report: dict, code: str) -> None:
        self.assertEqual(report["status"], "INVALID-CANDIDATE")
        self.assertTrue(report["scoreable"])
        self.assertEqual(report["score"], 0)
        self.assertIn(code, diagnostic_codes(report))

    def test_canonical_array_identity_collisions_are_invalid(self) -> None:
        report = score_with_temporary_root(
            identity_rubric(),
            permissive_schema(),
            "identity-canonical-array-collisions.json",
        )

        self.assert_invalid_candidate(report, "CANDIDATE-DUPLICATE-ID")
        self.assertEqual(
            {"cases", "claims", "findings.correctness"},
            {diagnostic["candidate_path"] for diagnostic in report["candidate_diagnostics"]},
        )

        invisible_report = score_with_temporary_root(
            identity_rubric(),
            permissive_schema(),
            "identity-default-ignorable-array-collisions.json",
        )
        self.assert_invalid_candidate(invisible_report, "CANDIDATE-DUPLICATE-ID")
        self.assertEqual(
            {"cases", "claims", "findings.correctness"},
            {diagnostic["candidate_path"] for diagnostic in invisible_report["candidate_diagnostics"]},
        )

    def test_canonical_map_identity_collisions_are_invalid(self) -> None:
        report = score_with_temporary_root(
            identity_rubric(),
            permissive_schema(),
            "identity-canonical-map-collisions.json",
        )

        self.assert_invalid_candidate(report, "CANDIDATE-DUPLICATE-ID")
        self.assertEqual(
            {"cases", "claims"},
            {diagnostic["candidate_path"] for diagnostic in report["candidate_diagnostics"]},
        )

        invisible_report = score_with_temporary_root(
            identity_rubric(),
            permissive_schema(),
            "identity-default-ignorable-map-collisions.json",
        )
        self.assert_invalid_candidate(invisible_report, "CANDIDATE-DUPLICATE-ID")
        self.assertEqual(
            {"cases", "claims"},
            {diagnostic["candidate_path"] for diagnostic in invisible_report["candidate_diagnostics"]},
        )

    def test_map_key_and_embedded_id_contradiction_is_invalid(self) -> None:
        report = score_with_temporary_root(
            identity_rubric(),
            permissive_schema(),
            "identity-map-key-embedded-id-contradiction.json",
        )

        self.assert_invalid_candidate(report, "CANDIDATE-ID-CONTRADICTION")
        self.assertEqual(report["candidate_diagnostics"][0]["candidate_path"], "claims")

    def test_duplicate_finding_id_is_invalid(self) -> None:
        report = score_root(
            fixture_root("V4C04-findings-review"),
            candidate("C04-schema-valid-duplicate-finding-id.json"),
        )

        self.assert_invalid_candidate(report, "CANDIDATE-DUPLICATE-ID")
        self.assertEqual(report["candidate_diagnostics"][0]["candidate_path"], "findings.correctness")

    def test_duplicate_finding_observation_is_invalid_with_reordered_evidence(self) -> None:
        report = score_root(
            fixture_root("V4C04-findings-review"),
            candidate("C04-schema-valid-duplicate-observation-reordered-evidence.json"),
        )

        self.assert_invalid_candidate(report, "CANDIDATE-DUPLICATE-OBSERVATION")
        self.assertEqual(report["candidate_diagnostics"][0]["candidate_path"], "findings.correctness")

    def test_raw_duplicate_json_keys_are_invalid(self) -> None:
        root = fixture_root("V4C02-numeric-reasoning")
        for name in [
            "C02-raw-duplicate-root-key.json",
            "C02-raw-duplicate-nested-key.json",
        ]:
            with self.subTest(candidate=name):
                report = score_root(root, candidate(name))
                self.assert_invalid_candidate(report, "CANDIDATE-DUPLICATE-JSON-KEY")

    def test_huge_integer_parse_domain_failure_is_invalid_zero_and_cli_exit_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            candidate_path = Path(temp_dir) / "huge-integer.json"
            json_out = Path(temp_dir) / "report.json"
            candidate_path.write_text(
                (
                    '{"scenario_id":"V4C02-numeric-reasoning",'
                    '"results":{"N1":{"value":'
                    + ("9" * 5000)
                    + ',"unit":"ms"},"N2":{"value":0.125,"unit":"ratio"},'
                    '"N3":{"value":64,"unit":"MiB"},"N4":{"value":3.5,"unit":"s"},'
                    '"N5":{"value":99.9,"unit":"percent"}},'
                    '"invariants":{"stability":["bounded-memory","finite-input"],'
                    '"ordering":["stable-order","unit-preserving"]},'
                    '"cases":{"F1":{"outcome":"PASS"},"F2":{"outcome":"PASS"}}}'
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "v4_rubric.cli",
                    "--root",
                    str(fixture_root("V4C02-numeric-reasoning").resolve()),
                    "--candidate",
                    str(candidate_path.resolve()),
                    "--json-out",
                    str(json_out.resolve()),
                ],
                cwd=TOOLING_ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(completed.stdout)
            self.assert_invalid_candidate(report, "CANDIDATE-NUMERIC-DOMAIN")
            self.assertEqual(json.loads(json_out.read_text(encoding="utf-8")), report)
            canonical_report_bytes(report)

    def test_unsafe_numeric_literals_are_invalid(self) -> None:
        root = fixture_root("V4C02-numeric-reasoning")
        for name in [
            "C02-unsafe-number-nan.json",
            "C02-unsafe-number-infinity.json",
            "C02-unsafe-number-negative-infinity.json",
            "C02-unsafe-number-overflow.json",
            "C02-unsafe-number-underflow.json",
            "C02-unsafe-integer.json",
            "C02-unsafe-float-safe-integer-positive.json",
            "C02-unsafe-float-safe-integer-negative.json",
            "C02-unsafe-float-safe-integer-exponent.json",
            "C02-unsafe-float-precision-collapse.json",
            "C02-unsafe-float-boundary-collapse.json",
        ]:
            with self.subTest(candidate=name):
                report = score_root(root, candidate(name))
                self.assert_invalid_candidate(report, "CANDIDATE-NUMERIC-DOMAIN")
                self.assertTrue(report["candidate_diagnostics"][0]["path"].startswith("/"))

    def test_safe_integer_boundaries_remain_scoreable(self) -> None:
        root = fixture_root("V4C02-numeric-reasoning")
        for name in [
            "C02-safe-integer-boundaries.json",
            "C02-safe-float-integer-boundaries.json",
        ]:
            with self.subTest(candidate=name):
                report = score_root(root, candidate(name))
                self.assertNotEqual(report["status"], "INVALID-CANDIDATE")
                self.assertTrue(report["scoreable"])
                self.assertEqual(report["candidate_diagnostics"], [])

        roundtrip_report = score_root(root, candidate("C02-safe-float-roundtrip-variants.json"))
        self.assertEqual(roundtrip_report["status"], "PASS")
        self.assertEqual(roundtrip_report["score"], 100)
        self.assertEqual(roundtrip_report["candidate_diagnostics"], [])

    def test_v4c04_narrative_fields_are_schema_invalid(self) -> None:
        root = fixture_root("V4C04-findings-review")
        for name in [
            "C04-schema-invalid-top-level-narrative.json",
            "C04-schema-invalid-finding-narrative.json",
        ]:
            with self.subTest(candidate=name):
                report = score_root(root, candidate(name))
                self.assert_invalid_candidate(report, "CANDIDATE-SCHEMA")

    def test_v4c04_scored_strings_reject_prose_and_preserve_valid_forms(self) -> None:
        root = fixture_root("V4C04-findings-review")
        for name in [
            "C04-schema-invalid-nested-prose-map.json",
            "C04-schema-invalid-nested-prose-array.json",
            "C04-schema-invalid-empty-finding-strings.json",
            "C04-schema-invalid-prose-scored-fields.json",
            "C04-schema-invalid-prose-map-keys.json",
        ]:
            with self.subTest(candidate=name):
                report = score_root(root, candidate(name))
                self.assert_invalid_candidate(report, "CANDIDATE-SCHEMA")

        valid_forms = [
            root / "oracle" / "reference-answer.json",
            root / "oracle" / "synthetic" / "paraphrase.json",
            candidate("C04-schema-valid-reordered-equivalent.json"),
            candidate("C04-schema-valid-map-embedded-ids-mixed-case.json"),
        ]
        for path in valid_forms:
            with self.subTest(valid_form=path.name):
                report = score_root(root, path)
                self.assertEqual(report["status"], "PASS")
                self.assertEqual(report["score"], 100)
                self.assertEqual(report["candidate_diagnostics"], [])

    def test_common_identity_invalid_values_are_invalid_before_scoring(self) -> None:
        for name in [
            "identity-invalid-array-ids.json",
            "identity-invalid-map-ids.json",
            "identity-invalid-finding-observation-fields.json",
        ]:
            with self.subTest(candidate=name):
                report = score_with_temporary_root(identity_rubric(), permissive_schema(), name)
                self.assertEqual(report["status"], "INVALID-CANDIDATE")
                self.assertEqual(report["score"], 0)
                self.assertTrue(
                    diagnostic_codes(report) <= {"CANDIDATE-INVALID-ID", "CANDIDATE-INVALID-OBSERVATION"}
                )

    def test_ambiguous_same_path_different_id_fields_is_rubric_contract_error(self) -> None:
        report = score_with_temporary_root(
            ambiguous_id_field_rubric(),
            permissive_schema(),
            "identity-ambiguous-id-fields-pass-before-fix.json",
        )

        self.assertEqual(report["status"], "SCORER-ERROR")
        self.assertFalse(report["scoreable"])
        self.assertEqual(report["error"]["code"], "RUBRIC-CONTRACT")

    def test_contradictory_duplicate_case_is_invalid_and_deterministic(self) -> None:
        root = fixture_root("V4C01-source-bound-advice")
        path = candidate("C01-schema-valid-contradictory-duplicate-case.json")
        reports = [score_root(root, path) for _ in range(2)]

        self.assertEqual(reports[0]["status"], "INVALID-CANDIDATE")
        self.assertTrue(reports[0]["scoreable"])
        self.assertEqual(reports[0]["score"], 0)
        self.assertEqual(reports[0]["candidate_diagnostics"][0]["code"], "CANDIDATE-DUPLICATE-ID")
        self.assertEqual(canonical_report_bytes(reports[0]), canonical_report_bytes(reports[1]))

    def test_map_collision_diagnostics_are_deterministic_under_json_member_reorder(self) -> None:
        reports = [
            score_with_temporary_root(identity_rubric(), permissive_schema(), name)
            for name in [
                "identity-canonical-map-collisions.json",
                "identity-canonical-map-collisions-reordered.json",
            ]
        ]

        self.assertEqual([report["status"] for report in reports], ["INVALID-CANDIDATE", "INVALID-CANDIDATE"])
        self.assertEqual(canonical_report_bytes(reports[0]), canonical_report_bytes(reports[1]))

    def test_visible_schema_violation_is_invalid_in_common_adapter(self) -> None:
        report = score_root(
            fixture_root("V4C01-source-bound-advice"),
            candidate("C01-schema-invalid-duplicate-ranking-still-passes.json"),
        )

        self.assertEqual(report["status"], "INVALID-CANDIDATE")
        self.assertTrue(report["scoreable"])
        self.assertEqual(report["score"], 0)
        self.assertEqual(report["candidate_diagnostics"][0]["code"], "CANDIDATE-SCHEMA")

    def test_declared_numeric_string_statuses_retain_full_credit(self) -> None:
        root = fixture_root("V4C03-implementation-runtime")
        for name in [
            "C03-schema-valid-string-status-paraphrase.json",
            "C03-schema-valid-numeric-equivalent-variants.json",
        ]:
            with self.subTest(candidate=name):
                report = score_root(root, candidate(name))
                self.assertEqual(report["status"], "PASS")
                self.assertEqual(report["score"], 100)

    def test_schema_valid_nonnumeric_status_strings_do_not_pass(self) -> None:
        report = score_root(
            fixture_root("V4C03-implementation-runtime"),
            candidate("C03-schema-valid-nonnumeric-statuses.json"),
        )

        self.assertTrue(report["scoreable"])
        self.assertLess(report["score"], 80)

    def test_wrong_present_commitments_are_capped_in_the_low_band(self) -> None:
        root = fixture_root("V4C04-findings-review")
        probes = {
            "C04-schema-valid-severity-denial.json": {
                "findings.correctness",
                "findings.reliability",
                "findings.performance",
                "findings.security",
            },
            "C04-schema-valid-wrong-evidence.json": {"binding.EC1"},
            "C04-schema-valid-finding-nonfinding-conflict.json": {"precision.non-findings"},
            "C04-schema-valid-wrong-review-scope.json": {"precision.review-scope"},
            "C04-schema-valid-wrong-actions.json": {"actions.A1-A2"},
        }
        for name, expected_refs in probes.items():
            with self.subTest(candidate=name):
                report = score_root(root, candidate(name))
                self.assertEqual(report["status"], "FAIL-COMMITMENT")
                self.assertEqual(report["score"], 40)
                self.assertGreater(report["raw_score"], report["score"])
                self.assertEqual(report["commitment_cap"], 40)
                self.assertTrue(
                    expected_refs
                    <= {violation["atom_ref"] for violation in report["commitment_violations"]}
                )

        omission_report = score_root(root, root / "oracle" / "synthetic" / "strong.json")
        self.assertEqual(omission_report["status"], "PASS")
        self.assertEqual(omission_report["score"], 90)
        self.assertEqual(omission_report["commitment_violations"], [])

    def test_duplicate_source_binding_id_is_invalid(self) -> None:
        report = score_root(
            fixture_root("V4C01-source-bound-advice"),
            candidate("C01-schema-valid-duplicate-claim.json"),
        )

        self.assertEqual(report["status"], "INVALID-CANDIDATE")
        self.assertEqual(report["score"], 0)
        self.assertEqual(report["candidate_diagnostics"][0]["candidate_path"], "claims")

    def test_duplicate_observation_rubric_is_rejected(self) -> None:
        rubric = json.loads(candidate("duplicate-observation-rubric.json").read_text(encoding="utf-8"))
        payload = json.loads(candidate("duplicate-observation-single-token.json").read_text(encoding="utf-8"))

        with self.assertRaisesRegex(ContractError, "duplicate observation identity"):
            score_candidate(rubric, payload)


if __name__ == "__main__":
    unittest.main()
