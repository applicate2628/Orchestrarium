#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import dataclasses
import importlib
import json
import sys
import time
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N69 real-repo patch-quality scorecard bundle.")
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


def check_shape(root: Path, contract: dict, errors: list[str]):
    actual_entries = sorted(path.name for path in root.iterdir())
    require(actual_entries == sorted(contract["required_top_level_entries"]), f"Top-level bundle entries drifted: {actual_entries}", errors)
    scenario = root / "scenario.yaml"
    require(top_level_yaml_keys(scenario) == contract["scenario_yaml_fields"], "scenario.yaml field order drifted", errors)
    require(parse_simple_yaml(scenario) == contract["expected_metadata"], "scenario.yaml metadata mismatch", errors)
    for path in contract["required_bundle_paths"]:
        require((root / path).exists(), f"Missing required bundle path: {path}", errors)


def check_changed_paths(changed_paths: list[str], contract: dict, failures: list[dict]):
    if not changed_paths:
        return
    expected = sorted(contract["requiredChangedPaths"])
    actual = sorted(changed_paths)
    if actual != expected:
        failures.append({"id": "scope-changed-paths", "detail": f"expected {expected}, got {actual}"})


def import_ledgerpatch(root: Path):
    src_root = root / "candidate" / "workspace" / "src"
    sys.path.insert(0, str(src_root))
    for name in list(sys.modules):
        if name == "ledgerpatch" or name.startswith("ledgerpatch."):
            del sys.modules[name]
    return {
        "pkg": importlib.import_module("ledgerpatch"),
        "models": importlib.import_module("ledgerpatch.models"),
        "reconcile": importlib.import_module("ledgerpatch.reconcile"),
        "reporting": importlib.import_module("ledgerpatch.reporting"),
    }


def as_dict(row):
    if dataclasses.is_dataclass(row):
        return dataclasses.asdict(row)
    return dict(row)


def normalize_rows(rows):
    normalized = []
    for row in rows:
        item = as_dict(row)
        item["evidence_ids"] = tuple(item["evidence_ids"])
        normalized.append(item)
    return sorted(normalized, key=lambda item: (item["account_id"], item["period"], item["currency"]))


def hidden_events(models):
    Event = models.LedgerEvent
    return [
        Event("dup-1", "acct-alpha", "2026-04", "USD", "charge", 1000, 1),
        Event("dup-1", "acct-alpha", "2026-04", "USD", "charge", 1500, 4),
        Event("refund-1", "acct-alpha", "2026-04", "USD", "refund", 200, 5),
        Event("charge-voided", "acct-alpha", "2026-04", "USD", "charge", 700, 6),
        Event("void-hidden", "acct-alpha", "2026-04", "USD", "void", 0, 7, "charge-voided"),
        Event("eur-1", "acct-alpha", "2026-04", "EUR", "charge", 900, 8),
        Event("other-1", "acct-beta", "2026-05", "USD", "charge", 300, 9),
        Event("other-refund", "acct-beta", "2026-05", "USD", "refund", 50, 10),
    ]


def expected_hidden_rows():
    return [
        {
            "account_id": "acct-alpha",
            "period": "2026-04",
            "currency": "EUR",
            "net_cents": 900,
            "event_count": 1,
            "evidence_ids": ("eur-1",),
        },
        {
            "account_id": "acct-alpha",
            "period": "2026-04",
            "currency": "USD",
            "net_cents": 1300,
            "event_count": 2,
            "evidence_ids": ("dup-1", "refund-1"),
        },
        {
            "account_id": "acct-beta",
            "period": "2026-05",
            "currency": "USD",
            "net_cents": 250,
            "event_count": 2,
            "evidence_ids": ("other-1", "other-refund"),
        },
    ]


def generated_events(models, count: int):
    Event = models.LedgerEvent
    events = []
    currencies = ["USD", "EUR", "JPY"]
    for i in range(count):
        account = f"acct-{i % 113:03d}"
        period = f"2026-{(i % 12) + 1:02d}"
        currency = currencies[i % len(currencies)]
        kind = "refund" if i % 17 == 0 else "charge"
        events.append(Event(f"gen-{i:05d}", account, period, currency, kind, 100 + (i % 37), i))
        if i % 29 == 0:
            events.append(Event(f"gen-{i:05d}", account, period, currency, kind, 125 + (i % 37), i + count))
        if i % 211 == 0:
            events.append(Event(f"void-{i:05d}", account, period, currency, "void", 0, i + count * 2, f"gen-{i:05d}"))
    return events


