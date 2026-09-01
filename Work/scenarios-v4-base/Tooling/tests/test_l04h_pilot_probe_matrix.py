from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
import subprocess
import sys
import unittest
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator


PACK_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = Path(__file__).resolve().parents[4]
SCRATCH_TEMP_ROOT = REPO_ROOT / ".scratch" / "l04h-authoring" / "test-tmp"
TOOLING_ROOT = PACK_ROOT / "Tooling"
sys.path.insert(0, str(TOOLING_ROOT))

from v4_rubric.contracts import validate_rubric  # noqa: E402


ROOTS = (
    "V4L04HB-hidden-consumer-contract",
    "V4L04HF-hidden-consumer-contract",
)
PERMANENT_PROBES = (
    "reference",
    "competent",
    "vacuous",
    "decoy",
    "alternate-valid",
    "paraphrase",
    "overclaim",
)
EXPECTED_SCORES = {
    "V4L04HB-hidden-consumer-contract": {
        "competent": Decimal("88.27"),
        "decoy": Decimal("49.17"),
        "max_atom_points": Decimal("8"),
    },
    "V4L04HF-hidden-consumer-contract": {
        "competent": Decimal("92.1"),
        "decoy": Decimal("50.05"),
        "max_atom_points": Decimal("6"),
    },
}


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _load_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return loaded


def _run_adapter(root: Path, candidate_path: Path) -> tuple[dict[str, Any], bytes]:
    completed = subprocess.run(
        [sys.executable, str(root / "verifiers" / "score.py"), "--candidate", str(candidate_path)],
        cwd=root,
        check=False,
        capture_output=True,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"{root.name} adapter failed for {candidate_path.name}: exit={completed.returncode}; "
            f"stderr={completed.stderr.decode('utf-8', errors='replace')}"
        )
    return json.loads(completed.stdout.decode("utf-8")), completed.stdout


def _all_atoms(rubric: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (component["id"], atom)
        for component in rubric["components"]
        for atom in component["atoms"]
    ]


def _atom_reports(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        f"{component['id']}.{atom['id']}": atom
        for component in report["components"]
        for atom in component["atoms"]
    }


def _component_scores(report: dict[str, Any]) -> dict[str, Decimal]:
    return {component["id"]: _decimal(component["score"]) for component in report["components"]}


