from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml


PACK_ROOT = Path(__file__).resolve().parents[2]
TOOLING_ROOT = PACK_ROOT / "Tooling"
sys.path.insert(0, str(TOOLING_ROOT))

from v4_rubric.contracts import validate_rubric  # noqa: E402


FORM_CONTRACTS = {
    "V4L04XB-store-buffer-litmus": {
        "form": "base",
        "program_count": 16,
        "observation_count": 32,
        "points": {"verdict": Decimal("2.75"), "set": Decimal("8"), "gate": Decimal("4")},
        "class_counts": {"both": 14, "neither": 10, "b-only": 5, "a-only": 3},
        "divergent_count": 8,
    },
    "V4L04XF-store-buffer-litmus": {
        "form": "frontier",
        "program_count": 20,
        "observation_count": 40,
        "points": {"verdict": Decimal("2.2"), "set": Decimal("8"), "gate": Decimal("4")},
        "class_counts": {"both": 12, "neither": 15, "b-only": 10, "a-only": 3},
        "divergent_count": 12,
    },
}

EXPECTED_FILES = {
    "README.md",
    "scenario.yaml",
    "inputs/task.md",
    "inputs/output-schema.json",
    "inputs/sources/machine-spec.md",
    "inputs/sources/programs.md",
    "candidate/README.md",
    "oracle/rubric.json",
    "oracle/reference-answer.json",
    "oracle/ground-truth/index.json",
    "oracle/ground-truth/reproducer/machines.py",
    "oracle/ground-truth/reproducer/corpus.py",
    "oracle/ground-truth/reproducer/genlib.py",
    "oracle/ground-truth/reproducer/generate.py",
    "oracle/ground-truth/reproducer/test_machines.py",
    "oracle/probes/reference.json",
    "oracle/probes/competent.json",
    "oracle/probes/vacuous.json",
    "oracle/probes/decoy.json",
    "oracle/probes/alternate-valid.json",
    "oracle/probes/paraphrase.json",
    "oracle/probes/overclaim.json",
    "verifiers/score.py",
}

# Derived artifacts that reproducer/generate.py must regenerate byte-identically.
REGENERATED_FILES = (
    "inputs/output-schema.json",
    "inputs/sources/programs.md",
    "oracle/rubric.json",
    "oracle/reference-answer.json",
    "oracle/ground-truth/index.json",
    "oracle/probes/reference.json",
    "oracle/probes/competent.json",
    "oracle/probes/vacuous.json",
    "oracle/probes/decoy.json",
    "oracle/probes/alternate-valid.json",
    "oracle/probes/paraphrase.json",
    "oracle/probes/overclaim.json",
)

FROZEN_HASHES = {
    "Tooling/validate_calibration.py": "6950edc0fe1ff1cbd9eccbc890f84231beef08b5410d3eff5e70a00c16d1fa81",
    "Tooling/v4_rubric/__init__.py": "247cf41ce68359e2d209d2b17c9c3cc64c6f4edcb9b3d8c909329b1ebd36385b",
    "Tooling/v4_rubric/cli.py": "3f4423680842238c7aeebbf6b3656d65d684891ca41bf63aa0bf94093723e408",
    "Tooling/v4_rubric/contracts.py": "1acab8ab8b612fdf4e1afb2321ae4abaa6d43ef04781dd7d6347a95ffbc47300",
    "Tooling/v4_rubric/normalization.py": "75bc22c63ad17aebc4fa0fc6feb322d2cd46353678291e9921664a7a7afb03ca",
    "Tooling/v4_rubric/scoring.py": "fd1c2ad10d75508105c45579d050591f96dbf0a8c4fc7adc07232e60111db8cb",
    "Tooling/v4_rubric/signals.py": "7dba1902144fcbde14a4d8b3f2ed9fa4255d646880fd1ea33c4cf1bcf0b3ca3d",
    "Fixtures/V4C01-source-bound-advice/verifiers/score.py": "a23ddc11d966772a122f3eb4a6e73671adfbe0dec6e3e112bbb3c84df77d03a2",
    "Fixtures/V4C02-numeric-reasoning/verifiers/score.py": "34550a4c35c963053ee0bd6543ca5523831e42bd038cc946bc235ca22fa02b0c",
    "Fixtures/V4C03-implementation-runtime/verifiers/score.py": "f2d7ee3be8ebb6ec7dbfadea7148ae982668981e4db35710d2f4c94961d197b1",
    "Fixtures/V4C04-findings-review/verifiers/score.py": "1d3e85c3dacd5d3efd55f53cbeecd9bfd481b479b696e6434e7887b3e6019ca4",
}

