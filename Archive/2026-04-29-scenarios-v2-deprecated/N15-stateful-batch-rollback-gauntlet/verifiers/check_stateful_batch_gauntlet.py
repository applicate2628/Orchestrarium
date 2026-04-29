#!/usr/bin/env python3

from __future__ import annotations

import argparse
import copy
import importlib
import json
import subprocess
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check the N15 stateful batch gauntlet.")
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


def import_api(root: Path):
    src_root = root / "candidate" / "workspace" / "src"
    sys.path.insert(0, str(src_root))
    for name in list(sys.modules):
        if name == "batchflow" or name.startswith("batchflow."):
            del sys.modules[name]
    return importlib.import_module("batchflow")


def event_steps(store, event_type: str, batch_id: str | None = None):
    events = [event for event in store.events if event.get("type") == event_type]
    if batch_id is not None:
        events = [event for event in events if event.get("batch_id") == batch_id]
    return [event.get("step_id") for event in events]


def assert_equal(actual, expected, label: str):
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def plan(*steps):
    return [dict(step) for step in steps]


def evaluate_invariants(root: Path):
    api = import_api(root)
    failures = []

    def case(case_id, fn):
        try:
            fn(api)
        except Exception as exc:  # noqa: BLE001 - verifier must report candidate behavior
            failures.append({"id": case_id, "detail": str(exc)})

    def input_plan_not_mutated(api):
        store = api.MemoryStore()
        batch_plan = plan(
            {"id": "z-first", "op": "append", "key": "audit", "value": "first"},
            {"id": "a-second", "op": "append", "key": "audit", "value": "second"},
        )
        original = copy.deepcopy(batch_plan)
        api.execute_batch(store, "B-plan", batch_plan)
        assert_equal(batch_plan, original, "caller plan mutation")

    def causal_plan_order_preserved(api):
        store = api.MemoryStore()
        api.execute_batch(
            store,
            "B-order",
            plan(
                {"id": "z-first", "op": "append", "key": "audit", "value": "first"},
                {"id": "a-second", "op": "append", "key": "audit", "value": "second"},
            ),
        )
        assert_equal(store.state.get("audit"), ["first", "second"], "causal step order")

    def completed_batch_idempotent(api):
        store = api.MemoryStore()
        batch_plan = plan({"id": "s1", "op": "inc", "key": "balance", "amount": 5})
        api.execute_batch(store, "B-idem", batch_plan)
        second = api.execute_batch(store, "B-idem", copy.deepcopy(batch_plan))
        assert_equal(second["status"], "already-complete", "second status")
        assert_equal(store.state.get("balance"), 5, "idempotent state")
        assert_equal(event_steps(store, "committed", "B-idem"), ["s1"], "idempotent commits")

    def per_batch_checkpoint_isolation(api):
        store = api.MemoryStore()
        api.execute_batch(
            store,
            "B-one",
            plan(
                {"id": "s1", "op": "set", "key": "one", "value": 1},
                {"id": "s2", "op": "set", "key": "one-done", "value": True},
            ),
        )
        result = api.execute_batch(
            store,
            "B-two",
            plan(
                {"id": "s1", "op": "set", "key": "two", "value": 2},
                {"id": "s2", "op": "set", "key": "two-done", "value": True},
            ),
        )
        assert_equal(result["status"], "completed", "second batch status")
        assert_equal(store.state.get("two"), 2, "second batch state")
        assert_equal(store.checkpoints.get("B-two"), 2, "second batch checkpoint")

    def resume_after_crash(api):
        store = api.MemoryStore()
        batch_plan = plan(
            {"id": "s1", "op": "inc", "key": "n", "amount": 1},
            {"id": "s2", "op": "inc", "key": "n", "amount": 2},
            {"id": "s3", "op": "inc", "key": "n", "amount": 3},
        )
        first = api.execute_batch(store, "B-crash", copy.deepcopy(batch_plan), crash_after="s2")
        second = api.execute_batch(store, "B-crash", copy.deepcopy(batch_plan))
        assert_equal(first["status"], "crashed", "first status")
        assert_equal(second["status"], "completed", "second status")
        assert_equal(store.state.get("n"), 6, "resume state")
        assert_equal(event_steps(store, "committed", "B-crash"), ["s1", "s2", "s3"], "resume commits")

    def rollback_current_attempt_only(api):
        store = api.MemoryStore()
        batch_plan = plan(
            {"id": "s1", "op": "inc", "key": "balance", "amount": 10},
            {"id": "s2", "op": "inc", "key": "balance", "amount": 5, "retryable": True},
        )
        api.execute_batch(store, "B-rollback", copy.deepcopy(batch_plan), crash_after="s1")
        failed = api.execute_batch(store, "B-rollback", copy.deepcopy(batch_plan), fail_after="s2")
        assert_equal(failed["status"], "failed", "failed status")
        assert_equal(store.state.get("balance"), 10, "rollback scope state")
        assert_equal(store.checkpoints.get("B-rollback"), 1, "rollback checkpoint")
        assert_equal(event_steps(store, "rolled-back", "B-rollback"), ["s2"], "rolled-back steps")

    def retry_queue_causal_order(api):
        store = api.MemoryStore()
        api.execute_batch(
            store,
            "B-retry-z",
            plan({"id": "z-retry", "op": "inc", "key": "r", "amount": 1, "retryable": True}),
            fail_before="z-retry",
        )
        result = api.execute_batch(
            store,
            "B-retry-a",
            plan({"id": "a-retry", "op": "inc", "key": "r", "amount": 1, "retryable": True}),
            fail_before="a-retry",
        )
        assert_equal(result["retry_queue"], ["B-retry-z:z-retry", "B-retry-a:a-retry"], "retry causal order")

    def journal_sequence_global(api):
        store = api.MemoryStore()
        api.execute_batch(store, "B-seq-1", plan({"id": "s1", "op": "set", "key": "a", "value": 1}))
        api.execute_batch(store, "B-seq-2", plan({"id": "s1", "op": "set", "key": "b", "value": 2}))
        seqs = [event["seq"] for event in store.events]
        assert_equal(seqs, list(range(1, len(seqs) + 1)), "global journal sequence")

    def report_derived_from_journal(api):
        store = api.MemoryStore()
        api.execute_batch(store, "B-report", plan({"id": "s1", "op": "set", "key": "x", "value": 1}))
        store.state.clear()
        store.checkpoints.clear()
        summary = api.summarize_store(store)
        assert_equal(summary["committed"], 1, "summary committed")
        assert_equal(summary["batches"], ["B-report"], "summary batches")

    case("input-plan-not-mutated", input_plan_not_mutated)
    case("causal-plan-order-preserved", causal_plan_order_preserved)
    case("completed-batch-idempotent", completed_batch_idempotent)
    case("per-batch-checkpoint-isolation", per_batch_checkpoint_isolation)
    case("resume-after-crash", resume_after_crash)
    case("rollback-current-attempt-only", rollback_current_attempt_only)
    case("retry-queue-causal-order", retry_queue_causal_order)
    case("journal-sequence-global", journal_sequence_global)
    case("report-derived-from-journal", report_derived_from_journal)
    return failures


