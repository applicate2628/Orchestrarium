#!/usr/bin/env python3

import argparse
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the S02 lead-recovery bundle shape or a completed candidate packet."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--bundle-root",
        type=Path,
        default=default_root,
        help="Path to the S02 bundle root.",
    )
    parser.add_argument(
        "--bundle-shape-only",
        action="store_true",
        help="Validate only the bundle contract, not a completed candidate run.",
    )
    return parser.parse_args()


def load_contract(bundle_root: Path):
    contract_path = bundle_root / "oracle" / "recovery-contract.json"
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


def check_bundle_shape(bundle_root: Path, contract, errors):
    for entry in contract["required_top_level_entries"]:
        require((bundle_root / entry).exists(), f"Missing top-level entry: {entry}", errors)

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
    active_root = bundle_root / "candidate" / "work-items" / "active" / "WAVE-P01-S02"
    brief_path = active_root / "brief.md"
    status_path = active_root / "status.md"
    handoff_path = active_root / "routing" / "qa-engineer-handoff.md"

    for path in (brief_path, status_path, handoff_path):
        require(path.exists(), f"Missing candidate file: {path.relative_to(bundle_root)}", errors)

    if errors:
        return

    brief = brief_path.read_text(encoding="utf-8")
    status = status_path.read_text(encoding="utf-8")
    handoff = handoff_path.read_text(encoding="utf-8")

    require(
        "Phase 1 - Bootstrap Scenarios-v2 with S02" in brief,
        "brief.md no longer preserves the primary task",
        errors,
    )
    require(
        contract["expected_later_gate"] in brief,
        "brief.md does not preserve the later architecture-review gate",
        errors,
    )
    require(
        f"Current stage: {contract['expected_resume_stage']}" in status,
        "status.md does not advance to the QA stage",
        errors,
    )
    require(
        contract["expected_last_accepted_artifact"] in status,
        "status.md does not record the accepted implementation package",
        errors,
    )
    require(
        "Side request status: closed" in status,
        "status.md does not mark the side request as closed",
        errors,
    )
    require(
        contract["expected_next_role"] in handoff,
        "qa-engineer-handoff.md does not target $qa-engineer",
        errors,
    )
    require("TODO" not in handoff, "qa-engineer-handoff.md still contains TODO markers", errors)

    for section in contract["required_handoff_sections"]:
        require(section in handoff, f"Missing handoff section: {section}", errors)


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

    mode = "bundle shape" if args.bundle_shape_only else "completed packet"
    print(f"S02 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
