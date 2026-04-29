#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N11 ADR bundle.")
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
        if not line or line.startswith(" ") or line.startswith("#"):
            continue
        if ":" in line:
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


def numbered_block(text, prefix):
    pattern = rf"(?ms)^{re.escape(prefix)}\s+.*?(?=^\d+\.\s+|\Z)"
    match = re.search(pattern, text)
    return match.group(0) if match else ""


def extract_json_object(section):
    fence = re.search(r"(?ms)```json\s*(\{.*?\})\s*```", section)
    raw = fence.group(1) if fence else section
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(raw[start : end + 1])
    except json.JSONDecodeError:
        return None


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
    packet = root / "candidate" / "design-package.md"
    text = packet.read_text(encoding="utf-8")
    lowered = text.lower()
    sections = section_bodies(text)

    for marker in contract["disallowed_markers"]:
        require(marker.lower() not in lowered, f"Disallowed marker present: {marker}", errors)
    for section in contract["required_sections"]:
        require(section in text, f"Missing required section: {section}", errors)
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
    evidence_header, evidence_rows = parse_markdown_table(sections.get("## Evidence Binding Table", ""))
    if evidence_header:
        require(
            evidence_header == ["Evidence", "Concrete source", "Accepted claim", "Decision use", "Conflict risk"],
            "Evidence Binding Table header does not match required columns exactly",
            errors,
        )
    evidence_by_id = {row[0].strip("` "): row for row in evidence_rows if len(row) >= 5}
    for binding in contract.get("required_evidence_bindings", []):
        row = evidence_by_id.get(binding["evidence"])
        require(row is not None, f"Missing evidence binding row for {binding['evidence']}", errors)
        if row is None:
            continue
        require(binding["source"] in row[1], f"Evidence {binding['evidence']} has wrong concrete source", errors)
        require_terms(row[2], binding["accepted_claim_terms"], f"accepted claim for {binding['evidence']}", errors)
        require_terms(row[3], binding["decision_use_terms"], f"decision use for {binding['evidence']}", errors)
        require_terms(row[4], binding["conflict_risk_terms"], f"conflict risk for {binding['evidence']}", errors)
    _, forbidden_rows = parse_markdown_table(sections.get("## Forbidden Direction Test", ""))
    for index, row_rule in enumerate(contract.get("required_forbidden_read_rows", []), start=1):
        matching_rows = []
        for row in forbidden_rows:
            if len(row) < 3:
                continue
            if all(term.lower() in row[0].lower() for term in row_rule["forbidden_terms"]):
                matching_rows.append(row)
        require(matching_rows, f"Missing forbidden-direction table row {index}", errors)
        if not matching_rows:
            continue
        row = matching_rows[0]
        require_terms(row[1], row_rule["why_terms"], f"forbidden-direction why row {index}", errors)
        require_terms(row[2], row_rule["test_terms"], f"forbidden-direction test row {index}", errors)
    for prefix in contract["required_claim_prefixes"]:
        require(re.search(rf"(?m)^{re.escape(prefix)}\s+\S+", text), f"Missing claim prefix {prefix}", errors)
    claims_body = sections.get("## Claims", "")
    for term in contract.get("required_claim_terms", []):
        for prefix in contract["required_claim_prefixes"]:
            block = numbered_block(claims_body, prefix)
            require(block, f"Missing claim block {prefix}", errors)
            require(term.lower() in block.lower(), f"Missing {term} in claim {prefix}", errors)
    expected_decision = contract.get("machine_decision")
    if expected_decision is not None:
        parsed_decision = extract_json_object(sections.get("## Machine-Checkable Decision", ""))
        require(parsed_decision is not None, "Missing parseable JSON machine decision", errors)
        if parsed_decision is not None:
            require(parsed_decision == expected_decision, "Machine decision JSON does not match expected invariant", errors)
    require(any(re.search(rf"(?m)^{decision}$", text) for decision in contract["valid_gate_decisions"]), "Gate decision missing or invalid", errors)


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    errors = []
    contract = json.loads((root / "oracle" / "architecture-conflict-contract.json").read_text(encoding="utf-8"))
    check_shape(root, contract, errors)
    if not args.bundle_shape_only:
        check_completed(root, contract, errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("N11 verifier PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
