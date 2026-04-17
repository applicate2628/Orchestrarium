#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the S22 geometry bundle shape, start state, or a completed candidate run."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--bundle-root",
        type=Path,
        default=default_root,
        help="Path to the S22 bundle root.",
    )
    parser.add_argument(
        "--bundle-shape-only",
        action="store_true",
        help="Validate only the bundle contract and metadata.",
    )
    parser.add_argument(
        "--expect-start-state",
        action="store_true",
        help="Validate that the bundled candidate root still exhibits the intended failing cases.",
    )
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_simple_yaml(path: Path):
    data = {}
    current_list = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            if current_list is None:
                raise ValueError(f"Unexpected list item in {path}: {line}")
            data[current_list].append(line[4:].strip())
            continue
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if value == "":
            data[key] = []
            current_list = key
        elif value == "[]":
            data[key] = []
            current_list = None
        else:
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            data[key] = value
            current_list = None
    return data


def top_level_yaml_keys(path: Path):
    keys = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith(" ") or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key = line.split(":", 1)[0].strip()
        if key:
            keys.append(key)
    return keys


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def load_contract(bundle_root: Path):
    return load_json(bundle_root / "oracle" / "geometry-contract.json")


def load_truth_table(bundle_root: Path):
    return load_json(bundle_root / "oracle" / "truth-table.json")


def import_candidate_module(bundle_root: Path):
    module_path = bundle_root / "candidate" / "geometry-owned" / "src" / "geometry" / "predicates.py"
    spec = importlib.util.spec_from_file_location("s22_candidate_predicates", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import candidate module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evaluate_cases(bundle_root: Path):
    module = import_candidate_module(bundle_root)
    truth = load_truth_table(bundle_root)
    failures = []

    for case in truth["orientation_cases"]:
        actual = module.orientation(*[tuple(point) for point in case["points"]])
        if actual != case["expected_orientation"]:
            failures.append(case["id"])

    for case in truth["segment_cases"]:
        segment_a = tuple(tuple(point) for point in case["segment_a"])
        segment_b = tuple(tuple(point) for point in case["segment_b"])
        actual = module.segments_intersect(
            segment_a[0],
            segment_a[1],
            segment_b[0],
            segment_b[1],
        )
        if actual != case["expected_intersects"]:
            failures.append(case["id"])

    return failures


def check_bundle_shape(bundle_root: Path, contract, errors):
    for entry in contract["required_top_level_entries"]:
        require((bundle_root / entry).exists(), f"Missing top-level entry: {entry}", errors)

    scenario_path = bundle_root / "scenario.yaml"
    require(scenario_path.exists(), "Missing scenario.yaml", errors)
    if not scenario_path.exists():
        return

    keys = top_level_yaml_keys(scenario_path)
    require(
        keys == contract["scenario_yaml_fields"],
        "scenario.yaml fields do not match the required contract order exactly",
        errors,
    )

    metadata = parse_simple_yaml(scenario_path)
    for key, expected in contract["expected_metadata"].items():
        require(metadata.get(key) == expected, f"scenario.yaml has unexpected {key}", errors)

    for path_str in contract["required_candidate_paths"]:
        require((bundle_root / path_str).exists(), f"Missing required candidate path: {path_str}", errors)

    for path_str in contract["scope_guard_roots"]:
        require((bundle_root / path_str).exists(), f"Missing scope guard root: {path_str}", errors)


def check_start_state(bundle_root: Path, contract, errors):
    failing_ids = evaluate_cases(bundle_root)
    expected = sorted(contract["expected_start_state_failures"])
    actual = sorted(failing_ids)
    require(
        actual == expected,
        f"Expected start-state failures {expected}, found {actual}",
        errors,
    )


def check_completed_run(bundle_root: Path, errors):
    failing_ids = evaluate_cases(bundle_root)
    require(not failing_ids, f"Completed candidate still fails oracle cases: {sorted(failing_ids)}", errors)


def main():
    args = parse_args()
    bundle_root = args.bundle_root.resolve()
    errors = []

    if not bundle_root.exists():
        print(f"Bundle root does not exist: {bundle_root}", file=sys.stderr)
        return 1

    contract = load_contract(bundle_root)
    check_bundle_shape(bundle_root, contract, errors)

    if not args.bundle_shape_only:
        if args.expect_start_state:
            check_start_state(bundle_root, contract, errors)
        else:
            check_completed_run(bundle_root, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.bundle_shape_only:
        mode = "bundle shape"
    elif args.expect_start_state:
        mode = "start state"
    else:
        mode = "completed run"

    print(f"S22 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
