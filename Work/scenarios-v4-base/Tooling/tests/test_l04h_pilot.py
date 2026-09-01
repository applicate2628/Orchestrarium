from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
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
    "V4L04HB-hidden-consumer-contract": {
        "form": "base",
        "consumer_count": 16,
        "change_count": 10,
        "points": {"verdict": Decimal("2.5"), "cause": Decimal("1.5"), "fix": Decimal("1.5"),
                   "set": Decimal("8"), "gate": Decimal("4")},
        "fix_menu_size": 8,
        "breaking_count": 6,
    },
    "V4L04HF-hidden-consumer-contract": {
        "form": "frontier",
        "consumer_count": 24,
        "change_count": 12,
        "points": {"verdict": Decimal("2"), "cause": Decimal("1"), "fix": Decimal("0.75"),
                   "set": Decimal("6"), "gate": Decimal("4")},
        "fix_menu_size": 9,
        "breaking_count": 8,
    },
}

EXPECTED_FILES = {
    "README.md",
    "scenario.yaml",
    "inputs/task.md",
    "inputs/output-schema.json",
    "inputs/sources/changelog.md",
    "inputs/sources/consumers.md",
    "inputs/sources/provider/relaycfg_v1.py",
    "inputs/sources/provider/relaycfg_v2.py",
    "inputs/sources/tests/test_migration_visible.py",
    "candidate/README.md",
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
    "verifiers/score.py",
}

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


def _load_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return loaded


def _atom_map(rubric: dict[str, Any]) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    return {
        f"{component['id']}.{atom['id']}": (component, atom)
        for component in rubric["components"]
        for atom in component["atoms"]
    }


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


