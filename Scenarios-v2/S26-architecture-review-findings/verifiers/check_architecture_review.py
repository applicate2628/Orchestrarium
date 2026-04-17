#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the S26 architecture-review bundle shape or a completed review report."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--bundle-root",
        type=Path,
        default=default_root,
        help="Path to the S26 bundle root.",
    )
    parser.add_argument(
        "--bundle-shape-only",
        action="store_true",
        help="Validate only the bundle contract, not a completed candidate run.",
    )
    return parser.parse_args()


def load_contract(bundle_root: Path):
    contract_path = bundle_root / "oracle" / "review-contract.json"
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


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def check_bundle_shape(bundle_root: Path, contract, errors):
    for entry in contract["required_top_level_entries"]:
        require((bundle_root / entry).exists(), f"Missing top-level entry: {entry}", errors)

    for relative_path in contract["required_bundle_paths"]:
        require(
            (bundle_root / relative_path).exists(),
            f"Missing required bundle path: {relative_path}",
            errors,
        )

    scenario_path = bundle_root / "scenario.yaml"
    require(scenario_path.exists(), "Missing scenario.yaml", errors)
    if scenario_path.exists():
        keys = top_level_yaml_keys(scenario_path)
        require(
            keys == contract["scenario_yaml_fields"],
            "scenario.yaml fields do not match the required contract order exactly",
            errors,
        )


def check_completed_report(bundle_root: Path, contract, errors):
    report_path = bundle_root / contract["editable_report"]
    require(report_path.exists(), f"Missing candidate file: {contract['editable_report']}", errors)
    if errors:
        return

    report_text = report_path.read_text(encoding="utf-8")
    report_lower = report_text.lower()

    for section in contract["required_report_sections"]:
        require(section in report_text, f"Missing report section: {section}", errors)

    require("todo" not in report_lower, "review-report.md still contains TODO markers", errors)
    require(
        contract["expected_gate_decision"].lower() in report_lower,
        f"review-report.md does not contain gate decision {contract['expected_gate_decision']}",
        errors,
    )

    for finding in contract["required_findings"]:
        severity = finding["severity"].lower()
        require(
            f"[{severity}]" in report_lower,
            f"Missing severity label for finding: {finding['name']}",
            errors,
        )
        for term in finding["required_terms"]:
            require(
                term.lower() in report_lower,
                f"Missing required anchor '{term}' for finding: {finding['name']}",
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
        check_completed_report(bundle_root, contract, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    mode = "bundle shape" if args.bundle_shape_only else "completed review report"
    print(f"S26 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