def _score_surface(report: dict[str, Any]) -> bytes:
    surface = {
        "scoreable": report["scoreable"],
        "status": report["status"],
        "raw_score": report["raw_score"],
        "adjusted_components": report["adjusted_components"],
        "penalty": report["penalty"],
        "score": report["score"],
        "thresholds": report["thresholds"],
        "integrity_events": report["integrity_events"],
        "commitment_cap": report["commitment_cap"],
        "commitment_violations": report["commitment_violations"],
        "components": [
            {
                "id": component["id"],
                "score": component["score"],
                "atoms": [
                    {
                        "id": atom["id"],
                        "credit": atom["credit"],
                        "max_points": atom["max_points"],
                        "raw_points": atom["raw_points"],
                        "adjusted_points": atom["adjusted_points"],
                    }
                    for atom in component["atoms"]
                ],
            }
            for component in report["components"]
        ],
    }
    return json.dumps(surface, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _scratch_files() -> list[Path]:
    if not SCRATCH_TEMP_ROOT.exists():
        return []
    return [path for path in SCRATCH_TEMP_ROOT.rglob("*") if path.is_file()]


def _cleanup_empty_scratch() -> None:
    if not SCRATCH_TEMP_ROOT.exists():
        return
    for path in sorted(SCRATCH_TEMP_ROOT.rglob("*"), reverse=True):
        if path.is_dir():
            path.rmdir()
    SCRATCH_TEMP_ROOT.rmdir()


def _with_generated_candidate(
    root: Path,
    candidate: dict[str, Any],
    callback: Callable[[dict[str, Any]], Any],
) -> Any:
    SCRATCH_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    candidate_path = SCRATCH_TEMP_ROOT / f"l04h-{root.name}-{uuid.uuid4().hex}.json"
    candidate_path.write_text(
        json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    try:
        report, _ = _run_adapter(root, candidate_path)
        return callback(report)
    finally:
        candidate_path.unlink(missing_ok=True)
        _cleanup_empty_scratch()


class L04HPilotProbeMatrixTests(unittest.TestCase):
    maxDiff = None

    def tearDown(self) -> None:
        self.assertEqual(_scratch_files(), [])

    def _assert_scoreable(self, report: dict[str, Any], label: str) -> None:
        self.assertTrue(report["scoreable"], label)
        self.assertEqual(report["candidate_diagnostics"], [], label)
        self.assertEqual(report["integrity_events"], [], label)

    def _assert_only_atom_changed(
        self,
        reference: dict[str, Any],
        mutant: dict[str, Any],
        atom_ref: str,
        expected_delta: Decimal,
    ) -> None:
        self._assert_scoreable(mutant, atom_ref)
        reference_atoms = _atom_reports(reference)
        mutant_atoms = _atom_reports(mutant)
        changed_atoms = [
            key
            for key in reference_atoms
            if _decimal(reference_atoms[key]["raw_points"]) != _decimal(mutant_atoms[key]["raw_points"])
        ]
        self.assertEqual(changed_atoms, [atom_ref])
        reference_components = _component_scores(reference)
        mutant_components = _component_scores(mutant)
        changed_components = [
            key for key in reference_components if reference_components[key] != mutant_components[key]
        ]
        self.assertEqual(changed_components, [atom_ref.split(".", 1)[0]])
        self.assertEqual(
            _decimal(reference_atoms[atom_ref]["raw_points"])
            - _decimal(mutant_atoms[atom_ref]["raw_points"]),
            expected_delta,
        )
        self.assertEqual(_decimal(reference["score"]) - _decimal(mutant["score"]), expected_delta)

    def _run_form_matrix(self, scenario_id: str) -> None:
        root = PACK_ROOT / "Fixtures" / scenario_id
        expected_scores = EXPECTED_SCORES[scenario_id]
        self.assertTrue(root.is_dir(), f"missing L04H root: {root}")
        for probe_name in PERMANENT_PROBES:
            self.assertTrue(
                (root / "oracle" / "probes" / f"{probe_name}.json").is_file(),
                f"missing {scenario_id}/{probe_name}",
            )

        rubric = _load_json(root / "oracle" / "rubric.json")
        validate_rubric(rubric)
        schema = _load_json(root / "inputs" / "output-schema.json")
        validator = Draft202012Validator(schema)
        reference_candidate = _load_json(root / "oracle" / "probes" / "reference.json")

        reports: dict[str, dict[str, Any]] = {}
        outputs: dict[str, bytes] = {}
        for probe_name in PERMANENT_PROBES:
            candidate_path = root / "oracle" / "probes" / f"{probe_name}.json"
            validator.validate(_load_json(candidate_path))
            reports[probe_name], outputs[probe_name] = _run_adapter(root, candidate_path)
            self._assert_scoreable(reports[probe_name], f"{scenario_id}/{probe_name}")

        reference = reports["reference"]
        self.assertEqual(_decimal(reference["score"]), Decimal("100"))
        self.assertGreaterEqual(_decimal(reference["score"]), Decimal("95"))
        self.assertEqual(reference["status"], "PASS")
        self.assertEqual(reference["commitment_violations"], [])

        competent = reports["competent"]
        self.assertEqual(_decimal(competent["score"]), expected_scores["competent"])
        self.assertGreaterEqual(_decimal(competent["score"]), Decimal("85"))
        self.assertGreater(_decimal(competent["score"]), _decimal(competent["thresholds"]["pass"]))

        vacuous = reports["vacuous"]
        self.assertEqual(_decimal(vacuous["score"]), Decimal("0"))
        self.assertLessEqual(_decimal(vacuous["score"]), Decimal("10"))
        self.assertEqual(vacuous["commitment_violations"], [])
        self.assertEqual(vacuous["status"], "FAIL")

        decoy = reports["decoy"]
        self.assertEqual(_decimal(decoy["score"]), expected_scores["decoy"])
        self.assertGreaterEqual(_decimal(decoy["score"]), Decimal("30"))
        self.assertLessEqual(_decimal(decoy["score"]), Decimal("70"))
        self.assertLess(_decimal(decoy["score"]), _decimal(decoy["thresholds"]["pass"]))
        self.assertEqual(decoy["commitment_violations"], [])

        self.assertEqual(_score_surface(reports["alternate-valid"]), _score_surface(reference))
        self.assertEqual(_score_surface(reports["paraphrase"]), _score_surface(reference))

        overclaim = reports["overclaim"]
        self.assertEqual(overclaim["status"], "FAIL-COMMITMENT")
        self.assertEqual(_decimal(overclaim["score"]), Decimal("40"))
        self.assertEqual(_decimal(overclaim["raw_score"]), Decimal("96"))
        self.assertEqual(
            overclaim["commitment_violations"],
            [{"atom_ref": "release-gate.migration-clearance", "wrong_present_count": 1}],
        )

        atoms = _all_atoms(rubric)
        reference_atoms = _atom_reports(reference)
        case_atoms = [(component_id, atom) for component_id, atom in atoms if atom["type"] == "case_fraction"]
        for component_id, atom in case_atoms:
            consumer_id = atom["id"]
            atom_ref = f"{component_id}.{consumer_id}"
            declared_points = _decimal(reference_atoms[atom_ref]["max_points"])
            deleted = deepcopy(reference_candidate)
            del deleted[component_id][consumer_id]
            validator.validate(deleted)
            mutant = _with_generated_candidate(root, deleted, lambda report: report)
            self._assert_only_atom_changed(reference, mutant, atom_ref, declared_points)

        emptied_set = deepcopy(reference_candidate)
        emptied_set["breaking_change_ids"] = []
        validator.validate(emptied_set)
        mutant = _with_generated_candidate(root, emptied_set, lambda report: report)
        self._assert_only_atom_changed(
            reference,
            mutant,
            "breaking-changes.breaking-set",
            _decimal(reference_atoms["breaking-changes.breaking-set"]["max_points"]),
        )

        gate_deleted = deepcopy(reference_candidate)
        del gate_deleted["release_gate"]["migration_clearance"]
        validator.validate(gate_deleted)

        def _check_gate_deletion(report: dict[str, Any]) -> None:
            self._assert_only_atom_changed(
                reference,
                report,
                "release-gate.migration-clearance",
                _decimal(reference_atoms["release-gate.migration-clearance"]["max_points"]),
            )
            self.assertEqual(report["commitment_violations"], [])
            self.assertNotEqual(report["status"], "FAIL-COMMITMENT")

        _with_generated_candidate(root, gate_deleted, _check_gate_deletion)

        replay = [
            _run_adapter(root, root / "oracle" / "probes" / "reference.json")[1]
            for _ in range(3)
        ]
        self.assertEqual(replay, [outputs["reference"], outputs["reference"], outputs["reference"]])
        self.assertEqual(len({hashlib.sha256(payload).hexdigest() for payload in replay}), 1)

        total_weight = sum(_decimal(component["weight"]) for component in rubric["components"])
        semantic_weight = sum(
            _decimal(component["weight"])
            for component in rubric["components"]
            if component.get("semantic") is True
        )
        max_atom_points = max(
            _decimal(reference_atoms[f"{component_id}.{atom['id']}"]["max_points"])
            for component_id, atom in atoms
        )
        self.assertEqual(total_weight, Decimal("100"))
        self.assertEqual(semantic_weight, Decimal("100"))
        self.assertGreaterEqual(semantic_weight, Decimal("70"))
        self.assertEqual(max_atom_points, expected_scores["max_atom_points"])
        self.assertLessEqual(max_atom_points, Decimal("10"))

        def _deliberate_failure(_: dict[str, Any]) -> None:
            raise AssertionError("deliberate generated-candidate assertion path")

        with self.assertRaisesRegex(AssertionError, "deliberate generated-candidate assertion path"):
            _with_generated_candidate(root, reference_candidate, _deliberate_failure)
        self.assertEqual(_scratch_files(), [])

    def test_base_probe_matrix(self) -> None:
        self._run_form_matrix("V4L04HB-hidden-consumer-contract")

    def test_frontier_probe_matrix(self) -> None:
        self._run_form_matrix("V4L04HF-hidden-consumer-contract")


if __name__ == "__main__":
    unittest.main()
