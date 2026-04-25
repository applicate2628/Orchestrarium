#!/usr/bin/env python3

from __future__ import annotations

import argparse
import dataclasses
import importlib
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N63 frame-inversion compact API migration bundle.")
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
    ignored = set(contract.get("ignored_top_level_entries", []))
    actual_entries = sorted(path.name for path in root.iterdir() if path.name not in ignored)
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


def import_modules(root: Path):
    src_root = root / "candidate" / "workspace" / "src"
    sys.path.insert(0, str(src_root))
    for name in list(sys.modules):
        if name == "billingmesh" or name.startswith("billingmesh."):
            del sys.modules[name]
    return {
        "pkg": importlib.import_module("billingmesh"),
        "models": importlib.import_module("billingmesh.models"),
        "account_directory": importlib.import_module("billingmesh.account_directory"),
        "entitlement_policy": importlib.import_module("billingmesh.entitlement_policy"),
        "usage_publisher": importlib.import_module("billingmesh.usage_publisher"),
        "service": importlib.import_module("billingmesh.service"),
        "reporting": importlib.import_module("billingmesh.reporting"),
        "api": importlib.import_module("billingmesh.api"),
    }


def get_field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def assert_equal(actual, expected, label: str):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def sample_accounts():
    return {
        "acct-pro": {
            "account_id": "acct-pro",
            "tenant": "acme",
            "state": "active",
            "features": ["metering.read", "metering.write"],
            "plan_expires_at": 90,
        },
        "acct-basic": {
            "account_id": "acct-basic",
            "tenant": "acme",
            "state": "active",
            "features": ["metering.read"],
            "plan_expires_at": 90,
        },
        "acct-expired": {
            "account_id": "acct-expired",
            "tenant": "acme",
            "state": "active",
            "features": ["metering.read", "metering.write"],
            "plan_expires_at": 40,
        },
        "acct-suspended": {
            "account_id": "acct-suspended",
            "tenant": "acme",
            "state": "suspended",
            "features": ["metering.read", "metering.write"],
            "plan_expires_at": 90,
        },
    }


class ScriptedTransport:
    def __init__(self, outcomes=None):
        self.outcomes = list(outcomes or [True])
        self.sent = []

    def send(self, event):
        self.sent.append(dict(event))
        outcome = self.outcomes.pop(0) if self.outcomes else True
        if outcome == "timeout":
            raise TimeoutError("usage publisher timeout")
        return outcome


