#!/usr/bin/env python3

from __future__ import annotations

import argparse
import dataclasses
import importlib
import json
import sys
import time
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N59 real-repo performance cache bundle.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    parser.add_argument("--metrics-out", type=Path)
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


def import_quoteperf(root: Path):
    src_root = root / "candidate" / "workspace" / "src"
    sys.path.insert(0, str(src_root))
    for name in list(sys.modules):
        if name == "quoteperf" or name.startswith("quoteperf."):
            del sys.modules[name]
    return {
        "pkg": importlib.import_module("quoteperf"),
        "models": importlib.import_module("quoteperf.models"),
        "catalog": importlib.import_module("quoteperf.catalog"),
        "engine": importlib.import_module("quoteperf.engine"),
        "reporting": importlib.import_module("quoteperf.reporting"),
    }


def get_field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def as_record(value):
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, dict):
        return dict(value)
    return {
        "request_id": get_field(value, "request_id"),
        "account_id": get_field(value, "account_id"),
        "sku": get_field(value, "sku"),
        "gross_cents": get_field(value, "gross_cents"),
        "discount_bps": get_field(value, "discount_bps"),
        "net_cents": get_field(value, "net_cents"),
        "applied_rule_id": get_field(value, "applied_rule_id"),
        "reason": get_field(value, "reason"),
    }


def make_result(models, request, rule):
    gross = request.quantity * request.unit_price_cents
    if rule is None:
        return models.QuoteResult(
            request_id=request.request_id,
            account_id=request.account_id,
            sku=request.sku,
            gross_cents=gross,
            discount_bps=0,
            net_cents=gross,
            applied_rule_id=None,
            reason="no-rule",
        )
    discount = gross * rule.discount_bps // 10000
    return models.QuoteResult(
        request_id=request.request_id,
        account_id=request.account_id,
        sku=request.sku,
        gross_cents=gross,
        discount_bps=rule.discount_bps,
        net_cents=gross - discount,
        applied_rule_id=rule.rule_id,
        reason="matched",
    )


def rule_matches(rule, request) -> bool:
    return (
        (rule.tier == "*" or rule.tier == request.tier)
        and (rule.region == "*" or rule.region == request.region)
        and request.sku.startswith(rule.sku_prefix)
        and request.quantity >= rule.min_quantity
        and rule.effective_from <= request.ordered_at < rule.effective_until
    )


def oracle_quote(models, rules, request):
    best_rule = None
    best_key = None
    for index, rule in enumerate(rules):
        if not rule_matches(rule, request):
            continue
        key = (rule.priority, rule.min_quantity, len(rule.sku_prefix), -index)
        if best_key is None or key > best_key:
            best_key = key
            best_rule = rule
    return make_result(models, request, best_rule)


def hidden_rules(models):
    Rule = models.DiscountRule
    return [
        Rule("wildcard-base", "*", "*", "sku-", 1, 50, 1, 0, 999),
        Rule("pro-us", "pro", "us", "sku-", 1, 100, 5, 0, 999),
        Rule("pro-us-widget", "pro", "us", "sku-777-", 1, 250, 5, 0, 999),
        Rule("pro-us-widget-bulk", "pro", "us", "sku-777-", 10, 400, 5, 0, 999),
        Rule("expired-high", "pro", "us", "sku-777-", 1, 900, 99, 0, 10),
        Rule("future-high", "pro", "us", "sku-777-", 1, 900, 99, 90, 120),
        Rule("same-priority-first", "pro", "eu", "sku-888-", 1, 180, 7, 0, 999),
        Rule("same-priority-second", "pro", "eu", "sku-888-", 1, 999, 7, 0, 999),
        Rule("enterprise-region", "enterprise", "apac", "sku-777-special-", 3, 700, 6, 0, 999),
    ]


def hidden_requests(models):
    Request = models.QuoteRequest
    return [
        Request("h-1", "acct-a", "pro", "us", "sku-777-basic", 2, 50, 1000),
        Request("h-2", "acct-a", "pro", "us", "sku-777-basic", 12, 50, 1000),
        Request("h-3", "acct-b", "free", "us", "sku-777-basic", 2, 50, 1000),
        Request("h-4", "acct-c", "pro", "us", "sku-777-basic", 2, 5, 1000),
        Request("h-5", "acct-d", "pro", "eu", "sku-888-basic", 2, 50, 1000),
        Request("h-6", "acct-e", "enterprise", "apac", "sku-777-special-alpha", 4, 50, 1000),
        Request("h-7", "acct-f", "enterprise", "apac", "sku-777-special-alpha", 2, 50, 1000),
    ]


