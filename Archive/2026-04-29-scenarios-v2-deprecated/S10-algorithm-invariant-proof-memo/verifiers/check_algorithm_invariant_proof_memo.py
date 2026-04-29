#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the S10 invariant-proof bundle shape or a completed candidate memo."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--bundle-root",
        type=Path,
        default=default_root,
        help="Path to the S10 bundle root.",
    )
    parser.add_argument(
        "--bundle-shape-only",
        action="store_true",
        help="Validate only the bundle contract, not a completed candidate run.",
    )
    return parser.parse_args()


def load_contract(bundle_root: Path):
    contract_path = bundle_root / "oracle" / "algorithm-invariant-proof-contract.json"
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


def parse_simple_yaml(path: Path):
    data = {}
    current_list = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith("  - ") and current_list is not None:
            data[current_list].append(raw_line[4:].strip())
            continue
        if raw_line.startswith(" "):
            continue
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not value:
            data[key] = []
            current_list = key
            continue
        if value == "[]":
            data[key] = []
        else:
            data[key] = value.strip('"')
        current_list = None
    return data


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
        parsed = parse_simple_yaml(scenario_path)
        for field, expected in contract["expected_metadata"].items():
            require(
                parsed.get(field) == expected,
                f"scenario.yaml field {field!r} does not match the expected value",
                errors,
            )


def count_numbered_claims(text: str):
    return len(re.findall(r"(?m)^\\d+\\.\\s", text))


def check_completed_memo(bundle_root: Path, contract, errors):
    memo_path = bundle_root / contract["candidate_file"]
    require(memo_path.exists(), f"Missing candidate file: {contract['candidate_file']}", errors)
    if errors:
        return

    memo = memo_path.read_text(encoding="utf-8")
    memo_lower = memo.lower()

    require("TODO" not in memo, "algorithm-invariant-proof-memo.md still contains TODO markers", errors)

    for section in contract["required_sections"]:
        require(section in memo, f"Missing memo section: {section}", errors)

    for definition_id in contract["required_definition_ids"]:
        require(definition_id in memo, f"Missing formal definition reference: {definition_id}", errors)

    for assumption_id in contract["required_assumption_ids"]:
        require(assumption_id in memo, f"Missing assumption reference: {assumption_id}", errors)

    for alternative_id in contract["required_alternative_ids"]:
        require(alternative_id in memo, f"Missing alternative reference: {alternative_id}", errors)

    for invariant_id in contract["required_invariant_ids"]:
        require(invariant_id in memo, f"Missing invariant reference: {invariant_id}", errors)

    for edge_case_id in contract["required_edge_case_ids"]:
        require(edge_case_id in memo, f"Missing edge-case reference: {edge_case_id}", errors)

    for test_id in contract["required_test_ids"]:
        require(test_id in memo, f"Missing test recommendation reference: {test_id}", errors)

    for evidence_ref in contract["required_evidence_refs"]:
        require(evidence_ref in memo, f"Missing evidence reference: {evidence_ref}", errors)

    for phrase in contract["required_phrases"]:
        require(
            phrase.lower() in memo_lower,
            f"Missing required phrase: {phrase}",
            errors,
        )

    claim_count = count_numbered_claims(memo)
    require(
        claim_count >= contract["minimum_claim_count"],
        f"Claims section has {claim_count} numbered claims; expected at least {contract['minimum_claim_count']}",
        errors,
    )

    gate_pattern = rf"(?mi)^`?{re.escape(contract['expected_gate_decision'])}`?$"
    require(
        re.search(gate_pattern, memo) is not None,
        f"Gate decision is not {contract['expected_gate_decision']}",
        errors,
    )


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
        check_completed_memo(bundle_root, contract, errors)

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    mode = "bundle shape" if args.bundle_shape_only else "completed memo"
    print(f"S10 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
