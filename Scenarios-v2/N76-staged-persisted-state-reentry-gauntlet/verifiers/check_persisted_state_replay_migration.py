#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import fnmatch
import importlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


CONTRACT_ID = "N76-W54-staged-persisted-state-reentry"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify N76 staged persisted-state reentry.")
    parser.add_argument("--bundle-root", type=Path, default=Path.cwd())
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    parser.add_argument("--metrics-out", type=Path)
    parser.add_argument("--changed-path", action="append", default=[])
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(read_text(path))


def normalize_path_text(value: str) -> str:
    return value.replace("\\", "/").strip("/")


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
    contract_path = root / "oracle" / "persistence-contract.json"
    if not contract_path.exists():
        failures.append(("bundle-contract", "missing oracle/persistence-contract.json"))
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

    for key, expected in contract["expected_metadata"].items():
        if scenario.get(key) != expected:
            failures.append(("scenario-metadata", f"{key} mismatch: {scenario.get(key)!r} != {expected!r}"))

    return contract


def import_workspace(root: Path):
    src = root / "candidate" / "workspace" / "src"
    sys.path.insert(0, str(src))
    for name in list(sys.modules):
        if name == "statedock" or name.startswith("statedock."):
            del sys.modules[name]
    package = importlib.import_module("statedock")
    events = importlib.import_module("statedock.events")
    migrator = importlib.import_module("statedock.migrator")
    return package, events, migrator


def hidden_events() -> list[dict[str, Any]]:
    return [
        {
            "account_id": "tenant-red-hidden",
            "user_id": "legacy-u1",
            "operation": "credit",
            "sequence": 1,
            "amount": 100,
            "checkpoint_id": "cp-hidden-a",
            "dedupe_key": "red-1",
        },
        {
            "tenant": "tenant-red-hidden",
            "actor": "u2",
            "op": "debit",
            "seq": 2,
            "amount": 30,
            "checkpoint_id": "cp-hidden-b",
            "dedupe_key": "red-2",
            "payload": {"ticket": "T-200"},
        },
        {
            "tenant": "tenant-red-hidden",
            "actor": "u2",
            "op": "debit",
            "seq": 2,
            "amount": 30,
            "checkpoint_id": "cp-hidden-b",
            "dedupe_key": "red-2",
            "payload": {"ticket": "T-200-duplicate"},
        },
        {
            "tenant": "tenant-blue-hidden",
            "actor": "u3",
            "op": "credit",
            "seq": 1,
            "amount": 50,
            "checkpoint_id": "cp-hidden-x",
            "dedupe_key": "blue-1",
        },
        {
            "tenant": "tenant-red-hidden",
            "actor": "u4",
            "op": "set_status",
            "seq": 3,
            "status": "hold",
            "checkpoint_id": "cp-hidden-c",
            "dedupe_key": "red-3",
        },
    ]


def applied_count(snapshot: dict[str, Any]) -> int | None:
    if "applied_count" in snapshot:
        return snapshot["applied_count"]
    applied = snapshot.get("applied")
    if isinstance(applied, list):
        return len(applied)
    return None


def verify_normalization(events_module: Any, migrator_module: Any, failures: list[tuple[str, str]]) -> None:
    legacy = {
        "account_id": "legacy-visible",
        "user_id": "u-legacy",
        "operation": "credit",
        "sequence": 7,
        "amount": 11,
        "checkpoint_id": "cp-legacy",
        "dedupe_key": "legacy-7",
    }
    original = copy.deepcopy(legacy)
    try:
        normalized = events_module.normalize_event(legacy)
    except Exception as exc:
        failures.append(("normalization-v1", f"{type(exc).__name__}: {exc}"))
        return
    if legacy != original:
        failures.append(("normalization-immutability", "normalize_event mutated legacy source event"))
    expected = {
        "tenant": "legacy-visible",
        "actor": "u-legacy",
        "op": "credit",
        "seq": 7,
        "amount": 11,
        "checkpoint_id": "cp-legacy",
        "dedupe_key": "legacy-7",
        "payload": {},
        "source_schema": "v1",
    }
    for key, value in expected.items():
        if normalized.get(key) != value:
            failures.append(("normalization-v1", f"{key} {normalized.get(key)!r} != {value!r}"))

    batch = hidden_events()
    batch_original = copy.deepcopy(batch)
    try:
        migrated = migrator_module.migrate_events(batch)
    except Exception as exc:
        failures.append(("migration-batch", f"{type(exc).__name__}: {exc}"))
        return
    if batch != batch_original:
        failures.append(("migration-immutability", "migrate_events mutated source batch"))
    if len(migrated) != len(batch):
        failures.append(("migration-batch", "migrated event count changed"))


