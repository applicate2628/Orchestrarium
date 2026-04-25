#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import fnmatch
import importlib
import json
import subprocess
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any


CONTRACT_ID = "N72-W50-caller-spanning-api-refactor"
EXPECTED_V2_QUOTE = {
    "account_id": "acct-hidden-a",
    "region": "eu",
    "sku": "pro",
    "quantity": 2,
    "unit_cents": 2500,
    "currency": "EUR",
    "total_cents": 5000,
    "source": "api-v2",
}
EXPECTED_LEGACY_QUOTE = {
    "account_id": "cust-hidden-legacy",
    "region": "us",
    "sku": "basic",
    "quantity": 3,
    "unit_cents": 1000,
    "currency": "USD",
    "total_cents": 3000,
    "source": "api-legacy",
}
EXPECTED_REPORT_ROW = {
    "customer_id": "acct-hidden-a",
    "account_id": "acct-hidden-a",
    "region": "eu",
    "sku": "pro",
    "quantity": 2,
    "currency": "EUR",
    "total_cents": 5000,
    "source": "api-v2",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify N72 caller-spanning API refactor.")
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
    contract_path = root / "oracle" / "caller-contract.json"
    if not contract_path.exists():
        failures.append(("bundle-contract", "missing oracle/caller-contract.json"))
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
        if name == "billinglink" or name.startswith("billinglink."):
            del sys.modules[name]
    return importlib.import_module("billinglink")


def quote_to_dict(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    return dict(value)


def verify_api_callers(module: Any, failures: list[tuple[str, str]]) -> None:
    v2_payload = {"account": {"id": "acct-hidden-a", "region": "eu"}, "sku": "pro", "quantity": 2}
    original_payload = copy.deepcopy(v2_payload)
    try:
        quote = module.quote_invoice(v2_payload)
        if quote != EXPECTED_V2_QUOTE:
            failures.append(("behavior-api-v2", f"v2 API quote {quote!r} != {EXPECTED_V2_QUOTE!r}"))
    except Exception as exc:
        failures.append(("behavior-api-v2", f"{type(exc).__name__}: {exc}"))
    if v2_payload != original_payload:
        failures.append(("behavior-payload-immutability", "schema-v2 payload was mutated"))

    legacy_payload = {"customer_id": "cust-hidden-legacy", "sku": "basic", "quantity": 3}
    try:
        quote = module.quote_invoice(legacy_payload)
        if quote != EXPECTED_LEGACY_QUOTE:
            failures.append(("behavior-api-legacy", f"legacy quote {quote!r} != {EXPECTED_LEGACY_QUOTE!r}"))
    except Exception as exc:
        failures.append(("behavior-api-legacy", f"{type(exc).__name__}: {exc}"))


def verify_service_caller(module: Any, failures: list[tuple[str, str]]) -> None:
    try:
        account = module.AccountRef("acct-hidden-a", "eu")
        quote = quote_to_dict(module.quote_account(account, "pro", 2))
        if quote != EXPECTED_V2_QUOTE:
            failures.append(("behavior-service-v2", f"service quote {quote!r} != {EXPECTED_V2_QUOTE!r}"))
    except Exception as exc:
        failures.append(("behavior-service-v2", f"{type(exc).__name__}: {exc}"))


def verify_cli_caller(module: Any, failures: list[tuple[str, str]]) -> None:
    try:
        raw = module.render_quote(["--account-id", "acct-hidden-a", "--region", "eu", "--sku", "pro", "--quantity", "2"])
        quote = json.loads(raw)
        if quote != EXPECTED_V2_QUOTE:
            failures.append(("behavior-cli-v2", f"CLI quote {quote!r} != {EXPECTED_V2_QUOTE!r}"))
    except SystemExit as exc:
        failures.append(("behavior-cli-v2", f"SystemExit: {exc}"))
    except Exception as exc:
        failures.append(("behavior-cli-v2", f"{type(exc).__name__}: {exc}"))


def verify_report_caller(module: Any, failures: list[tuple[str, str]]) -> None:
    try:
        row = module.build_quote_row(EXPECTED_V2_QUOTE)
        if row != EXPECTED_REPORT_ROW:
            failures.append(("behavior-report-v2", f"report row {row!r} != {EXPECTED_REPORT_ROW!r}"))
    except Exception as exc:
        failures.append(("behavior-report-v2", f"{type(exc).__name__}: {exc}"))


def run_visible_tests(root: Path, failures: list[tuple[str, str]]) -> None:
    workspace = root / "candidate" / "workspace"
    env_code = (
        "import os,sys,subprocess; "
        "os.environ['PYTHONPATH']='src'; "
        "raise SystemExit(subprocess.call([sys.executable,'-m','unittest','discover','-s','tests'], "
        f"cwd=r'{workspace}', env=os.environ.copy()))"
    )
    completed = subprocess.run([sys.executable, "-c", env_code], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if completed.returncode != 0:
        failures.append(("tests-visible", completed.stdout.strip()))


def verify_behavior(root: Path, failures: list[tuple[str, str]]) -> None:
    try:
        module = import_workspace(root)
    except Exception as exc:
        failures.append(("import", f"cannot import billinglink: {exc}"))
        return

    verify_api_callers(module, failures)
    verify_service_caller(module, failures)
    verify_cli_caller(module, failures)
    verify_report_caller(module, failures)


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
        root / "candidate" / "workspace" / "src" / "billinglink" / "service.py",
        root / "candidate" / "workspace" / "src" / "billinglink" / "api.py",
        root / "candidate" / "workspace" / "src" / "billinglink" / "cli.py",
        root / "candidate" / "workspace" / "src" / "billinglink" / "reports.py",
    ]
    source_text = "\n".join(read_text(path) for path in source_paths).lower()
    for term in contract["forbiddenStaticTerms"]:
        if term.lower() in source_text:
            failures.append(("static-forbidden-term", f"forbidden static term {term!r} present in source"))

    try:
        ledger = load_json(root / "candidate" / "refactor-ledger.json")
    except Exception as exc:
        failures.append(("ledger-json", f"cannot parse refactor-ledger.json: {exc}"))
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
        print("N72 verifier PASS (bundle shape)")
        return 0

    if not failures:
        verify_changed_paths(contract, args.changed_path, failures)
        run_visible_tests(root, failures)
        verify_behavior(root, failures)
        verify_static_and_ledger(root, contract, failures)

    if args.expect_start_state:
        observed = {failure_id for failure_id, _ in failures}
        expected = {
            "behavior-api-v2",
            "behavior-service-v2",
            "behavior-cli-v2",
            "behavior-report-v2",
            "ledger-changed-files",
            "ledger-term",
        }
        write_metrics(args.metrics_out, failures)
        if expected & observed:
            print("N72 verifier PASS (expected start-state failures present)")
            return 0
        print(f"N72 expected start-state failure missing; observed {sorted(observed)}")
        return 1

    write_metrics(args.metrics_out, failures)
    if failures:
        for failure_id, detail in failures:
            print(f"Failed invariant: {failure_id} :: {detail}")
        return 1
    print("N72 verifier PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
