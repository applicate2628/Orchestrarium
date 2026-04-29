#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the S18 model-view bundle shape, start state, or a completed candidate run."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--bundle-root", type=Path, default=default_root)
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_simple_yaml(path: Path):
    data = {}
    current_key = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            data.setdefault(current_key, []).append(line[4:].strip())
            continue
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip()
        value = raw_value.strip()
        if value == "":
            data[key] = []
            current_key = key
        elif value == "[]":
            data[key] = []
            current_key = None
        else:
            data[key] = value.strip('"')
            current_key = None
    return data


def top_level_yaml_keys(path: Path):
    keys = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith(" ") or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        keys.append(line.split(":", 1)[0].strip())
    return keys


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def import_candidate_module(bundle_root: Path):
    module_path = (
        bundle_root
        / "candidate"
        / "model-view-owned"
        / "src"
        / "model_view_owned"
        / "selection_model.py"
    )
    spec = importlib.util.spec_from_file_location("s18_candidate_model_view", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import candidate module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_case_pairs(bundle_root: Path):
    packet = load_json(bundle_root / "inputs" / "selection-cases.json")
    oracle = load_json(bundle_root / "oracle" / "model-view-oracle.json")
    expected_by_id = {case["id"]: case["expected_state"] for case in oracle["cases"]}
    return [
        {
          "id": case["id"],
          "rows": case["rows"],
          "selected_id": case["selected_id"],
          "expected_state": expected_by_id[case["id"]],
        }
        for case in packet["cases"]
    ]


def evaluate_cases(bundle_root: Path):
    module = import_candidate_module(bundle_root)
    failures = []
    for case in load_case_pairs(bundle_root):
        actual = module.build_view_state(case["rows"], case["selected_id"])
        if actual != case["expected_state"]:
            failures.append(case["id"])
    return failures


def check_bundle_shape(bundle_root: Path, contract, errors):
    actual_entries = sorted(path.name for path in bundle_root.iterdir())
    require(
        actual_entries == sorted(contract["required_top_level_entries"]),
        "Top-level bundle entries do not match the required six-entry contract",
        errors,
    )
    scenario_path = bundle_root / "scenario.yaml"
    require(scenario_path.exists(), "Missing scenario.yaml", errors)
    if not scenario_path.exists():
        return
    require(
        top_level_yaml_keys(scenario_path) == contract["scenario_yaml_fields"],
        "scenario.yaml fields do not match the required contract order exactly",
        errors,
    )
    require(
        parse_simple_yaml(scenario_path) == contract["expected_metadata"],
        "scenario.yaml metadata does not match S18",
        errors,
    )
    for path_str in contract["required_candidate_paths"]:
        require((bundle_root / path_str).exists(), f"Missing required candidate path: {path_str}", errors)
    for path_str in contract["scope_guard_roots"]:
        require((bundle_root / path_str).exists(), f"Missing scope guard root: {path_str}", errors)


def run_direct_tests(bundle_root: Path, errors):
    workspace_root = bundle_root / "candidate" / "model-view-owned"
    result = subprocess.run(
        [sys.executable, "tests/test_selection_model.py"],
        cwd=workspace_root,
        capture_output=True,
        text=True,
        check=False,
    )
    output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part).strip()
    require(result.returncode == 0, f"Direct model-view tests failed: {output or 'no output'}", errors)


def main():
    args = parse_args()
    bundle_root = args.bundle_root.resolve()
    if not bundle_root.exists():
        print(f"Bundle root does not exist: {bundle_root}", file=sys.stderr)
        return 1

    errors = []
    contract = load_json(bundle_root / "oracle" / "model-view-contract.json")
    check_bundle_shape(bundle_root, contract, errors)

    if not args.bundle_shape_only:
        if args.expect_start_state:
            require(
                sorted(evaluate_cases(bundle_root)) == sorted(contract["expected_start_state_failures"]),
                f"Expected start-state failures {sorted(contract['expected_start_state_failures'])}, found {sorted(evaluate_cases(bundle_root))}",
                errors,
            )
        else:
            run_direct_tests(bundle_root, errors)
            if not errors:
                require(
                    not evaluate_cases(bundle_root),
                    f"Completed candidate still fails oracle cases: {sorted(evaluate_cases(bundle_root))}",
                    errors,
                )

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
    print(f"S18 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
