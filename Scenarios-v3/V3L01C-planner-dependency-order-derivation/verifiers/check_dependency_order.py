#!/usr/bin/env python3
"""Verifier for V3L01C - planner hidden dependency-ordering derivation.

Hidden-derivation oracle: the correct delivery order is RE-DERIVED here via Kahn's algorithm
with an ascending-slug tie-break over the union of (a) the explicit Depends-on edges in
inputs/workitems.json and (b) a derived edge that the candidate must infer from the prose
constraint in inputs/constraints.md. The derived edge is stored in the oracle contract (never
staged), so a leaked oracle does not hand over the order - the candidate must read the prose,
derive the edge, and topologically sort.

Read-only; executes no candidate code. Near-peer separation: a model that sorts only the explicit
edges places c-cache before d-auth; the prose-derived edge d-auth -> c-cache flips them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the V3L01C dependency-order bundle.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    return parser.parse_args()


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


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def check_shape(root: Path, contract: dict, errors: list):
    actual_entries = sorted(p.name for p in root.iterdir())
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


# ---- hidden-derivation oracle -------------------------------------------------

def build_edges(root: Path, contract: dict):
    """Merge explicit Depends-on edges (from inputs) with the prose-derived edges (from oracle)."""
    workitems = load_json(root / "inputs" / "workitems.json")
    deps: dict[str, set] = {item["slug"]: set(item.get("depends_on", [])) for item in workitems["items"]}
    for edge in contract["derived_edges"]:
        deps.setdefault(edge["item"], set()).add(edge["depends_on"])
    return [item["slug"] for item in workitems["items"]], deps


def kahn_order(items, deps):
    remaining = {i: set(deps.get(i, set())) for i in items}
    order = []
    while remaining:
        ready = sorted(i for i, d in remaining.items() if not d)
        if not ready:
            raise ValueError(f"cycle among {sorted(remaining)}")
        pick = ready[0]
        order.append(pick)
        del remaining[pick]
        for d in remaining.values():
            d.discard(pick)
    return order


def critical_path_length(items, deps):
    memo = {}

    def depth(i):
        if i in memo:
            return memo[i]
        memo[i] = 1 + max((depth(d) for d in deps.get(i, set())), default=0)
        return memo[i]

    return max(depth(i) for i in items)


def expected_answer(root: Path, contract: dict):
    items, deps = build_edges(root, contract)
    order = kahn_order(items, deps)
    return {
        "phase_order": order,
        "first_item": order[0],
        "critical_path_length": critical_path_length(items, deps),
    }


def evaluate_packet(root: Path, contract: dict):
    failures = []
    memo_path = root / "candidate" / "delivery-order.md"
    witness_path = root / "candidate" / "order-witness.json"
    text = memo_path.read_text(encoding="utf-8")

    missing_sections = [s for s in contract["required_sections"] if s not in text]
    if missing_sections:
        failures.append({"id": "missing-required-sections", "detail": ", ".join(missing_sections)})
    missing_phrases = [p for p in contract["required_exact_phrases"] if p not in text]
    if missing_phrases:
        failures.append({"id": "missing-required-phrases", "detail": ", ".join(missing_phrases)})
    missing_tables = [h for h in contract["required_table_headers"] if h not in text]
    if missing_tables:
        failures.append({"id": "missing-required-tables", "detail": ", ".join(missing_tables)})
    present_disallowed = [m for m in contract["disallowed_markers"] if m in text]
    if present_disallowed:
        failures.append({"id": "contains-disallowed-markers", "detail": ", ".join(present_disallowed)})

    try:
        witness = load_json(witness_path)
    except Exception as exc:  # noqa: BLE001
        failures.append({"id": "witness-json-invalid", "detail": str(exc)})
        return failures

    expected = expected_answer(root, contract)

    if witness.get("tie_break_rule") != contract["tie_break_rule"]:
        failures.append({"id": "witness-tie-break-rule", "detail": str(witness.get("tie_break_rule"))})
    if witness.get("phase_order") != expected["phase_order"]:
        failures.append({"id": "witness-phase-order", "detail": f"{witness.get('phase_order')} != {expected['phase_order']}"})
    if witness.get("first_item") != expected["first_item"]:
        failures.append({"id": "witness-first-item", "detail": str(witness.get("first_item"))})
    if witness.get("critical_path_length") != expected["critical_path_length"]:
        failures.append({"id": "witness-critical-path-length", "detail": str(witness.get("critical_path_length"))})

    declared = witness.get("derived_dependencies")
    declared_pairs = set()
    if isinstance(declared, list):
        for edge in declared:
            if isinstance(edge, dict) and "item" in edge and "depends_on" in edge:
                declared_pairs.add((edge["item"], edge["depends_on"]))
    for edge in contract["derived_edges"]:
        if (edge["item"], edge["depends_on"]) not in declared_pairs:
            failures.append({"id": "witness-missing-derived-edge", "detail": f"{edge['item']} depends on {edge['depends_on']}"})

    return failures


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    errors: list = []
    if not root.exists():
        print(f"Bundle root does not exist: {root}", file=sys.stderr)
        return 1

    contract = load_json(root / "oracle" / "dependency-order-contract.json")
    check_shape(root, contract, errors)

    if not args.bundle_shape_only:
        failures = evaluate_packet(root, contract)
        failure_ids = sorted({f["id"] for f in failures})
        if args.expect_start_state:
            expected = sorted(contract["expected_start_state_failures"])
            require(failure_ids == expected, f"Expected start-state failures {expected}, found {failure_ids}", errors)
        elif failures:
            errors.append(f"Completed V3L01C packet still fails checks: {json.dumps(failures, indent=2)}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    mode = "bundle shape" if args.bundle_shape_only else ("start state" if args.expect_start_state else "completed packet")
    print(f"V3L01C verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
