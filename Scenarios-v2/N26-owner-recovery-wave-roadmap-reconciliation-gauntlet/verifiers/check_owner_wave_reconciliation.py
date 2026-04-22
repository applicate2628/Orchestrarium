#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N26 owner wave reconciliation packet.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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
        if line and not line.startswith(" ") and not line.startswith("#") and ":" in line:
            keys.append(line.split(":", 1)[0].strip())
    return keys


def require(condition: bool, message: str, errors: list[str]):
    if not condition:
        errors.append(message)


def check_shape(root: Path, contract: dict, errors: list[str]):
    actual_entries = sorted(path.name for path in root.iterdir())
    require(
        actual_entries == sorted(contract["required_top_level_entries"]),
        f"Top-level bundle entries drifted: {actual_entries}",
        errors,
    )
    scenario = root / "scenario.yaml"
    require(top_level_yaml_keys(scenario) == contract["scenario_yaml_fields"], "scenario.yaml field order drifted", errors)
    require(parse_simple_yaml(scenario) == contract["expected_metadata"], "scenario.yaml metadata mismatch", errors)
    for path in contract["required_bundle_paths"]:
        require((root / path).exists(), f"Missing required bundle path: {path}", errors)


def extract_decision_json(text: str):
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if not match:
        return None, "missing fenced json block"
    try:
        return json.loads(match.group(1)), None
    except json.JSONDecodeError as exc:
        return None, f"invalid json: {exc}"


def evaluate_decision_json(text: str, contract: dict):
    failures = []
    decision, error = extract_decision_json(text)
    if error:
        failures.append({"id": "missing-decision-json", "detail": error})
        return failures

    missing_keys = [key for key in contract["decision_json_required_keys"] if key not in decision]
    if missing_keys:
        failures.append({"id": "missing-decision-json", "detail": "missing keys: " + ", ".join(missing_keys)})

    for key, expected in contract["decision_json_expected"].items():
        if decision.get(key) != expected:
            failures.append({"id": "missing-decision-json", "detail": f"{key} expected {expected!r}, found {decision.get(key)!r}"})

    run_order = decision.get("run_order")
    if not isinstance(run_order, list) or run_order[:2] != ["X1", "X3"]:
        failures.append({"id": "missing-decision-json", "detail": "run_order must start with X1 then X3"})

    resume_from = decision.get("resume_from")
    if not isinstance(resume_from, list) or len(resume_from) < 3:
        failures.append({"id": "missing-decision-json", "detail": "resume_from must list roadmap, scorecard, and status anchors"})

    return failures


def evaluate_packet(root: Path, contract: dict):
    failures = []
    packet = root / "candidate" / "owner-recovery-wave-roadmap-decision.md"
    text = packet.read_text(encoding="utf-8")

    missing_sections = [section for section in contract["required_sections"] if section not in text]
    if missing_sections:
        failures.append({"id": "missing-required-sections", "detail": ", ".join(missing_sections)})

    missing_phrases = [phrase for phrase in contract["required_exact_phrases"] if phrase not in text]
    if missing_phrases:
        failures.append({"id": "missing-required-phrases", "detail": ", ".join(missing_phrases)})

    missing_tables = [header for header in contract["required_table_headers"] if header not in text]
    if missing_tables:
        failures.append({"id": "missing-required-tables", "detail": ", ".join(missing_tables)})

    missing_citations = [citation for citation in contract["required_citations"] if citation not in text]
    if missing_citations:
        failures.append({"id": "missing-citations", "detail": ", ".join(missing_citations)})

    missing_interruptions = [item for item in contract["expected_interruption_ids"] if f"| `{item}` |" not in text]
    if missing_interruptions:
        failures.append({"id": "missing-interruption-classification", "detail": ", ".join(missing_interruptions)})

    missing_stale = [item for item in contract["expected_stale_ids"] if f"| `{item}` |" not in text]
    if missing_stale:
        failures.append({"id": "missing-stale-classification", "detail": ", ".join(missing_stale)})

    missing_lanes = [item for item in contract["expected_lane_ids"] if f"| `{item}` |" not in text]
    if missing_lanes:
        failures.append({"id": "missing-lane-state", "detail": ", ".join(missing_lanes)})

    failures.extend(evaluate_decision_json(text, contract))

    present_disallowed = [marker for marker in contract["disallowed_markers"] if marker in text]
    if present_disallowed:
        failures.append({"id": "contains-disallowed-markers", "detail": ", ".join(present_disallowed)})

    return failures


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    errors: list[str] = []

    if not root.exists():
        print(f"Bundle root does not exist: {root}", file=sys.stderr)
        return 1

    contract = load_json(root / "oracle" / "owner-wave-contract.json")
    check_shape(root, contract, errors)

    if not args.bundle_shape_only:
        failures = evaluate_packet(root, contract)
        failure_ids = sorted({failure["id"] for failure in failures})
        if args.expect_start_state:
            expected = sorted(contract["expected_start_state_failures"])
            require(failure_ids == expected, f"Expected start-state failures {expected}, found {failure_ids}", errors)
        elif failures:
            errors.append(f"Completed N26 packet still fails owner wave checks: {json.dumps(failures, indent=2)}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.bundle_shape_only:
        mode = "bundle shape"
    elif args.expect_start_state:
        mode = "start state"
    else:
        mode = "completed packet"
    print(f"N26 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
