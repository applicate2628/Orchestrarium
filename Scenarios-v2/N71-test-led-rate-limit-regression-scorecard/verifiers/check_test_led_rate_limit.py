#!/usr/bin/env python3

from __future__ import annotations

import os
import argparse
import copy
import fnmatch
import importlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True  # keep the tracked bundle tree free of __pycache__ when run in-place
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _mutation_gate  # noqa: E402  bundle-local scorer module beside this verifier


CONTRACT_ID = "N71-W49-test-led-rate-limit-regression"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify N71 test-led rate limit repair.")
    parser.add_argument("--bundle-root", type=Path, default=Path.cwd())
    parser.add_argument("--bundle-shape-only", action="store_true")
    parser.add_argument("--expect-start-state", action="store_true")
    parser.add_argument("--metrics-out", type=Path)
    parser.add_argument("--changed-path", action="append", default=[])
    parser.add_argument("--mutation-selftest", action="store_true",
                        help="run the four-probe mutation-gate regression (reference PASS, vacuous/decoy FAIL)")
    return parser.parse_args()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> Any:
    return json.loads(read_text(path))


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
    contract_path = root / "oracle" / "test-led-contract.json"
    if not contract_path.exists():
        failures.append(("bundle-contract", "missing oracle/test-led-contract.json"))
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
        if name == "flowlimit" or name.startswith("flowlimit."):
            del sys.modules[name]
    return importlib.import_module("flowlimit")


def verify_behavior(root: Path, failures: list[tuple[str, str]]) -> None:
    try:
        module = import_workspace(root)
        limiter = module.FixedWindowLimiter(limit=2, window_seconds=60.0)
        req_a1 = module.RateLimitRequest("tenant-hidden-a", "user-hidden-a", "/export", 10.0)
        req_b1 = module.RateLimitRequest("tenant-hidden-a", "user-hidden-b", "/export", 12.0)
        original = copy.deepcopy(req_a1)

        if not limiter.check(req_a1).allowed:
            failures.append(("correctness-first-user", "first user first request should be allowed"))
        if not limiter.check(req_a1).allowed:
            failures.append(("correctness-first-user", "first user second request should be allowed"))
        denied = limiter.check(req_a1)
        if denied.allowed:
            failures.append(("correctness-limit", "third request for same user should be denied"))
        if abs(denied.retry_after - 50.0) > 1e-9:
            failures.append(("correctness-retry-after", f"retry_after {denied.retry_after!r} != 50.0"))
        if not limiter.check(req_b1).allowed:
            failures.append(("correctness-user-isolation", "second user in same tenant/route should have independent budget"))
        if not limiter.check(module.RateLimitRequest("tenant-hidden-a", "user-hidden-a", "/export", 60.0)).allowed:
            failures.append(("correctness-boundary", "request at exact next-window boundary should be allowed"))
        if req_a1 != original:
            failures.append(("correctness-mutation", "RateLimitRequest was mutated"))
    except Exception as exc:
        failures.append(("correctness-exception", f"{type(exc).__name__}: {exc}"))


