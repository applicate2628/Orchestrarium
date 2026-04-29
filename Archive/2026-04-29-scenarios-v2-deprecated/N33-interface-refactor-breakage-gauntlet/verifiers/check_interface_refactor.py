#!/usr/bin/env python3

from __future__ import annotations

import argparse
import dataclasses
import importlib
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N33 interface-refactor gauntlet.")
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


def import_modules(root: Path):
    src_root = root / "candidate" / "workspace" / "src"
    sys.path.insert(0, str(src_root))
    for name in list(sys.modules):
        if name == "interfaceflow" or name.startswith("interfaceflow."):
            del sys.modules[name]
    return {
        "pkg": importlib.import_module("interfaceflow"),
        "models": importlib.import_module("interfaceflow.models"),
        "session_store": importlib.import_module("interfaceflow.session_store"),
        "policy": importlib.import_module("interfaceflow.policy"),
        "router": importlib.import_module("interfaceflow.router"),
        "orchestrator": importlib.import_module("interfaceflow.orchestrator"),
        "report": importlib.import_module("interfaceflow.report"),
        "api": importlib.import_module("interfaceflow.api"),
    }


def get_field(value, name, default=None):
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def assert_equal(actual, expected, label: str):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def sample_records():
    return {
        "active-admin": {
            "session_id": "active-admin",
            "tenant": "acme",
            "roles": ["admin"],
            "state": "active",
            "expires_at": 75,
        },
        "active-user": {
            "session_id": "active-user",
            "tenant": "acme",
            "roles": ["user"],
            "state": "active",
            "expires_at": 75,
        },
        "expired": {
            "session_id": "expired",
            "tenant": "acme",
            "roles": ["admin"],
            "state": "active",
            "expires_at": 30,
        },
        "revoked": {
            "session_id": "revoked",
            "tenant": "acme",
            "roles": ["admin"],
            "state": "revoked",
            "expires_at": 75,
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
            raise TimeoutError("transport timed out")
        return outcome


def case_runner(failures: list[dict], case_id: str, fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - verifier reports candidate behavior
        failures.append({"id": case_id, "detail": str(exc)})


def evaluate_static(root: Path, contract: dict):
    failures = []
    files = {
        "SessionStore": root / "candidate/workspace/src/interfaceflow/session_store.py",
        "PolicyEvaluator": root / "candidate/workspace/src/interfaceflow/policy.py",
        "EventRouter": root / "candidate/workspace/src/interfaceflow/router.py",
    }
    for class_name, marker in contract["legacyPublicMethods"].items():
        text = files[class_name].read_text(encoding="utf-8", errors="replace")
        forbidden = f"def {marker}("
        if forbidden in text:
            failures.append({"id": "legacy-interface-static", "detail": f"{class_name}.{marker} still defined"})
    return failures


def evaluate_runtime(root: Path, contract: dict):
    failures = []
    try:
        modules = import_modules(root)
    except Exception as exc:  # noqa: BLE001
        return [{"id": "import-interfaceflow", "detail": str(exc)}]

    models = modules["models"]
    store_mod = modules["session_store"]
    policy_mod = modules["policy"]
    router_mod = modules["router"]

    def result_models():
        for name in contract["requiredResultModels"]:
            model = getattr(models, name, None)
            if model is None:
                raise AssertionError(f"missing model {name}")
            if not dataclasses.is_dataclass(model):
                raise AssertionError(f"{name} must be a dataclass")

    def legacy_methods_removed():
        pairs = [
            (store_mod.SessionStore, "get"),
            (policy_mod.PolicyEvaluator, "evaluate"),
            (router_mod.EventRouter, "dispatch"),
        ]
        for cls, method in pairs:
            if hasattr(cls, method):
                raise AssertionError(f"{cls.__name__}.{method} still exists")

    def session_lookup_contract():
        records = sample_records()
        store = store_mod.SessionStore(records, now=contract["sessionNow"])
        cases = [
            ("active-admin", True, "active", "session-store"),
            ("missing", False, "missing", "session-store"),
            ("expired", False, "expired", "session-store"),
            ("revoked", False, "revoked", "session-store"),
        ]
        for session_id, found, reason, owner in cases:
            lookup = store.lookup(session_id)
            if isinstance(lookup, dict):
                raise AssertionError("lookup must return a structured object, not dict")
            assert_equal(get_field(lookup, "found"), found, f"{session_id}.found")
            assert_equal(get_field(lookup, "session_id"), session_id, f"{session_id}.session_id")
            assert_equal(get_field(lookup, "reason"), reason, f"{session_id}.reason")
            assert_equal(get_field(lookup, "owner"), owner, f"{session_id}.owner")
        if records["active-admin"]["roles"] != ["admin"]:
            raise AssertionError("lookup mutated source records")

    def policy_contract():
        store = store_mod.SessionStore(sample_records(), now=contract["sessionNow"])
        policy = policy_mod.PolicyEvaluator({"blockedTenants": ["blocked"]})
        cases = [
            ("active-admin", {"tenant": "acme", "action": "delete"}, True, "allowed", "policy-evaluator"),
            ("active-user", {"tenant": "acme", "action": "delete"}, False, "requires-admin", "policy-evaluator"),
            ("active-admin", {"tenant": "blocked", "action": "read"}, False, "blocked-tenant", "policy-evaluator"),
            ("missing", {"tenant": "acme", "action": "read"}, False, "missing", "session-store"),
            ("expired", {"tenant": "acme", "action": "read"}, False, "expired", "session-store"),
        ]
        for session_id, event, allowed, reason, owner in cases:
            decision = policy.evaluate_policy(store.lookup(session_id), event)
            if isinstance(decision, dict):
                raise AssertionError("policy must return a structured object, not dict")
            assert_equal(get_field(decision, "allowed"), allowed, f"{session_id}.allowed")
            assert_equal(get_field(decision, "reason"), reason, f"{session_id}.reason")
            assert_equal(get_field(decision, "owner"), owner, f"{session_id}.owner")
            source_ids = get_field(decision, "source_ids")
            if not isinstance(source_ids, list) or not source_ids:
                raise AssertionError(f"{session_id}.source_ids must be a non-empty list")

    def router_contract():
        policy = policy_mod.PolicyEvaluator({})
        lookup = store_mod.SessionStore(sample_records()).lookup("active-admin")
        allowed = policy.evaluate_policy(lookup, {"tenant": "acme", "action": "read"})

        timeout_transport = ScriptedTransport(["timeout"])
        timeout_router = router_mod.EventRouter(timeout_transport)
        timeout_result = timeout_router.dispatch_event({"event_id": "evt-timeout", "tenant": "acme"}, allowed)
        assert_equal(get_field(timeout_result, "accepted"), False, "timeout.accepted")
        assert_equal(get_field(timeout_result, "status"), "queued", "timeout.status")
        assert_equal(get_field(timeout_result, "retryable"), True, "timeout.retryable")
        assert_equal(get_field(timeout_result, "error_code"), "transport-timeout", "timeout.error")

        success_transport = ScriptedTransport([True, True])
        success_router = router_mod.EventRouter(success_transport)
        first = success_router.dispatch_event({"event_id": "evt-1", "tenant": "acme"}, allowed)
        second = success_router.dispatch_event({"event_id": "evt-1", "tenant": "acme"}, allowed)
        assert_equal(get_field(first, "status"), "accepted", "first.status")
        assert_equal(get_field(second, "status"), "accepted", "second.status")
        assert_equal(get_field(second, "error_code"), "duplicate-event", "duplicate.error")
        assert_equal(len(success_transport.sent), 1, "duplicate must not resend")

    def integration_contract():
        records = sample_records()
        rules = {"blockedTenants": ["blocked"]}
        api = modules["api"]

        ok = api.handle_event(records, rules, ScriptedTransport([True]), "active-admin", {
            "event_id": "evt-ok",
            "tenant": "acme",
            "action": "delete",
        })
        assert_equal(ok["status"], "accepted", "ok.status")
        assert_equal(ok["accepted"], True, "ok.accepted")
        assert_equal(ok["reason"], "accepted", "ok.reason")

        blocked = api.handle_event(records, rules, ScriptedTransport([True]), "active-admin", {
            "event_id": "evt-blocked",
            "tenant": "blocked",
            "action": "read",
        })
        assert_equal(blocked["status"], "rejected", "blocked.status")
        assert_equal(blocked["accepted"], False, "blocked.accepted")
        assert_equal(blocked["retryable"], False, "blocked.retryable")
        assert_equal(blocked["reason"], "blocked-tenant", "blocked.reason")
        assert_equal(blocked["owner"], "policy-evaluator", "blocked.owner")

        expired = api.handle_event(records, rules, ScriptedTransport([True]), "expired", {
            "event_id": "evt-expired",
            "tenant": "acme",
            "action": "read",
        })
        assert_equal(expired["reason"], "expired", "expired.reason")
        assert_equal(expired["owner"], "session-store", "expired.owner")

        timeout = api.handle_event(records, rules, ScriptedTransport(["timeout"]), "active-admin", {
            "event_id": "evt-timeout",
            "tenant": "acme",
            "action": "read",
        })
        assert_equal(timeout["status"], "queued", "timeout.integration.status")
        assert_equal(timeout["retryable"], True, "timeout.integration.retryable")
        assert_equal(timeout["reason"], "transport-timeout", "timeout.integration.reason")

    def report_contract():
        report = modules["report"].build_audit_summary([
            {"status": "accepted", "accepted": True, "retryable": False, "owner": "event-router", "reason": "accepted"},
            {"status": "queued", "accepted": False, "retryable": True, "owner": "event-router", "reason": "transport-timeout"},
            {"status": "rejected", "accepted": False, "retryable": False, "owner": "policy-evaluator", "reason": "blocked-tenant"},
            {"status": "rejected", "accepted": False, "retryable": False, "owner": "session-store", "reason": "missing"},
        ])
        assert_equal(report.get("accepted"), 1, "report.accepted")
        assert_equal(report.get("retryable"), 1, "report.retryable")
        assert_equal(report.get("rejected"), 2, "report.rejected")
        assert_equal(report.get("queued"), 1, "report.queued")
        owners = report.get("owners")
        if owners != ["event-router", "policy-evaluator", "session-store"]:
            raise AssertionError(f"report owners drifted: {owners!r}")
        reasons = report.get("reasons", {})
        for reason in ["transport-timeout", "blocked-tenant", "missing"]:
            if reasons.get(reason) != 1:
                raise AssertionError(f"report reason {reason!r} missing")

    for case_id, fn in [
        ("result-models", result_models),
        ("legacy-interface-removed", legacy_methods_removed),
        ("session-lookup-contract", session_lookup_contract),
        ("policy-contract", policy_contract),
        ("router-contract", router_contract),
        ("integration-contract", integration_contract),
        ("report-contract", report_contract),
    ]:
        case_runner(failures, case_id, fn)

    return failures


def evaluate_ledger(root: Path, contract: dict):
    failures = []
    try:
        ledger = load_json(root / "candidate" / "refactor-ledger.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "refactor-ledger-schema", "detail": f"invalid JSON: {exc}"}]

    def ledger_schema():
        required = {"contractId", "interfaceMap", "callSiteMigration", "compatibilityMatrix", "validation", "patchBudget"}
        assert_equal(set(ledger), required, "ledger top-level keys")
        assert_equal(ledger["contractId"], contract["contractId"], "ledger contract id")

    def interface_map():
        text = json.dumps(ledger.get("interfaceMap", []), sort_keys=True)
        for marker in contract["requiredLedgerRows"]["interfaceMap"]:
            if marker not in text:
                raise AssertionError(f"missing interface map marker {marker}")

    def call_sites():
        text = json.dumps(ledger.get("callSiteMigration", []), sort_keys=True)
        for marker in contract["requiredLedgerRows"]["callSites"]:
            if marker not in text:
                raise AssertionError(f"missing call-site marker {marker}")

    def compatibility():
        text = json.dumps(ledger.get("compatibilityMatrix", []), sort_keys=True)
        for marker in contract["requiredLedgerRows"]["compatibilityCases"]:
            if marker not in text:
                raise AssertionError(f"missing compatibility case {marker}")

    def validation():
        text = json.dumps(ledger.get("validation", {}), sort_keys=True)
        for marker in contract["requiredLedgerRows"]["validationMarkers"]:
            if marker not in text:
                raise AssertionError(f"missing validation marker {marker}")

    def patch_budget():
        budget = ledger.get("patchBudget", {})
        assert_equal(budget.get("maxChangedPaths"), len(contract["requiredChangedPaths"]), "patchBudget.maxChangedPaths")
        assert_equal(sorted(budget.get("requiredChangedPaths", [])), sorted(contract["requiredChangedPaths"]), "patchBudget.requiredChangedPaths")

    for case_id, fn in [
        ("refactor-ledger-schema", ledger_schema),
        ("refactor-ledger-interface-map", interface_map),
        ("refactor-ledger-call-sites", call_sites),
        ("refactor-ledger-compatibility", compatibility),
        ("refactor-ledger-validation", validation),
        ("refactor-ledger-patch-budget", patch_budget),
    ]:
        case_runner(failures, case_id, fn)

    return failures


def evaluate_test_markers(root: Path, contract: dict):
    text = (root / "candidate" / "workspace" / "tests" / "test_interfaceflow.py").read_text(
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
    failures.extend(evaluate_ledger(root, contract))
    failures.extend(evaluate_test_markers(root, contract))
    return failures


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    contract = load_json(root / "oracle" / "interface-refactor-contract.json")
    shape_errors: list[str] = []
    check_shape(root, contract, shape_errors)
    if shape_errors:
        for error in shape_errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if args.bundle_shape_only:
        print("N33 verifier PASS (bundle shape)")
        return 0

    failures = evaluate_bundle(root, contract)
    if args.expect_start_state:
        expected = {"legacy-interface-static", "result-models", "legacy-interface-removed", "session-lookup-contract", "refactor-ledger-interface-map"}
        observed = {failure["id"] for failure in failures}
        missing = sorted(expected - observed)
        if missing:
            print(f"ERROR: start state no longer exposes expected failures: {missing}", file=sys.stderr)
            return 1
        print("N33 verifier PASS (expected start-state failures present)")
        return 0

    if failures:
        for failure in failures:
            print(f"Failed invariant: {failure['id']} :: {failure.get('detail', '')}", file=sys.stderr)
        return 1

    print("N33 verifier PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
