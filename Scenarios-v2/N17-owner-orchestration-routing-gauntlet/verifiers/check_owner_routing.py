#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N17 owner orchestration routing packet.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    return parser.parse_args()


# --- Perturbation layer (R6/B4/L00) -----------------------------------------
#
# oracle/perturbation-contract.json defines input-conditioned variants of the
# correct owner decision (non-transcribable: the correct answer depends on the
# CURRENT content of inputs/interruption-log.md, not a memorized template).
# The active perturbation is detected by hashing the selector input file(s)
# and matching against the contract's pinned snapshots -- never an out-of-band
# flag -- so a candidate cannot special-case on a marker id.

def load_perturbation_contract(root: Path):
    path = root / "oracle" / "perturbation-contract.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def detect_active_perturbation(root: Path, perturbation_contract: dict):
    input_paths = perturbation_contract["selector"]["input_paths"]
    current_hashes = {}
    for rel in input_paths:
        candidate_path = root / rel
        if not candidate_path.exists():
            return None
        current_hashes[rel] = sha256_of(candidate_path)
    for entry in perturbation_contract["perturbations"]:
        if entry.get("input_snapshots", {}) == current_hashes:
            return entry
    return None


def apply_perturbation_delta(contract: dict, perturbation_entry: dict | None) -> dict:
    """Return a copy of `contract` with the active perturbation's answer_delta merged in.

    Only list-valued keys named `add_<key>` / `remove_<key>` in answer_delta are
    touched; every other contract field (sections, tables, interruption ids) is
    left as-is -- perturbations change which FACTS are correct, not the required
    packet structure.
    """
    effective = json.loads(json.dumps(contract))
    if perturbation_entry is None:
        return effective
    delta = perturbation_entry.get("answer_delta", {})
    for key in ("required_exact_phrases", "disallowed_markers"):
        base_list = effective.get(key, [])
        remove = set(delta.get(f"remove_{key}", []))
        add = delta.get(f"add_{key}", [])
        effective[key] = [item for item in base_list if item not in remove]
        for item in add:
            if item not in effective[key]:
                effective[key].append(item)
    return effective


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


def evaluate_packet(root: Path, contract: dict):
    failures = []
    packet = root / "candidate" / "owner-routing-decision.md"
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

    missing_interruptions = [item for item in contract["expected_interruption_ids"] if f"| `{item}` |" not in text]
    if missing_interruptions:
        failures.append({"id": "missing-interruption-classification", "detail": ", ".join(missing_interruptions)})

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

    contract = load_json(root / "oracle" / "owner-routing-contract.json")
    check_shape(root, contract, errors)

    if not args.bundle_shape_only:
        perturbation_contract = load_perturbation_contract(root)
        active_perturbation = None
        if perturbation_contract is not None:
            active_perturbation = detect_active_perturbation(root, perturbation_contract)
            if active_perturbation is None:
                errors.append(
                    "Unrecognized perturbation state: inputs/interruption-log.md content does not match "
                    "any entry in oracle/perturbation-contract.json (baseline or perturbed)."
                )
        effective_contract = apply_perturbation_delta(contract, active_perturbation)
        failures = evaluate_packet(root, effective_contract)
        failure_ids = sorted(failure["id"] for failure in failures)
        if args.expect_start_state:
            expected = sorted(contract["expected_start_state_failures"])
            require(failure_ids == expected, f"Expected start-state failures {expected}, found {failure_ids}", errors)
        elif failures:
            errors.append(f"Completed packet still fails owner routing checks: {json.dumps(failures, indent=2)}")

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
    print(f"N17 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