def case_runner(failures: list[dict], case_id: str, fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - verifier reports candidate behavior
        failures.append({"id": case_id, "detail": str(exc)})


def evaluate_static(root: Path, contract: dict):
    failures = []
    files = {
        "AccountDirectory": root / "candidate/workspace/src/billingmesh/account_directory.py",
        "EntitlementPolicy": root / "candidate/workspace/src/billingmesh/entitlement_policy.py",
        "UsagePublisher": root / "candidate/workspace/src/billingmesh/usage_publisher.py",
    }
    for class_name, marker in contract["legacyPublicMethods"].items():
        text = files[class_name].read_text(encoding="utf-8", errors="replace")
        if f"def {marker}(" in text:
            failures.append({"id": "legacy-api-static", "detail": f"{class_name}.{marker} still defined"})
    return failures


def evaluate_runtime(root: Path, contract: dict):
    failures = []
    try:
        modules = import_modules(root)
    except Exception as exc:  # noqa: BLE001
        return [{"id": "import-billingmesh", "detail": str(exc)}]

    models = modules["models"]
    directory_mod = modules["account_directory"]
    policy_mod = modules["entitlement_policy"]
    publisher_mod = modules["usage_publisher"]

    def result_models():
        for name, fields in contract["requiredResultModels"].items():
            model = getattr(models, name, None)
            if model is None:
                raise AssertionError(f"missing model {name}")
            if not dataclasses.is_dataclass(model):
                raise AssertionError(f"{name} must be a dataclass")
            model_fields = {field.name for field in dataclasses.fields(model)}
            missing = sorted(set(fields) - model_fields)
            if missing:
                raise AssertionError(f"{name} missing fields: {missing}")

    def legacy_methods_removed():
        pairs = [
            (directory_mod.AccountDirectory, "get_account"),
            (policy_mod.EntitlementPolicy, "check"),
            (publisher_mod.UsagePublisher, "publish"),
        ]
        for cls, method in pairs:
            if hasattr(cls, method):
                raise AssertionError(f"{cls.__name__}.{method} still exists")

    def account_lookup_contract():
        accounts = sample_accounts()
        directory = directory_mod.AccountDirectory(accounts, now=contract["currentTick"])
        cases = [
            ("acct-pro", None, True, "active", "account-directory"),
            ("acct-pro", 95, False, "plan-expired", "account-directory"),
            ("missing", None, False, "missing-account", "account-directory"),
            ("acct-expired", None, False, "plan-expired", "account-directory"),
            ("acct-suspended", None, False, "suspended-account", "account-directory"),
        ]
        for account_id, at_tick, found, reason, owner in cases:
            lookup = directory.lookup_account(account_id, at_tick=at_tick) if at_tick is not None else directory.lookup_account(account_id)
            if isinstance(lookup, dict):
                raise AssertionError("lookup_account must return a structured object, not dict")
            assert_equal(get_field(lookup, "found"), found, f"{account_id}.found")
            assert_equal(get_field(lookup, "account_id"), account_id, f"{account_id}.account_id")
            assert_equal(get_field(lookup, "reason"), reason, f"{account_id}.reason")
            assert_equal(get_field(lookup, "owner"), owner, f"{account_id}.owner")
        if accounts["acct-pro"]["features"] != ["metering.read", "metering.write"]:
            raise AssertionError("lookup_account mutated source records")

    def entitlement_contract():
        directory = directory_mod.AccountDirectory(sample_accounts(), now=contract["currentTick"])
        policy = policy_mod.EntitlementPolicy({"disabledTenants": ["blocked"]})
        cases = [
            ("acct-pro", {"tenant": "acme", "feature": "metering.write"}, True, "allowed", "entitlement-policy"),
            ("acct-basic", {"tenant": "acme", "feature": "metering.read"}, True, "allowed", "entitlement-policy"),
            ("acct-basic", {"tenant": "acme", "feature": "metering.write"}, False, "feature-not-entitled", "entitlement-policy"),
            ("acct-pro", {"tenant": "blocked", "feature": "metering.read"}, False, "tenant-disabled", "entitlement-policy"),
            ("missing", {"tenant": "acme", "feature": "metering.read"}, False, "missing-account", "account-directory"),
            ("acct-expired", {"tenant": "acme", "feature": "metering.write"}, False, "plan-expired", "account-directory"),
            ("acct-suspended", {"tenant": "acme", "feature": "metering.write"}, False, "suspended-account", "account-directory"),
        ]
        for account_id, request, allowed, reason, owner in cases:
            decision = policy.evaluate_entitlement(directory.lookup_account(account_id), request)
            if isinstance(decision, dict):
                raise AssertionError("evaluate_entitlement must return a structured object, not dict")
            assert_equal(get_field(decision, "allowed"), allowed, f"{account_id}.allowed")
            assert_equal(get_field(decision, "reason"), reason, f"{account_id}.reason")
            assert_equal(get_field(decision, "owner"), owner, f"{account_id}.owner")
            source_ids = get_field(decision, "source_ids")
            if not isinstance(source_ids, list) or not source_ids:
                raise AssertionError(f"{account_id}.source_ids must be a non-empty list")

    def publisher_contract():
        directory = directory_mod.AccountDirectory(sample_accounts())
        policy = policy_mod.EntitlementPolicy({"disabledTenants": ["blocked"]})
        allowed = policy.evaluate_entitlement(directory.lookup_account("acct-pro"), {"tenant": "acme", "feature": "metering.write"})
        denied = policy.evaluate_entitlement(directory.lookup_account("acct-basic"), {"tenant": "acme", "feature": "metering.write"})

        denied_transport = ScriptedTransport([True])
        denied_publisher = publisher_mod.UsagePublisher(denied_transport)
        denied_result = denied_publisher.publish_usage({"usage_id": "u-denied", "tenant": "acme"}, denied)
        assert_equal(get_field(denied_result, "accepted"), False, "denied.accepted")
        assert_equal(get_field(denied_result, "status"), "rejected", "denied.status")
        assert_equal(get_field(denied_result, "retryable"), False, "denied.retryable")
        assert_equal(get_field(denied_result, "reason"), "feature-not-entitled", "denied.reason")
        assert_equal(len(denied_transport.sent), 0, "denied decision must not publish")

        timeout_transport = ScriptedTransport(["timeout"])
        timeout_publisher = publisher_mod.UsagePublisher(timeout_transport)
        timeout_result = timeout_publisher.publish_usage({"usage_id": "u-timeout", "tenant": "acme"}, allowed)
        assert_equal(get_field(timeout_result, "accepted"), False, "timeout.accepted")
        assert_equal(get_field(timeout_result, "status"), "queued", "timeout.status")
        assert_equal(get_field(timeout_result, "retryable"), True, "timeout.retryable")
        assert_equal(get_field(timeout_result, "error_code"), "usage-publish-timeout", "timeout.error")

        success_transport = ScriptedTransport([True, True])
        success_publisher = publisher_mod.UsagePublisher(success_transport)
        first = success_publisher.publish_usage({"usage_id": "u-1", "tenant": "acme"}, allowed)
        second = success_publisher.publish_usage({"usage_id": "u-1", "tenant": "acme"}, allowed)
        assert_equal(get_field(first, "status"), "accepted", "first.status")
        assert_equal(get_field(first, "accepted"), True, "first.accepted")
        assert_equal(get_field(second, "status"), "duplicate", "duplicate.status")
        assert_equal(get_field(second, "accepted"), False, "duplicate.accepted")
        assert_equal(get_field(second, "error_code"), "duplicate-usage", "duplicate.error")
        assert_equal(len(success_transport.sent), 1, "duplicate must not republish")

    def integration_contract():
        accounts = sample_accounts()
        rules = {"disabledTenants": ["blocked"]}
        api = modules["api"]

        ok = api.handle_usage_event(accounts, rules, ScriptedTransport([True]), "acct-pro", {
            "usage_id": "u-ok",
            "tenant": "acme",
            "feature": "metering.write",
        })
        assert_equal(ok["status"], "accepted", "ok.status")
        assert_equal(ok["accepted"], True, "ok.accepted")
        assert_equal(ok["reason"], "accepted", "ok.reason")

        denied_transport = ScriptedTransport([True])
        denied = api.handle_usage_event(accounts, rules, denied_transport, "acct-basic", {
            "usage_id": "u-denied",
            "tenant": "acme",
            "feature": "metering.write",
        })
        assert_equal(denied["status"], "rejected", "denied.status")
        assert_equal(denied["accepted"], False, "denied.accepted")
        assert_equal(denied["retryable"], False, "denied.retryable")
        assert_equal(denied["reason"], "feature-not-entitled", "denied.reason")
        assert_equal(denied["owner"], "entitlement-policy", "denied.owner")
        assert_equal(len(denied_transport.sent), 0, "denied event must not publish")

        blocked = api.handle_usage_event(accounts, rules, ScriptedTransport([True]), "acct-pro", {
            "usage_id": "u-blocked",
            "tenant": "blocked",
            "feature": "metering.read",
        })
        assert_equal(blocked["reason"], "tenant-disabled", "blocked.reason")
        assert_equal(blocked["owner"], "entitlement-policy", "blocked.owner")

        expired = api.handle_usage_event(accounts, rules, ScriptedTransport([True]), "acct-expired", {
            "usage_id": "u-expired",
            "tenant": "acme",
            "feature": "metering.write",
        })
        assert_equal(expired["reason"], "plan-expired", "expired.reason")
        assert_equal(expired["owner"], "account-directory", "expired.owner")

        timeout = api.handle_usage_event(accounts, rules, ScriptedTransport(["timeout"]), "acct-pro", {
            "usage_id": "u-timeout",
            "tenant": "acme",
            "feature": "metering.write",
        })
        assert_equal(timeout["status"], "queued", "timeout.integration.status")
        assert_equal(timeout["retryable"], True, "timeout.integration.retryable")
        assert_equal(timeout["reason"], "usage-publish-timeout", "timeout.integration.reason")

        read_allowed = api.handle_usage_event(accounts, rules, ScriptedTransport([True]), "acct-basic", {
            "usage_id": "u-read",
            "tenant": "acme",
            "feature": "metering.read",
        })
        assert_equal(read_allowed["accepted"], True, "read allowed accepted")

    def reporting_contract():
        report = modules["reporting"].build_usage_summary([
            {"status": "accepted", "accepted": True, "retryable": False, "owner": "usage-publisher", "reason": "accepted"},
            {"status": "queued", "accepted": False, "retryable": True, "owner": "usage-publisher", "reason": "usage-publish-timeout"},
            {"status": "rejected", "accepted": False, "retryable": False, "owner": "entitlement-policy", "reason": "feature-not-entitled"},
            {"status": "rejected", "accepted": False, "retryable": False, "owner": "account-directory", "reason": "missing-account"},
            {"status": "duplicate", "accepted": False, "retryable": False, "owner": "usage-publisher", "reason": "duplicate-usage"},
        ])
        assert_equal(report.get("accepted"), 1, "report.accepted")
        assert_equal(report.get("retryable"), 1, "report.retryable")
        assert_equal(report.get("queued"), 1, "report.queued")
        assert_equal(report.get("duplicate"), 1, "report.duplicate")
        assert_equal(report.get("rejected"), 2, "report.rejected")
        owners = report.get("owners")
        if owners != ["account-directory", "entitlement-policy", "usage-publisher"]:
            raise AssertionError(f"report owners drifted: {owners!r}")
        reasons = report.get("reasons", {})
        for reason in ["usage-publish-timeout", "feature-not-entitled", "missing-account", "duplicate-usage"]:
            if reasons.get(reason) != 1:
                raise AssertionError(f"report reason {reason!r} missing")

    for case_id, fn in [
        ("result-models", result_models),
        ("legacy-api-removed", legacy_methods_removed),
        ("account-lookup-contract", account_lookup_contract),
        ("entitlement-contract", entitlement_contract),
        ("publisher-contract", publisher_contract),
        ("integration-contract", integration_contract),
        ("reporting-contract", reporting_contract),
    ]:
        case_runner(failures, case_id, fn)

    return failures


def json_text(value):
    return json.dumps(value, sort_keys=True)


def find_phase(state: dict, phase_id: str):
    for item in state.get("phases", []):
        if not isinstance(item, dict):
            continue
        if item.get("id") == phase_id or item.get("phase") == phase_id or item.get("phaseId") == phase_id:
            return item
    return None


def evaluate_migration_state(root: Path, contract: dict):
    failures = []
    try:
        state = load_json(root / "candidate" / "migration-state.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "migration-state-schema", "detail": f"invalid JSON: {exc}"}]

    required_keys = {
        "contractId",
        "planFingerprint",
        "phases",
        "sourceBindings",
        "staleSourceRejections",
        "interfaceMap",
        "callSiteMigration",
        "compatibilityMatrix",
        "validation",
        "patchBudget",
    }
    if not required_keys <= set(state):
        failures.append({"id": "migration-state-schema", "detail": f"missing keys: {sorted(required_keys - set(state))}"})
        return failures

    text = json_text(state)
    if state.get("contractId") != contract["contractId"]:
        failures.append({"id": "migration-state-schema", "detail": "contractId mismatch"})
    if contract["planFingerprint"] not in text:
        failures.append({"id": "phase-ledger-complete", "detail": "plan fingerprint missing"})
    for source_id in contract["expectedSourceIds"]:
        if source_id not in text:
            failures.append({"id": "source-binding-complete", "detail": f"missing {source_id}"})
            break
    for stale in contract["requiredLedgerRows"]["staleRejections"]:
        if stale not in text:
            failures.append({"id": "stale-source-rejection", "detail": f"missing stale rejection {stale}"})
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
        if section in {"validationMarkers", "staleRejections"}:
            continue
        for marker in markers:
            if marker not in text:
                failures.append({"id": f"migration-{section}", "detail": f"missing {marker}"})
                break

    validation_text = json_text(state.get("validation", {}))
    for marker in contract["requiredLedgerRows"]["validationMarkers"]:
        if marker not in validation_text:
            failures.append({"id": "migration-validation", "detail": f"missing {marker}"})
            break

    budget = state.get("patchBudget", {})
    if budget.get("maxChangedPaths") != len(contract["requiredChangedPaths"]):
        failures.append({"id": "migration-patch-budget", "detail": "maxChangedPaths mismatch"})
    if sorted(budget.get("requiredChangedPaths", [])) != sorted(contract["requiredChangedPaths"]):
        failures.append({"id": "migration-patch-budget", "detail": "requiredChangedPaths mismatch"})

    return failures


def evaluate_review_response(root: Path, contract: dict):
    failures = []
    try:
        review = load_json(root / "candidate" / "review-response.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "review-response-schema", "detail": f"invalid JSON: {exc}"}]

    responses = review.get("responses", [])
    if not isinstance(responses, list):
        return [{"id": "review-response-schema", "detail": "responses must be a list"}]

    response_by_id = {}
    for item in responses:
        if not isinstance(item, dict):
            continue
        item_id = item.get("id") or item.get("reviewId")
        if item_id:
            response_by_id[item_id] = item

    for review_id, decision in contract["reviewDecisions"].items():
        item = response_by_id.get(review_id)
        if not item:
            failures.append({"id": "review-response-complete", "detail": f"missing {review_id}"})
            break
        if str(item.get("decision", "")).lower() != decision:
            failures.append({"id": "review-response-complete", "detail": f"{review_id} decision mismatch"})
            break
        if not (item.get("owner") or item.get("ownerPath")):
            failures.append({"id": "review-response-complete", "detail": f"{review_id} missing owner"})
            break
        if not item.get("validationCue"):
            failures.append({"id": "review-response-complete", "detail": f"{review_id} missing validationCue"})
            break

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
    validation_text = json_text(closure.get("validation", []))
    if "python candidate/workspace/tests/test_billingmesh.py" not in validation_text:
        failures.append({"id": "closure-complete", "detail": "validation command missing"})
    if "reviewOutcome" not in closure or not closure.get("reviewOutcome"):
        failures.append({"id": "closure-complete", "detail": "review outcome missing"})
    if "residualRisk" not in closure:
        failures.append({"id": "closure-complete", "detail": "residualRisk missing"})
    return failures


def evaluate_test_markers(root: Path, contract: dict):
    text = (root / "candidate" / "workspace" / "tests" / "test_billingmesh.py").read_text(
        encoding="utf-8",
        errors="replace",
    )
    missing = [marker for marker in contract["requiredTestMarkers"] if marker not in text]
    if missing:
        return [{"id": "visible-test-markers", "detail": f"missing markers: {', '.join(missing)}"}]
    return []


def evaluate_bundle(root: Path, contract: dict):
    failures = []
    failures.extend(evaluate_static(root, contract))
    failures.extend(evaluate_runtime(root, contract))
    failures.extend(evaluate_migration_state(root, contract))
    failures.extend(evaluate_review_response(root, contract))
    failures.extend(evaluate_closure(root, contract))
    failures.extend(evaluate_test_markers(root, contract))
    return failures


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    contract = load_json(root / "oracle" / "compact-api-contract.json")
    shape_errors: list[str] = []
    check_shape(root, contract, shape_errors)
    if shape_errors:
        for error in shape_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.bundle_shape_only:
        print("N63 verifier PASS (bundle shape)")
        return 0

    failures = evaluate_bundle(root, contract)
    if args.expect_start_state:
        expected = {
            "legacy-api-static",
            "result-models",
            "legacy-api-removed",
            "account-lookup-contract",
            "migration-interfaceMap",
            "phase-ledger-complete",
            "review-response-complete",
            "closure-complete",
            "visible-test-markers",
        }
        observed = {failure["id"] for failure in failures}
        missing = sorted(expected - observed)
        if missing:
            print(f"ERROR: start state no longer exposes expected failures: {missing}", file=sys.stderr)
            return 1
        print("N63 verifier PASS (expected start-state failures present)")
        return 0

    if failures:
        for failure in failures:
            print(f"Failed invariant: {failure['id']} :: {failure.get('detail', '')}", file=sys.stderr)
        return 1

    print("N63 verifier PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
