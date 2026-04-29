#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N81 evidence-conflict repo action plan.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    parser.add_argument("--answer-file", type=Path)
    parser.add_argument("--metrics-out", type=Path)
    parser.add_argument("--changed-path", dest="changed_paths", action="append", default=[])
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def strip_quotes(value: str) -> str:
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


def top_level_yaml_keys(path: Path):
    keys = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith(" ") or line.startswith("#"):
            continue
        if ":" in line:
            keys.append(line.split(":", 1)[0].strip())
    return keys


def require(condition: bool, message: str, errors: list[str]):
    if not condition:
        errors.append(message)


def normalize(text: object) -> str:
    return re.sub(r"\s+", " ", str(text or "").lower()).strip()


def all_terms_in(text: str, terms):
    text_lower = normalize(text)
    return all(term.lower() in text_lower for term in terms)


def parse_int_cell(value: str):
    match = re.match(r"\s*`?(\d+)`?\s*$", value)
    return int(match.group(1)) if match else None


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
    matched = 0
    misses = []
    for spec in specs:
        matching = [
            idx for idx, row in enumerate(rows)
            if idx not in seen and matcher(row, spec)
        ]
        if not matching:
            spec_id = spec.get("id", spec.get("rank", "?"))
            message = f"{label} {spec_id} has no matching row"
            errors.append(message)
            misses.append(str(spec_id))
            continue
        seen.add(matching[0])
        matched += 1
    return matched, misses


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
        and all_terms_in(row.get("Current evidence", ""), spec["current_terms"])
        and all_terms_in(row.get("Conflicting evidence", ""), spec["conflicting_terms"])
        and all_terms_in(row.get("Decision", ""), spec["decision_terms"])
        and all_terms_in(row.get("Action", ""), spec["action_terms"])
    )


def command_match(row, spec):
    return (
        all_terms_in(row.get("Command", ""), spec["command_terms"])
        and all_terms_in(row.get("Observed status", ""), spec["status_terms"])
        and all_terms_in(row.get("Implication", ""), spec["implication_terms"])
        and all_terms_in(row.get("Action", ""), spec["action_terms"])
    )


def action_match(row, spec):
    return (
        all_terms_in(row.get("Owner", ""), spec["owner_terms"])
        and all_terms_in(row.get("Files", ""), spec["files_terms"])
        and all_terms_in(row.get("Change type", ""), spec["change_terms"])
        and all_terms_in(row.get("Gate", ""), spec["gate_terms"])
        and all_terms_in(row.get("Do not do", ""), spec["do_not_terms"])
    )


def non_claim_match(row, spec):
    return (
        all_terms_in(row.get("Non-claim", ""), spec["non_claim_terms"])
        and all_terms_in(row.get("Reason", ""), spec["reason_terms"])
    )


def check_changed_paths(changed_paths, contract, errors):
    if not changed_paths:
        return
    expected = sorted(contract["requiredChangedPaths"])
    actual = sorted(changed_paths)
    require(actual == expected, f"changed paths mismatch: expected {expected}, got {actual}", errors)


def check_bundle_shape(bundle_root: Path, contract, errors):
    actual_entries = sorted(path.name for path in bundle_root.iterdir())
    require(
        actual_entries == sorted(contract["required_top_level_entries"]),
        f"Top-level bundle entries drifted: {actual_entries}",
        errors,
    )
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
        "scenario.yaml metadata does not match N81",
        errors,
    )


