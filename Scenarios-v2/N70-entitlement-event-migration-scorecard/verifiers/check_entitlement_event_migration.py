#!/usr/bin/env python3

from __future__ import annotations

import argparse
import fnmatch
import importlib
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any


SCENARIO_ID = "N70"
CONTRACT_ID = "N70-W48-entitlement-event-migration"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify N70 entitlement event migration bundle.")
    parser.add_argument("--bundle-root", type=Path, default=Path.cwd())
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    parser.add_argument("--metrics-out", type=Path)
    parser.add_argument("--changed-path", action="append", default=[])
    return parser.parse_args()


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def normalize_rel(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def parse_simple_yaml(path: Path) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in read_text(path).splitlines():
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith("  - "):
            if current_key is None:
                raise AssertionError(f"list item without key in {path}: {line}")
            result.setdefault(current_key, []).append(line[4:].strip())
            continue
        if ":" not in line:
            raise AssertionError(f"cannot parse scenario yaml line: {line}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        current_key = key
        result[key] = [] if value == "" else value
    return result


def assert_bundle_shape(root: Path, failures: list[tuple[str, str]]) -> dict[str, Any]:
    contract_path = root / "oracle" / "migration-contract.json"
    if not contract_path.exists():
        failures.append(("bundle-contract", "missing oracle/migration-contract.json"))
        return {}
    contract = load_json(contract_path)

    for entry in contract["required_top_level_entries"]:
        if not (root / entry).exists():
            failures.append(("bundle-entry", f"missing top-level entry {entry}"))

    for rel in contract["required_bundle_paths"]:
        if not (root / rel).exists():
            failures.append(("bundle-path", f"missing required path {rel}"))

    scenario = parse_simple_yaml(root / "scenario.yaml")
    for field in contract["scenario_yaml_fields"]:
        if field not in scenario:
            failures.append(("scenario-field", f"missing scenario.yaml field {field}"))

    expected = contract["expected_metadata"]
    for key, expected_value in expected.items():
        if scenario.get(key) != expected_value:
            failures.append(("scenario-metadata", f"{key} mismatch: {scenario.get(key)!r} != {expected_value!r}"))

    return contract


def import_workspace(root: Path):
    src = root / "candidate" / "workspace" / "src"
    sys.path.insert(0, str(src))
    for name in list(sys.modules):
        if name == "entitlemesh" or name.startswith("entitlemesh."):
            del sys.modules[name]
    return importlib.import_module("entitlemesh")


def hidden_events() -> list[dict[str, Any]]:
    return [
        {
            "schema_version": 2,
            "id": "grant-hidden-1",
            "tenant": {"id": "tenant-hidden-a"},
            "principal": {"id": "principal-hidden-a"},
            "resource": {"id": "dashboard"},
            "op": "grant",
            "seq": 10,
            "entitlement": {"plan": "pro"},
        },
        {
            "schema_version": 2,
            "id": "hold-hidden-1",
            "tenant": {"id": "tenant-hidden-a"},
            "principal": {"id": "principal-hidden-a"},
            "resource": {"id": "dashboard"},
            "op": "hold",
            "seq": 20,
            "reason": {"code": "compliance"},
        },
        {
            "schema_version": 2,
            "id": "release-hidden-1",
            "tenant": {"id": "tenant-hidden-a"},
            "principal": {"id": "principal-hidden-a"},
            "resource": {"id": "dashboard"},
            "op": "release",
            "seq": 30,
            "reason": {"code": "compliance"},
        },
        {
            "event_id": "replace-hidden-old",
            "tenant_id": "tenant-hidden-b",
            "principal_id": "principal-hidden-b",
            "resource_id": "export",
            "action": "grant",
            "sequence": 1,
            "plan": "trial",
        },
        {
            "schema_version": 2,
            "id": "replace-hidden-new",
            "tenant": {"id": "tenant-hidden-b"},
            "principal": {"id": "principal-hidden-b"},
            "resource": {"id": "export"},
            "op": "grant",
            "seq": 2,
            "entitlement": {"plan": "enterprise"},
            "replaces": "replace-hidden-old",
        },
        {
            "schema_version": 2,
            "id": "dup-hidden",
            "tenant": {"id": "tenant-hidden-c"},
            "principal": {"id": "principal-hidden-c"},
            "resource": {"id": "billing"},
            "op": "grant",
            "seq": 4,
            "entitlement": {"plan": "starter"},
        },
        {
            "schema_version": 2,
            "id": "dup-hidden",
            "tenant": {"id": "tenant-hidden-c"},
            "principal": {"id": "principal-hidden-c"},
            "resource": {"id": "billing"},
            "op": "revoke",
            "seq": 8,
            "reason": {"code": "account-closed"},
        },
    ]


def state_to_dict(row: Any) -> dict[str, Any]:
    data = asdict(row) if hasattr(row, "__dataclass_fields__") else dict(row)
    data["audit_tags"] = tuple(data.get("audit_tags", ()))
    return data


def expected_states() -> list[dict[str, Any]]:
    return [
        {
            "tenant_id": "tenant-hidden-a",
            "principal_id": "principal-hidden-a",
            "resource_id": "dashboard",
            "allowed": True,
            "plan": "pro",
            "hold_reason": "",
            "audit_tags": ("grant:pro", "hold:compliance", "release:compliance"),
        },
        {
            "tenant_id": "tenant-hidden-b",
            "principal_id": "principal-hidden-b",
            "resource_id": "export",
            "allowed": True,
            "plan": "enterprise",
            "hold_reason": "",
            "audit_tags": ("grant:enterprise",),
        },
        {
            "tenant_id": "tenant-hidden-c",
            "principal_id": "principal-hidden-c",
            "resource_id": "billing",
            "allowed": False,
            "plan": "",
            "hold_reason": "",
            "audit_tags": ("revoke:account-closed",),
        },
    ]


def expected_summary() -> dict[str, Any]:
    return {
        "total": 3,
        "allowed": 2,
        "denied": 1,
        "held": 0,
        "tenants": {
            "tenant-hidden-a": {"allowed": 1, "denied": 0, "held": 0},
            "tenant-hidden-b": {"allowed": 1, "denied": 0, "held": 0},
            "tenant-hidden-c": {"allowed": 0, "denied": 1, "held": 0},
        },
    }


def generated_events(count: int) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for index in range(count):
        tenant = f"tenant-load-{index % 97}"
        principal = f"principal-load-{index % 503}"
        resource = f"resource-{index % 11}"
        events.append(
            {
                "schema_version": 2,
                "id": f"load-{index}",
                "tenant": {"id": tenant},
                "principal": {"id": principal},
                "resource": {"id": resource},
                "op": "grant" if index % 5 else "revoke",
                "seq": index,
                "entitlement": {"plan": "pro"},
                "reason": {"code": "load"},
            }
        )
    return events


def verify_semantics(root: Path, failures: list[tuple[str, str]]) -> float | None:
    try:
        module = import_workspace(root)
    except Exception as exc:
        failures.append(("import", f"cannot import entitlemesh: {exc}"))
        return None

    try:
        rows = module.build_entitlement_snapshot(hidden_events())
        actual = [state_to_dict(row) for row in rows]
        if actual != expected_states():
            failures.append(("correctness-hidden-states", f"hidden states mismatch: {actual}"))

        summary = module.summarize_snapshot(rows)
        if summary != expected_summary():
            failures.append(("correctness-summary", f"summary mismatch: {summary!r}"))

        reversed_rows = module.build_entitlement_snapshot(list(reversed(hidden_events())))
        reversed_actual = [state_to_dict(row) for row in reversed_rows]
        if reversed_actual != expected_states():
            failures.append(("correctness-order-independence", f"order independence failed: {reversed_actual}"))

        batch = generated_events(load_json(root / "oracle" / "migration-contract.json")["generatedEventCount"])
        started = time.perf_counter()
        module.build_entitlement_snapshot(batch)
        runtime = time.perf_counter() - started
        max_seconds = float(load_json(root / "oracle" / "migration-contract.json")["runtimeMaxSeconds"])
        if runtime > max_seconds:
            failures.append(("performance-runtime", f"runtime {runtime:.3f}s exceeds {max_seconds:.3f}s"))
        return runtime
    except Exception as exc:
        failures.append(("correctness-exception", f"exception during hidden checks: {type(exc).__name__}: {exc}"))
        return None


def verify_changed_paths(contract: dict[str, Any], changed: list[str], failures: list[tuple[str, str]]) -> None:
    if not changed:
        return
    normalized = sorted(path.replace("\\", "/").strip("/") for path in changed)
    required = sorted(contract["requiredChangedPaths"])
    if normalized != required:
        failures.append(("scope-changed-paths", f"changed paths {normalized} != required {required}"))

    protected = contract["expected_metadata"]["must_not_touch"]
    for path in normalized:
        for pattern in protected:
            if fnmatch.fnmatch(path, pattern):
                failures.append(("scope-protected-path", f"changed protected path {path} matches {pattern}"))


def verify_static_and_ledger(root: Path, contract: dict[str, Any], failures: list[tuple[str, str]]) -> None:
    code_paths = [
        root / "candidate" / "workspace" / "src" / "entitlemesh" / "parser.py",
        root / "candidate" / "workspace" / "src" / "entitlemesh" / "engine.py",
        root / "candidate" / "workspace" / "src" / "entitlemesh" / "reporting.py",
    ]
    combined = "\n".join(read_text(path) for path in code_paths).lower()

    for term in contract["forbiddenStaticTerms"]:
        if term.lower() in combined:
            failures.append(("static-forbidden-term", f"forbidden static term {term!r} present"))

    required_code_terms = ["schema_version", "principal", "resource", "replaces", "hold", "release"]
    for term in required_code_terms:
        if term not in combined:
            failures.append(("patch-missing-core-fields", f"implementation does not reference {term}"))

    ledger_path = root / "candidate" / "migration-ledger.json"
    try:
        ledger = load_json(ledger_path)
    except Exception as exc:
        failures.append(("ledger-json", f"cannot parse migration-ledger.json: {exc}"))
        return

    if ledger.get("contractId") != CONTRACT_ID:
        failures.append(("ledger-contract", "contractId mismatch"))

    if sorted(ledger.get("changedFiles", [])) != sorted(contract["requiredChangedPaths"]):
        failures.append(("ledger-changed-files", "changedFiles must match required changed paths"))

    ledger_text = json.dumps(ledger, sort_keys=True).lower()
    for term in contract["ledgerRequiredTerms"]:
        if term.lower() not in ledger_text:
            failures.append(("ledger-term", f"missing {term!r}"))


def write_metrics(path: Path | None, failures: list[tuple[str, str]], runtime: float | None, contract: dict[str, Any]) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "failure_ids": [item[0] for item in failures],
        "failures": [{"id": item[0], "detail": item[1]} for item in failures],
        "runtime_seconds": round(runtime, 6) if runtime is not None else None,
        "max_seconds": contract.get("runtimeMaxSeconds"),
        "generated_rows": contract.get("generatedEventCount"),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = args.bundle_root.resolve()
    failures: list[tuple[str, str]] = []
    contract = assert_bundle_shape(root, failures)

    if args.bundle_shape_only:
        if failures:
            for _, detail in failures:
                print(detail)
            return 1
        print("N70 verifier PASS (bundle shape)")
        return 0

    runtime: float | None = None
    if not failures:
        verify_changed_paths(contract, args.changed_path, failures)
        runtime = verify_semantics(root, failures)
        verify_static_and_ledger(root, contract, failures)

    if args.expect_start_state:
        expected = {
            "correctness-exception",
            "patch-missing-core-fields",
            "ledger-changed-files",
            "ledger-term",
        }
        observed = {failure_id for failure_id, _ in failures}
        write_metrics(args.metrics_out, failures, runtime, contract)
        if expected & observed:
            print("N70 verifier PASS (expected start-state failures present)")
            return 0
        print(f"N70 expected start-state failure missing; observed {sorted(observed)}")
        return 1

    write_metrics(args.metrics_out, failures, runtime, contract)
    if failures:
        for failure_id, detail in failures:
            print(f"Failed invariant: {failure_id} :: {detail}")
        return 1

    print("N70 verifier PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
