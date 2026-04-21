#!/usr/bin/env python3

import argparse
import hashlib
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the S25 QA-verification bundle shape or a completed QA verdict."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--bundle-root",
        type=Path,
        default=default_root,
        help="Path to the S25 bundle root.",
    )
    parser.add_argument(
        "--bundle-shape-only",
        action="store_true",
        help="Validate only the bundle contract, not a completed candidate run.",
    )
    return parser.parse_args()


def load_contract(bundle_root: Path):
    contract_path = bundle_root / "oracle" / "qa-contract.json"
    return json.loads(contract_path.read_text(encoding="utf-8"))


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
            data[key] = value.strip('"')
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


def extract_section_bodies(markdown_text: str):
    sections = {}
    current_section = None
    current_lines = []

    for line in markdown_text.splitlines():
        if line.startswith("## "):
            if current_section is not None:
                sections[current_section] = "\n".join(current_lines).strip()
            current_section = line.strip()
            current_lines = []
            continue

        if current_section is not None:
            current_lines.append(line)

    if current_section is not None:
        sections[current_section] = "\n".join(current_lines).strip()

    return sections


def sha256_hex(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
        require(
            parse_simple_yaml(scenario_path) == contract["expected_metadata"],
            "scenario.yaml metadata does not match S25",
            errors,
        )

    for relative_path, expected_hash in contract["protected_surface_hashes"].items():
        protected_path = bundle_root / relative_path
        require(protected_path.exists(), f"Missing protected file: {relative_path}", errors)
        if protected_path.exists():
            require(
                sha256_hex(protected_path) == expected_hash,
                f"Protected file changed: {relative_path}",
                errors,
            )


def check_completed_report(bundle_root: Path, contract, errors):
    report_path = bundle_root / contract["editable_report"]
    require(report_path.exists(), f"Missing candidate file: {contract['editable_report']}", errors)
    if errors:
        return

    report_text = report_path.read_text(encoding="utf-8")
    report_lower = report_text.lower()
    section_bodies = extract_section_bodies(report_text)

    for section in contract["required_report_sections"]:
        require(section in report_text, f"Missing report section: {section}", errors)

    require("todo" not in report_lower, "qa-verdict.md still contains TODO markers", errors)
    require(
        contract["expected_gate_decision"].lower()
        in section_bodies.get("## Gate Decision", "").lower(),
        f"qa-verdict.md does not contain gate decision {contract['expected_gate_decision']} in ## Gate Decision",
        errors,
    )

    for acceptance_id in contract["required_acceptance_ids"]:
        require(
            acceptance_id.lower() in report_lower,
            f"qa-verdict.md does not mention acceptance criterion {acceptance_id}",
            errors,
        )

    for anchor in contract["required_verdict_anchors"]:
        for term in anchor["required_terms"]:
            require(
                term.lower() in report_lower,
                f"Missing required anchor '{term}' for {anchor['name']}",
                errors,
            )

    for section_requirement in contract.get("required_section_terms", []):
        section_name = section_requirement["section"]
        section_text = section_bodies.get(section_name, "")
        section_lower = section_text.lower()
        require(section_text != "", f"Missing body for report section: {section_name}", errors)
        for term in section_requirement["required_terms"]:
            require(
                term.lower() in section_lower,
                f"Missing required term '{term}' in section {section_name}",
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

    mode = "bundle shape" if args.bundle_shape_only else "completed QA verdict"
    print(f"S25 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
