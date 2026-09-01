#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, ROUND_HALF_UP, getcontext
from fractions import Fraction
from pathlib import Path


getcontext().prec = 40


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N22 numerical stability decision bundle.")
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


def exact_p95(latency_counts: dict[str, int]):
    total = sum(int(count) for count in latency_counts.values())
    rank = (95 * total + 99) // 100
    cumulative = 0
    for value_text, count in sorted(latency_counts.items(), key=lambda item: int(item[0])):
        cumulative += int(count)
        if cumulative >= rank:
            return int(value_text)
    raise ValueError("empty latency count table")


def population_variance(variance_shards: list[list[int]]):
    samples = [int(value) for shard in variance_shards for value in shard]
    if not samples:
        raise ValueError("empty variance samples")
    mean = Fraction(sum(samples), len(samples))
    return sum((Fraction(value) - mean) ** 2 for value in samples) / len(samples)


def decimal_six(value: Fraction):
    decimal = Decimal(value.numerator) / Decimal(value.denominator)
    return decimal.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def expected_witnesses(root: Path):
    cases_doc = load_json(root / "inputs" / "cases.json")
    expected = {}
    for case in cases_doc["cases"]:
        p95 = exact_p95(case["latency_counts_ms"])
        variance = decimal_six(population_variance(case["variance_shards"]))
        reasons = []
        if p95 > 200:
            reasons.append(f"p95 latency {p95}ms exceeds <= 200ms")
        if variance > Decimal("4.000000"):
            reasons.append(f"population variance {variance} exceeds <= 4.000000")
        expected[case["case_id"]] = {
            "p95": p95,
            "population_variance": variance,
            "gate_verdict": "FAIL" if reasons else "PASS",
            "failure_reasons": reasons,
        }
    return expected


def parse_decimal(value):
    return Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def evaluate_packet(root: Path, contract: dict):
    failures = []
    memo_path = root / "candidate" / "numerical-stability-decision-memo.md"
    witness_path = root / "candidate" / "witness-ledger.json"
    text = memo_path.read_text(encoding="utf-8")

    missing_sections = [section for section in contract["required_sections"] if section not in text]
    if missing_sections:
        failures.append({"id": "missing-required-sections", "detail": ", ".join(missing_sections)})

    missing_phrases = [phrase for phrase in contract["required_exact_phrases"] if phrase not in text]
    if missing_phrases:
        failures.append({"id": "missing-required-phrases", "detail": ", ".join(missing_phrases)})

    missing_tables = [header for header in contract["required_table_headers"] if header not in text]
    if missing_tables:
        failures.append({"id": "missing-required-tables", "detail": ", ".join(missing_tables)})

    present_disallowed = [marker for marker in contract["disallowed_markers"] if marker in text]
    if present_disallowed:
        failures.append({"id": "contains-disallowed-markers", "detail": ", ".join(present_disallowed)})

    try:
        witness = load_json(witness_path)
    except Exception as exc:  # noqa: BLE001 - verifier should report any JSON failure compactly.
        failures.append({"id": "witness-json-invalid", "detail": str(exc)})
        return failures

    if witness.get("selected_option") != contract["selected_option"]:
        failures.append({"id": "witness-selected-option", "detail": str(witness.get("selected_option"))})

    if witness.get("quantile_convention") != contract["quantile_convention"]:
        failures.append({"id": "witness-quantile-convention", "detail": str(witness.get("quantile_convention"))})

    rejected = witness.get("rejected_options")
    if not isinstance(rejected, dict) or sorted(rejected) != sorted(contract["required_rejected_options"]):
        failures.append({"id": "witness-rejected-options", "detail": str(rejected)})

    cases = witness.get("cases")
    if not isinstance(cases, list):
        failures.append({"id": "witness-missing-cases", "detail": "cases is not a list"})
        return failures

    by_id = {case.get("case_id"): case for case in cases if isinstance(case, dict)}
    expected_ids = sorted(contract["required_case_ids"])
    if sorted(by_id) != expected_ids:
        failures.append({"id": "witness-missing-cases", "detail": f"found {sorted(by_id)}, expected {expected_ids}"})
        return failures

    expected = expected_witnesses(root)
    required_invariants = set(contract["required_invariants"])
    for case_id, expected_case in expected.items():
        actual = by_id[case_id]
        if actual.get("p95") != expected_case["p95"]:
            failures.append({"id": "witness-case-p95", "detail": f"{case_id}: {actual.get('p95')} != {expected_case['p95']}"})
        try:
            actual_variance = parse_decimal(actual.get("population_variance"))
        except Exception as exc:  # noqa: BLE001
            failures.append({"id": "witness-case-variance", "detail": f"{case_id}: {exc}"})
            actual_variance = None
        if actual_variance != expected_case["population_variance"]:
            failures.append({
                "id": "witness-case-variance",
                "detail": f"{case_id}: {actual.get('population_variance')} != {expected_case['population_variance']}",
            })
        if actual.get("gate_verdict") != expected_case["gate_verdict"]:
            failures.append({
                "id": "witness-case-verdict",
                "detail": f"{case_id}: {actual.get('gate_verdict')} != {expected_case['gate_verdict']}",
            })
        reasons = actual.get("failure_reasons")
        if sorted(reasons or []) != sorted(expected_case["failure_reasons"]):
            failures.append({
                "id": "witness-case-reasons",
                "detail": f"{case_id}: {reasons} != {expected_case['failure_reasons']}",
            })
        invariants = set(actual.get("invariant_ids") or [])
        if not required_invariants.issubset(invariants):
            failures.append({
                "id": "witness-case-invariants",
                "detail": f"{case_id}: missing {sorted(required_invariants - invariants)}",
            })

    return failures


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    errors: list[str] = []

    if not root.exists():
        print(f"Bundle root does not exist: {root}", file=sys.stderr)
        return 1

    contract = load_json(root / "oracle" / "numerical-contract.json")
    check_shape(root, contract, errors)

    if not args.bundle_shape_only:
        failures = evaluate_packet(root, contract)
        failure_ids = sorted({failure["id"] for failure in failures})
        if args.expect_start_state:
            expected = sorted(contract["expected_start_state_failures"])
            require(failure_ids == expected, f"Expected start-state failures {expected}, found {failure_ids}", errors)
        elif failures:
            errors.append(f"Completed N22 packet still fails checks: {json.dumps(failures, indent=2)}")

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
    print(f"N22 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
