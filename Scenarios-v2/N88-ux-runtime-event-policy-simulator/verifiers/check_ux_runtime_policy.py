#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N88 UX runtime event-policy simulator.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    parser.add_argument("--metrics-out", type=Path)
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


def check_bundle_shape(root: Path, contract: dict, errors: list[str]):
    actual_entries = sorted(path.name for path in root.iterdir())
    require(actual_entries == sorted(contract["required_top_level_entries"]), f"top-level entries drifted: {actual_entries}", errors)
    scenario = root / "scenario.yaml"
    require(top_level_yaml_keys(scenario) == contract["scenario_yaml_fields"], "scenario.yaml field order drifted", errors)
    require(parse_simple_yaml(scenario) == contract["expected_metadata"], "scenario.yaml metadata mismatch", errors)
    for relative_path in contract["required_bundle_paths"]:
        require((root / relative_path).exists(), f"missing required bundle path: {relative_path}", errors)


def load_candidate(root: Path):
    return {
        "runtime": load_json(root / "candidate" / "runtime-policy.json"),
        "breakpoints": load_json(root / "candidate" / "breakpoint-policy.json"),
        "reentry": load_json(root / "candidate" / "reentry-policy.json"),
    }


def has_keys(obj: dict, keys: list[str], label: str, errors: list[str]):
    missing = sorted(set(keys) - set(obj))
    if missing:
        errors.append(f"{label} missing keys: {missing}")


def match_when(condition: dict, state: dict):
    when = condition.get("when", {})
    if not isinstance(when, dict):
        return False
    for key, value in when.items():
        if state.get(key) != value:
            return False
    return True


def simulate(runtime: dict, state: dict):
    conditions = runtime.get("conditions", [])
    if not isinstance(conditions, list):
        return None
    ordered = sorted(
        [item for item in conditions if isinstance(item, dict)],
        key=lambda item: item.get("priority", 999),
    )
    for condition in ordered:
        if match_when(condition, state):
            return {
                "dominantAction": condition.get("dominantAction"),
                "publishEnabled": bool(condition.get("publishEnabled")),
                "disabledReason": condition.get("disabledReason"),
            }
    return None


def check_runtime(runtime: dict, contract: dict, errors: list[str], metrics: dict):
    has_keys(runtime, contract["requiredRuntimeKeys"], "runtime-policy", errors)
    if runtime.get("contractId") != contract["contractId"]:
        errors.append("runtime-policy contractId mismatch")
    if runtime.get("planFingerprint") != contract["planFingerprint"]:
        errors.append("runtime-policy planFingerprint mismatch")
    action_priority = runtime.get("actionPriority", [])
    for action in contract["requiredActions"]:
        if action not in action_priority:
            errors.append(f"runtime-policy missing action priority: {action}")
    reasons = runtime.get("disabledReasons", {})
    for reason in contract["requiredDisabledReasons"]:
        if reason not in reasons:
            errors.append(f"runtime-policy missing disabled reason: {reason}")

    passed_traces = 0
    failed = []
    for trace in contract["hiddenTraces"]:
        actual = simulate(runtime, trace["state"])
        expected = trace["expected"]
        if actual == expected:
            passed_traces += 1
        else:
            failed.append({"id": trace["id"], "expected": expected, "actual": actual})
            errors.append(f"trace {trace['id']} mismatch")
    metrics["passedTraces"] = passed_traces
    metrics["failedTraces"] = failed


def check_breakpoints(policy: dict, contract: dict, errors: list[str], metrics: dict):
    has_keys(policy, contract["requiredBreakpointKeys"], "breakpoint-policy", errors)
    if policy.get("contractId") != contract["contractId"]:
        errors.append("breakpoint-policy contractId mismatch")
    if policy.get("planFingerprint") != contract["planFingerprint"]:
        errors.append("breakpoint-policy planFingerprint mismatch")
    breakpoints = policy.get("breakpoints", {})
    passed = 0
    for bp_id, expectation in contract["breakpointExpectations"].items():
        order = breakpoints.get(bp_id, {}).get("order")
        if not isinstance(order, list):
            errors.append(f"breakpoint {bp_id} missing order")
            continue
        missing = [item for item in expectation["mustContain"] if item not in order]
        if missing:
            errors.append(f"breakpoint {bp_id} missing items: {missing}")
            continue
        bad_order = []
        for before, after in expectation["before"]:
            if order.index(before) > order.index(after):
                bad_order.append([before, after])
        if bad_order:
            errors.append(f"breakpoint {bp_id} order mismatch: {bad_order}")
            continue
        passed += 1
    metrics["passedBreakpoints"] = passed


