#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the S20 platform bundle shape, start state, or completed run."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--bundle-root",
        type=Path,
        default=default_root,
        help="Path to the S20 bundle root.",
    )
    parser.add_argument(
        "--bundle-shape-only",
        action="store_true",
        help="Validate only the bundle contract and metadata.",
    )
    parser.add_argument(
        "--expect-start-state",
        action="store_true",
        help="Validate that the bundled candidate root still exhibits the intended failures.",
    )
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def parse_simple_yaml(path: Path):
    parsed = {}
    current_list_key = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            if current_list_key is None:
                raise ValueError(f"List item without active key in {path}")
            parsed.setdefault(current_list_key, []).append(line[4:])
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_list_key = None
        if value == "":
            parsed[key] = []
            current_list_key = key
        elif value == "[]":
            parsed[key] = []
        else:
            parsed[key] = value.strip('"')

    return parsed


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


def sha256_path(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def run_validation_script(bundle_root: Path, contract, extra_args=None):
    extra_args = extra_args or []
    script_path = bundle_root / contract["validation_script_relative_path"]
    workdir = bundle_root / contract["validation_workdir"]
    argv = [sys.executable, str(script_path), *extra_args]
    return subprocess.run(
        argv,
        cwd=workdir,
        capture_output=True,
        text=True,
        check=False,
    )


def check_bundle_shape(bundle_root: Path, contract, errors):
    actual_entries = sorted(path.name for path in bundle_root.iterdir())
    expected_entries = sorted(contract["required_top_level_entries"])
    require(
        actual_entries == expected_entries,
        "Top-level bundle entries do not match the required six-entry contract",
        errors,
    )

    for entry in contract["required_top_level_entries"]:
        require((bundle_root / entry).exists(), f"Missing top-level entry: {entry}", errors)

    for entry in contract["required_bundle_files"]:
        require((bundle_root / entry).exists(), f"Missing bundle file: {entry}", errors)

    scenario_path = bundle_root / "scenario.yaml"
    require(scenario_path.exists(), "Missing scenario.yaml", errors)
    if scenario_path.exists():
        keys = top_level_yaml_keys(scenario_path)
        require(
            keys == contract["scenario_yaml_fields"],
            "scenario.yaml fields do not match the required contract order exactly",
            errors,
        )
        parsed = parse_simple_yaml(scenario_path)
        require(
            parsed == contract["expected_scenario"],
            "scenario.yaml values do not match the accepted S20 contract",
            errors,
        )

    for path_str in contract["editable_candidate_files"]:
        require((bundle_root / path_str).exists(), f"Missing editable candidate file: {path_str}", errors)

    for path_str in contract["scope_guard_roots"]:
        require((bundle_root / path_str).exists(), f"Missing scope guard root: {path_str}", errors)


def check_protected_candidate_files(bundle_root: Path, contract, errors):
    for relative_path, expected_hash in contract["protected_candidate_hashes"].items():
        path = bundle_root / relative_path
        require(path.exists(), f"Missing protected candidate file: {relative_path}", errors)
        if path.exists():
            actual_hash = sha256_path(path)
            require(
                actual_hash == expected_hash,
                f"Protected candidate file changed outside allowed scope: {relative_path}",
                errors,
            )


def check_start_state(bundle_root: Path, contract, errors):
    check_protected_candidate_files(bundle_root, contract, errors)
    if errors:
        return

    result = run_validation_script(bundle_root, contract, ["--emit-failure-ids"])
    combined_output = "\n".join(
        part for part in [result.stdout.strip(), result.stderr.strip()] if part
    ).strip()
    require(
        result.returncode == 0,
        f"Unable to inspect the bundled start state: {combined_output or 'no output'}",
        errors,
    )
    if result.returncode != 0:
        return

    actual_failures = sorted(
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    )
    expected_failures = sorted(contract["expected_start_state_failures"])
    require(
        actual_failures == expected_failures,
        f"Expected start-state failures {expected_failures}, found {actual_failures}",
        errors,
    )


def check_completed_run(bundle_root: Path, contract, errors):
    check_protected_candidate_files(bundle_root, contract, errors)
    if errors:
        return

    result = run_validation_script(bundle_root, contract)
    combined_output = "\n".join(
        part for part in [result.stdout.strip(), result.stderr.strip()] if part
    ).strip()
    require(
        result.returncode == 0,
        f"Local validation command failed: {combined_output or 'no output'}",
        errors,
    )
    if result.returncode == 0:
        require(
            contract["required_validation_output"] in combined_output,
            "Local validation output does not report PASS",
            errors,
        )


def main():
    args = parse_args()
    bundle_root = args.bundle_root.resolve()
    errors = []

    if not bundle_root.exists():
        print(f"Bundle root does not exist: {bundle_root}", file=sys.stderr)
        return 1

    contract = load_json(bundle_root / "oracle" / "platform-contract.json")
    check_bundle_shape(bundle_root, contract, errors)

    if not args.bundle_shape_only:
        if args.expect_start_state:
            check_start_state(bundle_root, contract, errors)
        else:
            check_completed_run(bundle_root, contract, errors)

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

    print(f"S20 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
