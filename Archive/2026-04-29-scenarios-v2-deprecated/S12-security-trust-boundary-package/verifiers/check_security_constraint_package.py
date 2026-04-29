#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the S12 security-constraint bundle shape or a completed candidate package."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--bundle-root",
        type=Path,
        default=default_root,
        help="Path to the S12 bundle root.",
    )
    parser.add_argument(
        "--bundle-shape-only",
        action="store_true",
        help="Validate only the bundle contract, not a completed candidate run.",
    )
    return parser.parse_args()


def load_contract(bundle_root: Path):
    contract_path = bundle_root / "oracle" / "security-constraint-contract.json"
    return json.loads(contract_path.read_text(encoding="utf-8"))


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


def parse_simple_yaml(path: Path):
    data = {}
    current_list = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith("  - ") and current_list is not None:
            data[current_list].append(raw_line[4:].strip())
            continue
        if raw_line.startswith(" "):
            continue
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            data[key] = []
            current_list = key
            continue
        if value == "[]":
            data[key] = []
        else:
            data[key] = value.strip('"')
        current_list = None
    return data


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def check_bundle_shape(bundle_root: Path, contract, errors):
    for entry in contract["required_top_level_entries"]:
        require((bundle_root / entry).exists(), f"Missing top-level entry: {entry}", errors)

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
        for field, expected in contract["expected_metadata"].items():
            require(
                parsed.get(field) == expected,
                f"scenario.yaml field {field!r} does not match the expected value",
                errors,
            )


def count_numbered_claims(text: str):
    return len(re.findall(r"(?m)^\\d+\\.\\s", text))


def check_completed_package(bundle_root: Path, contract, errors):
    package_path = bundle_root / contract["candidate_file"]
    require(package_path.exists(), f"Missing candidate file: {contract['candidate_file']}", errors)
    if errors:
        return

    package = package_path.read_text(encoding="utf-8")

    require("TODO" not in package, "security-constraint-package.md still contains TODO markers", errors)

    for section in contract["required_sections"]:
        require(section in package, f"Missing package section: {section}", errors)

    for boundary_id in contract["required_boundary_ids"]:
        require(boundary_id in package, f"Missing trust-boundary reference: {boundary_id}", errors)

    for abuse_case_id in contract["required_abuse_case_ids"]:
        require(abuse_case_id in package, f"Missing abuse-case reference: {abuse_case_id}", errors)

    for control_id in contract["required_control_ids"]:
        require(control_id in package, f"Missing control reference: {control_id}", errors)

    for must_fix_id in contract["required_must_fix_ids"]:
        require(must_fix_id in package, f"Missing must-fix reference: {must_fix_id}", errors)

    for verification_id in contract["required_verification_ids"]:
        require(verification_id in package, f"Missing verification reference: {verification_id}", errors)

    for evidence_ref in contract["required_evidence_refs"]:
        require(evidence_ref in package, f"Missing evidence reference: {evidence_ref}", errors)

    claim_count = count_numbered_claims(package)
    require(
        claim_count >= contract["minimum_claim_count"],
        f"Claims section has {claim_count} numbered claims; expected at least {contract['minimum_claim_count']}",
        errors,
    )

    gate_pattern = rf"(?mi)^`?{re.escape(contract['expected_gate_decision'])}`?$"
    require(
        re.search(gate_pattern, package) is not None,
        f"Gate decision is not {contract['expected_gate_decision']}",
        errors,
    )


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
        check_completed_package(bundle_root, contract, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    mode = "bundle shape" if args.bundle_shape_only else "completed package"
    print(f"S12 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
