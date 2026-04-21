#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the N02 UX bundle shape or a completed interaction-state flow brief."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--bundle-root",
        type=Path,
        default=default_root,
        help="Path to the N02 bundle root.",
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
    contract_path = bundle_root / "oracle" / "ux-brief-contract.json"
    return json.loads(contract_path.read_text(encoding="utf-8"))


def strip_quotes(value: str):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_simple_yaml(path: Path):
    data = {}
    current_key = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            if current_key is not None:
                data.setdefault(current_key, []).append(strip_quotes(line[4:].strip()))
            continue
        if line.startswith(" "):
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value == "[]":
            data[key] = []
            current_key = None
        elif value:
            data[key] = strip_quotes(value)
            current_key = None
        else:
            data[key] = []
            current_key = key
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


def extract_subsection_body(markdown_text: str, heading: str) -> str:
    pattern = rf"(?ms)^{re.escape(heading)}\s*\n(.*?)(?=^### |\Z)"
    match = re.search(pattern, markdown_text)
    if match is None:
        return ""
    return match.group(1).strip()


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
    lowered = text.lower()
    for term in terms:
        require(term.lower() in lowered, f"Missing required term '{term}' in {context}", errors)


def check_changed_paths(changed_paths, allowed_paths, errors):
    allowed = set(allowed_paths)
    unexpected = sorted({path for path in changed_paths if path not in allowed})
    if unexpected:
        errors.append(
            "Changed path outside the allowed change surface: " + ", ".join(unexpected)
        )


def contains_any(text, alternatives):
    lowered = text.lower()
    return any(option.lower() in lowered for option in alternatives)


def check_ordered_headings(text: str, headings: list[str], label: str, errors: list[str]) -> None:
    last_index = -1
    for heading in headings:
        index = text.find(heading)
        require(index >= 0, f"Missing {label}: {heading}", errors)
        if index >= 0:
            require(index > last_index, f"{label} out of order: {heading}", errors)
            last_index = index


def check_bundle_shape(bundle_root: Path, contract, errors):
    expected_entries = contract["required_top_level_entries"]
    actual_entries = sorted(path.name for path in bundle_root.iterdir())
    require(
        actual_entries == sorted(expected_entries),
        "Bundle root top-level entries do not match the required six-entry contract exactly",
        errors,
    )

    for entry in expected_entries:
        require((bundle_root / entry).exists(), f"Missing top-level entry: {entry}", errors)

    candidate_root = bundle_root / "candidate"
    if candidate_root.exists():
        actual_candidate_entries = sorted(path.name for path in candidate_root.iterdir())
        require(
            actual_candidate_entries == sorted(contract["expected_candidate_entries"]),
            "candidate/ contains files beyond the single UX brief contract",
            errors,
        )

    for relative_path in contract["required_bundle_files"]:
        require(
            (bundle_root / relative_path).exists(),
            f"Missing required bundle file: {relative_path}",
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
    for key, expected_value in contract["required_metadata"].items():
        actual_value = metadata.get(key)
        require(
            actual_value == expected_value,
            f"scenario.yaml field {key!r} does not match the required value",
            errors,
        )


def check_completed_brief(bundle_root: Path, contract, errors):
    brief_path = bundle_root / "candidate" / "ux-structure-brief.md"
    require(brief_path.exists(), "Missing candidate/ux-structure-brief.md", errors)
    if errors:
        return

    text = brief_path.read_text(encoding="utf-8")
    section_bodies = extract_section_bodies(text)

    for section in contract["required_brief_sections"]:
        require(section in text, f"Missing required section: {section}", errors)

    check_ordered_headings(text, contract["required_state_headings"], "state heading", errors)
    check_ordered_headings(text, contract["required_flow_headings"], "flow heading", errors)
    check_ordered_headings(text, contract["required_resume_headings"], "resume heading", errors)
    check_ordered_headings(text, contract["required_trace_headings"], "trace heading", errors)
    trace_table_header = contract["required_trace_table_header"]
    for heading in contract["required_trace_headings"]:
        subsection_body = extract_subsection_body(text, heading)
        require(
            trace_table_header in subsection_body,
            f"Trace subsection is missing required table header: {heading}",
            errors,
        )
        require(
            re.search(r"(?m)^\| .+ \| .+ \| .+ \| .+ \|$", subsection_body) is not None,
            f"Trace subsection is missing a populated trace row: {heading}",
            errors,
        )
        table_header, table_rows = parse_markdown_table(subsection_body)
        if table_header:
            require(
                table_header == [
                    "Source failure",
                    "Proposed state response",
                    "Owner",
                    "Visible return cue",
                ],
                f"Trace table header does not match required columns exactly: {heading}",
                errors,
            )
        row_rule = next(
            (rule for rule in contract.get("required_trace_rows", []) if rule["heading"] == heading),
            None,
        )
        if row_rule is not None:
            matching_rows = []
            for row in table_rows:
                if len(row) < 4:
                    continue
                if all(term.lower() in row[0].lower() for term in row_rule["source_terms"]):
                    matching_rows.append(row)
            require(matching_rows, f"Trace subsection is missing source-bound row: {heading}", errors)
            if matching_rows:
                row = matching_rows[0]
                require_terms(row[1], row_rule["response_terms"], f"trace response row {heading}", errors)
                require_terms(row[2], row_rule["owner_terms"], f"trace owner row {heading}", errors)
                require_terms(row[3], row_rule["cue_terms"], f"trace visible cue row {heading}", errors)

    for exact_line in contract["required_exact_lines"]:
        require(exact_line in text, f"Missing required line: {exact_line}", errors)

    for alternatives in contract["required_keyword_groups"]:
        require(
            contains_any(text, alternatives),
            f"Brief is missing required keyword coverage from: {alternatives}",
            errors,
        )

    for section_requirement in contract.get("required_section_terms", []):
        section_name = section_requirement["section"]
        section_lower = section_bodies.get(section_name, "").lower()
        require(section_lower != "", f"Missing body for section: {section_name}", errors)
        for term in section_requirement["required_terms"]:
            require(
                term.lower() in section_lower,
                f"Missing required term '{term}' in section {section_name}",
                errors,
            )

    status_pattern = r"(?ms)^## Brief status\s+([A-Z][A-Z -]+)\s*\Z"
    match = re.search(status_pattern, text)
    require(match is not None, "Brief status section is missing or malformed", errors)
    if match is not None:
        require(
            match.group(1) in contract["valid_statuses"],
            "Brief status is not an allowed value",
            errors,
        )

    for marker in contract["disallowed_markers"]:
        require(marker not in text, f"Disallowed marker present in brief: {marker}", errors)


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
        check_changed_paths(args.changed_paths, contract["required_metadata"]["allowed_change_surface"], errors)
    if not args.bundle_shape_only:
        check_completed_brief(bundle_root, contract, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    mode = "bundle shape" if args.bundle_shape_only else "completed interaction-state flow brief"
    print(f"N02 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
