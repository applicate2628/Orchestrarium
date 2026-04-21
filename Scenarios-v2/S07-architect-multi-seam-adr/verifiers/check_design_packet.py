#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the S07 architect bundle shape or a completed design package."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--bundle-root",
        type=Path,
        default=default_root,
        help="Path to the S07 bundle root.",
    )
    parser.add_argument(
        "--bundle-shape-only",
        action="store_true",
        help="Validate only the bundle contract, not a completed candidate run.",
    )
    return parser.parse_args()


def load_contract(bundle_root: Path):
    contract_path = bundle_root / "oracle" / "design-contract.json"
    return json.loads(contract_path.read_text(encoding="utf-8"))


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


def check_bundle_shape(bundle_root: Path, contract, errors):
    for entry in contract["required_top_level_entries"]:
        require((bundle_root / entry).exists(), f"Missing top-level entry: {entry}", errors)

    for relative_path in contract["required_bundle_files"]:
        require(
            (bundle_root / relative_path).exists(),
            f"Missing required bundle file: {relative_path}",
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
            parse_simple_yaml(scenario_path) == contract["required_metadata"],
            "scenario.yaml metadata does not match S07",
            errors,
        )


def check_completed_packet(bundle_root: Path, contract, errors):
    design_path = bundle_root / "candidate" / "design-package.md"
    require(design_path.exists(), "Missing candidate/design-package.md", errors)
    if errors:
        return

    text = design_path.read_text(encoding="utf-8")
    section_bodies = extract_section_bodies(text)

    for section in contract["required_design_sections"]:
        require(section in text, f"Missing required section: {section}", errors)

    for subsection in contract["required_design_subsections"]:
        require(subsection in text, f"Missing required subsection: {subsection}", errors)

    require(
        contract["required_chosen_seam"] in text,
        "Design package does not choose the admissible seam",
        errors,
    )

    for rejected_seam in contract["required_rejected_seams"]:
        require(
            rejected_seam in text,
            f"Design package does not explicitly address rejected seam: {rejected_seam}",
            errors,
        )

    for alternatives in contract["required_keyword_groups"]:
        require(
            contains_any(text, alternatives),
            f"Design package is missing required keyword coverage from: {alternatives}",
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

    for prefix in contract["required_claim_prefixes"]:
        pattern = rf"(?m)^{re.escape(prefix)}\s+\S+"
        require(
            re.search(pattern, text) is not None,
            f"Claims section is missing numbered claim prefix: {prefix}",
            errors,
        )

    require(
        any(re.search(rf"(?m)^{decision}$", text) for decision in contract["valid_gate_decisions"]),
        "Gate decision is missing or invalid",
        errors,
    )

    for marker in contract["disallowed_markers"]:
        require(marker not in text, f"Disallowed marker present in design package: {marker}", errors)


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
        check_completed_packet(bundle_root, contract, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    mode = "bundle shape" if args.bundle_shape_only else "completed design package"
    print(f"S07 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
