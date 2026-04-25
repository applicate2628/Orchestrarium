#!/usr/bin/env python3

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
from pathlib import Path
from typing import Any


CONTRACT_ID = "N74-W52-dom-runtime-output-budget"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify N74 DOM runtime output budget repair.")
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
    contract_path = root / "oracle" / "dom-runtime-contract.json"
    if not contract_path.exists():
        failures.append(("bundle-contract", "missing oracle/dom-runtime-contract.json"))
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


def run_visible_check(root: Path, failures: list[tuple[str, str]]) -> None:
    workspace = root / "candidate" / "workspace"
    completed = subprocess.run(
        ["node", "scripts/verify-visible-render.mjs"],
        cwd=workspace,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if completed.returncode != 0:
        failures.append(("tests-visible", completed.stdout.strip()))


def run_runtime_harness(root: Path, metrics_path: Path, failures: list[tuple[str, str]]) -> None:
    harness = root / "verifiers" / "dom-runtime-harness.mjs"
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["node", str(harness), str(root), str(metrics_path)],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if metrics_path.exists():
        metrics = load_json(metrics_path)
        for failure in metrics.get("failures", []):
            failures.append((failure.get("id", "runtime-unknown"), failure.get("detail", "")))
    elif completed.returncode != 0:
        failures.append(("runtime-harness", completed.stdout.strip()))


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
        root / "candidate" / "workspace" / "src" / "state.mjs",
        root / "candidate" / "workspace" / "src" / "view.mjs",
        root / "candidate" / "workspace" / "src" / "app.mjs",
        root / "candidate" / "workspace" / "src" / "styles.css",
    ]
    source_text = "\n".join(read_text(path) for path in source_paths)
    source_lower = source_text.lower()
    for term in contract["forbiddenStaticTerms"]:
        if term.lower() in source_lower:
            failures.append(("static-forbidden-term", f"forbidden static term {term!r} present in source"))

    try:
        ledger = load_json(root / "candidate" / "ui-runtime-ledger.json")
    except Exception as exc:
        failures.append(("ledger-json", f"cannot parse ui-runtime-ledger.json: {exc}"))
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
        print("N74 verifier PASS (bundle shape)")
        return 0

    metrics_base = args.metrics_out.resolve() if args.metrics_out else root / "candidate" / ".n73-metrics.json"
    runtime_metrics = metrics_base.with_suffix(".runtime.json")
    if not failures:
        verify_changed_paths(contract, args.changed_path, failures)
        run_visible_check(root, failures)
        run_runtime_harness(root, runtime_metrics, failures)
        verify_static_and_ledger(root, contract, failures)

    if args.expect_start_state:
        observed = {failure_id for failure_id, _ in failures}
        expected = {"runtime-filter-summary", "runtime-keyboard-dirty", "runtime-save-clears-dirty", "ledger-changed-files", "ledger-term"}
        write_metrics(args.metrics_out, failures)
        if expected & observed:
            print("N74 verifier PASS (expected start-state failures present)")
            return 0
        print(f"N74 expected start-state failure missing; observed {sorted(observed)}")
        return 1

    write_metrics(args.metrics_out, failures)
    if failures:
        for failure_id, detail in failures:
            print(f"Failed invariant: {failure_id} :: {detail}")
        return 1
    print("N74 verifier PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