def generated_rules(models, count: int):
    Rule = models.DiscountRule
    tiers = ["free", "pro", "enterprise"]
    regions = ["us", "eu", "apac"]
    rules = []
    for i in range(count):
        prefix = f"sku-{i:04d}-"
        rules.append(
            Rule(
                rule_id=f"perf-{i:04d}",
                tier=tiers[i % len(tiers)],
                region=regions[(i // len(tiers)) % len(regions)],
                sku_prefix=prefix,
                min_quantity=1 + (i % 9),
                discount_bps=25 + (i % 23) * 5,
                priority=10 + (i % 11),
                effective_from=0,
                effective_until=1000,
            )
        )
        if i % 19 == 0:
            rules.append(
                Rule(
                    rule_id=f"wild-{i:04d}",
                    tier="*",
                    region="*",
                    sku_prefix=prefix[:8],
                    min_quantity=1,
                    discount_bps=15,
                    priority=1,
                    effective_from=0,
                    effective_until=1000,
                )
            )
    return rules


def generated_requests(models, rules, count: int):
    Request = models.QuoteRequest
    requests = []
    usable_rules = [rule for rule in rules if rule.rule_id.startswith("perf-")]
    for j in range(count):
        rule = usable_rules[(j * 37) % len(usable_rules)]
        requests.append(
            Request(
                request_id=f"perf-q-{j:05d}",
                account_id=f"acct-{j % 97:03d}",
                tier=rule.tier,
                region=rule.region,
                sku=f"{rule.sku_prefix}variant-{j % 13}",
                quantity=rule.min_quantity + (j % 5),
                ordered_at=100 + (j % 200),
                unit_price_cents=100 + (j % 41),
            )
        )
    return requests


def compare_result(actual, expected, case_id: str):
    actual_record = as_record(actual)
    expected_record = as_record(expected)
    keys = ["request_id", "account_id", "sku", "gross_cents", "discount_bps", "net_cents", "applied_rule_id", "reason"]
    mismatches = {key: (actual_record.get(key), expected_record.get(key)) for key in keys if actual_record.get(key) != expected_record.get(key)}
    if mismatches:
        raise AssertionError(f"{case_id}: result mismatch {mismatches}")


def evaluate_correctness(modules):
    models = modules["models"]
    catalog_mod = modules["catalog"]
    engine_mod = modules["engine"]
    rules = hidden_rules(models)
    requests = hidden_requests(models)
    engine = engine_mod.QuoteEngine(catalog_mod.PricingCatalog(rules))
    failures = []
    for request in requests:
        try:
            compare_result(engine.quote(request), oracle_quote(models, rules, request), request.request_id)
        except Exception as exc:  # noqa: BLE001 - verifier reports candidate behavior
            failures.append({"id": f"correctness-{request.request_id}", "detail": str(exc)})
    try:
        batch = engine.quote_many(requests)
        if len(batch) != len(requests):
            raise AssertionError(f"quote_many length mismatch: {len(batch)} != {len(requests)}")
        for request, actual in zip(requests, batch):
            compare_result(actual, oracle_quote(models, rules, request), f"batch-{request.request_id}")
    except Exception as exc:  # noqa: BLE001
        failures.append({"id": "correctness-quote-many", "detail": str(exc)})
    return failures


def evaluate_performance(modules, contract):
    models = modules["models"]
    catalog_mod = modules["catalog"]
    engine_mod = modules["engine"]
    budget = contract["performance_budget"]
    rules = generated_rules(models, int(budget["rule_count"]))
    requests = generated_requests(models, rules, int(budget["request_count"]))
    engine = engine_mod.QuoteEngine(catalog_mod.PricingCatalog(rules))

    start = time.perf_counter()
    results = engine.quote_many(requests)
    elapsed = time.perf_counter() - start

    failures = []
    if len(results) != len(requests):
        failures.append({"id": "performance-result-count", "detail": f"{len(results)} != {len(requests)}"})
    for sample_index in range(int(budget["sample_check_count"])):
        request_index = (sample_index * 67) % len(requests)
        try:
            compare_result(results[request_index], oracle_quote(models, rules, requests[request_index]), f"perf-sample-{sample_index}")
        except Exception as exc:  # noqa: BLE001
            failures.append({"id": f"performance-sample-{sample_index}", "detail": str(exc)})
    if elapsed > float(budget["max_seconds"]):
        failures.append({"id": "performance-budget", "detail": f"{elapsed:.3f} > {float(budget['max_seconds']):.3f} seconds"})
    return failures, {"runtime_seconds": round(elapsed, 6), "max_seconds": float(budget["max_seconds"])}


def text_contains_all(text: str, phrases: list[str]):
    lowered = text.lower()
    return [phrase for phrase in phrases if phrase.lower() not in lowered]


def evaluate_metadata(root: Path, contract: dict):
    failures = []
    requirements = contract["metadata_requirements"]
    state_path = root / "candidate" / "optimization-state.json"
    ledger_path = root / "candidate" / "perf-ledger.json"
    closure_path = root / "candidate" / "closure.json"
    try:
        state = load_json(state_path)
        if state.get("status") != requirements["state_status"]:
            failures.append({"id": "state-status", "detail": f"status={state.get('status')!r}"})
        missing = text_contains_all(state_path.read_text(encoding="utf-8"), requirements["required_state_phrases"])
        if missing:
            failures.append({"id": "state-missing-phrases", "detail": f"missing {missing}"})
    except Exception as exc:  # noqa: BLE001
        failures.append({"id": "state-json", "detail": str(exc)})
    try:
        ledger = load_json(ledger_path)
        if ledger.get("budget_id") != contract["performance_budget"]["budget_id"]:
            failures.append({"id": "ledger-budget-id", "detail": f"budget_id={ledger.get('budget_id')!r}"})
        missing = text_contains_all(ledger_path.read_text(encoding="utf-8"), requirements["required_ledger_phrases"])
        if missing:
            failures.append({"id": "ledger-missing-phrases", "detail": f"missing {missing}"})
    except Exception as exc:  # noqa: BLE001
        failures.append({"id": "ledger-json", "detail": str(exc)})
    try:
        closure = load_json(closure_path)
        if closure.get("status") != requirements["closure_status"]:
            failures.append({"id": "closure-status", "detail": f"status={closure.get('status')!r}"})
        missing = text_contains_all(closure_path.read_text(encoding="utf-8"), requirements["required_closure_phrases"])
        if missing:
            failures.append({"id": "closure-missing-phrases", "detail": f"missing {missing}"})
    except Exception as exc:  # noqa: BLE001
        failures.append({"id": "closure-json", "detail": str(exc)})

    test_text = (root / "candidate" / "workspace" / "tests" / "test_quote_engine.py").read_text(encoding="utf-8", errors="replace").lower()
    if "quote_many" not in test_text or ("performance" not in test_text and "cache" not in test_text):
        failures.append({"id": "tests-missing-hot-path", "detail": "test file must exercise quote_many performance/cache behavior"})
    return failures


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    contract_path = root / "oracle" / "perf-cache-contract.json"
    errors: list[str] = []
    metrics: dict = {"failure_ids": []}

    if not contract_path.exists():
        print(f"ERROR: missing contract: {contract_path}", file=sys.stderr)
        return 1
    contract = load_json(contract_path)
    check_shape(root, contract, errors)
    if errors:
        print("N59 performance-cache FAIL (bundle shape)")
        for error in errors:
            print(f"- {error}")
        return 1
    if args.bundle_shape_only:
        print("N59 performance-cache PASS (bundle shape)")
        return 0

    try:
        modules = import_quoteperf(root)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"import-quoteperf: {exc}")
        modules = None

    failures = []
    if modules is not None:
        failures.extend(evaluate_correctness(modules))
        perf_failures, perf_metrics = evaluate_performance(modules, contract)
        failures.extend(perf_failures)
        metrics.update(perf_metrics)
    failures.extend(evaluate_metadata(root, contract))

    metrics["failure_ids"] = [failure["id"] for failure in failures]
    if args.metrics_out:
        args.metrics_out.parent.mkdir(parents=True, exist_ok=True)
        args.metrics_out.write_text(json.dumps(metrics, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.expect_start_state:
        if failures:
            print("N59 performance-cache PASS (start state)")
            print("Expected start-state failures:", ", ".join(metrics["failure_ids"][:8]))
            return 0
        print("N59 performance-cache FAIL (start state unexpectedly passes)")
        return 1

    if failures:
        print("N59 performance-cache FAIL")
        for failure in failures:
            print(f"- {failure['id']}: {failure['detail']}")
        return 1

    print(f"N59 performance-cache PASS ({metrics.get('runtime_seconds')} <= {metrics.get('max_seconds')} seconds)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
