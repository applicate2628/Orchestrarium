#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N40 staged owner recovery bundle.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    return parser.parse_args()


# --- Perturbation layer (R6/B4/L00) -----------------------------------------
#
# oracle/perturbation-contract.json defines input-conditioned variants of the
# correct route decision (non-transcribable: finding-18 -- the routeDecision
# markers appear verbatim in inputs/phases/02-route-decision.md, so a
# memorized/copied answer that reproduces the ORIGINAL phase-file wording must
# fail once the CURRENT phase file says something else). The active
# perturbation is detected by hashing the selector input file(s) and matching
# against the contract's pinned snapshots -- never an out-of-band flag.

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
    touched (here: routeDecisionMarkers); every other contract field (phase
    ids, required sections, changed-path budget) is left as-is -- perturbations
    change which FACTS are correct, not the required packet structure.
    """
    effective = json.loads(json.dumps(contract))
    if perturbation_entry is None:
        return effective
    delta = perturbation_entry.get("answer_delta", {})
    for key in ("routeDecisionMarkers",):
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
    require(actual_entries == sorted(contract["required_top_level_entries"]), f"Top-level bundle entries drifted: {actual_entries}", errors)
    scenario = root / "scenario.yaml"
    require(top_level_yaml_keys(scenario) == contract["scenario_yaml_fields"], "scenario.yaml field order drifted", errors)
    require(parse_simple_yaml(scenario) == contract["expected_metadata"], "scenario.yaml metadata mismatch", errors)
    for path in contract["required_bundle_paths"]:
        require((root / path).exists(), f"Missing required bundle path: {path}", errors)


def item_id(item: dict):
    return item.get("id") or item.get("sourceId") or item.get("staleId") or item.get("phaseId")


def evaluate_source_ledger(root: Path, contract: dict):
    try:
        ledger = load_json(root / "candidate" / "source-ledger.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "source-ledger-complete", "detail": f"invalid JSON: {exc}"}]
    text = json.dumps(ledger, sort_keys=True)
    failures = []
    if ledger.get("contractId") != contract["contractId"] or ledger.get("planFingerprint") != contract["planFingerprint"]:
        failures.append({"id": "source-ledger-complete", "detail": "contract or fingerprint mismatch"})
    if not contains_all(text, contract["expectedSourceIds"]):
        failures.append({"id": "source-ledger-complete", "detail": "missing source ids"})
    if not contains_all(text, contract["expectedStaleIds"]):
        failures.append({"id": "stale-rejection-complete", "detail": "missing stale ids"})
    for marker in ["no global winner", "runtime failures are model failures", "old full-v2 denominator includes N38/N39", "write a new parallel results copy"]:
        if marker.lower() not in text.lower():
            failures.append({"id": "stale-rejection-complete", "detail": f"missing stale rejection marker: {marker}"})
            break
    phase_ids = {item_id(item) for item in ledger.get("phases", []) if isinstance(item, dict)}
    phase_owners = [item for item in ledger.get("phases", []) if isinstance(item, dict) and (item.get("owner") or item.get("ownerPath"))]
    if set(contract["expectedPhaseIds"]) - phase_ids or len(phase_owners) < len(contract["expectedPhaseIds"]):
        failures.append({"id": "phase-ledger-complete", "detail": "phase ids or owners incomplete"})
    return failures


def evaluate_route(root: Path, contract: dict):
    text = (root / "candidate" / "route-decision.md").read_text(encoding="utf-8", errors="replace")
    failures = []
    if contract["planFingerprint"] not in text:
        failures.append({"id": "route-decision-complete", "detail": "plan fingerprint missing"})
    if not contains_all(text, contract["routeDecisionRequiredSections"]):
        failures.append({"id": "route-decision-complete", "detail": "required sections missing"})
    if not contains_all(text, contract["routeDecisionMarkers"]):
        failures.append({"id": "route-decision-complete", "detail": "route markers incomplete"})
    if not contains_all(text, contract["expectedSourceIds"]):
        failures.append({"id": "route-decision-complete", "detail": "source ids incomplete"})
    return failures


def evaluate_runtime(root: Path, contract: dict):
    try:
        policy = load_json(root / "candidate" / "runtime-policy.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "runtime-policy-complete", "detail": f"invalid JSON: {exc}"}]
    text = json.dumps(policy, sort_keys=True)
    if policy.get("contractId") != contract["contractId"] or policy.get("planFingerprint") != contract["planFingerprint"]:
        return [{"id": "runtime-policy-complete", "detail": "contract or fingerprint mismatch"}]
    if not contains_all(text, contract["runtimePolicyMarkers"]):
        return [{"id": "runtime-policy-complete", "detail": "runtime markers incomplete"}]
    return []


def evaluate_closure(root: Path, contract: dict):
    try:
        closure = load_json(root / "candidate" / "closure.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "closure-complete", "detail": f"invalid JSON: {exc}"}]
    text = json.dumps(closure, sort_keys=True)
    if closure.get("contractId") != contract["contractId"] or closure.get("planFingerprint") != contract["planFingerprint"]:
        return [{"id": "closure-complete", "detail": "contract or fingerprint mismatch"}]
    if sorted(closure.get("changedPaths", [])) != sorted(contract["requiredChangedPaths"]):
        return [{"id": "closure-complete", "detail": "changed paths mismatch"}]
    if not closure.get("outcome") or "residualRisk" not in closure or not closure.get("resumePoint"):
        return [{"id": "closure-complete", "detail": "outcome, residualRisk, or resumePoint missing"}]
    if not contains_all(text, contract["closureMarkers"]):
        return [{"id": "closure-complete", "detail": "closure markers incomplete"}]
    return []


def evaluate_bundle(root: Path, contract: dict):
    failures = []
    failures.extend(evaluate_source_ledger(root, contract))
    failures.extend(evaluate_route(root, contract))
    failures.extend(evaluate_runtime(root, contract))
    failures.extend(evaluate_closure(root, contract))
    return failures


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    contract = load_json(root / "oracle" / "owner-recovery-contract.json")
    shape_errors: list[str] = []
    check_shape(root, contract, shape_errors)
    if shape_errors:
        for error in shape_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.bundle_shape_only:
        print("N40 verifier PASS (bundle shape)")
        return 0

    perturbation_contract = load_perturbation_contract(root)
    active_perturbation = None
    if perturbation_contract is not None:
        active_perturbation = detect_active_perturbation(root, perturbation_contract)
        if active_perturbation is None:
            print(
                "ERROR: Unrecognized perturbation state: inputs/phases/02-route-decision.md content "
                "does not match any entry in oracle/perturbation-contract.json (baseline or perturbed).",
                file=sys.stderr,
            )
            return 1
    effective_contract = apply_perturbation_delta(contract, active_perturbation)

    failures = evaluate_bundle(root, effective_contract)
    if args.expect_start_state:
        expected = set(contract["expected_start_state_failures"])
        observed = {failure["id"] for failure in failures}
        if observed != expected:
            print(f"ERROR: expected start-state failures {sorted(expected)}, found {sorted(observed)}", file=sys.stderr)
            for failure in failures:
                print(f"Observed start failure: {failure['id']} :: {failure.get('detail', '')}", file=sys.stderr)
            return 1
        print("N40 verifier PASS (expected start-state failures present)")
        return 0

    if failures:
        for failure in failures:
            print(f"Failed invariant: {failure['id']} :: {failure.get('detail', '')}", file=sys.stderr)
        return 1

    print("N40 verifier PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
