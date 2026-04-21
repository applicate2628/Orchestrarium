#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the N05 secret-exposure review bundle shape or a completed review report."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--bundle-root", type=Path, default=default_root)
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--changed-path", dest="changed_paths", action="append", default=[])
    return parser.parse_args()


def load_contract(bundle_root: Path):
    return json.loads(
        (bundle_root / "oracle" / "secret-exposure-review-contract.json").read_text(encoding="utf-8")
    )


def parse_simple_yaml(path: Path):
    data = {}
    current_list = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            data.setdefault(current_list, []).append(line[4:].strip())
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
        keys.append(line.split(":", 1)[0].strip())
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


def split_finding_blocks(findings_text: str):
    blocks = []
    current = []
    for line in findings_text.splitlines():
        if line.lstrip().startswith("[") and current:
            blocks.append("\n".join(current).strip())
            current = []
        if line.strip():
            current.append(line)
    if current:
        blocks.append("\n".join(current).strip())
    return blocks


def check_changed_paths(changed_paths, allowed_paths, errors):
    allowed = set(allowed_paths)
    unexpected = sorted({path for path in changed_paths if path not in allowed})
    if unexpected:
        errors.append(
            "Changed path outside the allowed change surface: " + ", ".join(unexpected)
        )


def check_bundle_shape(bundle_root: Path, contract, errors):
    for entry in contract["required_top_level_entries"]:
        require((bundle_root / entry).exists(), f"Missing top-level entry: {entry}", errors)
    for relative_path in contract["required_bundle_paths"]:
        require((bundle_root / relative_path).exists(), f"Missing required bundle path: {relative_path}", errors)

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
        "scenario.yaml metadata does not match N05",
        errors,
    )


def check_completed_report(bundle_root: Path, contract, errors):
    report_path = bundle_root / contract["editable_report"]
    require(report_path.exists(), f"Missing candidate file: {contract['editable_report']}", errors)
    if errors:
        return
    text = report_path.read_text(encoding="utf-8")
    lower = text.lower()
    section_bodies = extract_section_bodies(text)

    for section in contract["required_report_sections"]:
        require(section in text, f"Missing report section: {section}", errors)
    gate_body = section_bodies.get("## Gate Decision", "")
    require(
        contract["expected_gate_decision"].lower() in gate_body.lower(),
        "Missing REVISE gate decision in ## Gate Decision",
        errors,
    )

    findings_body = section_bodies.get("## Findings", "")
    finding_blocks = split_finding_blocks(findings_body)
    for finding in contract["required_findings"]:
        severity = f"[{finding['severity']}]"
        matching_blocks = [
            block for block in finding_blocks
            if severity in block.lower() and finding["name"].split()[0].lower() in block.lower()
        ]
        if not matching_blocks:
            matching_blocks = [block for block in finding_blocks if severity in block.lower()]
        block_text = matching_blocks[0].lower() if matching_blocks else ""
        require(block_text != "", f"Missing distinct finding block for {finding['name']}", errors)
        for term in finding["required_terms"]:
            require(term.lower() in lower, f"Missing required term '{term}' for {finding['name']}", errors)
            require(
                term.lower() in block_text,
                f"Missing required term '{term}' inside finding block for {finding['name']}",
                errors,
            )

    false_positive_body = section_bodies.get("## False Positives Avoided", "").lower()
    for term in contract.get("required_false_positive_terms", []):
        require(
            term.lower() in false_positive_body,
            f"Missing false-positive boundary term: {term}",
            errors,
        )

    for snippet in contract["prohibited_report_snippets"]:
        require(snippet not in lower, f"Prohibited snippet present: {snippet}", errors)


def main():
    args = parse_args()
    bundle_root = args.bundle_root.resolve()
    if not bundle_root.exists():
        print(f"Bundle root does not exist: {bundle_root}", file=sys.stderr)
        return 1

    errors = []
    contract = load_contract(bundle_root)
    check_bundle_shape(bundle_root, contract, errors)
    if args.changed_paths:
        check_changed_paths(args.changed_paths, contract["expected_metadata"]["allowed_change_surface"], errors)
    if not args.bundle_shape_only:
        check_completed_report(bundle_root, contract, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    mode = "bundle shape" if args.bundle_shape_only else "completed review report"
    print(f"N05 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