def run_visible_tests(root: Path, failures: list[tuple[str, str]]) -> None:
    exec_root = Path(os.environ["BENCH_EXEC_ROOT"]).resolve() if os.environ.get("BENCH_EXEC_ROOT") else root
    workspace = exec_root / "candidate" / "workspace"
    env_code = "import os,sys,subprocess; os.environ['PYTHONPATH']='src'; raise SystemExit(subprocess.call([sys.executable,'-m','unittest','discover','-s','tests'], cwd=r'%s', env=os.environ.copy()))" % str(workspace)
    completed = subprocess.run([sys.executable, "-c", env_code], text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if completed.returncode != 0:
        failures.append(("tests-visible", completed.stdout.strip()))


def verify_changed_paths(contract: dict[str, Any], changed: list[str], failures: list[tuple[str, str]]) -> None:
    if not changed:
        return
    normalized = sorted(path.replace("\\", "/").strip("/") for path in changed)
    required = sorted(contract["requiredChangedPaths"])
    if normalized != required:
        failures.append(("scope-changed-paths", f"changed paths {normalized} != required {required}"))
    for path in normalized:
        for pattern in contract["expected_metadata"]["must_not_touch"]:
            if fnmatch.fnmatch(path, pattern):
                failures.append(("scope-protected-path", f"changed protected path {path} matches {pattern}"))


def verify_static_test_and_ledger(root: Path, contract: dict[str, Any], failures: list[tuple[str, str]]) -> None:
    limiter_text = read_text(root / "candidate" / "workspace" / "src" / "flowlimit" / "limiter.py").lower()
    test_text = read_text(root / "candidate" / "workspace" / "tests" / "test_window_regression.py")
    test_lower = test_text.lower()

    for term in contract["forbiddenStaticTerms"]:
        if term.lower() in limiter_text:
            failures.append(("static-forbidden-term", f"forbidden static term {term!r} present in limiter"))

    for term in contract["testRequiredTerms"]:
        if term.lower() not in test_lower:
            failures.append(("test-required-term", f"regression test missing {term!r}"))

    if test_lower.count("assert") < 3 and "self.assert" not in test_text:
        failures.append(("test-assertions", "regression test lacks enough assertions"))

    try:
        ledger = load_json(root / "candidate" / "test-ledger.json")
    except Exception as exc:
        failures.append(("ledger-json", f"cannot parse test-ledger.json: {exc}"))
        return

    if ledger.get("contractId") != CONTRACT_ID:
        failures.append(("ledger-contract", "contractId mismatch"))
    if sorted(ledger.get("changedFiles", [])) != sorted(contract["requiredChangedPaths"]):
        failures.append(("ledger-changed-files", "changedFiles must match required changed paths"))

    ledger_text = json.dumps(ledger, sort_keys=True).lower()
    for term in contract["ledgerRequiredTerms"]:
        if term.lower() not in ledger_text:
            failures.append(("ledger-term", f"missing {term!r}"))


def write_metrics(path: Path | None, failures: list[tuple[str, str]], gate_report: dict | None = None) -> None:
    if not path:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "verdict": "PASS" if not failures else "FAIL",
        "failure_ids": [item[0] for item in failures],
        "failures": [{"id": item[0], "detail": item[1]} for item in failures],
    }
    if gate_report is not None:
        payload["mutation_gate"] = {
            "status": gate_report["status"],
            "reason": gate_report["reason"],
            "failures": [fid for fid, _ in gate_report["failures"]],
            "variants": gate_report["variants"],
        }
        payload["gate_not_satisfiable"] = gate_report["status"] == "not-satisfiable"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = args.bundle_root.resolve()
    failures: list[tuple[str, str]] = []
    contract = assert_bundle_shape(root, failures)

    if args.mutation_selftest:
        ok, results = _mutation_gate.mutation_selftest(root)
        print(json.dumps({"mutation_selftest": "PASS" if ok else "FAIL", "probes": results}, indent=2))
        return 0 if ok else 1

    if args.bundle_shape_only:
        if failures:
            for _, detail in failures:
                print(detail)
            return 1
        print("N71 verifier PASS (bundle shape)")
        return 0

    gate_report = None
    if not failures:
        verify_changed_paths(contract, args.changed_path, failures)
        run_visible_tests(root, failures)
        verify_behavior(root, failures)
        verify_static_test_and_ledger(root, contract, failures)
        if not args.expect_start_state:
            exec_root = Path(os.environ["BENCH_EXEC_ROOT"]).resolve() if os.environ.get("BENCH_EXEC_ROOT") else root
            gate_report = _mutation_gate.run_mutation_gate(root, _mutation_gate.candidate_test_path(root, exec_root))
            failures.extend(gate_report["failures"])

    if args.expect_start_state:
        observed = {failure_id for failure_id, _ in failures}
        expected = {"correctness-user-isolation", "correctness-retry-after", "test-required-term", "ledger-changed-files", "ledger-term"}
        write_metrics(args.metrics_out, failures)
        if expected & observed:
            print("N71 verifier PASS (expected start-state failures present)")
            return 0
        print(f"N71 expected start-state failure missing; observed {sorted(observed)}")
        return 1

    write_metrics(args.metrics_out, failures, gate_report)
    if gate_report is not None and gate_report["status"] == "not-satisfiable":
        print(f"N71 mutation-gate NOT-SATISFIABLE (abstain, not a fail-certification): {gate_report['reason']}")
    if failures:
        for failure_id, detail in failures:
            print(f"Failed invariant: {failure_id} :: {detail}")
        return 1
    print("N71 verifier PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