def score_completed_plan(answer_path: Path, contract):
    errors: list[str] = []
    metrics = {
        "verdict": "FAIL",
        "score_0_100": 0.0,
        "matched_count": 0,
        "expected_count": 24,
        "pass_score_threshold_0_100": float(contract["pass_score_threshold_0_100"]),
        "failures": [],
        "missing": {},
    }
    if not answer_path.exists():
        metrics["failures"].append(f"missing answer file: {answer_path}")
        return metrics

    text = answer_path.read_text(encoding="utf-8", errors="replace")
    lower = text.lower()
    section_bodies = extract_section_bodies(text)

    for section in contract["required_report_sections"]:
        require(section in section_bodies, f"Missing report section: {section}", errors)

    counts = contract["exact_counts"]
    source_rows = table_dicts(
        section_bodies,
        "## Source Authority",
        contract["source_authority_header"],
        counts["source_authority"],
        errors,
    )
    conflict_rows = table_dicts(
        section_bodies,
        "## Evidence Conflict Ledger",
        contract["conflict_ledger_header"],
        counts["conflict_ledger"],
        errors,
    )
    command_rows = table_dicts(
        section_bodies,
        "## Command Evidence",
        contract["command_evidence_header"],
        counts["command_evidence"],
        errors,
    )
    action_rows = table_dicts(
        section_bodies,
        "## Action Plan",
        contract["action_plan_header"],
        counts["action_plan"],
        errors,
    )
    non_claim_rows = table_dicts(
        section_bodies,
        "## Non-Claims",
        contract["non_claims_header"],
        counts["non_claims"],
        errors,
    )

    matched, missing = match_distinct(source_rows, contract["required_source_authority"], source_match, "source authority", errors)
    metrics["matched_count"] += matched
    metrics["missing"]["source_authority"] = missing
    matched, missing = match_distinct(conflict_rows, contract["required_conflicts"], conflict_match, "conflict", errors)
    metrics["matched_count"] += matched
    metrics["missing"]["conflicts"] = missing
    matched, missing = match_distinct(command_rows, contract["required_command_evidence"], command_match, "command evidence", errors)
    metrics["matched_count"] += matched
    metrics["missing"]["command_evidence"] = missing
    matched, missing = match_distinct(action_rows, contract["required_action_plan"], action_match, "action plan", errors)
    metrics["matched_count"] += matched
    metrics["missing"]["action_plan"] = missing
    matched, missing = match_distinct(non_claim_rows, contract["required_non_claims"], non_claim_match, "non-claim", errors)
    metrics["matched_count"] += matched
    metrics["missing"]["non_claims"] = missing

    reintake_text = section_bodies.get("## Re-Intake Trigger", "")
    missing_reintake = []
    for term in contract["required_reintake_terms"]:
        if term.lower() not in reintake_text.lower():
            missing_reintake.append(term)
            errors.append(f"Missing re-intake term: {term}")
    metrics["missing"]["reintake_terms"] = missing_reintake
    if not missing_reintake and reintake_text:
        metrics["matched_count"] += 1

    for snippet in contract["prohibited_report_snippets"]:
        require(snippet not in lower, f"Prohibited stale/draft/runtime claim present: {snippet}", errors)

    metrics["score_0_100"] = round(100.0 * metrics["matched_count"] / metrics["expected_count"], 3)
    if metrics["score_0_100"] < metrics["pass_score_threshold_0_100"]:
        errors.append(
            f"score below threshold: {metrics['score_0_100']} < {metrics['pass_score_threshold_0_100']}"
        )
    metrics["failures"] = errors
    if not errors:
        metrics["verdict"] = "PASS"
    return metrics


def write_metrics(path: Path | None, metrics: dict):
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")


def main():
    args = parse_args()
    bundle_root = args.bundle_root.resolve()
    if not bundle_root.exists():
        print(f"Bundle root does not exist: {bundle_root}", file=sys.stderr)
        return 1

    errors: list[str] = []
    contract = load_json(bundle_root / "oracle" / "evidence-action-contract.json")
    check_bundle_shape(bundle_root, contract, errors)
    check_changed_paths(args.changed_paths, contract, errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.bundle_shape_only:
        print("N81 verifier PASS (bundle shape)")
        return 0

    answer_path = args.answer_file or (bundle_root / contract["editable_report"])
    metrics = score_completed_plan(answer_path, contract)
    write_metrics(args.metrics_out, metrics)

    if args.expect_start_state:
        if metrics["matched_count"] != 0 or metrics["verdict"] == "PASS":
            print("ERROR: start-state unexpectedly passes or partially matches", file=sys.stderr)
            return 1
        print("N81 verifier PASS (expected start-state failures present)")
        return 0

    if metrics["verdict"] != "PASS":
        for failure in metrics["failures"]:
            print(f"Failed invariant: {failure}", file=sys.stderr)
        print(f"N81 score: {metrics['score_0_100']} matched={metrics['matched_count']}/{metrics['expected_count']}", file=sys.stderr)
        return 1

    print("N81 verifier PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
