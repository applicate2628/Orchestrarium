from __future__ import annotations

import hashlib
import json
import re
import sys
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any

import jsonschema
import yaml


PACK_ROOT = Path(__file__).resolve().parents[2]
TOOLING_ROOT = PACK_ROOT / "Tooling"
sys.path.insert(0, str(TOOLING_ROOT))

from v4_rubric.contracts import validate_rubric  # noqa: E402


VISIBLE_IDS = tuple(
    [f"N{index:02d}" for index in range(1, 15)]
    + [f"I{index:02d}" for index in range(1, 7)]
    + [f"F{index:02d}" for index in range(1, 6)]
    + [f"W{index:02d}" for index in range(1, 5)]
    + [f"T{index:02d}" for index in range(1, 3)]
)

MEASUREMENT_IDS = tuple(
    [f"N{index:02d}" for index in range(1, 15)]
    + [f"W{index:02d}" for index in range(1, 5)]
    + [f"T{index:02d}" for index in range(1, 3)]
)

CASE_IDS = tuple(
    [f"I{index:02d}" for index in range(1, 7)]
    + [f"F{index:02d}" for index in range(1, 6)]
)

COMPONENT_IDS = {
    "numeric/logical": tuple(f"N{index:02d}" for index in range(1, 15)),
    "invariants": tuple(f"I{index:02d}" for index in range(1, 7)),
    "falsification": tuple(f"F{index:02d}" for index in range(1, 6)),
    "witness": tuple(f"W{index:02d}" for index in range(1, 5)),
    "target-metric": tuple(f"T{index:02d}" for index in range(1, 3)),
}

COMPONENT_PROFILE = {
    "numeric/logical": Decimal("50"),
    "invariants": Decimal("20"),
    "falsification": Decimal("15"),
    "witness": Decimal("10"),
    "target-metric": Decimal("5"),
}

POINTS = {
    **{f"N{index:02d}": Decimal("3") for index in range(1, 7)},
    **{f"N{index:02d}": Decimal("4") for index in range(7, 15)},
    **{f"I{index:02d}": Decimal("3") for index in range(1, 5)},
    **{f"I{index:02d}": Decimal("4") for index in range(5, 7)},
    **{f"F{index:02d}": Decimal("3") for index in range(1, 6)},
    "W01": Decimal("2"),
    "W02": Decimal("2"),
    "W03": Decimal("3"),
    "W04": Decimal("3"),
    "T01": Decimal("2.5"),
    "T02": Decimal("2.5"),
}

HARD_TAIL_IDS = {
    "N09", "N10", "N11", "N12",
    "W01", "W02", "W03", "W04",
    "T01", "T02",
}

FORM_CONTRACTS = {
    "V4L04B-constraint-casebook": {
        "form": "base",
        "units": {
            **{key: "records" for key in ("N01", "N02", "N03")},
            "N04": "ticks",
            "N05": "items",
            "N06": "evictions",
            "N07": "promotions",
            "N08": "items",
            "N09": "selections",
            "N10": "utility-points",
            "N11": "selections",
            "N12": "cost-credits",
            "N13": "mutations",
            "N14": "items",
            **{f"I{index:02d}": "enum" for index in range(1, 7)},
            "F01": "case-id",
            "F02": "case-id",
            "F03": "case-id",
            "F04": "step-id",
            "F05": "case-id",
            **{f"W{index:02d}": "units" for index in range(1, 5)},
            "T01": "utility-points",
            "T02": "utility-points",
        },
        "step_identities": {"F04": "BL-04"},
        "zero_tolerances": {
            "N01": 6, "N02": 5, "N03": 3, "N04": 3,
            "N05": 2, "N06": 2, "N07": 2, "N08": 2,
            "N09": 3, "N10": 8, "N11": 2, "N12": 4,
            "N13": 2, "N14": 2,
            "W01": 2, "W02": 2, "W03": 2, "W04": 2,
            "T01": 10, "T02": 3,
        },
    },
    "V4L04F-constraint-casebook": {
        "form": "frontier",
        "units": {
            **{key: "records" for key in ("N01", "N02", "N03")},
            "N04": "ticks",
            "N05": "weight-units",
            "N06": "evictions",
            "N07": "items",
            "N08": "promotions",
            "N09": "selections",
            "N10": "utility-points",
            "N11": "selections",
            "N12": "cost-credits",
            "N13": "mutations",
            "N14": "items",
            **{f"I{index:02d}": "enum" for index in range(1, 7)},
            "F01": "case-id",
            "F02": "step-id",
            "F03": "case-id",
            "F04": "case-id",
            "F05": "step-id",
            **{f"W{index:02d}": "units" for index in range(1, 5)},
            "T01": "utility-points",
            "T02": "utility-points",
        },
        "step_identities": {"F02": "FW-03", "F05": "FL-08"},
        "zero_tolerances": {
            "N01": 8, "N02": 6, "N03": 4, "N04": 4,
            "N05": 3, "N06": 3, "N07": 2, "N08": 2,
            "N09": 2, "N10": 8, "N11": 2, "N12": 4,
            "N13": 2, "N14": 2,
            "W01": 2, "W02": 2, "W03": 2, "W04": 2,
            "T01": 10, "T02": 3,
        },
    },
}

