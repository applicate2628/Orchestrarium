#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N12 source-truth memo bundle.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
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


def check_completed(root, contract, errors):
    memo = (root / "candidate" / "repository-fact-memo.md").read_text(encoding="utf-8")
    lowered = memo.lower()
    sections = section_bodies(memo)
    for marker in contract["disallowed_markers"]:
        require(marker.lower() not in lowered, f"Disallowed marker present: {marker}", errors)
    for section in contract["required_sections"]:
        require(section in memo, f"Missing required section: {section}", errors)
    for rule in contract["section_terms"]:
        body = sections.get(rule["section"], "").lower()
        require(body != "", f"Missing body for section: {rule['section']}", errors)
        for term in rule["terms"]:
            require(term.lower() in body, f"Missing term '{term}' in section {rule['section']}", errors)
    for table_rule in contract.get("required_table_headers", []):
        body = sections.get(table_rule["section"], "")
        header = table_rule["header"]
        require(header in body, f"Missing required table header in section {table_rule['section']}: {header}", errors)
        require(
            re.search(r"(?m)^\| .+ \| .+ \| .+ \|", body) is not None,
            f"Missing populated table row in section {table_rule['section']}",
            errors,
        )
    ledger_header, ledger_rows = parse_markdown_table(sections.get("## Evidence Line Ledger", ""))
    if ledger_header:
        require(
            ledger_header == ["Citation", "Source", "Fact extracted", "Status"],
            "Evidence Line Ledger header does not match required columns exactly",
            errors,
        )
    ledger_by_citation = {row[0].strip("` "): row for row in ledger_rows if len(row) >= 4}
    for row_rule in contract.get("required_ledger_rows", []):
        row = ledger_by_citation.get(row_rule["citation"])
        require(row is not None, f"Missing evidence ledger row for {row_rule['citation']}", errors)
        if row is None:
            continue
        require_terms(row[2], row_rule["fact_terms"], f"fact extracted for {row_rule['citation']}", errors)
        require_terms(row[3], row_rule["status_terms"], f"status for {row_rule['citation']}", errors)
    _, non_claim_rows = parse_markdown_table(sections.get("## Non-Claim And Gap Ledger", ""))
    for index, row_rule in enumerate(contract.get("required_non_claim_rows", []), start=1):
        matching_rows = []
        for row in non_claim_rows:
            if len(row) < 3:
                continue
            if all(term.lower() in row[0].lower() for term in row_rule["non_claim_terms"]):
                matching_rows.append(row)
        require(matching_rows, f"Missing non-claim ledger row {index}", errors)
        if not matching_rows:
            continue
        row = matching_rows[0]
        require_terms(row[1], row_rule["why_terms"], f"non-claim reason row {index}", errors)
        require_terms(row[2], row_rule["follow_up_terms"], f"non-claim follow-up row {index}", errors)
    for citation in contract.get("required_citations", []):
        require(citation.lower() in lowered, f"Missing required citation: {citation}", errors)
    require(any(re.search(rf"(?m)^{decision}$", memo) for decision in contract["valid_gate_decisions"]), "Gate decision missing or invalid", errors)


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    errors = []
    contract = json.loads((root / "oracle" / "source-truth-contract.json").read_text(encoding="utf-8"))
    check_shape(root, contract, errors)
    if not args.bundle_shape_only:
        check_completed(root, contract, errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("N12 verifier PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
