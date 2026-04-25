#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the N66 conflicting-evidence fact memo bundle shape or completed memo."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument("--bundle-root", type=Path, default=default_root)
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--changed-path", dest="changed_paths", action="append", default=[])
    return parser.parse_args()


def load_contract(bundle_root: Path):
    return json.loads(
        (bundle_root / "oracle" / "conflicting-evidence-contract.json").read_text(encoding="utf-8")
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


def parse_table(section_body: str):
    rows = []
    header = None
    for raw_line in section_body.splitlines():
        line = raw_line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        if header is None:
            header = cells
            continue
        rows.append(cells)
    return header, rows


def row_to_dict(header, row):
    if len(row) < len(header):
        row = row + [""] * (len(header) - len(row))
    elif len(row) > len(header):
        row = row[: len(header)]
    return {header[i]: row[i] for i in range(len(header))}


def parse_int_cell(value: str):
    match = re.match(r"\s*`?(\d+)`?\s*$", value)
    return int(match.group(1)) if match else None


def all_terms_in(text: str, terms):
    text_lower = text.lower()
    return all(term.lower() in text_lower for term in terms)


def table_dicts(section_bodies, section_name, expected_header, exact_count, errors):
    body = section_bodies.get(section_name, "")
    header, rows = parse_table(body)
    require(header is not None, f"Missing table in {section_name}", errors)
    if header is None:
        return []
    require(
        header == expected_header,
        f"{section_name} table header mismatch: expected {expected_header}, got {header}",
        errors,
    )
    if header != expected_header:
        return []
    require(
        len(rows) == exact_count,
        f"{section_name} row count mismatch: expected {exact_count}, got {len(rows)}",
        errors,
    )
    return [row_to_dict(header, row) for row in rows]


def match_distinct(rows, specs, matcher, label, errors):
    seen = set()
    for spec in specs:
        matching = [
            idx for idx, row in enumerate(rows)
            if idx not in seen and matcher(row, spec)
        ]
        if not matching:
            errors.append(f"{label} {spec['id'] if 'id' in spec else spec.get('rank')} has no matching row")
            continue
        seen.add(matching[0])


def source_match(row, spec):
    rank = parse_int_cell(row.get("Rank", ""))
    return (
        rank == spec["rank"]
        and all_terms_in(row.get("Source", ""), spec["source_terms"])
        and all_terms_in(row.get("Status", ""), spec["status_terms"])
        and all_terms_in(row.get("Why", ""), spec["why_terms"])
    )


def conflict_match(row, spec):
    return (
        all_terms_in(row.get("Claim", ""), spec["claim_terms"])
        and all_terms_in(row.get("Current source of truth", ""), spec["current_terms"])
        and all_terms_in(row.get("Stale/conflicting source", ""), spec["stale_terms"])
        and all_terms_in(row.get("Decision", ""), spec["decision_terms"])
        and all_terms_in(row.get("Evidence", ""), spec["evidence_terms"])
    )


def fact_match(row, spec):
    return (
        all_terms_in(row.get("Fact", ""), spec["fact_terms"])
        and all_terms_in(row.get("Evidence", ""), spec["evidence_terms"])
    )


def non_claim_match(row, spec):
    return (
        all_terms_in(row.get("Non-claim", ""), spec["non_claim_terms"])
        and all_terms_in(row.get("Reason", ""), spec["reason_terms"])
    )


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
        "scenario.yaml metadata does not match N66",
        errors,
    )


def check_completed_memo(bundle_root: Path, contract, errors):
    memo_path = bundle_root / contract["editable_report"]
    require(memo_path.exists(), f"Missing candidate file: {contract['editable_report']}", errors)
    if errors:
        return
    text = memo_path.read_text(encoding="utf-8")
    lower = text.lower()
    section_bodies = extract_section_bodies(text)

    for section in contract["required_report_sections"]:
        require(section in text, f"Missing report section: {section}", errors)

    counts = contract["exact_counts"]
    source_rows = table_dicts(
        section_bodies,
        "## Source Ranking",
        contract["source_ranking_header"],
        counts["source_ranking"],
        errors,
    )
    conflict_rows = table_dicts(
        section_bodies,
        "## Conflict Ledger",
        contract["conflict_ledger_header"],
        counts["conflict_ledger"],
        errors,
    )
    fact_rows = table_dicts(
        section_bodies,
        "## Confirmed Current Facts",
        contract["confirmed_facts_header"],
        counts["confirmed_facts"],
        errors,
    )
    non_claim_rows = table_dicts(
        section_bodies,
        "## Non-Claims",
        contract["non_claims_header"],
        counts["non_claims"],
        errors,
    )

    match_distinct(source_rows, contract["required_source_ranking"], source_match, "source ranking", errors)
    match_distinct(conflict_rows, contract["required_conflicts"], conflict_match, "conflict", errors)
    match_distinct(fact_rows, contract["required_confirmed_facts"], fact_match, "confirmed fact", errors)
    match_distinct(non_claim_rows, contract["required_non_claims"], non_claim_match, "non-claim", errors)

    next_action = section_bodies.get("## Bounded Next Action", "")
    for term in contract["required_next_action_terms"]:
        require(term.lower() in next_action.lower(), f"Missing bounded next-action term: {term}", errors)

    for snippet in contract["prohibited_report_snippets"]:
        require(snippet not in lower, f"Prohibited stale/draft claim present: {snippet}", errors)


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
        check_completed_memo(bundle_root, contract, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    mode = "bundle shape" if args.bundle_shape_only else "completed fact memo"
    print(f"N66 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
