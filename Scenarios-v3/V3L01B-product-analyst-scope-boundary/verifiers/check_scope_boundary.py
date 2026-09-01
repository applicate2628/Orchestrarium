#!/usr/bin/env python3
"""Verifier for V3L01B - product-analyst scope-inflation trap with an enforced penalty.

Section-scoped oracle: the brief must hold the accepted scope boundary. The `## In Scope` section must
cover every required in-scope group and must contain NONE of the scope-inflation terms (the enforced
penalty); the scope-inflation asks from the noisy intake must be explicitly parked in `## Out Of Scope
(Parked)`. Read-only; executes no candidate code.

Near-peer separation: the noisy intake dangles tempting adjacent asks (extra export formats, scheduled
email export, a reporting dashboard). A near-peer product analyst pulls one or two into scope; a top
analyst holds the boundary and parks them with a reason. Pulling any inflation term into `## In Scope`
fails; silently dropping the asks (not parking them) also fails.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the V3L01B scope-boundary bundle or brief.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--changed-path", dest="changed_paths", action="append", default=[])
    return parser.parse_args()


def load_contract(bundle_root: Path):
    return json.loads((bundle_root / "oracle" / "scope-contract.json").read_text(encoding="utf-8"))


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


def any_term_in(text_lower, terms):
    return any(term.lower() in text_lower for term in terms)


def check_changed_paths(changed_paths, allowed_paths, errors):
    allowed = set(allowed_paths)
    unexpected = sorted({path for path in changed_paths if path not in allowed})
    if unexpected:
        errors.append("Changed path outside the allowed change surface: " + ", ".join(unexpected))


def check_bundle_shape(bundle_root: Path, contract, errors):
    for entry in contract["required_top_level_entries"]:
        require((bundle_root / entry).exists(), f"Missing top-level entry: {entry}", errors)
    for relative_path in contract["required_bundle_paths"]:
        require((bundle_root / relative_path).exists(), f"Missing required bundle path: {relative_path}", errors)
    scenario_path = bundle_root / "scenario.yaml"
    require(scenario_path.exists(), "Missing scenario.yaml", errors)
    if scenario_path.exists():
        require(
            top_level_yaml_keys(scenario_path) == contract["scenario_yaml_fields"],
            "scenario.yaml fields do not match the required contract order exactly",
            errors,
        )
        require(
            parse_simple_yaml(scenario_path) == contract["required_metadata"],
            "scenario.yaml metadata does not match V3L01B",
            errors,
        )


def check_completed_brief(bundle_root: Path, contract, errors):
    brief_path = bundle_root / contract["editable_brief"]
    require(brief_path.exists(), f"Missing candidate file: {contract['editable_brief']}", errors)
    if errors:
        return
    text = brief_path.read_text(encoding="utf-8")
    section_bodies = extract_section_bodies(text)

    for section in contract["required_sections"]:
        require(section in text, f"Missing brief section: {section}", errors)

    for marker in contract["disallowed_markers"]:
        require(marker not in text, f"Disallowed marker present: {marker}", errors)

    gate_pattern = re.compile(rf"(?m)^{re.escape(contract['expected_gate_decision'])}$")
    require(gate_pattern.search(text) is not None, f"Brief does not contain gate decision {contract['expected_gate_decision']} on its own line", errors)

    in_scope = section_bodies.get(contract["in_scope_section"], "").lower()
    parked = section_bodies.get(contract["out_of_scope_section"], "").lower()
    problem = section_bodies.get(contract["problem_section"], "").lower()

    require(in_scope != "", f"Missing body for {contract['in_scope_section']}", errors)
    require(parked != "", f"Missing body for {contract['out_of_scope_section']}", errors)
    require(problem != "", f"Missing body for {contract['problem_section']}", errors)

    # In Scope must cover every required in-scope group.
    for group in contract["required_in_scope_groups"]:
        require(
            any_term_in(in_scope, group),
            f"In Scope is missing a required in-scope item (one of {group})",
            errors,
        )

    # Enforced penalty: no scope-inflation term may appear in the In Scope section.
    for term in contract["forbidden_in_scope_terms"]:
        require(
            term.lower() not in in_scope,
            f"Scope inflation: forbidden term '{term}' appears in {contract['in_scope_section']}",
            errors,
        )

    # The inflation asks must be explicitly parked, not silently dropped.
    for group in contract["required_parked_groups"]:
        require(
            any_term_in(parked, group),
            f"Out Of Scope is missing a required parked item (one of {group})",
            errors,
        )

    # Problem statement must stay scoped: mention the core, exclude inflation.
    for term in contract["problem_required_terms"]:
        require(term.lower() in problem, f"Problem Statement is missing required scope term '{term}'", errors)
    for term in contract["forbidden_in_scope_terms"]:
        require(term.lower() not in problem, f"Scope inflation: forbidden term '{term}' appears in {contract['problem_section']}", errors)


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
        check_changed_paths(args.changed_paths, contract["required_metadata"]["allowed_change_surface"], errors)
    if not args.bundle_shape_only:
        check_completed_brief(bundle_root, contract, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    mode = "bundle shape" if args.bundle_shape_only else "completed product brief"
    print(f"V3L01B verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
