#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the S14 reliability-constraint bundle shape or a completed package."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--bundle-root", type=Path, default=default_root)
    parser.add_argument("--bundle-shape-only", action="store_true")
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


def check_bundle_shape(bundle_root: Path, contract, errors):
    for entry in contract["required_top_level_entries"]:
        require((bundle_root / entry).exists(), f"Missing top-level entry: {entry}", errors)
    for relative_path in contract["required_bundle_files"]:
        require((bundle_root / relative_path).exists(), f"Missing required file: {relative_path}", errors)

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
        parse_simple_yaml(scenario_path) == contract["required_metadata"],
        "scenario.yaml metadata does not match S14",
        errors,
    )


def check_completed_package(bundle_root: Path, contract, errors):
    package_path = bundle_root / contract["candidate_file"]
    require(package_path.exists(), f"Missing candidate file: {contract['candidate_file']}", errors)
    if errors:
        return
    text = package_path.read_text(encoding="utf-8")
    lower = text.lower()

    for section in contract["required_sections"]:
        require(section in text, f"Missing package section: {section}", errors)
    for term in contract["required_anchor_terms"]:
        require(term in lower, f"Missing required anchor term: {term}", errors)
    for marker in contract["disallowed_markers"]:
        require(marker not in text, f"Disallowed placeholder remains: {marker}", errors)
    claim_count = len(re.findall(r"(?m)^\\d+\\.\\s", text))
    require(
        claim_count >= contract["minimum_claim_count"],
        f"Claims section has {claim_count} numbered claims; expected at least {contract['minimum_claim_count']}",
        errors,
    )
    require(
        contract["expected_gate_decision"] in text,
        f"Package does not contain gate decision {contract['expected_gate_decision']}",
        errors,
    )


def main():
    args = parse_args()
    bundle_root = args.bundle_root.resolve()
    if not bundle_root.exists():
        print(f"Bundle root does not exist: {bundle_root}", file=sys.stderr)
        return 1

    contract = load_json(bundle_root / "oracle" / "reliability-constraint-contract.json")
    errors = []
    check_bundle_shape(bundle_root, contract, errors)
    if not args.bundle_shape_only:
        check_completed_package(bundle_root, contract, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    mode = "bundle shape" if args.bundle_shape_only else "completed package"
    print(f"S14 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
