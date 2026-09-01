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
from typing import Any

import jsonschema


PACK_ROOT = Path(__file__).resolve().parents[2]
SCRATCH_TEMP_ROOT = PACK_ROOT / ".scratch" / "rf12-rerun-2026-07" / "sdd"
TOOLING_ROOT = PACK_ROOT / "Tooling"
sys.path.insert(0, str(TOOLING_ROOT))

from v4_rubric.contracts import validate_rubric  # noqa: E402


PILOT_ROOTS = {
    "V4L09B-pre-pr-review": {
        "root": "Fixtures/V4L09B-pre-pr-review",
        "lane": "L09",
        "form": "base",
        "required_files": [
            "README.md",
            "scenario.yaml",
            "inputs/task.md",
            "inputs/output-schema.json",
            "inputs/sources/source-cards.md",
            "candidate/README.md",
            "oracle/rubric.json",
            "oracle/reference-answer.json",
            "oracle/ground-truth/index.json",
            "verifiers/score.py",
        ],
    },
    "V4L09F-pre-pr-review": {
        "root": "Fixtures/V4L09F-pre-pr-review",
        "lane": "L09",
        "form": "frontier",
        "required_files": [
            "README.md",
            "scenario.yaml",
            "inputs/task.md",
            "inputs/output-schema.json",
            "inputs/sources/source-cards.md",
            "candidate/README.md",
            "oracle/rubric.json",
            "oracle/reference-answer.json",
            "oracle/ground-truth/index.json",
            "verifiers/score.py",
        ],
    },
}

COMPETENT_DERIVED_PROBE = "competent-derived"

LEGACY_PROBES = (
    "reference",
    "vacuous",
    "decoy",
    "wrong-substance",
    "one-atom-deletion",
    "semantic-deletion-20pct",
    "alternate-valid",
    "paraphrase-reordered",
    "extra-false-finding",
    "forbidden-positive-claim",
    "defensible-alternate",
)

PROBES = LEGACY_PROBES + (COMPETENT_DERIVED_PROBE,)

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


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _load_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return loaded


def _run_adapter(root: Path, candidate: Path) -> tuple[dict[str, Any], bytes]:
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    completed = subprocess.run(
        [sys.executable, str(root / "verifiers" / "score.py"), "--candidate", str(candidate)],
        cwd=root,
        check=False,
        capture_output=True,
        env=env,
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"{root.name} adapter failed for {candidate.name}: "
            f"exit={completed.returncode}; stderr={completed.stderr.decode('utf-8', errors='replace')}"
        )
    return json.loads(completed.stdout.decode("utf-8")), completed.stdout


def _component_scores(report: dict[str, Any]) -> dict[str, Decimal]:
    return {component["id"]: _decimal(component["score"]) for component in report["components"]}


def _adjusted_components(report: dict[str, Any]) -> dict[str, Decimal]:
    return {component_id: _decimal(score) for component_id, score in report["adjusted_components"].items()}


