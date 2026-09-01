#!/usr/bin/env python3

import argparse
import hashlib
import json
import re
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
