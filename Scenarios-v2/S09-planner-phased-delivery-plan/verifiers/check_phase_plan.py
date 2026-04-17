#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the S09 planner bundle shape or a completed phase plan."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--bundle-root",
        type=Path,
        default=default_root,
        help="Path to the S09 bundle root.",
    )
    parser.add_argument(
        "--bundle-shape-only",
        action="store_true",
        help="Validate only the bundle contract, not a completed candidate run.",
    )
    return parser.parse_args()


def load_contract(bundle_root: Path):
    contract_path = bundle_root / "oracle" / "plan-contract.json"
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


def contains_any(text, alternatives):
    lowered = text.lower()
    return any(option.lower() in lowered for option in alternatives)


def section_positions(text, headings):
    positions = []
    for heading in headings:
        index = text.find(heading)
        positions.append((heading, index))
    return positions


def phase_block(text, heading, next_heading):
    start = text.find(heading)
    if start == -1:
        return ""
    if next_heading is None:
        return text[start:]
    end = text.find(next_heading, start + len(heading))
    if end == -1:
        return text[start:]
    return text[start:end]


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


def check_completed_plan(bundle_root: Path, contract, errors):
    plan_path = bundle_root / "candidate" / "phase-plan.md"
    require(plan_path.exists(), "Missing candidate/phase-plan.md", errors)
    if errors:
        return

    text = plan_path.read_text(encoding="utf-8")

    for section in contract["required_plan_sections"]:
        require(section in text, f"Missing required section: {section}", errors)

    phase_headings = contract["required_phase_headings"]
    positions = section_positions(text, phase_headings)
    for heading, index in positions:
        require(index != -1, f"Missing required phase heading: {heading}", errors)
    if all(index != -1 for _, index in positions):
        ordered_indexes = [index for _, index in positions]
        require(
            ordered_indexes == sorted(ordered_indexes),
            "Phase headings are not in the required order",
            errors,
        )

    after_phase_section = "## Cross-phase risks and mitigations"
    for i, heading in enumerate(phase_headings):
        next_heading = phase_headings[i + 1] if i + 1 < len(phase_headings) else after_phase_section
        block = phase_block(text, heading, next_heading)
        require(block, f"Could not isolate phase block: {heading}", errors)
        for label in contract["required_phase_labels"]:
            require(label in block, f"Missing phase label {label} in {heading}", errors)
        for required_text in contract["phase_expectations"][heading]["must_include"]:
            require(
                required_text in block,
                f"Missing required phase detail {required_text!r} in {heading}",
                errors,
            )

    for reference in contract["required_input_references"]:
        require(reference in text, f"Missing accepted-input reference: {reference}", errors)

    for alternatives in contract["required_keyword_groups"]:
        require(
            contains_any(text, alternatives),
            f"Phase plan is missing required keyword coverage from: {alternatives}",
            errors,
        )

    require(
        any(re.search(rf"(?m)^{decision}$", text) for decision in contract["valid_gate_decisions"]),
        "Gate decision is missing or invalid",
        errors,
    )

    for marker in contract["disallowed_markers"]:
        require(marker not in text, f"Disallowed marker present in phase plan: {marker}", errors)

    for heading in contract["disallowed_headings"]:
        require(heading not in text, f"Disallowed role-drift heading present: {heading}", errors)


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
        check_completed_plan(bundle_root, contract, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    mode = "bundle shape" if args.bundle_shape_only else "completed phase plan"
    print(f"S09 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