def verify_replay(package: Any, failures: list[tuple[str, str]]) -> tuple[Any, dict[str, Any] | None]:
    events = hidden_events()
    original = copy.deepcopy(events)
    try:
        store = package.StateStore()
        snapshot = store.replay(events)
    except Exception as exc:
        failures.append(("behavior-replay", f"{type(exc).__name__}: {exc}"))
        return None, None

    if events != original:
        failures.append(("behavior-source-immutability", "replay mutated source events"))
    if snapshot.get("schema_version") != 2:
        failures.append(("behavior-schema-version", f"schema_version {snapshot.get('schema_version')!r} != 2"))
    if snapshot.get("balances", {}).get("tenant-red-hidden") != 70:
        failures.append(("behavior-red-balance", f"red balance {snapshot.get('balances')}"))
    if snapshot.get("balances", {}).get("tenant-blue-hidden") != 50:
        failures.append(("behavior-blue-balance", f"blue balance {snapshot.get('balances')}"))
    if snapshot.get("statuses", {}).get("tenant-red-hidden") != "hold":
        failures.append(("behavior-status", f"red status {snapshot.get('statuses')}"))
    if applied_count(snapshot) != 4:
        failures.append(("behavior-dedupe", f"applied_count {applied_count(snapshot)!r} != 4"))

    try:
        second = store.replay(events)
    except Exception as exc:
        failures.append(("behavior-idempotent-replay", f"{type(exc).__name__}: {exc}"))
        return store, snapshot
    if second.get("balances") != snapshot.get("balances") or applied_count(second) != 4:
        failures.append(("behavior-idempotent-replay", "replaying same batch changed final state"))

    return store, snapshot


def verify_rollback(store: Any, failures: list[tuple[str, str]]) -> None:
    if store is None:
        return
    try:
        rolled = store.rollback_to("cp-hidden-b")
        final = store.snapshot()
    except Exception as exc:
        failures.append(("behavior-rollback", f"{type(exc).__name__}: {exc}"))
        return
    if rolled.get("balances", {}).get("tenant-red-hidden") != 70:
        failures.append(("behavior-rollback", f"rollback red balance {rolled.get('balances')}"))
    if "tenant-red-hidden" in rolled.get("statuses", {}):
        failures.append(("behavior-rollback", "rollback snapshot includes post-checkpoint status"))
    if applied_count(rolled) != 2:
        failures.append(("behavior-rollback", f"rollback applied_count {applied_count(rolled)!r} != 2"))
    if final.get("statuses", {}).get("tenant-red-hidden") != "hold":
        failures.append(("behavior-rollback-nondestructive", "rollback destroyed final snapshot state"))


def verify_persistence(package: Any, snapshot: dict[str, Any] | None, failures: list[tuple[str, str]]) -> None:
    if snapshot is None:
        return
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "snapshot.json"
        try:
            package.save_snapshot(path, snapshot)
            raw = load_json(path)
            loaded = package.load_snapshot(path)
        except Exception as exc:
            failures.append(("persist-load", f"{type(exc).__name__}: {exc}"))
            return
    if raw.get("schema_version") != 2 or "snapshot" not in raw:
        failures.append(("persist-envelope", f"bad persisted envelope {raw!r}"))
    if loaded != snapshot:
        failures.append(("persist-load", "load_snapshot did not return the original snapshot object"))


def run_visible_tests(root: Path, failures: list[tuple[str, str]]) -> None:
    exec_root = Path(os.environ["BENCH_EXEC_ROOT"]).resolve() if os.environ.get("BENCH_EXEC_ROOT") else root
    workspace = exec_root / "candidate" / "workspace"
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        cwd=workspace,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.returncode != 0:
        failures.append(("tests-visible", completed.stdout.strip()))


def verify_behavior(root: Path, failures: list[tuple[str, str]]) -> None:
    try:
        package, events_module, migrator_module = import_workspace(root)
    except Exception as exc:
        failures.append(("import", f"cannot import statedock: {exc}"))
        return
    verify_normalization(events_module, migrator_module, failures)
    store, snapshot = verify_replay(package, failures)
    verify_rollback(store, failures)
    verify_persistence(package, snapshot, failures)


def verify_changed_paths(contract: dict[str, Any], changed: list[str], failures: list[tuple[str, str]]) -> None:
    if not changed:
        return
    normalized = sorted(normalize_path_text(path) for path in changed)
    required = sorted(contract["requiredChangedPaths"])
    if normalized != required:
        failures.append(("scope-changed-paths", f"changed paths {normalized} != required {required}"))
    for path in normalized:
        for pattern in contract["expected_metadata"]["must_not_touch"]:
            if fnmatch.fnmatch(path, pattern):
                failures.append(("scope-protected-path", f"changed protected path {path} matches {pattern}"))


