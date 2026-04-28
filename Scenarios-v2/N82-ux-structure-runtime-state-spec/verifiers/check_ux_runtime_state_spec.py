#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N82 UX runtime state spec.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    parser.add_argument("--answer-file", type=Path)
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
        if not line or line.startswith(" ") or line.startswith("#"):
            continue
        if ":" in line:
            keys.append(line.split(":", 1)[0].strip())
    return keys


def normalize(value) -> str:
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


def all_terms_in(value, terms):
    text = normalize(value)
    return all(term.lower() in text for term in terms)


def require(condition: bool, message: str, errors: list[str]):
    if not condition:
        errors.append(message)


def check_changed_paths(changed_paths, contract, errors):
    if not changed_paths:
        return
    expected = sorted(contract["requiredChangedPaths"])
    actual = sorted(changed_paths)
    require(actual == expected, f"changed paths mismatch: expected {expected}, got {actual}", errors)


def check_bundle_shape(bundle_root: Path, contract, errors):
    actual_entries = sorted(path.name for path in bundle_root.iterdir())
    require(
        actual_entries == sorted(contract["required_top_level_entries"]),
        f"Top-level bundle entries drifted: {actual_entries}",
        errors,
    )
    for relative_path in contract["required_bundle_paths"]:
        require((bundle_root / relative_path).exists(), f"Missing required bundle path: {relative_path}", errors)

    scenario_path = bundle_root / "scenario.yaml"
    require(scenario_path.exists(), "Missing scenario.yaml", errors)
    if not scenario_path.exists():
        return
    require(
        top_level_yaml_keys(scenario_path) == contract["scenario_yaml_fields"],
        "scenario.yaml fields do not match the required contract order exactly",
        errors,
    )
    require(
        parse_simple_yaml(scenario_path) == contract["expected_metadata"],
        "scenario.yaml metadata does not match N82",
        errors,
    )


def load_answer(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return None, str(exc)


def match_by_id(items, specs, label, errors):
    matched = 0
    missing = []
    by_id = {}
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                by_id[item["id"]] = item
    for spec in specs:
        item = by_id.get(spec["id"])
        if item is None or not all_terms_in(item, spec["terms"]):
            errors.append(f"{label} {spec['id']} has no matching object")
            missing.append(spec["id"])
        else:
            matched += 1
    return matched, missing


def score_answer(answer_path: Path, contract):
    errors: list[str] = []
    metrics = {
        "verdict": "FAIL",
        "score_0_100": 0.0,
        "matched_count": 0,
        "expected_count": 27,
        "pass_score_threshold_0_100": float(contract["pass_score_threshold_0_100"]),
        "parse_error": None,
        "missing": {},
        "failures": [],
    }
    answer, parse_error = load_answer(answer_path)
    if parse_error:
        metrics["parse_error"] = parse_error
        metrics["failures"].append(f"parse-error: {parse_error}")
        return metrics
    if not isinstance(answer, dict):
        metrics["failures"].append("answer is not a JSON object")
        return metrics

    require(list(answer.keys()) == contract["top_level_keys"], "top-level key order mismatch", errors)
    require(answer.get("spec_id") == "N82-ux-runtime-state-v1", "spec_id mismatch", errors)
    require(answer.get("role_owner") == "$ux-designer", "role_owner must be $ux-designer", errors)

    for key, expected_count in contract["expected_counts"].items():
        value = answer.get(key)
        require(isinstance(value, list), f"{key} must be a list", errors)
        if isinstance(value, list):
            require(len(value) == expected_count, f"{key} count mismatch: expected {expected_count}, got {len(value)}", errors)

    matched, missing = match_by_id(answer.get("state_model"), contract["required_states"], "state", errors)
    metrics["matched_count"] += matched
    metrics["missing"]["state_model"] = missing
    matched, missing = match_by_id(answer.get("breakpoint_invariants"), contract["required_breakpoints"], "breakpoint", errors)
    metrics["matched_count"] += matched
    metrics["missing"]["breakpoint_invariants"] = missing
    matched, missing = match_by_id(answer.get("affordance_rules"), contract["required_affordances"], "affordance", errors)
    metrics["matched_count"] += matched
    metrics["missing"]["affordance_rules"] = missing
    matched, missing = match_by_id(answer.get("copy_ledger"), contract["required_copy"], "copy", errors)
    metrics["matched_count"] += matched
    metrics["missing"]["copy_ledger"] = missing
    matched, missing = match_by_id(answer.get("handoff_contracts"), contract["required_handoffs"], "handoff", errors)
    metrics["matched_count"] += matched
    metrics["missing"]["handoff_contracts"] = missing
    matched, missing = match_by_id(answer.get("non_goals"), contract["required_non_goals"], "non-goal", errors)
    metrics["matched_count"] += matched
    metrics["missing"]["non_goals"] = missing

    full_text = normalize(answer)
    for term in contract["forbidden_global_terms"]:
        require(term.lower() not in full_text, f"forbidden global term present: {term}", errors)

    metrics["score_0_100"] = round(100.0 * metrics["matched_count"] / metrics["expected_count"], 3)
    if metrics["score_0_100"] < metrics["pass_score_threshold_0_100"]:
        errors.append(
            f"score below threshold: {metrics['score_0_100']} < {metrics['pass_score_threshold_0_100']}"
        )
    metrics["failures"] = errors
    if not errors:
        metrics["verdict"] = "PASS"
    return metrics


def write_metrics(path: Path | None, metrics: dict):
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")


def main():
    args = parse_args()
    bundle_root = args.bundle_root.resolve()
    if not bundle_root.exists():
        print(f"Bundle root does not exist: {bundle_root}", file=sys.stderr)
        return 1

    errors: list[str] = []
    contract = load_json(bundle_root / "oracle" / "ux-state-contract.json")
    check_bundle_shape(bundle_root, contract, errors)
    check_changed_paths(args.changed_paths, contract, errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.bundle_shape_only:
        print("N82 verifier PASS (bundle shape)")
        return 0

    answer_path = args.answer_file or (bundle_root / contract["editable_report"])
    metrics = score_answer(answer_path, contract)
    write_metrics(args.metrics_out, metrics)

    if args.expect_start_state:
        if metrics["matched_count"] != 0 or metrics["verdict"] == "PASS":
            print("ERROR: start-state unexpectedly passes or partially matches", file=sys.stderr)
            return 1
        print("N82 verifier PASS (expected start-state failures present)")
        return 0

    if metrics["verdict"] != "PASS":
        for failure in metrics["failures"]:
            print(f"Failed invariant: {failure}", file=sys.stderr)
        print(f"N82 score: {metrics['score_0_100']} matched={metrics['matched_count']}/{metrics['expected_count']}", file=sys.stderr)
        return 1

    print("N82 verifier PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
