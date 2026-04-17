#!/usr/bin/env python3

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        description="Check the S11 model-validation bundle shape or a completed candidate memo."
    )
    default_root = Path(__file__).resolve().parents[1]
    parser.add_argument(
        "--bundle-root",
        type=Path,
        default=default_root,
        help="Path to the S11 bundle root.",
    )
    parser.add_argument(
        "--bundle-shape-only",
        action="store_true",
        help="Validate only the bundle contract, not a completed candidate run.",
    )
    return parser.parse_args()


def load_contract(bundle_root: Path):
    contract_path = bundle_root / "oracle" / "model-validation-contract.json"
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


def check_bundle_shape(bundle_root: Path, contract, errors):
    expected_entries = sorted(contract["required_top_level_entries"])
    actual_entries = sorted(path.name for path in bundle_root.iterdir())
    require(
        actual_entries == expected_entries,
        "Bundle root top-level entries do not match the required six-entry contract exactly",
        errors,
    )

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


def count_numbered_claims(text: str):
    return len(re.findall(r"(?m)^\d+\.\s", text))


def check_completed_memo(bundle_root: Path, contract, errors):
    memo_path = bundle_root / contract["candidate_file"]
    require(memo_path.exists(), f"Missing candidate file: {contract['candidate_file']}", errors)
    if errors:
        return

    memo = memo_path.read_text(encoding="utf-8")
    memo_lower = memo.lower()

    for marker in contract["disallowed_markers"]:
        require(marker not in memo, f"Disallowed marker present in memo: {marker}", errors)

    for section in contract["required_sections"]:
        require(section in memo, f"Missing memo section: {section}", errors)

    for equation_id in contract["required_equation_ids"]:
        require(equation_id in memo, f"Missing equation reference: {equation_id}", errors)

    for assumption_id in contract["required_assumption_ids"]:
        require(assumption_id in memo, f"Missing assumption reference: {assumption_id}", errors)

    for invariant_id in contract["required_invariant_ids"]:
        require(invariant_id in memo, f"Missing invariant reference: {invariant_id}", errors)

    for validation_id in contract["required_validation_ids"]:
        require(validation_id in memo, f"Missing validation reference: {validation_id}", errors)

    for limitation_id in contract["required_limitation_ids"]:
        require(limitation_id in memo, f"Missing limitation reference: {limitation_id}", errors)

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
    print(f"S11 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