def case(failures: list[dict], case_id: str, fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        failures.append({"id": case_id, "detail": str(exc)})


def evaluate_runtime(root: Path, contract: dict, metrics: dict):
    failures: list[dict] = []
    try:
        modules = import_ledgerpatch(root)
    except Exception as exc:  # noqa: BLE001
        return [{"id": "import-ledgerpatch", "detail": str(exc)}]
    models = modules["models"]
    reconcile = modules["reconcile"]

    def hidden_semantics():
        events = hidden_events(models)
        before = copy.deepcopy(events)
        actual = normalize_rows(reconcile.build_account_ledger(events))
        if actual != expected_hidden_rows():
            raise AssertionError(f"hidden rows mismatch: {actual}")
        if events != before:
            raise AssertionError("build_account_ledger mutated input events")
        reversed_actual = normalize_rows(reconcile.build_account_ledger(list(reversed(events))))
        if reversed_actual != expected_hidden_rows():
            raise AssertionError(f"order independence failed: {reversed_actual}")

    def performance_budget():
        events = generated_events(models, int(contract["generatedEventCount"]))
        started = time.perf_counter()
        rows = reconcile.build_account_ledger(events)
        elapsed = time.perf_counter() - started
        metrics["runtime_seconds"] = round(elapsed, 6)
        metrics["max_seconds"] = contract["runtimeMaxSeconds"]
        metrics["generated_rows"] = len(rows)
        if elapsed > float(contract["runtimeMaxSeconds"]):
            raise AssertionError(f"runtime {elapsed:.6f}s exceeded {contract['runtimeMaxSeconds']}s")
        if not rows:
            raise AssertionError("generated run produced no rows")

    case(failures, "correctness-hidden-semantics", hidden_semantics)
    case(failures, "performance-runtime-budget", performance_budget)
    return failures


def evaluate_static(root: Path, contract: dict):
    failures = []
    text = (root / "candidate/workspace/src/ledgerpatch/reconcile.py").read_text(encoding="utf-8", errors="replace")
    lower = text.lower()
    for term in contract["forbiddenStaticTerms"]:
        if term.lower() in lower:
            failures.append({"id": "patch-forbidden-static", "detail": f"forbidden term {term!r}"})
    if "voids_event_id" not in text or "sequence" not in text:
        failures.append({"id": "patch-missing-core-fields", "detail": "reconcile.py does not reference voids_event_id and sequence"})
    return failures


def evaluate_ledger(root: Path, contract: dict):
    failures = []
    try:
        ledger = load_json(root / "candidate" / "patch-quality-ledger.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "ledger-json", "detail": str(exc)}]
    if ledger.get("contractId") != contract["contractId"]:
        failures.append({"id": "ledger-contract", "detail": "contractId mismatch"})
    if sorted(ledger.get("changedFiles", [])) != sorted(contract["requiredChangedPaths"]):
        failures.append({"id": "ledger-changed-files", "detail": "changedFiles must match required changed paths"})
    text = json.dumps(ledger, sort_keys=True).lower()
    for term in contract["ledgerRequiredTerms"]:
        if term.lower() not in text:
            failures.append({"id": "ledger-term", "detail": f"missing {term!r}"})
    return failures


def write_metrics(path: Path | None, metrics: dict):
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(metrics, indent=2), encoding="utf-8")


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    contract = load_json(root / "oracle" / "patch-quality-contract.json")
    shape_errors: list[str] = []
    check_shape(root, contract, shape_errors)
    if shape_errors:
        for error in shape_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.bundle_shape_only:
        print("N69 verifier PASS (bundle shape)")
        return 0

    metrics = {
        "verdict": "FAIL",
        "failure_ids": [],
        "failures": [],
        "runtime_seconds": None,
        "max_seconds": contract["runtimeMaxSeconds"],
    }
    failures: list[dict] = []
    check_changed_paths(args.changed_paths, contract, failures)
    failures.extend(evaluate_runtime(root, contract, metrics))
    failures.extend(evaluate_static(root, contract))
    failures.extend(evaluate_ledger(root, contract))

    metrics["failures"] = failures
    metrics["failure_ids"] = [failure["id"] for failure in failures]
    if args.expect_start_state:
        expected = {"correctness-hidden-semantics", "ledger-changed-files", "ledger-term", "patch-missing-core-fields"}
        observed = set(metrics["failure_ids"])
        if not expected.issubset(observed):
            print(f"ERROR: expected start-state failure subset {sorted(expected)}, found {sorted(observed)}", file=sys.stderr)
            write_metrics(args.metrics_out, metrics)
            return 1
        print("N69 verifier PASS (expected start-state failures present)")
        write_metrics(args.metrics_out, metrics)
        return 0

    if failures:
        for failure in failures:
            print(f"Failed invariant: {failure['id']} :: {failure.get('detail', '')}", file=sys.stderr)
        write_metrics(args.metrics_out, metrics)
        return 1

    metrics["verdict"] = "PASS"
    print("N69 verifier PASS")
    write_metrics(args.metrics_out, metrics)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
