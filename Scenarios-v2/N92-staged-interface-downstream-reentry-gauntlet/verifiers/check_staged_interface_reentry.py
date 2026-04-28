#!/usr/bin/env python3

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N92 staged interface/downstream reentry bundle.")
    parser.add_argument("--bundle-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    parser.add_argument("--changed-path", dest="changed_paths", action="append", default=[])
    parser.add_argument("--metrics-out", type=Path, default=None)
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


def sha256_file(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str, errors: list[str]):
    if not condition:
        errors.append(message)


def check_shape(root: Path, contract: dict, errors: list[str]):
    ignored = set(contract.get("ignored_top_level_entries", []))
    actual_entries = sorted(path.name for path in root.iterdir() if path.name not in ignored)
    require(actual_entries == sorted(contract["required_top_level_entries"]), f"Top-level bundle entries drifted: {actual_entries}", errors)
    scenario = root / "scenario.yaml"
    require(top_level_yaml_keys(scenario) == contract["scenario_yaml_fields"], "scenario.yaml field order drifted", errors)
    require(parse_simple_yaml(scenario) == contract["expected_metadata"], "scenario.yaml metadata mismatch", errors)
    for path in contract["required_bundle_paths"]:
        require((root / path).exists(), f"Missing required bundle path: {path}", errors)
    for rel_path, expected_hash in contract.get("protectedPaths", {}).items():
        actual_path = root / rel_path
        require(actual_path.exists(), f"Protected path missing: {rel_path}", errors)
        if actual_path.exists():
            require(sha256_file(actual_path) == expected_hash, f"Protected path changed: {rel_path}", errors)


def check_changed_paths(contract: dict, changed_paths: list[str]):
    if not changed_paths:
        return []
    ignored_prefixes = tuple(contract.get("ignored_changed_path_prefixes", []))
    normalized = {path.replace("\\", "/") for path in changed_paths}
    observed = sorted(path for path in normalized if not any(path.startswith(prefix) for prefix in ignored_prefixes))
    required = sorted(contract["requiredChangedPaths"])
    if observed != required:
        return [{
            "id": "scope-changed-paths",
            "detail": f"changed paths {observed} != required {required}",
        }]
    return []


def import_modules(root: Path):
    src_root = root / "candidate" / "workspace" / "src"
    sys.path.insert(0, str(src_root))
    for name in list(sys.modules):
        if name == "subscriptionmesh" or name.startswith("subscriptionmesh."):
            del sys.modules[name]
    return {
        "pkg": importlib.import_module("subscriptionmesh"),
        "models": importlib.import_module("subscriptionmesh.models"),
        "customer_directory": importlib.import_module("subscriptionmesh.customer_directory"),
        "subscription_policy": importlib.import_module("subscriptionmesh.subscription_policy"),
        "webhook_publisher": importlib.import_module("subscriptionmesh.webhook_publisher"),
        "service": importlib.import_module("subscriptionmesh.service"),
        "api": importlib.import_module("subscriptionmesh.api"),
        "reporting": importlib.import_module("subscriptionmesh.reporting"),
        "legacy_adapter": importlib.import_module("subscriptionmesh.legacy_adapter"),
    }


def get_field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def as_mapping(value):
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, dict):
        return dict(value)
    return dict(value)