def verify_static_and_ledger(root: Path, contract: dict[str, Any], failures: list[tuple[str, str]]) -> None:
    source_paths = [
        root / "candidate" / "workspace" / "src" / "statedock" / "events.py",
        root / "candidate" / "workspace" / "src" / "statedock" / "migrator.py",
        root / "candidate" / "workspace" / "src" / "statedock" / "store.py",
        root / "candidate" / "workspace" / "src" / "statedock" / "api.py",
    ]
    source_text = "\n".join(read_text(path) for path in source_paths).lower()
    for term in contract["forbiddenStaticTerms"]:
        if term.lower() in source_text:
            failures.append(("static-forbidden-term", f"forbidden static term {term!r} present in source"))

    try:
        ledger = load_json(root / "candidate" / "migration-ledger.json")
    except Exception as exc:
        failures.append(("ledger-json", f"cannot parse migration-ledger.json: {exc}"))
        return

    if ledger.get("contractId") != CONTRACT_ID:
        failures.append(("ledger-contract", "contractId mismatch"))

    changed_files = sorted(normalize_path_text(path) for path in ledger.get("changedFiles", []))
    if changed_files != sorted(contract["requiredChangedPaths"]):
        failures.append(("ledger-changed-files", "changedFiles must match required changed paths"))

    ledger_text = json.dumps(ledger, sort_keys=True).lower()
    for term in contract["ledgerRequiredTerms"]:
        if term.lower() not in ledger_text:
            failures.append(("ledger-term", f"missing {term!r}"))


def require_json_terms(payload: Any, terms: list[str], failure_id: str, failures: list[tuple[str, str]]) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    for term in terms:
        if term.lower() not in text:
            failures.append((failure_id, f"missing {term!r}"))


def verify_source_ledger(root: Path, contract: dict[str, Any], failures: list[tuple[str, str]]) -> None:
    try:
        ledger = load_json(root / "candidate" / "source-ledger.json")
    except Exception as exc:
        failures.append(("source-ledger-json", f"cannot parse source-ledger.json: {exc}"))
        return
    if ledger.get("contractId") != CONTRACT_ID:
        failures.append(("source-ledger-contract", "contractId mismatch"))
    require_json_terms(ledger, contract["sourceLedgerRequiredTerms"], "source-ledger-term", failures)
    text = json.dumps(ledger, sort_keys=True).lower()
    for source_id in contract["expectedSourceIds"]:
        if source_id.lower() not in text or "accepted" not in text:
            failures.append(("source-ledger-decision", f"accepted source {source_id!r} missing"))
    for source_id in contract["expectedStaleIds"]:
        if source_id.lower() not in text or "rejected" not in text:
            failures.append(("source-ledger-stale", f"rejected stale source {source_id!r} missing"))


def verify_reentry_state(root: Path, contract: dict[str, Any], failures: list[tuple[str, str]]) -> None:
    try:
        state = load_json(root / "candidate" / "reentry-state.json")
    except Exception as exc:
        failures.append(("reentry-json", f"cannot parse reentry-state.json: {exc}"))
        return
    if state.get("contractId") != CONTRACT_ID:
        failures.append(("reentry-contract", "contractId mismatch"))
    require_json_terms(state, contract["reentryRequiredTerms"], "reentry-term", failures)
    text = json.dumps(state, sort_keys=True).lower()
    for phase_id in contract["expectedPhaseIds"]:
        if phase_id.lower() not in text:
            failures.append(("reentry-phase", f"missing phase {phase_id!r}"))


def verify_closeout(root: Path, contract: dict[str, Any], failures: list[tuple[str, str]]) -> None:
    try:
        closeout = load_json(root / "candidate" / "closeout.json")
    except Exception as exc:
        failures.append(("closeout-json", f"cannot parse closeout.json: {exc}"))
        return
    if closeout.get("contractId") != CONTRACT_ID:
        failures.append(("closeout-contract", "contractId mismatch"))
    require_json_terms(closeout, contract["closeoutRequiredTerms"], "closeout-term", failures)
    changed = closeout.get("changedPaths") or closeout.get("changed paths") or []
    if sorted(normalize_path_text(path) for path in changed) != sorted(contract["requiredChangedPaths"]):
        failures.append(("closeout-changed-paths", "closeout changedPaths must match required changed paths"))


def write_metrics(path: Path | None, failures: list[tuple[str, str]]) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "failure_ids": [item[0] for item in failures],
        "failures": [{"id": item[0], "detail": item[1]} for item in failures],
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
        print("N76 verifier PASS (bundle shape)")
        return 0

    if not failures:
        verify_changed_paths(contract, args.changed_path, failures)
        run_visible_tests(root, failures)
        verify_behavior(root, failures)
        verify_source_ledger(root, contract, failures)
        verify_static_and_ledger(root, contract, failures)
        verify_reentry_state(root, contract, failures)
        verify_closeout(root, contract, failures)

    if args.expect_start_state:
        observed = {failure_id for failure_id, _ in failures}
        expected = {
            "normalization-immutability",
            "behavior-schema-version",
            "behavior-dedupe",
            "behavior-rollback",
            "persist-envelope",
            "source-ledger-contract",
            "reentry-contract",
            "closeout-contract",
            "ledger-contract",
            "ledger-changed-files",
            "ledger-term",
        }
        write_metrics(args.metrics_out, failures)
        if expected & observed:
            print("N76 verifier PASS (expected start-state failures present)")
            return 0
        print(f"N76 expected start-state failure missing; observed {sorted(observed)}")
        return 1

    write_metrics(args.metrics_out, failures)
    if failures:
        for failure_id, detail in failures:
            print(f"Failed invariant: {failure_id} :: {detail}")
        return 1
    print("N76 verifier PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