class L04HPilotContractTests(unittest.TestCase):
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
        self.assertEqual(scenario["lane"], "L04H")
        self.assertEqual(scenario["form"], contract["form"])
        self.assertEqual(scenario["candidate_artifact"], "candidate/migration-answer.json")
        self.assertEqual(scenario["allowed_write_paths"], ["candidate/migration-answer.json"])

        index = _load_json(root / "oracle" / "ground-truth" / "index.json")
        self.assertEqual(index["schema_version"], "l04h-ground-truth-1")
        self.assertEqual(index["scenario_id"], scenario_id)
        self.assertEqual(index["form"], contract["form"])

        consumer_ids = sorted(index["consumers"])
        self.assertEqual(len(consumer_ids), contract["consumer_count"])
        change_ids = index["change_ids"]
        self.assertEqual(len(change_ids), contract["change_count"])
        fix_menu = index["fix_menu"]
        self.assertEqual(len(fix_menu), contract["fix_menu_size"])
        breaking = index["breaking_change_ids"]
        self.assertEqual(len(breaking), contract["breaking_count"])
        self.assertEqual(breaking, sorted(breaking))
        self.assertTrue(set(breaking) <= set(change_ids))
        self.assertEqual(index["migration_clearance"], "block")

        # Visible-anchor discipline: every scored identity is printed in the
        # visible sources exactly as the rubric expects it.
        consumers_text = (root / "inputs" / "sources" / "consumers.md").read_text(encoding="utf-8")
        visible_consumers = re.findall(r"^## (CONS-\d{2}) ", consumers_text, flags=re.MULTILINE)
        self.assertEqual(sorted(visible_consumers), consumer_ids)
        changelog_text = (root / "inputs" / "sources" / "changelog.md").read_text(encoding="utf-8")
        for change_id in change_ids:
            self.assertIn(f"`{change_id}`", changelog_text)
        task_text = (root / "inputs" / "task.md").read_text(encoding="utf-8")
        for fix_id in fix_menu:
            self.assertIn(f"`{fix_id}`", task_text)

        # Ground-truth vocabulary discipline.
        break_count = 0
        for consumer_id in consumer_ids:
            entry = index["consumers"][consumer_id]
            self.assertIn(entry["verdict"], ("break", "safe"), consumer_id)
            if entry["verdict"] == "break":
                break_count += 1
                self.assertIn(entry["cause"], change_ids, consumer_id)
                self.assertIn(entry["cause"], breaking, consumer_id)
                self.assertIn(entry["fix"], fix_menu, consumer_id)
                self.assertNotEqual(entry["fix"], "FIX-NONE", consumer_id)
            else:
                self.assertEqual(entry["cause"], "none", consumer_id)
                self.assertEqual(entry["fix"], "FIX-NONE", consumer_id)
        self.assertGreater(break_count, 0)
        self.assertLess(break_count, len(consumer_ids))
        self.assertEqual(
            sorted({index["consumers"][cid]["cause"] for cid in consumer_ids} - {"none"}),
            breaking,
        )

        rubric = _load_json(root / "oracle" / "rubric.json")
        validate_rubric(rubric)
        self.assertEqual(rubric["scenario_id"], scenario_id)
        self.assertEqual(rubric["candidate_artifact"], "migration-answer.json")
        score = rubric["score"]
        self.assertEqual(_decimal(score["pass_threshold"]), Decimal("80"))
        self.assertEqual(_decimal(score["partial_threshold"]), Decimal("50"))
        self.assertEqual(_decimal(score["integrity_penalty_cap"]), Decimal("15"))
        self.assertEqual(_decimal(score["wrong_commitment_cap"]), Decimal("40"))
        self.assertLess(_decimal(score["wrong_commitment_cap"]), _decimal(score["partial_threshold"]))
        self.assertEqual(rubric["integrity_events"], [])

        points = contract["points"]
        components = {component["id"]: component for component in rubric["components"]}
        self.assertEqual(
            set(components),
            {"verdicts", "causes", "fixes", "breaking-changes", "release-gate"},
        )
        for component in rubric["components"]:
            self.assertTrue(component.get("semantic"), component["id"])
            self.assertEqual(
                sum(_decimal(atom["weight"]) for atom in component["atoms"]),
                _decimal(component["weight"]),
                component["id"],
            )
        count = Decimal(contract["consumer_count"])
        self.assertEqual(_decimal(components["verdicts"]["weight"]), points["verdict"] * count)
        self.assertEqual(_decimal(components["causes"]["weight"]), points["cause"] * count)
        self.assertEqual(_decimal(components["fixes"]["weight"]), points["fix"] * count)
        self.assertEqual(_decimal(components["breaking-changes"]["weight"]), points["set"])
        self.assertEqual(_decimal(components["release-gate"]["weight"]), points["gate"])
        total = sum(_decimal(component["weight"]) for component in rubric["components"])
        self.assertEqual(total, Decimal("100"))

        expected_paths = {"verdicts": "verdicts", "causes": "causes", "fixes": "fixes"}
        for component_id, path in expected_paths.items():
            atoms = components[component_id]["atoms"]
            self.assertEqual([atom["id"] for atom in atoms], consumer_ids, component_id)
            for atom in atoms:
                consumer_id = atom["id"]
                entry = index["consumers"][consumer_id]
                expected_value = {
                    "verdicts": entry["verdict"],
                    "causes": entry["cause"],
                    "fixes": entry["fix"],
                }[component_id]
                self.assertEqual(atom["type"], "case_fraction", consumer_id)
                self.assertEqual(atom["candidate_path"], path, consumer_id)
                self.assertEqual(atom["id_field"], "item_id", consumer_id)
                self.assertEqual(atom["value_field"], "value", consumer_id)
                self.assertTrue(atom["casefold_ids"], consumer_id)
                self.assertTrue(atom["casefold_values"], consumer_id)
                self.assertEqual(atom["case_weights"], {consumer_id: 1}, consumer_id)
                self.assertEqual(atom["expected"], {consumer_id: expected_value}, consumer_id)
                self.assertNotIn("commitment", atom, consumer_id)
                self.assertNotIn("numeric_string_equivalence", atom, consumer_id)

        set_atoms = components["breaking-changes"]["atoms"]
        self.assertEqual(len(set_atoms), 1)
        set_atom = set_atoms[0]
        self.assertEqual(set_atom["type"], "set_f1")
        self.assertEqual(set_atom["candidate_path"], "breaking_change_ids")
        self.assertTrue(set_atom["casefold"])
        self.assertEqual(set_atom["expected"], breaking)
        self.assertNotIn("commitment", set_atom)

        gate_atoms = components["release-gate"]["atoms"]
        self.assertEqual(len(gate_atoms), 1)
        gate_atom = gate_atoms[0]
        self.assertEqual(gate_atom["id"], "migration-clearance")
        self.assertEqual(gate_atom["type"], "categorical")
        self.assertEqual(gate_atom["candidate_path"], "release_gate.migration_clearance")
        self.assertTrue(gate_atom["casefold"])
        self.assertEqual(gate_atom["expected"], "block")
        self.assertIs(gate_atom["commitment"], True)
        commitment_atoms = [
            key for key, (_, atom) in _atom_map(rubric).items() if atom.get("commitment") is True
        ]
        self.assertEqual(commitment_atoms, ["release-gate.migration-clearance"])

        # Collection-path partition: the three case collections, the set path,
        # and the gate path are mutually prefix-free.
        scored_paths = ["verdicts", "causes", "fixes", "breaking_change_ids", "release_gate.migration_clearance"]
        for left in scored_paths:
            for right in scored_paths:
                if left != right:
                    self.assertFalse(right.startswith(f"{left}."), (left, right))

        schema = _load_json(root / "inputs" / "output-schema.json")
        self.assertEqual(schema["properties"]["scenario_id"]["const"], scenario_id)
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            set(schema["required"]),
            {"scenario_id", "verdicts", "causes", "fixes", "breaking_change_ids", "release_gate"},
        )
        for collection in ("verdicts", "causes", "fixes"):
            collection_schema = schema["properties"][collection]
            self.assertFalse(collection_schema["additionalProperties"], collection)
            self.assertEqual(sorted(collection_schema["properties"]), consumer_ids, collection)
        self.assertEqual(schema["properties"]["breaking_change_ids"]["maxItems"], contract["change_count"])
        self.assertTrue(schema["properties"]["breaking_change_ids"]["uniqueItems"])
        self.assertFalse(schema["properties"]["release_gate"]["additionalProperties"])
        self.assertEqual(list(schema["properties"]["release_gate"]["properties"]), ["migration_clearance"])
        self.assertEqual(schema["properties"]["narrative"]["maxLength"], 4000)

        reference = _load_json(root / "oracle" / "reference-answer.json")
        probe_reference = _load_json(root / "oracle" / "probes" / "reference.json")
        self.assertEqual(reference, probe_reference)
        for consumer_id in consumer_ids:
            entry = index["consumers"][consumer_id]
            self.assertEqual(reference["verdicts"][consumer_id]["value"], entry["verdict"], consumer_id)
            self.assertEqual(reference["causes"][consumer_id]["value"], entry["cause"], consumer_id)
            self.assertEqual(reference["fixes"][consumer_id]["value"], entry["fix"], consumer_id)
        self.assertEqual(sorted(reference["breaking_change_ids"]), breaking)
        self.assertEqual(reference["release_gate"]["migration_clearance"], "block")

        # The visible test suite must be trivially green against the shipped v2.
        completed = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", str(root / "inputs" / "sources" / "tests")],
            capture_output=True,
            check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(
            completed.returncode,
            0,
            f"visible tests not green: {completed.stderr.decode('utf-8', errors='replace')}",
        )

        # Hidden-oracle separation: no oracle or verifier content below inputs/.
        self.assertFalse((root / "inputs" / "oracle").exists())
        for name in ("rubric", "ground-truth", "reference-answer"):
            self.assertNotIn(name, task_text)

    def test_base_contract(self) -> None:
        self._assert_form_contract("V4L04HB-hidden-consumer-contract")

    def test_frontier_contract(self) -> None:
        self._assert_form_contract("V4L04HF-hidden-consumer-contract")

    def test_frozen_hashes(self) -> None:
        for relative, expected in FROZEN_HASHES.items():
            path = PACK_ROOT / relative
            self.assertTrue(path.is_file(), f"missing frozen file: {path}")
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected, relative)


if __name__ == "__main__":
    unittest.main()
