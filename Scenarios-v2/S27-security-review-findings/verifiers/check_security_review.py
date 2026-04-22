#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the S27 security review bundle shape or a completed review report."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--bundle-root", type=Path, default=default_root)
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--changed-path", dest="changed_paths", action="append", default=[])
    return parser.parse_args()


def load_contract(bundle_root: Path):
    return json.loads(
        (bundle_root / "oracle" / "security-review-contract.json").read_text(encoding="utf-8")
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


def parse_findings_table(findings_body: str):
    rows = []
    header = None
    for raw_line in findings_body.splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        escaped = line.replace("\\|", "\x00")
        cells = [cell.strip().replace("\x00", "|") for cell in escaped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        if header is None:
            header = cells
            continue
        rows.append(cells)
    return header, rows


def row_to_dict(header, row):
    n = len(header)
    if len(row) > n:
        merged_last = " | ".join(row[n - 1 :])
        row = row[: n - 1] + [merged_last]
    elif len(row) < n:
        row = row + [""] * (n - len(row))
    return {header[i]: row[i] for i in range(n)}


def parse_int_cell(value: str):
    match = re.match(r"\s*`?(\d+)`?\s*$", value)
    return int(match.group(1)) if match else None


def any_keyword_in(text_lower: str, keywords):
    return any(keyword.lower() in text_lower for keyword in keywords)


def all_terms_in(text_lower: str, terms):
    return all(term.lower() in text_lower for term in terms)


def finding_matches_oracle(candidate, oracle):
    file_cell = candidate.get("File", "").strip().strip("`")
    if file_cell != oracle["file"]:
        return False
    line_value = parse_int_cell(candidate.get("Line", ""))
    if line_value is None or line_value not in oracle["acceptable_lines"]:
        return False
    severity_cell = candidate.get("Severity", "").strip().strip("`").lower()
    if severity_cell != oracle["severity"].lower():
        return False
    category_cell = candidate.get("Category", "").strip().strip("`").lower()
    if not any_keyword_in(category_cell, oracle["category_terms"]):
        return False
    title_cell = candidate.get("Title", "").strip().lower()
    if not any_keyword_in(title_cell, oracle["title_keywords"]):
        return False
    evidence_cell = candidate.get("Evidence", "").strip().lower()
    if not all_terms_in(evidence_cell, oracle["required_evidence_terms"]):
        return False
    return True


def finding_matches_forbidden(candidate, forbidden):
    title_cell = candidate.get("Title", "").strip().lower()
    return any_keyword_in(title_cell, forbidden["title_keywords"])


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
        "scenario.yaml metadata does not match S27",
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
        f"Missing {contract['expected_gate_decision']} gate decision in ## Gate Decision",
        errors,
    )

    findings_body = section_bodies.get("## Findings", "")
    header, rows = parse_findings_table(findings_body)
    require(header is not None, "Missing findings table in ## Findings", errors)
    if header is None:
        return

    expected_header = contract["findings_table_header"]
    require(
        header == expected_header,
        f"Findings table header does not match: expected {expected_header}, got {header}",
        errors,
    )
    if header != expected_header:
        return

    candidates = [row_to_dict(header, row) for row in rows]

    require(
        len(candidates) == contract["exact_finding_count"],
        f"Findings table row count mismatch: expected exactly {contract['exact_finding_count']}, got {len(candidates)}",
        errors,
    )

    allowed_categories_lower = {c.lower() for c in contract["allowed_categories"]}
    allowed_severities_lower = {s.lower() for s in contract["allowed_severities"]}
    for idx, candidate in enumerate(candidates, start=1):
        category_cell = candidate.get("Category", "").strip().strip("`").lower()
        severity_cell = candidate.get("Severity", "").strip().strip("`").lower()
        line_value = parse_int_cell(candidate.get("Line", ""))
        require(
            any(cat in category_cell for cat in allowed_categories_lower),
            f"Finding row {idx} Category cell '{candidate.get('Category', '')}' is not in allowed set {sorted(allowed_categories_lower)}",
            errors,
        )
        require(
            severity_cell in allowed_severities_lower,
            f"Finding row {idx} Severity cell '{candidate.get('Severity', '')}' is not in allowed set {sorted(allowed_severities_lower)}",
            errors,
        )
        require(
            line_value is not None,
            f"Finding row {idx} Line cell '{candidate.get('Line', '')}' is not a parseable integer",
            errors,
        )

    for forbidden in contract.get("forbidden_findings", []):
        for idx, candidate in enumerate(candidates, start=1):
            if finding_matches_forbidden(candidate, forbidden):
                errors.append(
                    f"Finding row {idx} title '{candidate.get('Title', '')}' matches forbidden trap "
                    f"({forbidden['reason']})"
                )

    matched_oracle_ids = []
    for oracle in contract["required_findings"]:
        matching = [
            idx for idx, candidate in enumerate(candidates, start=1)
            if finding_matches_oracle(candidate, oracle)
        ]
        if not matching:
            errors.append(
                f"Oracle finding {oracle['id']} has no matching candidate row "
                f"(file={oracle['file']}, acceptable_lines={oracle['acceptable_lines']}, "
                f"severity={oracle['severity']})"
            )
        else:
            matched_oracle_ids.append((oracle["id"], matching))

    seen_rows = set()
    for oracle_id, matching in matched_oracle_ids:
        picks = [idx for idx in matching if idx not in seen_rows]
        if not picks:
            errors.append(
                f"Oracle finding {oracle_id} only matches rows already claimed by other findings; "
                f"each oracle finding requires a distinct candidate row"
            )
            continue
        seen_rows.add(picks[0])

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
    print(f"S27 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
