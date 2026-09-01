#!/usr/bin/env python3
"""Verifier for V3L04A - exact quantile and dispersion certification.

Hidden numeric oracle: the expected per-case p99, IQR, population stddev, gate
verdict, and failure reasons are RE-DERIVED here from inputs/streams.json using
exact arithmetic. The oracle stores conventions and thresholds, never the answer
numbers, so a leaked oracle does not reveal the case answers - the candidate must
compute them under the declared conventions.

Pure algorithmic / numerical-stability task. No physics: separation rests on
percentile-rank convention, population-vs-sample variance, and offset-shift
numerical stability, so a physics-solver strength cannot mask algorithmic weakness.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, ROUND_HALF_UP, getcontext
from fractions import Fraction
from pathlib import Path


getcontext().prec = 60


def parse_args():
    parser = argparse.ArgumentParser(description="Check the V3L04A quantile/dispersion bundle.")
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


def require(condition: bool, message: str, errors: list):
    if not condition:
        errors.append(message)


def check_shape(root: Path, contract: dict, errors: list):
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


# ---- exact statistics (the hidden oracle) -------------------------------------

def histogram_n(histogram: dict) -> int:
    return sum(int(count) for count in histogram.values())


def ceil_fraction(fr: Fraction) -> int:
    return -((-fr.numerator) // fr.denominator)


def upper_rank_percentile(histogram: dict, p: Fraction) -> int:
    """rank = ceil(p * n), one-based, no interpolation; from a bounded histogram."""
    n = histogram_n(histogram)
    rank = ceil_fraction(p * n)
    cumulative = 0
    for value_text in sorted(histogram, key=lambda v: int(v)):
        cumulative += int(histogram[value_text])
        if cumulative >= rank:
            return int(value_text)
    raise ValueError("empty histogram")


def population_variance(shards: list) -> Fraction:
    samples = [int(v) for shard in shards for v in shard]
    if not samples:
        raise ValueError("empty dispersion samples")
    mean = Fraction(sum(samples), len(samples))
    return sum((Fraction(v) - mean) ** 2 for v in samples) / len(samples)


def decimal_six_sqrt(variance: Fraction) -> Decimal:
    value = Decimal(variance.numerator) / Decimal(variance.denominator)
    return value.sqrt().quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def parse_decimal(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def expected_cases(root: Path, contract: dict):
    streams = load_json(root / "inputs" / "streams.json")
    p99 = Fraction(99, 100)
    p25 = Fraction(1, 4)
    p75 = Fraction(3, 4)
    p99_max = int(contract["p99_max_ms"])
    iqr_max = int(contract["iqr_max_ms"])
    stddev_max = parse_decimal(contract["population_stddev_max"])
    expected = {}
    for case in streams["cases"]:
        hist = case["histogram"]
        p99_value = upper_rank_percentile(hist, p99)
        iqr_value = upper_rank_percentile(hist, p75) - upper_rank_percentile(hist, p25)
        stddev = decimal_six_sqrt(population_variance(case["dispersion_shards"]))
        reasons = []
        if p99_value > p99_max:
            reasons.append(f"p99 latency {p99_value}ms exceeds <= {p99_max}ms")
        if iqr_value > iqr_max:
            reasons.append(f"iqr {iqr_value}ms exceeds <= {iqr_max}ms")
        if stddev > stddev_max:
            reasons.append(f"population stddev {stddev} exceeds <= {contract['population_stddev_max']}")
        expected[case["case_id"]] = {
            "p99": p99_value,
            "iqr": iqr_value,
            "population_stddev": stddev,
            "gate_verdict": "FAIL" if reasons else "PASS",
            "failure_reasons": reasons,
        }
    return expected


# ---- candidate evaluation -----------------------------------------------------

def evaluate_packet(root: Path, contract: dict):
    failures = []
    memo_path = root / "candidate" / "quantile-dispersion-memo.md"
    witness_path = root / "candidate" / "witness-ledger.json"
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
    except Exception as exc:  # noqa: BLE001 - report any JSON failure compactly
        failures.append({"id": "witness-json-invalid", "detail": str(exc)})
        return failures

    if witness.get("selected_method") != contract["selected_method"]:
        failures.append({"id": "witness-selected-method", "detail": str(witness.get("selected_method"))})
    if witness.get("percentile_convention") != contract["percentile_convention"]:
        failures.append({"id": "witness-percentile-convention", "detail": str(witness.get("percentile_convention"))})
    if witness.get("variance_convention") != contract["variance_convention"]:
        failures.append({"id": "witness-variance-convention", "detail": str(witness.get("variance_convention"))})

    rejected = witness.get("rejected_methods")
    if not isinstance(rejected, dict) or sorted(rejected) != sorted(contract["required_rejected_methods"]):
        failures.append({"id": "witness-rejected-methods", "detail": str(rejected)})

    cases = witness.get("cases")
    if not isinstance(cases, list):
        failures.append({"id": "witness-missing-cases", "detail": "cases is not a list"})
        return failures

    by_id = {case.get("case_id"): case for case in cases if isinstance(case, dict)}
    expected = expected_cases(root, contract)
    expected_ids = sorted(expected)
    if sorted(by_id) != expected_ids:
        failures.append({"id": "witness-missing-cases", "detail": f"found {sorted(by_id)}, expected {expected_ids}"})
        return failures

    required_invariants = set(contract["required_invariants"])
    for case_id, exp in expected.items():
        actual = by_id[case_id]
        if actual.get("p99") != exp["p99"]:
            failures.append({"id": "witness-case-p99", "detail": f"{case_id}: {actual.get('p99')} != {exp['p99']}"})
        if actual.get("iqr") != exp["iqr"]:
            failures.append({"id": "witness-case-iqr", "detail": f"{case_id}: {actual.get('iqr')} != {exp['iqr']}"})
        try:
            actual_std = parse_decimal(actual.get("population_stddev"))
        except Exception as exc:  # noqa: BLE001
            failures.append({"id": "witness-case-stddev", "detail": f"{case_id}: {exc}"})
            actual_std = None
        if actual_std != exp["population_stddev"]:
            failures.append({
                "id": "witness-case-stddev",
                "detail": f"{case_id}: {actual.get('population_stddev')} != {exp['population_stddev']}",
            })
        if actual.get("gate_verdict") != exp["gate_verdict"]:
            failures.append({
                "id": "witness-case-verdict",
                "detail": f"{case_id}: {actual.get('gate_verdict')} != {exp['gate_verdict']}",
            })
        reasons = actual.get("failure_reasons")
        if sorted(reasons or []) != sorted(exp["failure_reasons"]):
            failures.append({
                "id": "witness-case-reasons",
                "detail": f"{case_id}: {reasons} != {exp['failure_reasons']}",
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
    errors: list = []

    if not root.exists():
        print(f"Bundle root does not exist: {root}", file=sys.stderr)
        return 1

    contract = load_json(root / "oracle" / "quantile-dispersion-contract.json")
    check_shape(root, contract, errors)

    if not args.bundle_shape_only:
        failures = evaluate_packet(root, contract)
        failure_ids = sorted({f["id"] for f in failures})
        if args.expect_start_state:
            expected = sorted(contract["expected_start_state_failures"])
            require(failure_ids == expected, f"Expected start-state failures {expected}, found {failure_ids}", errors)
        elif failures:
            errors.append(f"Completed V3L04A packet still fails checks: {json.dumps(failures, indent=2)}")

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
    print(f"V3L04A verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
