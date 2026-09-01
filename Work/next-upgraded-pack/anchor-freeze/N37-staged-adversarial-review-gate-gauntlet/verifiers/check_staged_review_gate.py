#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N37 staged ADR/review gate bundle.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
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


def json_text(value):
    return json.dumps(value, sort_keys=True)


def contains_all(text: str, markers: list[str]):
    lower = text.lower()
    return all(marker.lower() in lower for marker in markers)


def find_phase(state: dict, phase_id: str):
    for item in state.get("phases", []):
        if not isinstance(item, dict):
            continue
        if item.get("id") == phase_id or item.get("phase") == phase_id or item.get("phaseId") == phase_id:
            return item
    return None


def item_id(item: dict):
    return item.get("id") or item.get("findingId") or item.get("responseId") or item.get("reviewId")


def evaluate_state(root: Path, contract: dict):
    failures = []
    try:
        state = load_json(root / "candidate" / "review-state.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "review-state-schema", "detail": f"invalid JSON: {exc}"}]

    if not set(contract["requiredStateKeys"]) <= set(state):
        missing = sorted(set(contract["requiredStateKeys"]) - set(state))
        return [{"id": "review-state-schema", "detail": f"missing keys: {missing}"}]

    text = json_text(state)
    if state.get("contractId") != contract["contractId"]:
        failures.append({"id": "review-state-schema", "detail": "contractId mismatch"})
    if contract["planFingerprint"] not in text:
        failures.append({"id": "phase-ledger-complete", "detail": "plan fingerprint missing"})
    for source_id in contract["expectedSourceIds"]:
        if source_id not in text:
            failures.append({"id": "source-binding-complete", "detail": f"missing {source_id}"})
            break
    for phase_id in contract["expectedPhaseIds"]:
        phase = find_phase(state, phase_id)
        if not phase:
            failures.append({"id": "phase-ledger-complete", "detail": f"missing phase {phase_id}"})
            break
        if not (phase.get("owner") or phase.get("ownerPath")):
            failures.append({"id": "phase-ledger-complete", "detail": f"missing owner for {phase_id}"})
            break

    for section, markers in contract["requiredLedgerRows"].items():
        if section == "adrMarkers":
            continue
        if not contains_all(text, markers):
            failures.append({"id": f"ledger-{section}", "detail": f"missing one of {markers}"})

    budget = state.get("patchBudget", {})
    if budget.get("maxChangedPaths") != len(contract["requiredChangedPaths"]):
        failures.append({"id": "review-patch-budget", "detail": "maxChangedPaths mismatch"})
    if sorted(budget.get("requiredChangedPaths", [])) != sorted(contract["requiredChangedPaths"]):
        failures.append({"id": "review-patch-budget", "detail": "requiredChangedPaths mismatch"})
    return failures


def evaluate_adr(root: Path, contract: dict):
    text = (root / "candidate" / "decision-adr.md").read_text(encoding="utf-8", errors="replace")
    failures = []
    if contract["planFingerprint"] not in text:
        failures.append({"id": "adr-source-bound", "detail": "plan fingerprint missing"})
    if not contains_all(text, contract["requiredLedgerRows"]["adrMarkers"]):
        failures.append({"id": "adr-source-bound", "detail": "required ADR markers missing"})
    if not contains_all(text, contract["expectedSourceIds"]):
        failures.append({"id": "adr-source-bound", "detail": "source IDs incomplete"})
    return failures


def evaluate_findings(root: Path, contract: dict):
    failures = []
    try:
        findings_doc = load_json(root / "candidate" / "findings.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "findings-schema", "detail": f"invalid JSON: {exc}"}]

    findings = findings_doc.get("findings", [])
    if not isinstance(findings, list):
        return [{"id": "findings-schema", "detail": "findings must be a list"}]
    by_id = {item_id(item): item for item in findings if isinstance(item, dict) and item_id(item)}

    for finding_id, expected in contract["expectedFindings"].items():
        item = by_id.get(finding_id)
        if not item:
            failures.append({"id": "finding-tuples", "detail": f"missing {finding_id}"})
            continue
        for field in ["severity", "owner", "file", "symbol"]:
            if item.get(field) != expected[field]:
                failures.append({"id": "finding-tuples", "detail": f"{finding_id}.{field} mismatch"})
                break
        item_text = json_text(item)
        for field in ["evidenceCue", "remediationCue"]:
            if expected[field].lower() not in item_text.lower():
                failures.append({"id": "finding-tuples", "detail": f"{finding_id}.{field} missing"})
                break
        source_ids = item.get("source_ids") or item.get("sourceIds")
        if not isinstance(source_ids, list) or not source_ids:
            failures.append({"id": "finding-source-ids", "detail": f"{finding_id} source_ids missing"})

    all_text = json_text(findings_doc)
    for forbidden in contract["forbiddenFalsePositiveIds"]:
        if forbidden in by_id:
            failures.append({"id": "false-positive-avoidance", "detail": f"{forbidden} listed as finding"})
    if not contains_all(all_text, contract["forbiddenFalsePositiveIds"]):
        failures.append({"id": "non-finding-ledger", "detail": "false-positive IDs missing from nonFindings"})
    if not contains_all(all_text, contract["requiredNonClaimMarkers"]):
        failures.append({"id": "non-finding-ledger", "detail": "required non-claim markers missing"})
    return failures


def evaluate_response_gate(root: Path, contract: dict):
    failures = []
    try:
        response = load_json(root / "candidate" / "response-gate.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "response-gate-schema", "detail": f"invalid JSON: {exc}"}]

    responses = response.get("responses", [])
    if not isinstance(responses, list):
        return [{"id": "response-gate-schema", "detail": "responses must be a list"}]
    by_id = {item_id(item): item for item in responses if isinstance(item, dict) and item_id(item)}
    for response_id, decision in contract["responseDecisions"].items():
        item = by_id.get(response_id)
        if not item:
            failures.append({"id": "response-gate-complete", "detail": f"missing {response_id}"})
            continue
        if str(item.get("decision", "")).lower() != decision:
            failures.append({"id": "response-gate-complete", "detail": f"{response_id} decision mismatch"})
        if not (item.get("owner") or item.get("ownerPath")):
            failures.append({"id": "response-gate-complete", "detail": f"{response_id} missing owner"})
        if not (item.get("visibleReturnCue") or item.get("validationCue")):
            failures.append({"id": "response-gate-complete", "detail": f"{response_id} missing visible return cue"})
    return failures


def evaluate_closure(root: Path, contract: dict):
    failures = []
    try:
        closure = load_json(root / "candidate" / "closure.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "closure-schema", "detail": f"invalid JSON: {exc}"}]

    text = json_text(closure)
    if contract["planFingerprint"] not in text:
        failures.append({"id": "closure-complete", "detail": "plan fingerprint missing"})
    if sorted(closure.get("changedPaths", [])) != sorted(contract["requiredChangedPaths"]):
        failures.append({"id": "closure-complete", "detail": "changed paths mismatch"})
    if not contains_all(text, contract["requiredClosureMarkers"]):
        failures.append({"id": "closure-complete", "detail": "closure markers incomplete"})
    validation_text = json_text(closure.get("validation", []))
    for marker in contract["requiredLedgerRows"]["validationMarkers"]:
        if marker not in validation_text:
            failures.append({"id": "closure-complete", "detail": f"validation marker missing {marker}"})
            break
    if "reviewOutcome" not in closure or not closure.get("reviewOutcome"):
        failures.append({"id": "closure-complete", "detail": "review outcome missing"})
    if "residualRisk" not in closure:
        failures.append({"id": "closure-complete", "detail": "residualRisk missing"})
    return failures


def evaluate_bundle(root: Path, contract: dict):
    failures = []
    failures.extend(evaluate_state(root, contract))
    failures.extend(evaluate_adr(root, contract))
    failures.extend(evaluate_findings(root, contract))
    failures.extend(evaluate_response_gate(root, contract))
    failures.extend(evaluate_closure(root, contract))
    return failures


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    contract = load_json(root / "oracle" / "review-gate-contract.json")
    shape_errors: list[str] = []
    check_shape(root, contract, shape_errors)
    if shape_errors:
        for error in shape_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.bundle_shape_only:
        print("N37 verifier PASS (bundle shape)")
        return 0

    failures = evaluate_bundle(root, contract)
    if args.expect_start_state:
        expected = {
            "phase-ledger-complete",
            "source-binding-complete",
            "ledger-findings",
            "ledger-falsePositives",
            "ledger-staleRejections",
            "ledger-validationMarkers",
            "review-patch-budget",
            "adr-source-bound",
            "finding-tuples",
            "non-finding-ledger",
            "response-gate-complete",
            "closure-complete",
        }
        observed = {failure["id"] for failure in failures}
        missing = sorted(expected - observed)
        if missing:
            print(f"ERROR: start state no longer exposes expected failures: {missing}", file=sys.stderr)
            return 1
        print("N37 verifier PASS (expected start-state failures present)")
        return 0

    if failures:
        for failure in failures:
            print(f"Failed invariant: {failure['id']} :: {failure.get('detail', '')}", file=sys.stderr)
        return 1

    print("N37 verifier PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