CLASS_VOCABULARY = ("both", "a-only", "b-only", "neither")


def _load_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return loaded


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


class L04XPilotContractTests(unittest.TestCase):
    maxDiff = None

    def _assert_form_contract(self, scenario_id: str) -> None:
        contract = FORM_CONTRACTS[scenario_id]
        root = PACK_ROOT / "Fixtures" / scenario_id
        self.assertTrue(root.is_dir(), f"missing root: {root}")

        present = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        }
        self.assertEqual(present, EXPECTED_FILES, scenario_id)

        scenario = yaml.safe_load((root / "scenario.yaml").read_text(encoding="utf-8"))
        self.assertEqual(scenario["schema_version"], "scenarios-v4-ranked-1")
        self.assertEqual(scenario["scenario_id"], scenario_id)
        self.assertEqual(scenario["lane"], "L04X")
        self.assertEqual(scenario["form"], contract["form"])
        self.assertEqual(scenario["candidate_artifact"], "candidate/litmus-answer.json")
        self.assertEqual(scenario["allowed_write_paths"], ["candidate/litmus-answer.json"])

        rubric = _load_json(root / "oracle" / "rubric.json")
        validate_rubric(rubric)
        self.assertEqual(rubric["scenario_id"], scenario_id)
        self.assertEqual(rubric["candidate_artifact"], "litmus-answer.json")

        index = _load_json(root / "oracle" / "ground-truth" / "index.json")
        self.assertEqual(index["schema_version"], "l04x-ground-truth-1")
        self.assertEqual(index["scenario_id"], scenario_id)
        self.assertEqual(index["form"], contract["form"])
        self.assertEqual(list(index["class_vocabulary"]), list(CLASS_VOCABULARY))

        programs = index["programs"]
        self.assertEqual(len(programs), contract["program_count"])
        observation_classes: dict[str, str] = {}
        divergent_expected = []
        class_counts: dict[str, int] = {}
        for program_id, entry in programs.items():
            self.assertEqual(len(entry["observations"]), 2, program_id)
            program_divergent = False
            for obs_id, obs in entry["observations"].items():
                self.assertTrue(obs_id.startswith(f"{program_id}-O"), obs_id)
                cls = obs["class"]
                self.assertIn(cls, CLASS_VOCABULARY, obs_id)
                # The class MUST be the pure function of the two recorded
                # reachability bits — no hand-set class can disagree.
                expected_cls = {
                    (True, True): "both",
                    (True, False): "a-only",
                    (False, True): "b-only",
                    (False, False): "neither",
                }[(obs["reachable_sb_a"], obs["reachable_sb_b"])]
                self.assertEqual(cls, expected_cls, obs_id)
                if obs["reachable_sc"]:
                    # SC embeds into both machines, so an SC-reachable
                    # observation can only be class "both".
                    self.assertEqual(cls, "both", obs_id)
                observation_classes[obs_id] = cls
                class_counts[cls] = class_counts.get(cls, 0) + 1
                program_divergent = program_divergent or cls in ("a-only", "b-only")
            self.assertEqual(entry["divergent"], program_divergent, program_id)
            if program_divergent:
                divergent_expected.append(program_id)
        self.assertEqual(len(observation_classes), contract["observation_count"])
        self.assertEqual(class_counts, contract["class_counts"])
        self.assertEqual(index["divergent_program_ids"], divergent_expected)
        self.assertEqual(len(divergent_expected), contract["divergent_count"])
        self.assertEqual(index["machines_verdict"], "diverge")

        atoms = {
            f"{component['id']}.{atom['id']}": (component, atom)
            for component in rubric["components"]
            for atom in component["atoms"]
        }
        for obs_id, cls in observation_classes.items():
            component, atom = atoms[f"verdicts.{obs_id}"]
            self.assertEqual(_decimal(atom["weight"]), contract["points"]["verdict"], obs_id)
            self.assertEqual(atom["expected"], {obs_id: cls}, obs_id)
            self.assertEqual(atom["case_weights"], {obs_id: 1}, obs_id)
        component, set_atom = atoms["divergent-programs.divergent-set"]
        self.assertEqual(_decimal(set_atom["weight"]), contract["points"]["set"])
        self.assertEqual(set_atom["expected"], divergent_expected)
        component, gate_atom = atoms["equivalence-gate.machines-verdict"]
        self.assertEqual(_decimal(gate_atom["weight"]), contract["points"]["gate"])
        self.assertEqual(gate_atom["expected"], "diverge")
        self.assertTrue(gate_atom["commitment"])
        self.assertEqual(
            len(atoms), contract["observation_count"] + 2, "one atom per observation + set + gate"
        )

        reference = _load_json(root / "oracle" / "reference-answer.json")
        probe_reference = _load_json(root / "oracle" / "probes" / "reference.json")
        self.assertEqual(reference, probe_reference)
        for obs_id, cls in observation_classes.items():
            self.assertEqual(reference["verdicts"][obs_id]["value"], cls, obs_id)
        self.assertEqual(reference["divergent_program_ids"], divergent_expected)
        self.assertEqual(reference["equivalence_gate"]["machines_verdict"], "diverge")

        # Visible anchors: every program and observation ID appears verbatim
        # in the visible programs listing; the class vocabulary and gate
        # values appear verbatim in the visible task.
        programs_text = (root / "inputs" / "sources" / "programs.md").read_text(encoding="utf-8")
        for program_id in programs:
            self.assertIn(f"## {program_id}", programs_text)
        for obs_id in observation_classes:
            self.assertIn(f"`{obs_id}`", programs_text)
        task_text = (root / "inputs" / "task.md").read_text(encoding="utf-8")
        for token in CLASS_VOCABULARY + ("agree", "diverge", "divergent_program_ids"):
            self.assertIn(token, task_text)

        # Hidden-oracle separation: nothing under inputs/ names the oracle.
        self.assertFalse((root / "inputs" / "oracle").exists())
        for name in ("rubric", "ground-truth", "reference-answer"):
            self.assertNotIn(name, task_text)
            self.assertNotIn(name, programs_text)
        spec_text = (root / "inputs" / "sources" / "machine-spec.md").read_text(encoding="utf-8")
        for name in ("rubric", "ground-truth", "reference-answer", "reproducer"):
            self.assertNotIn(name, spec_text)
        # The visible inputs never state any expected class for a listed
        # observation: the only "-only" tokens under inputs/ are the two
        # vocabulary definitions in task.md.
        self.assertEqual(programs_text.count("a-only") + programs_text.count("b-only"), 0)

    def _assert_reproducer_regenerates(self, scenario_id: str) -> None:
        root = PACK_ROOT / "Fixtures" / scenario_id
        out_dir = Path(tempfile.mkdtemp(prefix="l04x-regen-"))
        try:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(root / "oracle" / "ground-truth" / "reproducer" / "generate.py"),
                    "--out",
                    str(out_dir),
                ],
                capture_output=True,
                check=False,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            self.assertEqual(
                completed.returncode,
                0,
                f"generate.py failed: {completed.stderr.decode('utf-8', errors='replace')}",
            )
            for relative in REGENERATED_FILES:
                shipped = (root / relative).read_bytes()
                regenerated = (out_dir / relative).read_bytes()
                self.assertEqual(shipped, regenerated, f"{scenario_id}/{relative} drifted")
        finally:
            shutil.rmtree(out_dir, ignore_errors=True)

    def _assert_reproducer_validation_matrix(self, scenario_id: str) -> None:
        reproducer = PACK_ROOT / "Fixtures" / scenario_id / "oracle" / "ground-truth" / "reproducer"
        completed = subprocess.run(
            [sys.executable, "-m", "unittest", "test_machines", "-v"],
            cwd=reproducer,
            capture_output=True,
            check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        stderr = completed.stderr.decode("utf-8", errors="replace")
        self.assertEqual(completed.returncode, 0, f"validation matrix failed: {stderr}")
        self.assertIn("Ran 16 tests", stderr)

    def test_base_contract(self) -> None:
        self._assert_form_contract("V4L04XB-store-buffer-litmus")

    def test_frontier_contract(self) -> None:
        self._assert_form_contract("V4L04XF-store-buffer-litmus")

    def test_base_reproducer_regenerates(self) -> None:
        self._assert_reproducer_regenerates("V4L04XB-store-buffer-litmus")

    def test_frontier_reproducer_regenerates(self) -> None:
        self._assert_reproducer_regenerates("V4L04XF-store-buffer-litmus")

    def test_base_reproducer_validation_matrix(self) -> None:
        self._assert_reproducer_validation_matrix("V4L04XB-store-buffer-litmus")

    def test_frontier_reproducer_validation_matrix(self) -> None:
        self._assert_reproducer_validation_matrix("V4L04XF-store-buffer-litmus")

    def test_frozen_hashes(self) -> None:
        for relative, expected in FROZEN_HASHES.items():
            path = PACK_ROOT / relative
            self.assertTrue(path.is_file(), f"missing frozen file: {path}")
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected, relative)


if __name__ == "__main__":
    unittest.main()