def run_direct_tests(root: Path, errors: list[str]):
    workspace = root / "candidate" / "workspace"
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests"],
        cwd=workspace,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part).strip()
        errors.append(f"Direct tests failed: {output or 'no output'}")


def check_no_oracle_hardcoding(root: Path, contract: dict, errors: list[str]):
    paths = contract["expected_metadata"]["allowed_change_surface"]
    terms = [term.lower() for term in contract["prohibited_candidate_terms"]]
    for rel_path in paths:
        text = (root / rel_path).read_text(encoding="utf-8").lower()
        for term in terms:
            if term in text:
                errors.append(f"Candidate file {rel_path} contains prohibited oracle/case literal: {term}")


def main():
    args = parse_args()
    root = args.bundle_root.resolve()
    errors: list[str] = []

    if not root.exists():
        print(f"Bundle root does not exist: {root}", file=sys.stderr)
        return 1

    contract = load_json(root / "oracle" / "stateful-contract.json")
    check_shape(root, contract, errors)

    if not args.bundle_shape_only:
        failures = evaluate_invariants(root)
        failure_ids = sorted(failure["id"] for failure in failures)
        if args.expect_start_state:
            expected = sorted(contract["expected_start_state_failures"])
            require(failure_ids == expected, f"Expected start-state failures {expected}, found {failure_ids}", errors)
        else:
            run_direct_tests(root, errors)
            check_no_oracle_hardcoding(root, contract, errors)
            if failures:
                rendered = json.dumps(failures, indent=2, sort_keys=True)
                errors.append(f"Completed candidate still fails stateful invariants: {rendered}")

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    if args.bundle_shape_only:
        mode = "bundle shape"
    elif args.expect_start_state:
        mode = "start state"
    else:
        mode = "completed run"
    print(f"N15 verifier PASS ({mode})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