def assert_equal(actual, expected, label: str):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def sample_customers():
    return {
        "cust-pro": {
            "customer_id": "cust-pro",
            "tenant": "acme",
            "state": "active",
            "features": ["webhook.read", "webhook.write"],
            "subscription_expires_at": 180,
            "source_ids": ["S1"],
        },
        "cust-basic": {
            "customer_id": "cust-basic",
            "tenant": "acme",
            "state": "active",
            "features": ["webhook.read"],
            "subscription_expires_at": 180,
            "source_ids": ["S1"],
        },
        "cust-expired": {
            "customer_id": "cust-expired",
            "tenant": "acme",
            "state": "active",
            "features": ["webhook.write"],
            "subscription_expires_at": 80,
            "source_ids": ["S1"],
        },
        "cust-suspended": {
            "customer_id": "cust-suspended",
            "tenant": "acme",
            "state": "suspended",
            "features": ["webhook.write"],
            "subscription_expires_at": 180,
            "source_ids": ["S1"],
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
            raise TimeoutError("webhook transport timed out")
        return outcome


def case_runner(failures: list[dict], case_id: str, fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - verifier reports candidate behavior
        failures.append({"id": case_id, "detail": str(exc)})


def evaluate_static(root: Path, contract: dict):
    failures = []
    files = {
        "CustomerDirectory": root / "candidate/workspace/src/subscriptionmesh/customer_directory.py",
        "SubscriptionPolicy": root / "candidate/workspace/src/subscriptionmesh/subscription_policy.py",
        "WebhookPublisher": root / "candidate/workspace/src/subscriptionmesh/webhook_publisher.py",
    }
    for class_name, marker in contract["legacyPublicMethods"].items():
        text = files[class_name].read_text(encoding="utf-8", errors="replace")
        if f"def {marker}(" in text:
            failures.append({"id": "legacy-api-static", "detail": f"{class_name}.{marker} still defined"})
    return failures


def evaluate_visible_tests(root: Path):
    failures = []
    test_path = root / "candidate" / "workspace" / "tests" / "test_subscriptionmesh.py"
    src_root = root / "candidate" / "workspace" / "src"
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    code = f"""
import importlib.util
import pathlib
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, {str(src_root)!r})
path = pathlib.Path({str(test_path)!r})
spec = importlib.util.spec_from_file_location("n92_visible_tests", path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
for name in sorted(dir(mod)):
    if name.startswith("test_"):
        getattr(mod, name)()
"""
    result = subprocess.run([sys.executable, "-c", code], cwd=root, env=env, text=True, capture_output=True, timeout=10)
    if result.returncode != 0:
        failures.append({"id": "visible-tests", "detail": (result.stderr or result.stdout).strip()})
    return failures


def evaluate_runtime(root: Path, contract: dict):
    failures = []
    try:
        modules = import_modules(root)
    except Exception as exc:  # noqa: BLE001
        return [{"id": "import-subscriptionmesh", "detail": str(exc)}]

    models = modules["models"]
    directory_mod = modules["customer_directory"]
    policy_mod = modules["subscription_policy"]
    publisher_mod = modules["webhook_publisher"]

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

    def public_exports():
        public_all = set(get_field(modules["pkg"], "__all__", []))
        missing = [name for name in contract["downstreamPublicExports"] if not hasattr(modules["pkg"], name)]
        if missing:
            raise AssertionError(f"missing root exports: {missing}")
        unlisted = [name for name in contract["downstreamPublicExports"] if name not in public_all]
        if unlisted:
            raise AssertionError(f"exports missing from __all__: {unlisted}")

    def legacy_methods_removed():
        pairs = [
            (directory_mod.CustomerDirectory, "get_customer"),
            (policy_mod.SubscriptionPolicy, "check"),
            (publisher_mod.WebhookPublisher, "publish"),
        ]
        for cls, method in pairs:
            if hasattr(cls, method):
                raise AssertionError(f"{cls.__name__}.{method} still exists")

    def customer_lookup_contract():
        customers = sample_customers()
        directory = directory_mod.CustomerDirectory(customers, now=contract["currentTick"])
        cases = [
            ("cust-pro", None, True, "active", "customer-directory"),
            ("cust-pro", 200, False, "subscription-expired", "customer-directory"),
            ("missing", None, False, "missing-customer", "customer-directory"),
            ("cust-expired", None, False, "subscription-expired", "customer-directory"),
            ("cust-suspended", None, False, "suspended-customer", "customer-directory"),
        ]
        for customer_id, at_tick, found, reason, owner in cases:
            lookup = directory.lookup_customer(customer_id, at_tick=at_tick) if at_tick is not None else directory.lookup_customer(customer_id)
            if isinstance(lookup, dict):
                raise AssertionError("lookup_customer must return a structured object, not dict")
            assert_equal(get_field(lookup, "found"), found, f"{customer_id}.found")
            assert_equal(get_field(lookup, "customer_id"), customer_id, f"{customer_id}.customer_id")
            assert_equal(get_field(lookup, "reason"), reason, f"{customer_id}.reason")
            assert_equal(get_field(lookup, "owner"), owner, f"{customer_id}.owner")
            source_ids = get_field(lookup, "source_ids")
            if not isinstance(source_ids, list) or not source_ids:
                raise AssertionError(f"{customer_id}.source_ids missing")
        if customers["cust-pro"]["features"] != ["webhook.read", "webhook.write"]:
            raise AssertionError("lookup_customer mutated source records")

    def subscription_contract():
        directory = directory_mod.CustomerDirectory(sample_customers(), now=contract["currentTick"])
        policy = policy_mod.SubscriptionPolicy({"disabledTenants": ["blocked"]})
        cases = [
            ("cust-pro", {"tenant": "acme", "feature": "webhook.write"}, True, "allowed", "subscription-policy"),
            ("cust-basic", {"tenant": "acme", "feature": "webhook.read"}, True, "allowed", "subscription-policy"),
            ("cust-basic", {"tenant": "acme", "feature": "webhook.write"}, False, "feature-not-entitled", "subscription-policy"),
            ("cust-pro", {"tenant": "blocked", "feature": "webhook.read"}, False, "tenant-disabled", "subscription-policy"),
            ("missing", {"tenant": "acme", "feature": "webhook.read"}, False, "missing-customer", "customer-directory"),
            ("cust-expired", {"tenant": "acme", "feature": "webhook.write"}, False, "subscription-expired", "customer-directory"),
            ("cust-suspended", {"tenant": "acme", "feature": "webhook.write"}, False, "suspended-customer", "customer-directory"),
        ]
        for customer_id, request, allowed, reason, owner in cases:
            decision = policy.evaluate_subscription(directory.lookup_customer(customer_id), request)
            if isinstance(decision, dict):
                raise AssertionError("evaluate_subscription must return a structured object, not dict")
            assert_equal(get_field(decision, "allowed"), allowed, f"{customer_id}.allowed")
            assert_equal(get_field(decision, "reason"), reason, f"{customer_id}.reason")
            assert_equal(get_field(decision, "owner"), owner, f"{customer_id}.owner")
            source_ids = get_field(decision, "source_ids")
            if not isinstance(source_ids, list) or not source_ids:
                raise AssertionError(f"{customer_id}.source_ids missing")

    def publisher_contract():
        directory = directory_mod.CustomerDirectory(sample_customers())
        policy = policy_mod.SubscriptionPolicy({"disabledTenants": ["blocked"]})
        allowed = policy.evaluate_subscription(directory.lookup_customer("cust-pro"), {"tenant": "acme", "feature": "webhook.write"})
        denied = policy.evaluate_subscription(directory.lookup_customer("cust-basic"), {"tenant": "acme", "feature": "webhook.write"})

        denied_transport = ScriptedTransport([True])
        denied_result = publisher_mod.WebhookPublisher(denied_transport).publish_webhook(
            {"event_id": "evt-denied", "tenant": "acme"},
            denied,
        )
        assert_equal(get_field(denied_result, "accepted"), False, "denied.accepted")
        assert_equal(get_field(denied_result, "status"), "rejected", "denied.status")
        assert_equal(get_field(denied_result, "retryable"), False, "denied.retryable")
        assert_equal(get_field(denied_result, "reason"), "feature-not-entitled", "denied.reason")
        assert_equal(get_field(denied_result, "owner"), "subscription-policy", "denied.owner")
        assert_equal(len(denied_transport.sent), 0, "denied decision must not publish")

        timeout_transport = ScriptedTransport(["timeout"])
        timeout_result = publisher_mod.WebhookPublisher(timeout_transport).publish_webhook(
            {"event_id": "evt-timeout", "tenant": "acme"},
            allowed,
        )
        assert_equal(get_field(timeout_result, "accepted"), False, "timeout.accepted")
        assert_equal(get_field(timeout_result, "status"), "queued", "timeout.status")
        assert_equal(get_field(timeout_result, "retryable"), True, "timeout.retryable")
        assert_equal(get_field(timeout_result, "error_code"), "webhook-timeout", "timeout.error")
        assert_equal(get_field(timeout_result, "owner"), "webhook-publisher", "timeout.owner")

        success_transport = ScriptedTransport([True, True])
        success_publisher = publisher_mod.WebhookPublisher(success_transport)
        first = success_publisher.publish_webhook({"event_id": "evt-1", "tenant": "acme"}, allowed)
        second = success_publisher.publish_webhook({"event_id": "evt-1", "tenant": "acme"}, allowed)
        assert_equal(get_field(first, "status"), "accepted", "first.status")
        assert_equal(get_field(first, "accepted"), True, "first.accepted")
        assert_equal(get_field(second, "status"), "duplicate", "duplicate.status")
        assert_equal(get_field(second, "accepted"), False, "duplicate.accepted")
        assert_equal(get_field(second, "error_code"), "duplicate-event", "duplicate.error")
        assert_equal(len(success_transport.sent), 1, "duplicate must not republish")

    def integration_contract():
        customers = sample_customers()
        rules = {"disabledTenants": ["blocked"]}
        api = modules["api"]

        ok = as_mapping(api.handle_subscription_event(customers, rules, ScriptedTransport([True]), "cust-pro", {
            "event_id": "evt-ok",
            "tenant": "acme",
            "feature": "webhook.write",
        }))
        assert_equal(ok["status"], "accepted", "ok.status")
        assert_equal(ok["accepted"], True, "ok.accepted")
        assert_equal(ok["reason"], "accepted", "ok.reason")

        denied_transport = ScriptedTransport([True])
        denied = as_mapping(api.handle_subscription_event(customers, rules, denied_transport, "cust-basic", {
            "event_id": "evt-denied",
            "tenant": "acme",
            "feature": "webhook.write",
        }))
        assert_equal(denied["status"], "rejected", "denied.status")
        assert_equal(denied["accepted"], False, "denied.accepted")
        assert_equal(denied["retryable"], False, "denied.retryable")
        assert_equal(denied["reason"], "feature-not-entitled", "denied.reason")
        assert_equal(denied["owner"], "subscription-policy", "denied.owner")
        assert_equal(len(denied_transport.sent), 0, "denied event must not publish")

        timeout = as_mapping(api.handle_subscription_event(customers, rules, ScriptedTransport(["timeout"]), "cust-pro", {
            "event_id": "evt-timeout",
            "tenant": "acme",
            "feature": "webhook.write",
        }))
        assert_equal(timeout["status"], "queued", "timeout.integration.status")
        assert_equal(timeout["retryable"], True, "timeout.integration.retryable")
        assert_equal(timeout["reason"], "webhook-timeout", "timeout.integration.reason")

    def legacy_event_contract():
        envelope = {
            "id": "legacy-17",
            "customer": "cust-pro",
            "tenant": "acme",
            "featureName": "webhook.write",
            "source": "S7",
        }
        before = dict(envelope)
        migrated = modules["legacy_adapter"].migrate_legacy_event(envelope)
        assert_equal(envelope, before, "legacy envelope immutability")
        assert_equal(migrated.get("event_id"), "legacy-17", "legacy.event_id")
        assert_equal(migrated.get("customer_id"), "cust-pro", "legacy.customer_id")
        assert_equal(migrated.get("tenant"), "acme", "legacy.tenant")
        assert_equal(migrated.get("feature"), "webhook.write", "legacy.feature")
        assert_equal(migrated.get("source_id"), "S7", "legacy.source_id")
        if not migrated.get("migrated_from_legacy"):
            raise AssertionError("legacy event must be marked migrated")

    def reporting_contract():
        allowed = modules["models"].WebhookPublishResult(
            accepted=True,
            status="accepted",
            retryable=False,
            event_id="evt-ok",
            error_code=None,
            owner="webhook-publisher",
            reason="accepted",
            source_ids=["S3"],
        )
        queued = modules["models"].WebhookPublishResult(
            accepted=False,
            status="queued",
            retryable=True,
            event_id="evt-timeout",
            error_code="webhook-timeout",
            owner="webhook-publisher",
            reason="webhook-timeout",
            source_ids=["S3"],
        )
        report = modules["reporting"].build_subscription_summary([
            allowed,
            queued,
            {"status": "rejected", "accepted": False, "retryable": False, "owner": "subscription-policy", "reason": "feature-not-entitled", "source_ids": ["S2"]},
            {"status": "duplicate", "accepted": False, "retryable": False, "owner": "webhook-publisher", "reason": "duplicate-event", "source_ids": ["S3"]},
        ])
        assert_equal(report.get("accepted"), 1, "report.accepted")
        assert_equal(report.get("queued"), 1, "report.queued")
        assert_equal(report.get("retryable"), 1, "report.retryable")
        assert_equal(report.get("duplicate"), 1, "report.duplicate")
        assert_equal(report.get("rejected"), 1, "report.rejected")
        owners = report.get("owners")
        if owners != ["subscription-policy", "webhook-publisher"]:
            raise AssertionError(f"report owners drifted: {owners!r}")
        reasons = report.get("reasons", {})
        for reason in ["webhook-timeout", "feature-not-entitled", "duplicate-event"]:
            if reasons.get(reason) != 1:
                raise AssertionError(f"report reason {reason!r} missing")

    for case_id, fn in [
        ("result-models", result_models),
        ("public-exports", public_exports),
        ("legacy-api-removed", legacy_methods_removed),
        ("customer-lookup-contract", customer_lookup_contract),
        ("subscription-contract", subscription_contract),
        ("publisher-contract", publisher_contract),
        ("integration-contract", integration_contract),
        ("legacy-event-migration", legacy_event_contract),
        ("reporting-contract", reporting_contract),
    ]:
        case_runner(failures, case_id, fn)

    return failures


def evaluate_clean_room_public_import(root: Path, contract: dict):
    src_root = root / "candidate" / "workspace" / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(src_root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    code = r'''
import dataclasses
import subscriptionmesh as sm

required = [
    "CustomerDirectory",
    "SubscriptionPolicy",
    "WebhookPublisher",
    "CustomerLookup",
    "SubscriptionDecision",
    "WebhookPublishResult",
    "handle_subscription_event",
    "process_subscription_request",
    "build_subscription_summary",
    "migrate_legacy_event",
]
public_all = set(getattr(sm, "__all__", []))
for name in required:
    assert hasattr(sm, name), name
    assert name in public_all, name
for name in ["CustomerLookup", "SubscriptionDecision", "WebhookPublishResult"]:
    assert dataclasses.is_dataclass(getattr(sm, name)), name
for cls, method in [
    (sm.CustomerDirectory, "get_customer"),
    (sm.SubscriptionPolicy, "check"),
    (sm.WebhookPublisher, "publish"),
]:
    assert not hasattr(cls, method), f"{cls.__name__}.{method}"

class T:
    def __init__(self, outcomes=None):
        self.outcomes = list(outcomes or [True])
        self.sent = []
    def send(self, event):
        self.sent.append(dict(event))
        outcome = self.outcomes.pop(0) if self.outcomes else True
        if outcome == "timeout":
            raise TimeoutError("timeout")
        return outcome

customers = {
    "cust-pro": {"customer_id": "cust-pro", "tenant": "acme", "state": "active", "features": ["webhook.write"], "subscription_expires_at": 180, "source_ids": ["S1"]},
    "cust-basic": {"customer_id": "cust-basic", "tenant": "acme", "state": "active", "features": ["webhook.read"], "subscription_expires_at": 180, "source_ids": ["S1"]},
}
rules = {"disabledTenants": []}
ok = sm.handle_subscription_event(customers, rules, T([True]), "cust-pro", {"event_id": "evt-ok", "tenant": "acme", "feature": "webhook.write"})
assert dataclasses.asdict(ok)["status"] == "accepted"
denied_transport = T([True])
denied = sm.handle_subscription_event(customers, rules, denied_transport, "cust-basic", {"event_id": "evt-denied", "tenant": "acme", "feature": "webhook.write"})
assert dataclasses.asdict(denied)["reason"] == "feature-not-entitled"
assert len(denied_transport.sent) == 0
timeout = sm.handle_subscription_event(customers, rules, T(["timeout"]), "cust-pro", {"event_id": "evt-timeout", "tenant": "acme", "feature": "webhook.write"})
assert dataclasses.asdict(timeout)["retryable"] is True
legacy = sm.migrate_legacy_event({"id": "legacy-a", "customer": "cust-pro", "tenant": "acme", "featureName": "webhook.write", "source": "S7"})
assert legacy["customer_id"] == "cust-pro"
assert legacy["source_id"] == "S7"
summary = sm.build_subscription_summary([ok, timeout, {"status": "duplicate", "accepted": False, "retryable": False, "owner": "webhook-publisher", "reason": "duplicate-event", "source_ids": ["S3"]}])
assert summary["accepted"] == 1
assert summary["queued"] == 1
assert summary["duplicate"] == 1
'''
    result = subprocess.run([sys.executable, "-c", code], cwd=root, env=env, text=True, capture_output=True, timeout=10)
    if result.returncode != 0:
        return [{"id": "clean-room-public-import", "detail": (result.stderr or result.stdout).strip()}]
    return []


def json_text(value):
    return json.dumps(value, sort_keys=True)


def has_any(text: str, needles: list[str]):
    return any(needle in text for needle in needles)


def find_phase(state: dict, phase_id: str):
    for item in state.get("phases", []):
        if not isinstance(item, dict):
            continue
        if item.get("id") == phase_id or item.get("phase") == phase_id or item.get("phaseId") == phase_id:
            return item
    return None


def evaluate_source_ledger(root: Path, contract: dict):
    failures = []
    try:
        ledger = load_json(root / "candidate" / "source-ledger.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "source-ledger-schema", "detail": f"invalid JSON: {exc}"}]
    text = json_text(ledger)
    if ledger.get("contractId") != contract["contractId"]:
        failures.append({"id": "source-ledger-schema", "detail": "contractId mismatch"})
    if contract["planFingerprint"] not in text:
        failures.append({"id": "source-ledger-complete", "detail": "plan fingerprint missing"})
    for source_id in contract["expectedSourceIds"]:
        if source_id not in text:
            failures.append({"id": "source-ledger-complete", "detail": f"missing {source_id}"})
            break
    stale_text = json_text(ledger.get("staleSourceRejections", []))
    for source_id in contract["staleSourceIds"]:
        if source_id not in stale_text:
            failures.append({"id": "source-ledger-stale-rejections", "detail": f"missing {source_id}"})
            break
    for marker in contract["requiredLedgerRows"]["sourceOwners"]:
        if marker not in text:
            failures.append({"id": "source-ledger-owners", "detail": f"missing owner {marker}"})
            break
    return failures


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
        "interfaceMap",
        "callSiteMigration",
        "compatibilityMatrix",
        "validation",
        "patchBudget",
    }
    if not required_keys <= set(state):
        return [{"id": "migration-state-schema", "detail": f"missing keys: {sorted(required_keys - set(state))}"}]

    text = json_text(state)
    if state.get("contractId") != contract["contractId"]:
        failures.append({"id": "migration-state-schema", "detail": "contractId mismatch"})
    if contract["planFingerprint"] not in text:
        failures.append({"id": "phase-ledger-complete", "detail": "plan fingerprint missing"})
    for phase_id in contract["expectedPhaseIds"]:
        phase = find_phase(state, phase_id)
        if not phase:
            failures.append({"id": "phase-ledger-complete", "detail": f"missing phase {phase_id}"})
            break
        if not (phase.get("owner") or phase.get("ownerPath")):
            failures.append({"id": "phase-ledger-complete", "detail": f"missing owner for {phase_id}"})
            break

    marker_sections = ["interfaceMap", "callSites", "compatibilityCases", "validationMarkers"]
    for section in marker_sections:
        section_text = text if section != "validationMarkers" else json_text(state.get("validation", {}))
        for marker in contract["requiredLedgerRows"][section]:
            if marker not in section_text:
                failures.append({"id": f"migration-{section}", "detail": f"missing {marker}"})
                break

    budget = state.get("patchBudget", {})
    if budget.get("maxChangedPaths") != len(contract["requiredChangedPaths"]):
        failures.append({"id": "migration-patch-budget", "detail": "maxChangedPaths mismatch"})
    if sorted(budget.get("requiredChangedPaths", [])) != sorted(contract["requiredChangedPaths"]):
        failures.append({"id": "migration-patch-budget", "detail": "requiredChangedPaths mismatch"})
    return failures


def evaluate_reentry_state(root: Path, contract: dict):
    failures = []
    try:
        state = load_json(root / "candidate" / "reentry-state.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "reentry-state-schema", "detail": f"invalid JSON: {exc}"}]
    text = json_text(state)
    if state.get("contractId") != contract["contractId"]:
        failures.append({"id": "reentry-state-schema", "detail": "contractId mismatch"})
    if contract["planFingerprint"] not in text:
        failures.append({"id": "reentry-state-complete", "detail": "plan fingerprint missing"})
    if "03-downstream-reentry" not in text:
        failures.append({"id": "reentry-state-complete", "detail": "downstream reentry phase missing"})
    for marker in contract["requiredLedgerRows"]["reentryMarkers"]:
        if marker not in text:
            failures.append({"id": "reentry-state-complete", "detail": f"missing {marker}"})
            break
    if sorted(state.get("changedPaths", [])) != sorted(contract["requiredChangedPaths"]):
        failures.append({"id": "reentry-state-complete", "detail": "changed paths mismatch"})
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
    for marker in ["python candidate/workspace/tests/test_subscriptionmesh.py", "check_staged_interface_reentry.py", "clean-room public import"]:
        if marker not in validation_text:
            failures.append({"id": "closure-complete", "detail": f"validation marker missing: {marker}"})
            break
    if not closure.get("reviewOutcome"):
        failures.append({"id": "closure-complete", "detail": "review outcome missing"})
    if "residualRisk" not in closure:
        failures.append({"id": "closure-complete", "detail": "residualRisk missing"})
    return failures


def evaluate_test_markers(root: Path, contract: dict):
    text = (root / "candidate" / "workspace" / "tests" / "test_subscriptionmesh.py").read_text(encoding="utf-8", errors="replace")
    missing = [marker for marker in contract["requiredTestMarkers"] if marker not in text]
    if missing:
        return [{"id": "visible-test-markers", "detail": f"missing markers: {', '.join(missing)}"}]
    return []


def evaluate_bundle(root: Path, contract: dict, changed_paths: list[str]):
    failures = []
    failures.extend(check_changed_paths(contract, changed_paths))
    failures.extend(evaluate_static(root, contract))
    failures.extend(evaluate_visible_tests(root))
    failures.extend(evaluate_runtime(root, contract))
    failures.extend(evaluate_clean_room_public_import(root, contract))
    failures.extend(evaluate_source_ledger(root, contract))
    failures.extend(evaluate_migration_state(root, contract))
    failures.extend(evaluate_reentry_state(root, contract))
    failures.extend(evaluate_review_response(root, contract))
    failures.extend(evaluate_closure(root, contract))
    failures.extend(evaluate_test_markers(root, contract))
    return failures


def write_metrics(path: Path | None, score: float, failures: list[dict]):
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "score": score,
        "passed": not failures,
        "failures": failures,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    contract = load_json(root / "oracle" / "staged-interface-reentry-contract.json")
    shape_errors: list[str] = []
    check_shape(root, contract, shape_errors)
    if shape_errors:
        failures = [{"id": "bundle-shape", "detail": error} for error in shape_errors]
        write_metrics(args.metrics_out, 0.0, failures)
        for failure in failures:
            print(f"ERROR: {failure['detail']}", file=sys.stderr)
        return 1
    if args.bundle_shape_only:
        print("N92 verifier PASS (bundle shape)")
        return 0

    failures = evaluate_bundle(root, contract, args.changed_paths)
    if args.expect_start_state:
        expected = {
            "legacy-api-static",
            "result-models",
            "legacy-api-removed",
            "customer-lookup-contract",
            "clean-room-public-import",
            "source-ledger-complete",
            "migration-interfaceMap",
            "reentry-state-complete",
            "review-response-complete",
            "closure-complete",
            "visible-test-markers",
        }
        observed = {failure["id"] for failure in failures}
        missing = sorted(expected - observed)
        if missing:
            print(f"ERROR: start state no longer exposes expected failures: {missing}", file=sys.stderr)
            return 1
        print("N92 verifier PASS (expected start-state failures present)")
        return 0

    score = 100.0 if not failures else max(0.0, 100.0 - 5.0 * len({failure["id"] for failure in failures}))
    write_metrics(args.metrics_out, score, failures)
    if failures:
        for failure in failures:
            print(f"Failed invariant: {failure['id']} :: {failure.get('detail', '')}", file=sys.stderr)
        return 1
    print("N92 verifier PASS (100.0 / 100)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
