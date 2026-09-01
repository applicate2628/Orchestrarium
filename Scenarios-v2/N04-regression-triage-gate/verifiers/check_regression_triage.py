#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the N04 regression-triage bundle shape or a completed triage report."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--bundle-root",
        type=Path,
        default=default_root,
        help="Path to the N04 bundle root.",
    )
    parser.add_argument(
        "--bundle-shape-only",
        action="store_true",
        help="Validate only the bundle contract, not a completed candidate run.",
    )
    parser.add_argument(
        "--changed-path",
        dest="changed_paths",
        action="append",
        default=[],
        help="Relative benchmark path changed during the run; may be repeated.",
    )
    return parser.parse_args()


def load_contract(bundle_root: Path):
    contract_path = bundle_root / "oracle" / "regression-triage-contract.json"
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


def split_label_blocks(section_text: str):
    blocks = []
    current = []
    for line in section_text.splitlines():
        if line.lstrip().startswith("[") and current:
            blocks.append("\n".join(current).strip())
            current = []
        if line.strip():
            current.append(line)
    if current:
        blocks.append("\n".join(current).strip())
    return blocks


def parse_findings_table(section_text: str):
    rows = []
    header = None
    for raw_line in section_text.splitlines():
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


def table_finding_matches_oracle(candidate, oracle):
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


def table_finding_matches_forbidden(candidate, forbidden):
    title_cell = candidate.get("Title", "").strip().lower()
    return any_keyword_in(title_cell, forbidden["title_keywords"])


def check_table_findings(section_bodies, contract, errors):
    if "table_findings" not in contract:
        return
    section_name = contract.get("findings_table_section", "## Findings")
    section_body = section_bodies.get(section_name, "")
    header, rows = parse_findings_table(section_body)
    require(header is not None, f"Missing findings table in {section_name}", errors)
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
            f"Findings table row {idx} Category cell '{candidate.get('Category', '')}' is not in allowed set {sorted(allowed_categories_lower)}",
            errors,
        )
        require(
            severity_cell in allowed_severities_lower,
            f"Findings table row {idx} Severity cell '{candidate.get('Severity', '')}' is not in allowed set {sorted(allowed_severities_lower)}",
            errors,
        )
        require(
            line_value is not None,
            f"Findings table row {idx} Line cell '{candidate.get('Line', '')}' is not a parseable integer",
            errors,
        )

    for forbidden in contract.get("forbidden_findings", []):
        for idx, candidate in enumerate(candidates, start=1):
            if table_finding_matches_forbidden(candidate, forbidden):
                errors.append(
                    f"Findings table row {idx} title '{candidate.get('Title', '')}' matches forbidden trap "
                    f"({forbidden['reason']})"
                )

    matched_oracle_ids = []
    for oracle in contract["table_findings"]:
        matching = [
            idx for idx, candidate in enumerate(candidates, start=1)
            if table_finding_matches_oracle(candidate, oracle)
        ]
        if not matching:
            errors.append(
                f"Oracle table finding {oracle['id']} has no matching candidate row "
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
                f"Oracle table finding {oracle_id} only matches rows already claimed by other findings; "
                f"each oracle finding requires a distinct candidate row"
            )
            continue
        seen_rows.add(picks[0])


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
        require(
            (bundle_root / relative_path).exists(),
            f"Missing required bundle path: {relative_path}",
            errors,
        )

    scenario_path = bundle_root / "scenario.yaml"
    require(scenario_path.exists(), "Missing scenario.yaml", errors)
    if not scenario_path.exists():
        return

    keys = top_level_yaml_keys(scenario_path)
    require(
        keys == contract["scenario_yaml_fields"],
        "scenario.yaml fields do not match the required contract order exactly",
        errors,
    )

    metadata = parse_simple_yaml(scenario_path)
    require(metadata == contract["expected_metadata"], "scenario.yaml metadata does not match N04", errors)


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

    require(
        "todo" not in report_lower,
        "regression-triage-report.md still contains TODO markers",
        errors,
    )
    gate_body = section_bodies.get("## Gate Decision", "")
    require(
        contract["expected_gate_decision"].lower() in gate_body.lower(),
        (
            "regression-triage-report.md does not contain gate decision in ## Gate Decision "
            f"{contract['expected_gate_decision']}"
        ),
        errors,
    )

    likely_body = section_bodies.get("## Likely Regressions", "")
    regression_blocks = split_label_blocks(likely_body)
    last_index = -1
    for regression in contract["required_regressions"]:
        severity = regression["severity"].lower()
        require(
            f"[{severity}]" in report_lower,
            f"Missing severity label for regression: {regression['name']}",
            errors,
        )
        block_anchor = regression["required_terms"][1].lower()
        matching_index = next(
            (
                index for index, block in enumerate(regression_blocks)
                if f"[{severity}]" in block.lower()
                and block_anchor in block.lower()
            ),
            -1,
        )
        require(matching_index >= 0, f"Missing distinct regression block for: {regression['name']}", errors)
        require(matching_index > last_index, f"Regression appears out of required order: {regression['name']}", errors)
        if matching_index >= 0:
            last_index = matching_index
        block_lower = regression_blocks[matching_index].lower() if matching_index >= 0 else ""
        for term in regression["required_terms"]:
            require(
                term.lower() in report_lower,
                f"Missing required anchor '{term}' for regression: {regression['name']}",
                errors,
            )
            require(
                term.lower() in block_lower,
                f"Missing required anchor '{term}' inside regression block: {regression['name']}",
                errors,
            )

    for point in contract["required_supporting_points"]:
        for term in point["required_terms"]:
            require(
                term.lower() in report_lower,
                f"Missing required supporting anchor '{term}' for {point['name']}",
                errors,
            )

    for section_requirement in contract.get("required_section_terms", []):
        section_name = section_requirement["section"]
        section_lower = section_bodies.get(section_name, "").lower()
        require(section_lower != "", f"Missing body for report section: {section_name}", errors)
        for term in section_requirement["required_terms"]:
            require(
                term.lower() in section_lower,
                f"Missing required term '{term}' in section {section_name}",
                errors,
            )

    for snippet in contract["prohibited_report_snippets"]:
        require(
            snippet.lower() not in report_lower,
            f"regression-triage-report.md contains prohibited snippet: {snippet}",
            errors,
        )

    check_table_findings(section_bodies, contract, errors)


def main():
    args = parse_args()
    bundle_root = args.bundle_root.resolve()
    errors = []

    if not bundle_root.exists():
        print(f"Bundle root does not exist: {bundle_root}", file=sys.stderr)
        return 1

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

    mode = "bundle shape" if args.bundle_shape_only else "completed regression triage report"
    print(f"N04 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
