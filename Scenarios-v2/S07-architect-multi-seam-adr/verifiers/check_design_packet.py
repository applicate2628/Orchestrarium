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


def require(condition, message, errors):
    if not condition:
        errors.append(message)


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


def check_completed_packet(bundle_root: Path, contract, errors):
    design_path = bundle_root / "candidate" / "design-package.md"
    require(design_path.exists(), "Missing candidate/design-package.md", errors)
    if errors:
        return

    text = design_path.read_text(encoding="utf-8")

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
