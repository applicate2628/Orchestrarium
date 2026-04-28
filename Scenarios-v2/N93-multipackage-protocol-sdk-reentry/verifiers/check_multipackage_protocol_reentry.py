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
    parser = argparse.ArgumentParser(description="Check the N93 multipackage protocol/sdk reentry bundle.")
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
        if (
            name.startswith("protocolmesh_core")
            or name.startswith("protocolmesh_sdk")
            or name.startswith("protocolmesh_plugins")
            or name.startswith("protocolmesh_cli")
        ):
            del sys.modules[name]
    return {
        "core": importlib.import_module("protocolmesh_core"),
        "core_models": importlib.import_module("protocolmesh_core.models"),
        "core_registry": importlib.import_module("protocolmesh_core.registry"),
        "core_router": importlib.import_module("protocolmesh_core.router"),
        "sdk": importlib.import_module("protocolmesh_sdk"),
        "sdk_client": importlib.import_module("protocolmesh_sdk.client"),
        "sdk_compat": importlib.import_module("protocolmesh_sdk.compat"),
        "sdk_serializer": importlib.import_module("protocolmesh_sdk.serializer"),
        "plugins": importlib.import_module("protocolmesh_plugins"),
        "plugins_http": importlib.import_module("protocolmesh_plugins.http_adapter"),
        "cli": importlib.import_module("protocolmesh_cli"),
        "cli_main": importlib.import_module("protocolmesh_cli.main"),
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
    raise AssertionError(f"expected dataclass or dict, got {type(value).__name__}")


def assert_equal(actual, expected, label: str):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def make_envelope(core, *, event_id="evt-ok", action="approve", schema_version=2):
    return core.WireEnvelope(
        event_id=event_id,
        tenant="tenant-a",
        subject="invoice-9",
        action=action,
        payload={"amount": 10, "currency": "USD"},
        trace_id=f"trace-{event_id}",
        source_id="S2",
        schema_version=schema_version,
    )


class ScriptedTransport:
    def __init__(self, outcomes=None):
        self.outcomes = list(outcomes or [True])
        self.sent = []

    def send(self, payload):
        self.sent.append(dict(payload))
        outcome = self.outcomes.pop(0) if self.outcomes else True
        if outcome == "timeout":
            raise TimeoutError("plugin transport timed out")
        return outcome


def accept_handler(envelope):
    return {"accepted": True, "owner": "orders-handler", "reason": "accepted"}


def deny_handler(envelope):
    return {"accepted": False, "owner": "risk-policy", "reason": "policy-denied"}


def case_runner(failures: list[dict], case_id: str, fn):
    try:
        fn()
    except Exception as exc:  # noqa: BLE001 - verifier reports candidate behavior
        failures.append({"id": case_id, "detail": str(exc)})


def evaluate_static(root: Path, contract: dict):
    failures = []
    for entry in contract["legacyForbiddenDefinitions"]:
        path = root / entry["path"]
        text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        for snippet in entry["snippets"]:
            if snippet in text:
                failures.append({"id": "legacy-api-static", "detail": f"{snippet!r} still present in {entry['path']}"})
                return failures
    return failures


def evaluate_visible_tests(root: Path):
    failures = []
    test_path = root / "candidate" / "workspace" / "tests" / "test_protocolmesh.py"
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
spec = importlib.util.spec_from_file_location("n93_visible_tests", path)
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
        return [{"id": "import-protocolmesh", "detail": str(exc)}]

    core = modules["core"]
    sdk = modules["sdk"]
    plugins = modules["plugins"]
    cli = modules["cli"]

    def result_models():
        model_locations = {
            "WireEnvelope": core,
            "RouteDecision": core,
            "PluginAck": plugins,
            "SendResult": sdk,
        }
        for name, fields in contract["requiredResultModels"].items():
            model = getattr(model_locations[name], name, None)
            if model is None:
                raise AssertionError(f"missing model {name}")
            if not dataclasses.is_dataclass(model):
                raise AssertionError(f"{name} must be a dataclass")
            model_fields = {field.name for field in dataclasses.fields(model)}
            missing = sorted(set(fields) - model_fields)
            if missing:
                raise AssertionError(f"{name} missing fields: {missing}")

    def public_exports():
        packages = {
            "protocolmesh_core": core,
            "protocolmesh_sdk": sdk,
            "protocolmesh_plugins": plugins,
            "protocolmesh_cli": cli,
        }
        for package_name, exports in contract["publicExports"].items():
            package = packages[package_name]
            public_all = set(get_field(package, "__all__", []))
            missing = [name for name in exports if not hasattr(package, name)]
            if missing:
                raise AssertionError(f"{package_name} missing exports: {missing}")
            unlisted = [name for name in exports if name not in public_all]
            if unlisted:
                raise AssertionError(f"{package_name} exports missing from __all__: {unlisted}")

    def legacy_apis_removed():
        checks = [
            (core, "route_event", "protocolmesh_core.route_event"),
            (modules["core_router"], "route_event", "protocolmesh_core.router.route_event"),
            (sdk.ProtocolClient, "send_event", "ProtocolClient.send_event"),
            (sdk, "serialize_event", "protocolmesh_sdk.serialize_event"),
            (modules["sdk_serializer"], "serialize_event", "protocolmesh_sdk.serializer.serialize_event"),
            (sdk, "deserialize_event", "protocolmesh_sdk.deserialize_event"),
            (modules["sdk_serializer"], "deserialize_event", "protocolmesh_sdk.serializer.deserialize_event"),
            (sdk, "upgrade_legacy", "protocolmesh_sdk.upgrade_legacy"),
            (modules["sdk_compat"], "upgrade_legacy", "protocolmesh_sdk.compat.upgrade_legacy"),
            (plugins, "HttpAdapter", "protocolmesh_plugins.HttpAdapter"),
            (modules["plugins_http"], "HttpAdapter", "protocolmesh_plugins.http_adapter.HttpAdapter"),
            (modules["cli_main"], "main", "protocolmesh_cli.main.main"),
        ]
        for obj, attr, label in checks:
            if hasattr(obj, attr):
                raise AssertionError(f"{label} still exists")
        if hasattr(plugins.HttpPluginAdapter, "publish"):
            raise AssertionError("HttpPluginAdapter.publish still exists")

    def registry_router_contract():
        registry = core.HandlerRegistry({"approve": accept_handler, "deny": deny_handler})
        if not hasattr(registry, "get"):
            raise AssertionError("HandlerRegistry.get missing")
        if registry.get("approve") is None:
            raise AssertionError("HandlerRegistry.get does not return registered handler")

        accepted = core.route_envelope(make_envelope(core, action="approve"), registry)
        if isinstance(accepted, dict):
            raise AssertionError("route_envelope must return RouteDecision dataclass, not dict")
        assert_equal(get_field(accepted, "accepted"), True, "accepted.accepted")
        assert_equal(get_field(accepted, "status"), "accepted", "accepted.status")
        assert_equal(get_field(accepted, "reason"), "accepted", "accepted.reason")
        assert_equal(get_field(accepted, "owner"), "orders-handler", "accepted.owner")
        assert_equal(get_field(accepted, "handler"), "approve", "accepted.handler")
        assert_equal(get_field(accepted, "trace_id"), "trace-evt-ok", "accepted.trace_id")
        if "S2" not in get_field(accepted, "source_ids", []):
            raise AssertionError("accepted decision missing envelope source_id")

        denied = core.route_envelope(make_envelope(core, event_id="evt-deny", action="deny"), registry)
        assert_equal(get_field(denied, "accepted"), False, "denied.accepted")
        assert_equal(get_field(denied, "status"), "rejected", "denied.status")
        assert_equal(get_field(denied, "reason"), "policy-denied", "denied.reason")
        assert_equal(get_field(denied, "owner"), "risk-policy", "denied.owner")

        missing = core.route_envelope(make_envelope(core, event_id="evt-missing", action="missing"), registry)
        assert_equal(get_field(missing, "accepted"), False, "missing.accepted")
        assert_equal(get_field(missing, "status"), "rejected", "missing.status")
        assert_equal(get_field(missing, "reason"), "handler-not-found", "missing.reason")
        assert_equal(get_field(missing, "owner"), "handler-registry", "missing.owner")

        invalid = core.route_envelope(make_envelope(core, event_id="evt-bad", schema_version=1), registry)
        assert_equal(get_field(invalid, "accepted"), False, "invalid.accepted")
        assert_equal(get_field(invalid, "reason"), "invalid-schema-version", "invalid.reason")
        assert_equal(get_field(invalid, "owner"), "core-router", "invalid.owner")

    def serializer_contract():
        envelope = make_envelope(core)
        wire = sdk.serialize_envelope(envelope)
        assert_equal(wire.get("schemaVersion"), 2, "wire.schemaVersion")
        assert_equal(wire.get("eventId"), "evt-ok", "wire.eventId")
        assert_equal(wire.get("tenant"), "tenant-a", "wire.tenant")
        assert_equal(wire.get("subject"), "invoice-9", "wire.subject")
        assert_equal(wire.get("action"), "approve", "wire.action")
        assert_equal(wire.get("traceId"), "trace-evt-ok", "wire.traceId")
        assert_equal(wire.get("sourceId"), "S2", "wire.sourceId")
        roundtrip = sdk.deserialize_envelope(wire)
        if isinstance(roundtrip, dict):
            raise AssertionError("deserialize_envelope must return WireEnvelope dataclass")
        assert_equal(get_field(roundtrip, "event_id"), "evt-ok", "roundtrip.event_id")
        assert_equal(get_field(roundtrip, "schema_version"), 2, "roundtrip.schema_version")
        assert_equal(dataclasses.asdict(roundtrip)["payload"], {"amount": 10, "currency": "USD"}, "roundtrip.payload")

    def legacy_migration_contract():
        legacy = {
            "id": "legacy-77",
            "tenantId": "tenant-a",
            "resource": "invoice-77",
            "command": "approve",
            "body": {"amount": 77},
            "trace": "trace-legacy",
            "source": "S6",
        }
        before = json.loads(json.dumps(legacy, sort_keys=True))
        migrated = sdk.migrate_legacy_envelope(legacy)
        assert_equal(legacy, before, "legacy input mutated")
        if isinstance(migrated, dict):
            raise AssertionError("migrate_legacy_envelope must return WireEnvelope dataclass")
        assert_equal(get_field(migrated, "event_id"), "legacy-77", "legacy.event_id")
        assert_equal(get_field(migrated, "tenant"), "tenant-a", "legacy.tenant")
        assert_equal(get_field(migrated, "subject"), "invoice-77", "legacy.subject")
        assert_equal(get_field(migrated, "action"), "approve", "legacy.action")
        assert_equal(get_field(migrated, "payload"), {"amount": 77}, "legacy.payload")
        assert_equal(get_field(migrated, "trace_id"), "trace-legacy", "legacy.trace_id")
        assert_equal(get_field(migrated, "source_id"), "S6", "legacy.source_id")
        assert_equal(get_field(migrated, "schema_version"), 2, "legacy.schema_version")

    def plugin_contract():
        registry = core.HandlerRegistry({"approve": accept_handler, "deny": deny_handler})
        accepted_decision = core.route_envelope(make_envelope(core, action="approve"), registry)
        denied_decision = core.route_envelope(make_envelope(core, event_id="evt-deny", action="deny"), registry)

        success_transport = ScriptedTransport([True, True])
        success_adapter = plugins.HttpPluginAdapter(success_transport)
        first = success_adapter.deliver(make_envelope(core, event_id="evt-1"), accepted_decision)
        second = success_adapter.deliver(make_envelope(core, event_id="evt-1"), accepted_decision)
        assert_equal(get_field(first, "delivered"), True, "first.delivered")
        assert_equal(get_field(first, "status"), "delivered", "first.status")
        assert_equal(get_field(first, "event_id"), "evt-1", "first.event_id")
        assert_equal(get_field(second, "delivered"), False, "duplicate.delivered")
        assert_equal(get_field(second, "status"), "duplicate", "duplicate.status")
        assert_equal(get_field(second, "error_code"), "duplicate-event", "duplicate.error_code")
        assert_equal(len(success_transport.sent), 1, "duplicate must not republish")

        denied_transport = ScriptedTransport([True])
        denied_ack = plugins.HttpPluginAdapter(denied_transport).deliver(make_envelope(core, event_id="evt-deny"), denied_decision)
        assert_equal(get_field(denied_ack, "delivered"), False, "denied.delivered")
        assert_equal(get_field(denied_ack, "status"), "rejected", "denied.status")
        assert_equal(get_field(denied_ack, "retryable"), False, "denied.retryable")
        assert_equal(get_field(denied_ack, "reason"), "policy-denied", "denied.reason")
        assert_equal(get_field(denied_ack, "owner"), "risk-policy", "denied.owner")
        assert_equal(len(denied_transport.sent), 0, "denied decision must not deliver")

        timeout_ack = plugins.HttpPluginAdapter(ScriptedTransport(["timeout"])).deliver(
            make_envelope(core, event_id="evt-timeout"),
            accepted_decision,
        )
        assert_equal(get_field(timeout_ack, "delivered"), False, "timeout.delivered")
        assert_equal(get_field(timeout_ack, "status"), "queued", "timeout.status")
        assert_equal(get_field(timeout_ack, "retryable"), True, "timeout.retryable")
        assert_equal(get_field(timeout_ack, "error_code"), "plugin-timeout", "timeout.error_code")
        assert_equal(get_field(timeout_ack, "owner"), "plugin-adapter", "timeout.owner")

    def client_contract():
        registry = core.HandlerRegistry({"approve": accept_handler, "deny": deny_handler})

        ok_transport = ScriptedTransport([True])
        ok_result = sdk.ProtocolClient(registry, plugins.HttpPluginAdapter(ok_transport)).send(make_envelope(core, event_id="evt-client-ok"))
        if isinstance(ok_result, dict):
            raise AssertionError("ProtocolClient.send must return SendResult dataclass")
        assert_equal(get_field(ok_result, "accepted"), True, "client.ok.accepted")
        assert_equal(get_field(ok_result, "status"), "delivered", "client.ok.status")
        assert_equal(get_field(ok_result, "event_id"), "evt-client-ok", "client.ok.event_id")
        assert_equal(get_field(ok_result, "reason"), "accepted", "client.ok.reason")
        assert_equal(as_mapping(get_field(ok_result, "ack")).get("delivered"), True, "client.ok.ack.delivered")
        assert_equal(get_field(ok_result, "wire").get("schemaVersion"), 2, "client.ok.wire.schemaVersion")

        denied_transport = ScriptedTransport([True])
        denied_result = sdk.ProtocolClient(registry, plugins.HttpPluginAdapter(denied_transport)).send(make_envelope(core, event_id="evt-client-deny", action="deny"))
        assert_equal(get_field(denied_result, "accepted"), False, "client.denied.accepted")
        assert_equal(get_field(denied_result, "status"), "rejected", "client.denied.status")
        assert_equal(get_field(denied_result, "retryable"), False, "client.denied.retryable")
        assert_equal(get_field(denied_result, "reason"), "policy-denied", "client.denied.reason")
        assert_equal(len(denied_transport.sent), 0, "client denied event must not deliver")

        timeout_result = sdk.ProtocolClient(registry, plugins.HttpPluginAdapter(ScriptedTransport(["timeout"]))).send(make_envelope(core, event_id="evt-client-timeout"))
        assert_equal(get_field(timeout_result, "accepted"), False, "client.timeout.accepted")
        assert_equal(get_field(timeout_result, "status"), "queued", "client.timeout.status")
        assert_equal(get_field(timeout_result, "retryable"), True, "client.timeout.retryable")
        assert_equal(get_field(timeout_result, "reason"), "plugin-timeout", "client.timeout.reason")

        duplicate_transport = ScriptedTransport([True, True])
        duplicate_client = sdk.ProtocolClient(registry, plugins.HttpPluginAdapter(duplicate_transport))
        duplicate_client.send(make_envelope(core, event_id="evt-client-dup"))
        duplicate = duplicate_client.send(make_envelope(core, event_id="evt-client-dup"))
        assert_equal(get_field(duplicate, "status"), "duplicate", "client.duplicate.status")
        assert_equal(get_field(duplicate, "accepted"), False, "client.duplicate.accepted")
        assert_equal(len(duplicate_transport.sent), 1, "client duplicate must not republish")

    def cli_contract():
        registry = core.HandlerRegistry({"approve": accept_handler, "deny": deny_handler})
        wire = sdk.serialize_envelope(make_envelope(core, event_id="evt-cli"))
        result = cli.run_cli(["--json", json.dumps(wire)], registry=registry, transport=ScriptedTransport([True]))
        if not isinstance(result, dict):
            raise AssertionError("run_cli must return dict")
        assert_equal(result.get("event_id"), "evt-cli", "cli.event_id")
        assert_equal(result.get("status"), "delivered", "cli.status")
        assert_equal(result.get("wire", {}).get("schemaVersion"), 2, "cli.wire.schemaVersion")

        legacy = {
            "id": "legacy-cli",
            "tenantId": "tenant-a",
            "resource": "invoice-cli",
            "command": "approve",
            "body": {"amount": 4},
            "trace": "trace-cli",
            "source": "S6",
        }
        legacy_result = cli.run_cli(["--legacy-json", json.dumps(legacy)], registry=registry, transport=ScriptedTransport([True]))
        assert_equal(legacy_result.get("event_id"), "legacy-cli", "cli.legacy.event_id")
        assert_equal(legacy_result.get("status"), "delivered", "cli.legacy.status")
        assert_equal(legacy_result.get("wire", {}).get("sourceId"), "S6", "cli.legacy.sourceId")

    for case_id, fn in [
        ("result-models", result_models),
        ("public-exports", public_exports),
        ("legacy-api-removed", legacy_apis_removed),
        ("registry-router-contract", registry_router_contract),
        ("serializer-contract", serializer_contract),
        ("legacy-envelope-migration", legacy_migration_contract),
        ("plugin-contract", plugin_contract),
        ("client-contract", client_contract),
        ("cli-contract", cli_contract),
    ]:
        case_runner(failures, case_id, fn)

    return failures


def evaluate_clean_room_public_import(root: Path):
    src_root = root / "candidate" / "workspace" / "src"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(src_root)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    code = r'''
import dataclasses
import json
import protocolmesh_core as core
import protocolmesh_sdk as sdk
import protocolmesh_plugins as plugins
import protocolmesh_cli as cli

for package, names in [
    (core, ["HandlerRegistry", "WireEnvelope", "RouteDecision", "route_envelope"]),
    (sdk, ["ProtocolClient", "SendResult", "serialize_envelope", "deserialize_envelope", "migrate_legacy_envelope"]),
    (plugins, ["HttpPluginAdapter", "PluginAck"]),
    (cli, ["run_cli"]),
]:
    public_all = set(getattr(package, "__all__", []))
    for name in names:
        assert hasattr(package, name), name
        assert name in public_all, name

for model in [core.WireEnvelope, core.RouteDecision, plugins.PluginAck, sdk.SendResult]:
    assert dataclasses.is_dataclass(model), model

assert not hasattr(core, "route_event")
assert not hasattr(sdk.ProtocolClient, "send_event")
assert not hasattr(sdk, "serialize_event")
assert not hasattr(sdk, "upgrade_legacy")
assert not hasattr(plugins, "HttpAdapter")
assert not hasattr(cli.main, "main")

class T:
    def __init__(self, outcomes=None):
        self.outcomes = list(outcomes or [True])
        self.sent = []
    def send(self, payload):
        self.sent.append(dict(payload))
        outcome = self.outcomes.pop(0) if self.outcomes else True
        if outcome == "timeout":
            raise TimeoutError("timeout")
        return outcome

def ok(envelope):
    return {"accepted": True, "owner": "orders-handler", "reason": "accepted"}

def deny(envelope):
    return {"accepted": False, "owner": "risk-policy", "reason": "policy-denied"}

registry = core.HandlerRegistry({"approve": ok, "deny": deny})
env = core.WireEnvelope("evt-clean", "tenant-a", "invoice-1", "approve", {"x": 1}, "trace-clean", "S2", 2)
wire = sdk.serialize_envelope(env)
assert wire["schemaVersion"] == 2
assert dataclasses.asdict(sdk.deserialize_envelope(wire))["event_id"] == "evt-clean"
result = sdk.ProtocolClient(registry, plugins.HttpPluginAdapter(T([True]))).send(env)
assert dataclasses.asdict(result)["status"] == "delivered"
denied_transport = T([True])
denied = sdk.ProtocolClient(registry, plugins.HttpPluginAdapter(denied_transport)).send(
    core.WireEnvelope("evt-denied", "tenant-a", "invoice-2", "deny", {}, "trace-denied", "S2", 2)
)
assert dataclasses.asdict(denied)["status"] == "rejected"
assert len(denied_transport.sent) == 0
timeout = sdk.ProtocolClient(registry, plugins.HttpPluginAdapter(T(["timeout"]))).send(env)
assert dataclasses.asdict(timeout)["retryable"] is True
legacy = sdk.migrate_legacy_envelope({"id": "legacy-clean", "tenantId": "tenant-a", "resource": "invoice-3", "command": "approve", "body": {}, "trace": "trace-legacy", "source": "S6"})
assert dataclasses.asdict(legacy)["source_id"] == "S6"
cli_result = cli.run_cli(["--json", json.dumps(wire)], registry=registry, transport=T([True]))
assert cli_result["event_id"] == "evt-clean"
'''
    result = subprocess.run([sys.executable, "-c", code], cwd=root, env=env, text=True, capture_output=True, timeout=10)
    if result.returncode != 0:
        return [{"id": "clean-room-public-import", "detail": (result.stderr or result.stdout).strip()}]
    return []


def json_text(value):
    return json.dumps(value, sort_keys=True)


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

    for section in ["interfaceMap", "callSites", "compatibilityCases", "validationMarkers"]:
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


def evaluate_sdk_compat_ledger(root: Path, contract: dict):
    failures = []
    try:
        ledger = load_json(root / "candidate" / "sdk-compat-ledger.json")
    except Exception as exc:  # noqa: BLE001
        return [{"id": "sdk-compat-ledger-schema", "detail": f"invalid JSON: {exc}"}]
    text = json_text(ledger)
    if ledger.get("contractId") != contract["contractId"]:
        failures.append({"id": "sdk-compat-ledger-schema", "detail": "contractId mismatch"})
    if contract["planFingerprint"] not in text:
        failures.append({"id": "sdk-compat-ledger-complete", "detail": "plan fingerprint missing"})
    for marker in contract["requiredLedgerRows"]["sdkCompatMarkers"]:
        if marker not in text:
            failures.append({"id": "sdk-compat-ledger-complete", "detail": f"missing {marker}"})
            break
    for source_id in ["S4", "S5", "S6", "S7", "S8", "S9", "S10"]:
        if source_id not in text:
            failures.append({"id": "sdk-compat-ledger-complete", "detail": f"missing {source_id}"})
            break
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
    if "04-cli-downstream-reentry" not in text:
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
    for marker in ["python candidate/workspace/tests/test_protocolmesh.py", "check_multipackage_protocol_reentry.py", "clean-room protocol/sdk import", "CLI contract replay"]:
        if marker not in validation_text:
            failures.append({"id": "closure-complete", "detail": f"validation marker missing: {marker}"})
            break
    if not closure.get("reviewOutcome"):
        failures.append({"id": "closure-complete", "detail": "review outcome missing"})
    if "residualRisk" not in closure:
        failures.append({"id": "closure-complete", "detail": "residualRisk missing"})
    return failures


def evaluate_test_markers(root: Path, contract: dict):
    text = (root / "candidate" / "workspace" / "tests" / "test_protocolmesh.py").read_text(encoding="utf-8", errors="replace")
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
    failures.extend(evaluate_clean_room_public_import(root))
    failures.extend(evaluate_source_ledger(root, contract))
    failures.extend(evaluate_migration_state(root, contract))
    failures.extend(evaluate_sdk_compat_ledger(root, contract))
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
    contract = load_json(root / "oracle" / "multipackage-protocol-contract.json")
    shape_errors: list[str] = []
    check_shape(root, contract, shape_errors)
    if shape_errors:
        failures = [{"id": "bundle-shape", "detail": error} for error in shape_errors]
        write_metrics(args.metrics_out, 0.0, failures)
        for failure in failures:
            print(f"ERROR: {failure['detail']}", file=sys.stderr)
        return 1
    if args.bundle_shape_only:
        print("N93 verifier PASS (bundle shape)")
        return 0

    failures = evaluate_bundle(root, contract, args.changed_paths)
    if args.expect_start_state:
        expected = {
            "legacy-api-static",
            "result-models",
            "public-exports",
            "legacy-api-removed",
            "registry-router-contract",
            "clean-room-public-import",
            "source-ledger-complete",
            "migration-interfaceMap",
            "sdk-compat-ledger-complete",
            "reentry-state-complete",
            "review-response-complete",
            "closure-complete",
            "visible-test-markers",
        }
        observed = {failure["id"] for failure in failures}
        missing = sorted(expected - observed)
        if missing:
            print(f"ERROR: start state no longer exposes expected failures: {missing}", file=sys.stderr)
            for failure in failures:
                print(f"Observed failure: {failure['id']} :: {failure.get('detail', '')}", file=sys.stderr)
            return 1
        print("N93 verifier PASS (expected start-state failures present)")
        return 0

    score = 100.0 if not failures else max(0.0, 100.0 - 5.0 * len({failure["id"] for failure in failures}))
    write_metrics(args.metrics_out, score, failures)
    if failures:
        for failure in failures:
            print(f"Failed invariant: {failure['id']} :: {failure.get('detail', '')}", file=sys.stderr)
        return 1
    print("N93 verifier PASS (100.0 / 100)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
