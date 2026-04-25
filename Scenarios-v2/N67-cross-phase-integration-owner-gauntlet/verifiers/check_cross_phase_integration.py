#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N67 cross-phase integration-owner bundle.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    parser.add_argument("--changed-path", dest="changed_paths", action="append", default=[])
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def strip_quotes(value: str) -> str:
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


def contains_all(text: str, markers: list[str]):
    lower = text.lower()
    return all(marker.lower() in lower for marker in markers)


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


def check_changed_paths(changed_paths: list[str], contract: dict, errors: list[str]):
    if not changed_paths:
        return
    expected = sorted(contract["requiredChangedPaths"])
    actual = sorted(changed_paths)
    require(actual == expected, f"changed paths mismatch: expected {expected}, got {actual}", errors)


def evaluate_ledger(root: Path, contract: dict):
    try:
        ledger = load_json(root / "candidate" / "integration-ledger.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "ledger", "detail": f"invalid JSON: {exc}"}]
    text = json.dumps(ledger, sort_keys=True)
    failures = []
    if ledger.get("contractId") != contract["contractId"] or ledger.get("integrationFingerprint") != contract["integrationFingerprint"]:
        failures.append({"id": "ledger", "detail": "contract or fingerprint mismatch"})
    if not contains_all(text, contract["artifactMarkers"]):
        failures.append({"id": "ledger", "detail": "artifact ids or owners incomplete"})
    if not contains_all(text, contract["ledgerMarkers"]):
        failures.append({"id": "ledger", "detail": "source-ranking / pre-QA compatibility markers incomplete"})
    return failures


def evaluate_report(root: Path, contract: dict):
    text = (root / "candidate" / "incompatibility-report.md").read_text(encoding="utf-8", errors="replace")
    failures = []
    required_sections = ["## Integration Owner", "## Blocking Conflict", "## Repair Order"]
    if not contains_all(text, required_sections):
        failures.append({"id": "report", "detail": "required sections missing"})
    if not contains_all(text, contract["artifactMarkers"]):
        failures.append({"id": "report", "detail": "artifact ids or owners incomplete"})
    if not contains_all(text, contract["compatibilityMarkers"]):
        failures.append({"id": "report", "detail": "compatibility / QA-stop markers incomplete"})
    return failures


def evaluate_gate(root: Path, contract: dict):
    try:
        gate = load_json(root / "candidate" / "qa-gate.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "qa-gate", "detail": f"invalid JSON: {exc}"}]
    text = json.dumps(gate, sort_keys=True)
    failures = []
    if gate.get("contractId") != contract["contractId"] or gate.get("integrationFingerprint") != contract["integrationFingerprint"]:
        failures.append({"id": "qa-gate", "detail": "contract or fingerprint mismatch"})
    if gate.get("gate") != "REVISE_BEFORE_QA":
        failures.append({"id": "qa-gate", "detail": "gate must be REVISE_BEFORE_QA"})
    if gate.get("qaMayRun") is not False:
        failures.append({"id": "qa-gate", "detail": "qaMayRun must be false"})
    if gate.get("owner") != "integration-owner":
        failures.append({"id": "qa-gate", "detail": "owner must be integration-owner"})
    if not contains_all(text, contract["compatibilityMarkers"]):
        failures.append({"id": "qa-gate", "detail": "repair/re-entry markers incomplete"})
    return failures


def evaluate_closure(root: Path, contract: dict):
    try:
        closure = load_json(root / "candidate" / "closure.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "closure", "detail": f"invalid JSON: {exc}"}]
    text = json.dumps(closure, sort_keys=True)
    failures = []
    if closure.get("contractId") != contract["contractId"] or closure.get("integrationFingerprint") != contract["integrationFingerprint"]:
        failures.append({"id": "closure", "detail": "contract or fingerprint mismatch"})
    if sorted(closure.get("changedPaths", [])) != sorted(contract["requiredChangedPaths"]):
        failures.append({"id": "closure", "detail": "changed paths mismatch"})
    if not closure.get("outcome") or "residualRisk" not in closure or not closure.get("resumePoint"):
        failures.append({"id": "closure", "detail": "outcome, residualRisk, or resumePoint missing"})
    if not contains_all(text, contract["closureMarkers"]):
        failures.append({"id": "closure", "detail": "closure markers incomplete"})
    return failures


def evaluate_bundle(root: Path, contract: dict):
    failures = []
    failures.extend(evaluate_ledger(root, contract))
    failures.extend(evaluate_report(root, contract))
    failures.extend(evaluate_gate(root, contract))
    failures.extend(evaluate_closure(root, contract))
    return failures


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    contract = load_json(root / "oracle" / "integration-owner-contract.json")
    errors: list[str] = []
    check_shape(root, contract, errors)
    check_changed_paths(args.changed_paths, contract, errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.bundle_shape_only:
        print("N67 verifier PASS (bundle shape)")
        return 0

    failures = evaluate_bundle(root, contract)
    if args.expect_start_state:
        expected = set(contract["expected_start_state_failures"])
        observed = {failure["id"] for failure in failures}
        if observed != expected:
            print(f"ERROR: expected start-state failures {sorted(expected)}, found {sorted(observed)}", file=sys.stderr)
            for failure in failures:
                print(f"Observed start failure: {failure['id']} :: {failure.get('detail', '')}", file=sys.stderr)
            return 1
        print("N67 verifier PASS (expected start-state failures present)")
        return 0

    if failures:
        for failure in failures:
            print(f"Failed invariant: {failure['id']} :: {failure.get('detail', '')}", file=sys.stderr)
        return 1

    print("N67 verifier PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