EXPECTED_FILES = {
    "README.md",
    "scenario.yaml",
    "inputs/task.md",
    "inputs/sources/casebook.md",
    "inputs/output-schema.json",
    "candidate/README.md",
    "oracle/rubric.json",
    "oracle/reference-answer.json",
    "oracle/ground-truth/index.json",
    "oracle/probes/reference.json",
    "oracle/probes/vacuous.json",
    "oracle/probes/decoy.json",
    "oracle/probes/competent.json",
    "oracle/probes/alternate-valid.json",
    "oracle/probes/paraphrase.json",
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


def _decimal(value: Any) -> Decimal:
    return Decimal(str(value))


def _load_json(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise AssertionError(f"{path} must contain a JSON object")
    return loaded


def _atom_map(rubric: dict[str, Any]) -> dict[str, tuple[dict[str, Any], dict[str, Any]]]:
    return {
        atom["id"]: (component, atom)
        for component in rubric["components"]
        for atom in component["atoms"]
    }


class L04PilotContractTests(unittest.TestCase):
    maxDiff = None

    def _assert_form_contract(self, scenario_id: str) -> None:
        contract = FORM_CONTRACTS[scenario_id]
        root = PACK_ROOT / "Fixtures" / scenario_id
        self.assertTrue(root.is_dir(), f"missing L04 root: {root}")

        actual_files = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(actual_files, EXPECTED_FILES)

        scenario = yaml.safe_load((root / "scenario.yaml").read_text(encoding="utf-8"))
        self.assertEqual(
            scenario,
            {
                "schema_version": "scenarios-v4-ranked-1",
                "scenario_id": scenario_id,
                "lane": "L04",
                "form": contract["form"],
                "candidate_artifact": "candidate/numeric-answer.json",
                "allowed_write_paths": ["candidate/numeric-answer.json"],
            },
        )

        readme = (root / "README.md").read_text(encoding="utf-8")
        for relative in (
            "inputs/task.md",
            "inputs/sources/casebook.md",
            "inputs/output-schema.json",
            "candidate/README.md",
            "verifiers/score.py",
        ):
            self.assertIn(relative, readme)

        task = (root / "inputs" / "task.md").read_text(encoding="utf-8")
        casebook = (root / "inputs" / "sources" / "casebook.md").read_text(encoding="utf-8")
        for item_id in VISIBLE_IDS:
            pattern = rf"(?<![A-Z0-9]){re.escape(item_id)}(?![A-Z0-9])"
            self.assertRegex(task, pattern, f"task does not expose {item_id}")
            self.assertRegex(casebook, pattern, f"casebook does not expose {item_id}")
        for phrase in ("half-open", "least-to-most-recent", "lexicographically"):
            self.assertIn(phrase, task.lower())

        schema = _load_json(root / "inputs" / "output-schema.json")
        jsonschema.Draft202012Validator.check_schema(schema)
        self.assertEqual(schema["properties"]["scenario_id"], {"const": scenario_id})
        self.assertEqual(schema["required"], ["scenario_id", "measurements", "cases"])
        self.assertFalse(schema["additionalProperties"])
        for collection_name, expected_ids in (
            ("measurements", MEASUREMENT_IDS),
            ("cases", CASE_IDS),
        ):
            collection_schema = schema["properties"][collection_name]
            self.assertEqual(tuple(collection_schema["properties"]), expected_ids)
            self.assertFalse(collection_schema["additionalProperties"])
            self.assertNotIn("required", collection_schema)
            for item_id, cell_schema in collection_schema["properties"].items():
                self.assertEqual(cell_schema["required"], ["value", "unit"], item_id)
                self.assertFalse(cell_schema["additionalProperties"], item_id)
                self.assertEqual(cell_schema["properties"]["value"]["oneOf"][0], {"type": "number"})
                self.assertEqual(
                    cell_schema["properties"]["value"]["oneOf"][1],
                    {"type": "string", "minLength": 1, "maxLength": 64},
                )
                self.assertEqual(
                    cell_schema["properties"]["unit"],
                    {"type": "string", "minLength": 1, "maxLength": 32},
                )

        candidate_readme = (root / "candidate" / "README.md").read_text(encoding="utf-8")
        self.assertIn("candidate/numeric-answer.json", candidate_readme)
        self.assertIn("inputs/output-schema.json", candidate_readme)

        expected_adapter = f'''from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACK_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PACK_ROOT / "Tooling"))

from v4_rubric.cli import run_cli  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Score {scenario_id} deterministically.")
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    return run_cli(ROOT, args.candidate, args.json_out)


if __name__ == "__main__":
    raise SystemExit(main())
'''
        self.assertEqual((root / "verifiers" / "score.py").read_text(encoding="utf-8"), expected_adapter)

        rubric = _load_json(root / "oracle" / "rubric.json")
        validate_rubric(rubric)
        self.assertEqual(rubric["schema_version"], "v4-rubric-1")
        self.assertEqual(rubric["scenario_id"], scenario_id)
        self.assertEqual(rubric["candidate_artifact"], "numeric-answer.json")
        self.assertEqual(rubric["integrity_events"], [])
        self.assertEqual(
            {component["id"]: _decimal(component["weight"]) for component in rubric["components"]},
            COMPONENT_PROFILE,
        )
        self.assertTrue(all(component.get("semantic") is True for component in rubric["components"]))
        self.assertEqual(sum(COMPONENT_PROFILE.values()), Decimal("100"))

        atoms = _atom_map(rubric)
        self.assertEqual(tuple(atoms), VISIBLE_IDS)
        self.assertEqual(len(atoms), 31)
        self.assertEqual(max(POINTS.values()), Decimal("4"))

        ground_truth = _load_json(root / "oracle" / "ground-truth" / "index.json")
        self.assertEqual(ground_truth["scenario_id"], scenario_id)
        self.assertEqual(tuple(ground_truth["items"]), VISIBLE_IDS)
        hard_tail_ids = {
            item_id
            for item_id, item in ground_truth["items"].items()
            if item["tier"] == "hard-tail"
        }
        self.assertEqual(hard_tail_ids, HARD_TAIL_IDS)
        self.assertEqual(
            sum(POINTS[item_id] for item_id in hard_tail_ids),
            Decimal("31"),
        )
        for item_id, expected in contract["step_identities"].items():
            item = ground_truth["items"][item_id]
            self.assertEqual(item["expected"], expected, item_id)
            self.assertEqual(item["unit"], "step-id", item_id)
        reference = _load_json(root / "oracle" / "reference-answer.json")
        self.assertEqual(reference, _load_json(root / "oracle" / "probes" / "reference.json"))
        self.assertEqual(reference["scenario_id"], scenario_id)
        self.assertEqual(tuple(reference["measurements"]), MEASUREMENT_IDS)
        self.assertEqual(tuple(reference["cases"]), CASE_IDS)
        jsonschema.Draft202012Validator(schema).validate(reference)

        competent = _load_json(root / "oracle" / "probes" / "competent.json")
        jsonschema.Draft202012Validator(schema).validate(competent)
        self.assertEqual(competent["scenario_id"], scenario_id)
        self.assertEqual(set(competent["measurements"]), set(MEASUREMENT_IDS))
        self.assertEqual(set(competent["cases"]), set(CASE_IDS))
        self.assertNotEqual(competent.get("narrative"), reference.get("narrative"))
        forbidden_competent_keys = {
            "expected", "weight", "points", "zero_tolerance", "full_tolerance",
            "tier", "dependency", "logical_dependency", "reasoning_target", "oracle",
        }
        competent_keys = set()
        stack: list[Any] = [competent]
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                competent_keys.update(value)
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)
        self.assertEqual(competent_keys & forbidden_competent_keys, set())

        for item_id in VISIBLE_IDS:
            component, atom = atoms[item_id]
            item = ground_truth["items"][item_id]
            expected_component = next(
                component_id for component_id, ids in COMPONENT_IDS.items() if item_id in ids
            )
            expected_primitive = "numeric" if item_id.startswith(("N", "W", "T")) else "case_fraction"
            self.assertEqual(component["id"], expected_component, item_id)
            self.assertEqual(item["component"], expected_component, item_id)
            self.assertEqual(item["primitive"], expected_primitive, item_id)
            self.assertEqual(atom["type"], expected_primitive, item_id)
            self.assertEqual(_decimal(atom["weight"]), POINTS[item_id], item_id)
            self.assertEqual(_decimal(item["points"]), POINTS[item_id], item_id)
            self.assertEqual(item["unit"], contract["units"][item_id], item_id)
            collection_name = "measurements" if item_id in MEASUREMENT_IDS else "cases"
            self.assertEqual(reference[collection_name][item_id]["value"], item["expected"], item_id)
            self.assertEqual(reference[collection_name][item_id]["unit"], item["unit"], item_id)
            self.assertIn(item["tier"], {"easy", "easy-medium", "medium", "hard", "hard-tail"})
            self.assertIsInstance(item["logical_dependency"], str)
            self.assertTrue(item["logical_dependency"])
            self.assertIsInstance(item["reasoning_target"], str)
            self.assertTrue(item["reasoning_target"])

            if expected_primitive == "numeric":
                self.assertEqual(atom["candidate_path"], f"measurements.{item_id}", item_id)
                self.assertEqual(atom["expected"], item["expected"], item_id)
                self.assertEqual(atom["unit"], item["unit"], item_id)
                self.assertEqual(_decimal(atom["full_tolerance"]), Decimal("0"), item_id)
                self.assertEqual(
                    _decimal(atom["zero_tolerance"]),
                    _decimal(contract["zero_tolerances"][item_id]),
                    item_id,
                )
                self.assertEqual(
                    _decimal(item["zero_tolerance"]),
                    _decimal(contract["zero_tolerances"][item_id]),
                    item_id,
                )
                self.assertNotIn("numeric_string_equivalence", atom)
            else:
                self.assertEqual(atom["candidate_path"], "cases", item_id)
                self.assertEqual(atom["id_field"], "item_id", item_id)
                self.assertEqual(atom["value_field"], "value", item_id)
                self.assertEqual(atom["expected"], {item_id: item["expected"]}, item_id)
                self.assertEqual(atom.get("case_weights"), {item_id: 1}, item_id)
                self.assertTrue(atom["casefold_ids"], item_id)
                self.assertTrue(atom["casefold_values"], item_id)
                if isinstance(item["expected"], (int, float)) and not isinstance(item["expected"], bool):
                    self.assertTrue(atom["numeric_string_equivalence"], item_id)
                else:
                    self.assertNotIn("numeric_string_equivalence", atom)
                self.assertIsNone(item["zero_tolerance"], item_id)

        for component in rubric["components"]:
            self.assertEqual(
                sum(_decimal(atom["weight"]) for atom in component["atoms"]),
                _decimal(component["weight"]),
                component["id"],
            )

        normalized_collection_paths = {
            atom["candidate_path"]
            for _, atom in atoms.values()
            if atom["type"] == "case_fraction"
        }
        self.assertEqual(normalized_collection_paths, {"cases"})
        numeric_paths = {
            atom["candidate_path"]
            for _, atom in atoms.values()
            if atom["type"] == "numeric"
        }
        self.assertEqual(numeric_paths, {f"measurements.{item_id}" for item_id in MEASUREMENT_IDS})
        for normalized_path in normalized_collection_paths:
            self.assertFalse(
                any(
                    numeric_path == normalized_path or numeric_path.startswith(f"{normalized_path}.")
                    for numeric_path in numeric_paths
                )
            )

        allowed_identity_keys = set(VISIBLE_IDS)
        rubric_identity_keys = {
            item_id
            for item_id, (_, atom) in atoms.items()
            if atom["candidate_path"] == f"measurements.{item_id}"
            or set(atom.get("expected", {})) == {item_id}
        }
        self.assertEqual(rubric_identity_keys, allowed_identity_keys)

    def test_base_contract(self) -> None:
        self._assert_form_contract("V4L04B-constraint-casebook")

    def test_frontier_contract(self) -> None:
        self._assert_form_contract("V4L04F-constraint-casebook")

    def test_frozen_hashes(self) -> None:
        for relative, expected in FROZEN_HASHES.items():
            path = PACK_ROOT / relative
            self.assertTrue(path.is_file(), f"missing frozen file: {path}")
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), expected, relative)


if __name__ == "__main__":
    unittest.main()