def _atom_scores(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    atoms: dict[str, dict[str, Any]] = {}
    for component in report["components"]:
        for atom in component["atoms"]:
            atoms[f"{component['id']}.{atom['id']}"] = atom
    return atoms


def _changed_items(left: dict[str, Decimal], right: dict[str, Decimal]) -> list[str]:
    return sorted(key for key in left if left[key] != right.get(key))


def _score_surface_bytes(report: dict[str, Any]) -> bytes:
    score_surface = {
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
    return json.dumps(score_surface, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _all_atoms(rubric: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    return [
        (component["id"], atom)
        for component in rubric["components"]
        for atom in component["atoms"]
    ]


def _numeric_atom(rubric: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    numeric = [
        (component_id, atom)
        for component_id, atom in _all_atoms(rubric)
        if atom.get("type") == "numeric"
    ]
    if len(numeric) != 1:
        raise AssertionError(f"frontier rubric must contain exactly one numeric atom, found {len(numeric)}")
    return numeric[0]


def _set_path(candidate: dict[str, Any], dotted_path: str, value: Any) -> None:
    parts = dotted_path.split(".")
    target: dict[str, Any] = candidate
    for part in parts[:-1]:
        nested = target.setdefault(part, {})
        if not isinstance(nested, dict):
            raise AssertionError(f"cannot set {dotted_path}: {part} is not an object")
        target = nested
    target[parts[-1]] = value


def _numeric_near_miss_candidate(rubric: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    _, atom = _numeric_atom(rubric)
    expected = _decimal(atom["expected"])
    near_value = expected - Decimal(1)
    candidate = deepcopy(reference)
    _set_path(
        candidate,
        atom["candidate_path"],
        {"value": int(near_value) if near_value == near_value.to_integral() else float(near_value), "unit": atom["unit"]},
    )
    return candidate


def _run_generated_candidate(root: Path, candidate: dict[str, Any]) -> dict[str, Any]:
    SCRATCH_TEMP_ROOT.mkdir(parents=True, exist_ok=True)
    candidate_path = SCRATCH_TEMP_ROOT / f"l09-generated-{root.name}-{uuid.uuid4().hex}.json"
    candidate_path.write_text(
        json.dumps(candidate, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    try:
        report, _ = _run_adapter(root, candidate_path)
        return report
    finally:
        candidate_path.unlink(missing_ok=True)


def _l09_scratch_leftovers() -> list[Path]:
    if not SCRATCH_TEMP_ROOT.exists():
        return []
    return [
        path
        for path in SCRATCH_TEMP_ROOT.rglob("*")
        if path.is_file() and ("l09" in path.name.lower() or "v4l09" in path.name.lower())
    ]


class L09PilotProbeMatrixTests(unittest.TestCase):
    def tearDown(self) -> None:
        self.assertEqual(_l09_scratch_leftovers(), [])

    def test_manifest_static_contract_and_metadata_are_clean(self) -> None:
        manifest_path = PACK_ROOT / "Planning" / "v4-pack-manifest.json"
        manifest_text = manifest_path.read_text(encoding="utf-8")
        manifest = json.loads(manifest_text)
        self.assertEqual(
            manifest["fixtures"],
            [
                {
                    "scenario_id": root_name,
                    "root": expected["root"],
                    "lane": expected["lane"],
                    "form": expected["form"],
                }
                for root_name, expected in PILOT_ROOTS.items()
            ],
        )

        for token in FORBIDDEN_METADATA_TOKENS:
            self.assertNotIn(token, manifest_text.lower(), f"manifest contains {token!r}")

        for root_name, expected in PILOT_ROOTS.items():
            root = PACK_ROOT / expected["root"]
            with self.subTest(root=root_name):
                for relative in expected["required_files"]:
                    self.assertTrue((root / relative).is_file(), f"missing {root_name}/{relative}")
                actual_probes = sorted(path.stem for path in (root / "oracle" / "probes").glob("*.json"))
                self.assertEqual(actual_probes, sorted(PROBES))

                schema = _load_json(root / "inputs" / "output-schema.json")
                jsonschema.Draft202012Validator.check_schema(schema)
                rubric = _load_json(root / "oracle" / "rubric.json")
                validate_rubric(rubric)

                files_to_scan = [
                    path
                    for path in root.rglob("*")
                    if path.is_file() and path.suffix.lower() in {".json", ".md", ".yaml", ".yml"}
                ]
                for path in files_to_scan:
                    lowered = path.read_text(encoding="utf-8").lower()
                    for token in FORBIDDEN_METADATA_TOKENS:
                        self.assertNotIn(
                            token,
                            lowered,
                            f"{path.relative_to(PACK_ROOT)} contains forbidden metadata token {token!r}",
                        )

    def test_probe_matrix_scores_and_deltas_through_thin_adapters(self) -> None:
        for root_name, expected in PILOT_ROOTS.items():
            root = PACK_ROOT / expected["root"]
            with self.subTest(root=root_name):
                rubric = _load_json(root / "oracle" / "rubric.json")
                probe_reports: dict[str, dict[str, Any]] = {}
                probe_bytes: dict[str, bytes] = {}
                for probe_name in PROBES:
                    candidate_path = root / "oracle" / "probes" / f"{probe_name}.json"
                    self.assertTrue(candidate_path.is_file(), f"missing {root_name}/oracle/probes/{probe_name}.json")
                    report, stdout = _run_adapter(root, candidate_path)
                    probe_reports[probe_name] = report
                    probe_bytes[probe_name] = stdout
                    if probe_name in LEGACY_PROBES:
                        self.assertTrue(report["scoreable"], f"{root_name}/{probe_name} must be scoreable")
                        self.assertEqual(report["candidate_diagnostics"], [], f"{root_name}/{probe_name} diagnostics")

                reference = probe_reports["reference"]
                self.assertGreaterEqual(_decimal(reference["score"]), Decimal(95))
                self.assertLessEqual(_decimal(reference["score"]), Decimal(100))
                self.assertEqual(reference["integrity_events"], [])

                vacuous = probe_reports["vacuous"]
                self.assertGreaterEqual(_decimal(vacuous["score"]), Decimal(0))
                self.assertLessEqual(_decimal(vacuous["score"]), Decimal(10))

                decoy = probe_reports["decoy"]
                self.assertGreaterEqual(_decimal(decoy["score"]), Decimal(30))
                self.assertLessEqual(_decimal(decoy["score"]), Decimal(70))
                self.assertLess(_decimal(decoy["score"]), _decimal(decoy["thresholds"]["pass"]))

                wrong_substance = probe_reports["wrong-substance"]
                self.assertLessEqual(_decimal(wrong_substance["score"]), Decimal(40))

                deletion = probe_reports["one-atom-deletion"]
                self.assertNotEqual(deletion["status"], "FAIL-COMMITMENT")
                self.assertEqual(deletion["commitment_violations"], [])
                component_deltas = {
                    component_id: _component_scores(reference)[component_id] - _component_scores(deletion)[component_id]
                    for component_id in _component_scores(reference)
                }
                changed_components = [component_id for component_id, delta in component_deltas.items() if delta != 0]
                self.assertEqual(len(changed_components), 1)
                atom_deltas = {
                    atom_ref: _decimal(_atom_scores(reference)[atom_ref]["raw_points"])
                    - _decimal(_atom_scores(deletion)[atom_ref]["raw_points"])
                    for atom_ref in _atom_scores(reference)
                }
                changed_atoms = [atom_ref for atom_ref, delta in atom_deltas.items() if delta != 0]
                self.assertEqual(len(changed_atoms), 1)
                declared_atom_points = _decimal(_atom_scores(reference)[changed_atoms[0]]["max_points"])
                self.assertEqual(atom_deltas[changed_atoms[0]], declared_atom_points)
                self.assertEqual(_decimal(reference["score"]) - _decimal(deletion["score"]), declared_atom_points)

                semantic = probe_reports["semantic-deletion-20pct"]
                self.assertGreaterEqual(_decimal(semantic["score"]), Decimal(72))
                self.assertLessEqual(_decimal(semantic["score"]), Decimal(84))
                self.assertEqual(_decimal(reference["score"]) - _decimal(semantic["score"]), Decimal(20))

                alternate = probe_reports["alternate-valid"]
                self.assertEqual(alternate["status"], reference["status"])
                self.assertEqual(alternate["integrity_events"], [])
                self.assertEqual(_score_surface_bytes(alternate), _score_surface_bytes(reference))

                paraphrase = probe_reports["paraphrase-reordered"]
                self.assertEqual(_score_surface_bytes(paraphrase), _score_surface_bytes(reference))

                extra_false = probe_reports["extra-false-finding"]
                self.assertEqual(_changed_items(_component_scores(reference), _component_scores(extra_false)), ["findings"])
                reference_atoms = _atom_scores(reference)
                extra_atoms = _atom_scores(extra_false)
                changed_finding_atoms = [
                    atom_ref
                    for atom_ref in reference_atoms
                    if _decimal(reference_atoms[atom_ref]["raw_points"]) != _decimal(extra_atoms[atom_ref]["raw_points"])
                ]
                self.assertEqual(len(changed_finding_atoms), 1)
                changed_atom = changed_finding_atoms[0]
                self.assertTrue(changed_atom.startswith("findings."))
                reference_detail = reference_atoms[changed_atom]["detail"]
                extra_detail = extra_atoms[changed_atom]["detail"]
                self.assertEqual(extra_detail["recall"], reference_detail["recall"])
                self.assertLess(extra_detail["precision"], reference_detail["precision"])
                self.assertLess(extra_detail["f1"], reference_detail["f1"])
                self.assertGreater(extra_detail["unmatched_reported_count"], reference_detail["unmatched_reported_count"])

                integrity = probe_reports["forbidden-positive-claim"]
                self.assertEqual(integrity["status"], "FAIL-INTEGRITY")
                self.assertEqual(len(integrity["integrity_events"]), 1)
                self.assertGreater(_decimal(integrity["penalty"]), Decimal(0))
                self.assertLessEqual(_decimal(integrity["penalty"]), Decimal(15))
                self.assertLess(_decimal(integrity["score"]), _decimal(integrity["thresholds"]["pass"]))

                defensible = probe_reports["defensible-alternate"]
                self.assertNotEqual(defensible["status"], "FAIL-COMMITMENT")
                self.assertEqual(defensible["commitment_violations"], [])
                self.assertGreater(_decimal(defensible["score"]), Decimal(70))
                self.assertGreaterEqual(_decimal(defensible["score"]), Decimal(75))
                self.assertLessEqual(_decimal(defensible["score"]), _decimal(reference["score"]))
                self.assertGreater(_decimal(defensible["score"]), _decimal(defensible["thresholds"]["partial"]))

                competent = probe_reports[COMPETENT_DERIVED_PROBE]
                self.assertEqual(competent["candidate_diagnostics"], [], f"{root_name}/competent-derived diagnostics")
                self.assertTrue(competent["scoreable"], f"{root_name}/competent-derived must be scoreable")
                self.assertEqual(competent["integrity_events"], [], f"{root_name}/competent-derived integrity events")
                self.assertGreaterEqual(_decimal(competent["score"]), Decimal(85))
                self.assertGreater(_decimal(competent["score"]), _decimal(competent["thresholds"]["pass"]))

                replay = [
                    _run_adapter(root, root / "oracle" / "probes" / "reference.json")[1]
                    for _ in range(3)
                ]
                self.assertEqual(len({hashlib.sha256(payload).hexdigest() for payload in replay}), 1)
                self.assertEqual(replay, [probe_bytes["reference"], probe_bytes["reference"], probe_bytes["reference"]])

                if expected["form"] == "frontier":
                    reference_candidate = _load_json(root / "oracle" / "probes" / "reference.json")
                    numeric_ref = f"{_numeric_atom(rubric)[0]}.{_numeric_atom(rubric)[1]['id']}"
                    near_miss = _run_generated_candidate(root, _numeric_near_miss_candidate(rubric, reference_candidate))
                    self.assertNotEqual(near_miss["status"], "FAIL-COMMITMENT")
                    self.assertEqual(near_miss["commitment_violations"], [])
                    self.assertGreater(_decimal(_atom_scores(near_miss)[numeric_ref]["raw_points"]), Decimal(0))
                    self.assertLess(
                        _decimal(_atom_scores(near_miss)[numeric_ref]["raw_points"]),
                        _decimal(_atom_scores(reference)[numeric_ref]["raw_points"]),
                    )

                self.assertEqual(_l09_scratch_leftovers(), [])


if __name__ == "__main__":
    unittest.main()