def check_reentry(policy: dict, contract: dict, errors: list[str], metrics: dict):
    has_keys(policy, contract["requiredReentryKeys"], "reentry-policy", errors)
    if policy.get("contractId") != contract["contractId"]:
        errors.append("reentry-policy contractId mismatch")
    if policy.get("planFingerprint") != contract["planFingerprint"]:
        errors.append("reentry-policy planFingerprint mismatch")
    passed = 0
    for section, expected in contract["reentryExpectations"].items():
        actual = policy.get(section, {})
        section_ok = True
        for key, value in expected.items():
            if actual.get(key) != value:
                errors.append(f"reentry {section}.{key} mismatch")
                section_ok = False
        if section_ok:
            passed += 1
    metrics["passedReentrySections"] = passed


def check_changed_paths(changed_paths: list[str], contract: dict, errors: list[str]):
    if not changed_paths:
        return
    expected = sorted(contract["requiredChangedPaths"])
    actual = sorted(path.replace("\\", "/") for path in changed_paths)
    require(actual == expected, f"changed paths mismatch: expected {expected}, got {actual}", errors)


def evaluate(root: Path, contract: dict, changed_paths: list[str]):
    errors: list[str] = []
    metrics = {
        "verdict": "FAIL",
        "score_0_100": 0.0,
        "passedTraces": 0,
        "passedBreakpoints": 0,
        "passedReentrySections": 0,
        "expectedTraces": len(contract["hiddenTraces"]),
        "expectedBreakpoints": len(contract["breakpointExpectations"]),
        "expectedReentrySections": len(contract["reentryExpectations"]),
        "failedTraces": [],
    }
    try:
        candidate = load_candidate(root)
    except Exception as exc:  # noqa: BLE001
        return [f"candidate JSON load failed: {exc}"], metrics

    check_runtime(candidate["runtime"], contract, errors, metrics)
    check_breakpoints(candidate["breakpoints"], contract, errors, metrics)
    check_reentry(candidate["reentry"], contract, errors, metrics)
    check_changed_paths(changed_paths, contract, errors)

    total = metrics["expectedTraces"] + metrics["expectedBreakpoints"] + metrics["expectedReentrySections"]
    passed = metrics["passedTraces"] + metrics["passedBreakpoints"] + metrics["passedReentrySections"]
    metrics["score_0_100"] = round((passed / total) * 100.0, 1)
    if not errors and metrics["score_0_100"] >= contract["pass_score_threshold_0_100"]:
        metrics["verdict"] = "PASS"
    return errors, metrics


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    contract = load_json(root / "oracle" / "ux-runtime-policy-contract.json")
    shape_errors: list[str] = []
    check_bundle_shape(root, contract, shape_errors)
    if shape_errors:
        for error in shape_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.bundle_shape_only:
        print("N88 verifier PASS (bundle shape)")
        return 0

    errors, metrics = evaluate(root, contract, args.changed_paths)
    if args.metrics_out:
        args.metrics_out.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    if args.expect_start_state:
        required = {
            "runtime-policy planFingerprint mismatch",
            "breakpoint-policy planFingerprint mismatch",
            "reentry-policy planFingerprint mismatch",
            "runtime-policy missing action priority: refresh-source",
            "trace T1-remote-stale mismatch",
            "breakpoint desktop-1440 missing order",
            "reentry publishedReceipt.persistDuringFollowUp mismatch",
        }
        observed = set(errors)
        missing = sorted(required - observed)
        if missing:
            print(f"ERROR: start state no longer exposes expected failures: {missing}", file=sys.stderr)
            return 1
        print("N88 verifier PASS (expected start-state failures present)")
        return 0

    if errors:
        for error in errors:
            print(f"Failed invariant: {error}", file=sys.stderr)
        print(f"N88 score: {metrics['score_0_100']} / 100", file=sys.stderr)
        return 1

    print(f"N88 verifier PASS ({metrics['score_0_100']} / 100)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
