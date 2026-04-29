#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N13 adversarial review bundle.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--changed-path", dest="changed_paths", action="append", default=[])
    return parser.parse_args()


def strip_quotes(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_simple_yaml(path):
    data = {}
    current_key = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            data.setdefault(current_key, []).append(strip_quotes(line[4:].strip()))
            continue
        if ":" not in line or line.startswith(" "):
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
            data[key] = strip_quotes(value)
            current_key = None
    return data


def top_level_yaml_keys(path):
    keys = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if line and not line.startswith(" ") and not line.startswith("#") and ":" in line:
            keys.append(line.split(":", 1)[0].strip())
    return keys


def section_bodies(text):
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


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def parse_markdown_table(section):
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


def require_terms(text, terms, context, errors):
    lowered = text.lower()
    for term in terms:
        require(term.lower() in lowered, f"Missing term '{term}' in {context}", errors)


def check_shape(root, contract, errors):
    for entry in contract["required_top_level_entries"]:
        require((root / entry).exists(), f"Missing top-level entry: {entry}", errors)
    for path in contract["required_bundle_paths"]:
        require((root / path).exists(), f"Missing required bundle path: {path}", errors)
    scenario = root / "scenario.yaml"
    require(top_level_yaml_keys(scenario) == contract["scenario_yaml_fields"], "scenario.yaml field order drifted", errors)
    require(parse_simple_yaml(scenario) == contract["expected_metadata"], "scenario.yaml metadata mismatch", errors)


def check_changed_paths(changed_paths, contract, errors):
    allowed = set(contract["expected_metadata"]["allowed_change_surface"])
    unexpected = sorted({path for path in changed_paths if path not in allowed})
    if unexpected:
        errors.append("Changed path outside allowed surface: " + ", ".join(unexpected))


def check_completed(root, contract, errors):
    report = (root / "candidate" / "review-report.md").read_text(encoding="utf-8")
    lowered = report.lower()
    sections = section_bodies(report)
    for marker in contract["disallowed_markers"]:
        require(marker.lower() not in lowered, f"Disallowed marker present: {marker}", errors)
    for section in contract["required_sections"]:
        require(section in report, f"Missing required section: {section}", errors)
    findings = sections.get("## Findings", "")
    findings_lower = findings.lower()
    finding_blocks = [block for block in re.split(r"(?m)^\s*-\s+", findings) if block.strip()]
    expected_count = contract.get("exact_finding_count")
    if expected_count is not None:
        require(len(finding_blocks) == expected_count, f"Expected exactly {expected_count} findings, found {len(finding_blocks)}", errors)
    for finding in contract["required_findings"]:
        require(f"[{finding['severity']}]" in findings_lower, f"Missing severity for {finding['name']}", errors)
        for term in finding["terms"]:
            require(term.lower() in findings_lower, f"Missing term '{term}' for {finding['name']}", errors)
        name_terms = [term.lower() for term in finding["terms"][:3]]
        matching_blocks = []
        for block in finding_blocks:
            block_lower = block.lower()
            if all(term in block_lower for term in name_terms):
                matching_blocks.append(block)
        require(matching_blocks, f"Missing structured block for {finding['name']}", errors)
        for block in matching_blocks[:1]:
            for label in contract.get("required_finding_labels", []):
                require(label.lower() in block.lower(), f"Missing {label} for {finding['name']}", errors)
    false_positive = sections.get("## False Positives Avoided", "").lower()
    for term in contract["false_positive_terms"]:
        require(term.lower() in false_positive, f"Missing false-positive term: {term}", errors)
    for table_rule in contract.get("required_table_headers", []):
        body = sections.get(table_rule["section"], "")
        header = table_rule["header"]
        require(header in body, f"Missing required table header in section {table_rule['section']}: {header}", errors)
    ledger_header, ledger_rows = parse_markdown_table(sections.get("## Scoreability Causal Ledger", ""))
    if ledger_header:
        require(
            ledger_header == ["Source signal", "Local wrong class", "Correct class", "Downstream score impact", "Owner fix"],
            "Scoreability Causal Ledger header does not match required columns exactly",
            errors,
        )
    for index, row_rule in enumerate(contract.get("required_causal_rows", []), start=1):
        matching_rows = []
        for row in ledger_rows:
            if len(row) < 5:
                continue
            if all(term.lower() in row[0].lower() for term in row_rule["source_terms"]):
                matching_rows.append(row)
        require(matching_rows, f"Missing scoreability causal ledger row {index}", errors)
        if not matching_rows:
            continue
        row = matching_rows[0]
        require_terms(row[1], row_rule["wrong_class_terms"], f"causal ledger wrong class row {index}", errors)
        require_terms(row[2], row_rule["correct_class_terms"], f"causal ledger correct class row {index}", errors)
        require_terms(row[3], row_rule["impact_terms"], f"causal ledger impact row {index}", errors)
        require_terms(row[4], row_rule["owner_fix_terms"], f"causal ledger owner fix row {index}", errors)
    require(any(re.search(rf"(?m)^{decision}$", report) for decision in contract["valid_gate_decisions"]), "Gate decision missing or invalid", errors)


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    errors = []
    contract = json.loads((root / "oracle" / "adversarial-review-contract.json").read_text(encoding="utf-8"))
    check_shape(root, contract, errors)
    if args.changed_paths:
        check_changed_paths(args.changed_paths, contract, errors)
    if not args.bundle_shape_only:
        check_completed(root, contract, errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("N13 verifier PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
