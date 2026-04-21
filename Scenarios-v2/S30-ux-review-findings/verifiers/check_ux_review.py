#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the S30 UX-review bundle shape or a completed review report."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--bundle-root", type=Path, default=default_root)
    parser.add_argument("--bundle-shape-only", action="store_true")
    return parser.parse_args()


def load_contract(bundle_root: Path):
    return json.loads((bundle_root / "oracle" / "ux-review-contract.json").read_text(encoding="utf-8"))


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


def section_bodies(text: str):
    sections = {}
    current = None
    lines = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current is not None:
                sections[current] = "\n".join(lines).strip()
            current = line.strip()
            lines = []
        elif current is not None:
            lines.append(line)
    if current is not None:
        sections[current] = "\n".join(lines).strip()
    return sections


def parse_markdown_table(section: str):
    rows = []
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if not cells or all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)
    if not rows:
        return [], []
    return rows[0], rows[1:]


def require_terms(text: str, terms, context: str, errors):
    lower = text.lower()
    for term in terms:
        require(term.lower() in lower, f"Missing required term '{term}' in {context}", errors)


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
        "scenario.yaml metadata does not match S30",
        errors,
    )


def check_completed_report(bundle_root: Path, contract, errors):
    report_path = bundle_root / contract["editable_report"]
    require(report_path.exists(), f"Missing candidate file: {contract['editable_report']}", errors)
    if errors:
        return
    text = report_path.read_text(encoding="utf-8")
    lower = text.lower()
    sections = section_bodies(text)

    for section in contract["required_report_sections"]:
        require(section in text, f"Missing report section: {section}", errors)
    require(contract["expected_gate_decision"].lower() in lower, "Missing REVISE gate decision", errors)

    findings = sections.get("## Findings", "")
    finding_blocks = [block for block in re.split(r"(?m)^\s*-\s+", findings) if block.strip()]
    expected_count = contract.get("exact_finding_count")
    if expected_count is not None:
        require(len(finding_blocks) == expected_count, f"Expected exactly {expected_count} findings, found {len(finding_blocks)}", errors)

    for finding in contract["required_findings"]:
        require(f"[{finding['severity']}]" in lower, f"Missing severity label for {finding['name']}", errors)
        for term in finding["required_terms"]:
            require(term.lower() in lower, f"Missing required term '{term}' for {finding['name']}", errors)
        matching_blocks = []
        for block in finding_blocks:
            block_lower = block.lower()
            if all(term.lower() in block_lower for term in finding["required_terms"][:2]):
                matching_blocks.append(block)
        require(matching_blocks, f"Missing structured finding block for {finding['name']}", errors)
        if matching_blocks:
            block_lower = matching_blocks[0].lower()
            for label in contract.get("required_finding_labels", []):
                require(label.lower() in block_lower, f"Missing {label} for {finding['name']}", errors)

    for table_rule in contract.get("required_table_headers", []):
        body = sections.get(table_rule["section"], "")
        require(table_rule["header"] in body, f"Missing table header in {table_rule['section']}: {table_rule['header']}", errors)

    _, evidence_rows = parse_markdown_table(sections.get("## Evidence-To-Finding Ledger", ""))
    for index, row_rule in enumerate(contract.get("required_evidence_rows", []), start=1):
        matching_rows = []
        for row in evidence_rows:
            if len(row) < 4:
                continue
            if all(term.lower() in row[0].lower() for term in row_rule["finding_terms"]):
                matching_rows.append(row)
        require(matching_rows, f"Missing evidence-to-finding ledger row {index}", errors)
        if matching_rows:
            row = matching_rows[0]
            require_terms(row[1], row_rule["evidence_terms"], f"evidence ledger evidence row {index}", errors)
            require_terms(row[2], row_rule["impact_terms"], f"evidence ledger impact row {index}", errors)
            require_terms(row[3], row_rule["severity_terms"], f"evidence ledger severity row {index}", errors)

    _, false_positive_rows = parse_markdown_table(sections.get("## False Positives Avoided", ""))
    for index, row_rule in enumerate(contract.get("required_false_positive_rows", []), start=1):
        matching_rows = []
        for row in false_positive_rows:
            if len(row) < 3:
                continue
            if all(term.lower() in row[0].lower() for term in row_rule["decoy_terms"]):
                matching_rows.append(row)
        require(matching_rows, f"Missing false-positive ledger row {index}", errors)
        if matching_rows:
            row = matching_rows[0]
            require_terms(row[1], row_rule["why_terms"], f"false-positive why row {index}", errors)
            require_terms(row[2], row_rule["boundary_terms"], f"false-positive boundary row {index}", errors)

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
    if not args.bundle_shape_only:
        check_completed_report(bundle_root, contract, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    mode = "bundle shape" if args.bundle_shape_only else "completed review report"
    print(f"S30 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
