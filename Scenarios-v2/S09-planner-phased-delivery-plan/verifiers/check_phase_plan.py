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
    parser.add_argument(
        "--candidate-file",
        type=Path,
        default=None,
        help="Optional alternate phase-plan path (for reference/probe scoring).",
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


def contains_any(text, alternatives):
    lowered = text.lower()
    return any(option.lower() in lowered for option in alternatives)


# ----- R4b derivation (dependency-ordering) graded scorer -----------------------

def block_between(text, start_marker, end_marker):
    start = text.find(start_marker)
    if start == -1:
        return ""
    body = text[start + len(start_marker):]
    if end_marker:
        end = body.find(end_marker)
        if end != -1:
            body = body[:end]
    return body


def any_hit(text, options):
    low = text.lower()
    return any(opt.lower() in low for opt in options)


def score_derivation(text, spec):
    """Return (score, mandatory_ok, breakdown, notes)."""
    scopes = {
        "whole": text,
        "phase2_block": block_between(text, spec["phase2_block_start"], spec["phase2_block_end"]),
        "phase3_block": block_between(text, spec["phase3_block_start"], spec["phase3_block_end"]),
    }
    breakdown = {}
    notes = []
    total = 0.0
    mandatory_ok = True
    for name, comp in spec["components"].items():
        scope_text = scopes.get(comp.get("scope", "whole"), text)
        pts = comp["points"]
        if "conjunction" in comp:
            groups = comp["conjunction"]
            hits = sum(1 for g in groups if any_hit(scope_text, g["any_of"]))
            earned = pts * (hits / len(groups))
            missing = [g["group"] for g in groups if not any_hit(scope_text, g["any_of"])]
            if missing:
                notes.append(f"{name}: missing groups {missing}")
        else:
            earned = pts if any_hit(scope_text, comp["any_of"]) else 0.0
            if earned == 0.0:
                notes.append(f"{name}: no evidence in scope '{comp.get('scope')}'")
        breakdown[name] = round(earned, 2)
        total += earned
        if "mandatory_min" in comp and earned < comp["mandatory_min"]:
            mandatory_ok = False
            notes.append(
                f"{name}: earned {round(earned, 2)} < mandatory_min {comp['mandatory_min']} "
                "(the derived dependency / shortcut rejection is required, not optional)"
            )
    return round(total, 2), mandatory_ok, breakdown, notes


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


def check_completed_plan(bundle_root: Path, contract, errors, plan_path=None):
    if plan_path is None:
        plan_path = bundle_root / "candidate" / "phase-plan.md"
    require(plan_path.exists(), f"Missing phase-plan file: {plan_path}", errors)
    if errors:
        return

    text = plan_path.read_text(encoding="utf-8")
    section_bodies = extract_section_bodies(text)

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
    plan_path = args.candidate_file.resolve() if args.candidate_file else None
    if not args.bundle_shape_only:
        check_completed_plan(bundle_root, contract, errors, plan_path=plan_path)

    # Floor gate: structural + phase-order + phase_expectations are a hard prerequisite.
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.bundle_shape_only:
        print("S09 verifier PASS (bundle shape)")
        return 0

    spec = contract.get("derivation_scoring")
    if spec is None:
        print("S09 verifier PASS (completed phase plan; no graded spec)")
        return 0

    resolved = plan_path if plan_path else bundle_root / "candidate" / "phase-plan.md"
    text = resolved.read_text(encoding="utf-8")
    score, mandatory_ok, breakdown, notes = score_derivation(text, spec)
    threshold = spec["pass_threshold"]
    passed = score >= threshold and mandatory_ok

    for name, pts in breakdown.items():
        print(f"  {name}: {pts}")
    for note in notes:
        print(f"  note: {note}", file=sys.stderr)

    verdict = "PASS" if passed else "FAIL"
    stream = sys.stdout if passed else sys.stderr
    print(
        f"S09 derivation score {score}/{spec['max_points']} "
        f"(threshold {threshold}, mandatory_ok={mandatory_ok}) -> {verdict}",
        file=stream,
    )
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
