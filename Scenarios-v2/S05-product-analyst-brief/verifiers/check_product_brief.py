#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the S05 product-brief bundle shape or a completed brief."
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
    for relative_path in contract["required_bundle_paths"]:
        require((bundle_root / relative_path).exists(), f"Missing required path: {relative_path}", errors)

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
        "scenario.yaml metadata does not match S05",
        errors,
    )


def check_completed_brief(bundle_root: Path, contract, errors):
    brief_path = bundle_root / contract["editable_brief"]
    require(brief_path.exists(), f"Missing candidate file: {contract['editable_brief']}", errors)
    if errors:
        return
    text = brief_path.read_text(encoding="utf-8")
    lower = text.lower()

    for section in contract["required_brief_sections"]:
        require(section in text, f"Missing brief section: {section}", errors)
    for marker in contract["disallowed_markers"]:
        require(marker not in text, f"Disallowed placeholder remains: {marker}", errors)
    for term in contract["required_anchor_terms"]:
        require(term in lower, f"Missing required anchor term: {term}", errors)
    require(
        contract["expected_gate_decision"] in text,
        f"Brief does not contain gate decision {contract['expected_gate_decision']}",
        errors,
    )


def main():
    args = parse_args()
    bundle_root = args.bundle_root.resolve()
    if not bundle_root.exists():
        print(f"Bundle root does not exist: {bundle_root}", file=sys.stderr)
        return 1

    contract = load_json(bundle_root / "oracle" / "product-brief-contract.json")
    errors = []
    check_bundle_shape(bundle_root, contract, errors)
    if not args.bundle_shape_only:
        check_completed_brief(bundle_root, contract, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    mode = "bundle shape" if args.bundle_shape_only else "completed product brief"
    print(f"S05 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
