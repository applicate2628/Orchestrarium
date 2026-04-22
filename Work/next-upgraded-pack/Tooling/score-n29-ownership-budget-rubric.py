#!/usr/bin/env python3

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path


PROTECTED_MARKERS = ("/docs/", "/legacy/", "/ui/", "/inputs/", "/oracle/", "/verifiers/")
TOTAL_RUNTIME_INVARIANTS = 12
TOTAL_LEDGER_INVARIANTS = 5
REQUIRED_BUDGET_PATHS = {
    "candidate/workspace/src/deploygrid/executor.py",
    "candidate/workspace/src/deploygrid/report.py",
    "candidate/workspace/tests/test_deploygrid.py",
    "candidate/repair-ledger.json",
}
STATEFUL_INVARIANTS = {
    "semantic-dedupe-latest-wins",
    "idempotent-repeat",
    "crash-resume-no-replay",
    "rollback-current-attempt-only",
    "report-from-ledger-audit",
}
LEDGER_INVARIANTS = {
    "repair-ledger-schema",
    "source-decisions-ledger",
    "review-response-ledger",
    "validation-ledger",
    "patch-budget-ledger",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Score N29 ownership-budget incident repair run roots.")
    parser.add_argument("run_roots", nargs="+", type=Path)
    parser.add_argument(
        "--scenario-root",
        type=Path,
        default=Path("Scenarios-v2/N29-ownership-budget-incident-repair-gauntlet"),
    )
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def infer_row_from_path(run_root: Path):
    match = re.search(r"-(X\d)-", str(run_root))
    return match.group(1) if match else "unknown"


def classify_binary(summary: dict, worker_text: str):
    if summary.get("wrapperExitCode") == 0 and summary.get("verificationPassed") is True:
        return "PASS", "scoreable"
    if summary.get("wrapperExitCode") != 0 and (
        "Tool \"run_shell_command\" not found" in worker_text or "AbortError" in worker_text
    ):
        return "ROUTE-FAIL", "runtime-route"
    if summary.get("wrapperExitCode") != 0 and "quota" in worker_text.lower():
        return "REQUEUE", "runtime-quota"
    if summary.get("wrapperExitCode") != 0:
        return "RUNTIME-FAIL", "runtime-wrapper"
    return "FAIL", "scoreable"


def count_diff_lines(original: Path, candidate: Path):
    if not original.exists() or not candidate.exists():
        return {"added": 0, "deleted": 0}
    before = original.read_text(encoding="utf-8", errors="replace").splitlines()
    after = candidate.read_text(encoding="utf-8", errors="replace").splitlines()
    added = 0
    deleted = 0
    for line in difflib.unified_diff(before, after, lineterm=""):
        if line.startswith("+++") or line.startswith("---"):
            continue
        if line.startswith("+"):
            added += 1
        elif line.startswith("-"):
            deleted += 1
    return {"added": added, "deleted": deleted}


def failed_invariants(summary: dict):
    failed = set()
    for result in summary.get("verificationResults", []):
        log_path = result.get("log")
        if result.get("passed") or not log_path:
            continue
        path = Path(log_path)
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r'"id":\s*"([^"]+)"', text):
            failed.add(match.group(1))
    return failed


def score_time(seconds: float | None):
    if seconds is None:
        return 0
    if seconds <= 900:
        return 5
    if seconds <= 1500:
        return 4
    if seconds <= 2400:
        return 2
    return 1


def score_cost(output_bytes: int | None):
    if output_bytes is None:
        return 0
    if output_bytes <= 25000:
        return 5
    if output_bytes <= 60000:
        return 4
    if output_bytes <= 120000:
        return 2
    return 1


def score_one(scenario_root: Path, run_root: Path):
    meta_root = run_root / "meta"
    bundle_root = run_root / "run"
    summary_path = meta_root / "summary.json"
    worker_output = meta_root / "worker-output.txt"
    prompt_path = meta_root / "prompt.txt"

    if not summary_path.exists():
        launched = prompt_path.exists() or worker_output.exists() or bundle_root.exists()
        return {
            "run_root": str(run_root),
            "row": infer_row_from_path(run_root),
            "binary": "RUNTIME-FAIL" if launched else "NOT-RUN",
            "scoreability": "runtime-no-summary",
            "total": 0,
            "notes": ["missing summary.json after launch" if launched else "missing summary.json"],
        }

    summary = load_json(summary_path)
    worker_text = worker_output.read_text(encoding="utf-8", errors="replace") if worker_output.exists() else ""
    binary, scoreability = classify_binary(summary, worker_text)
    failed = failed_invariants(summary)

    if binary == "PASS":
        correctness = 35
    elif scoreability == "scoreable":
        runtime_failed = {item for item in failed if item not in LEDGER_INVARIANTS}
        correctness = round(max(0, TOTAL_RUNTIME_INVARIANTS - len(runtime_failed)) / TOTAL_RUNTIME_INVARIANTS * 35)
    else:
        correctness = 0

    stateful_passed = len(STATEFUL_INVARIANTS - failed)
    stateful_recovery = round(stateful_passed / len(STATEFUL_INVARIANTS) * 10) if scoreability == "scoreable" else 0

    ledger_failed = {
        item
        for item in failed
        if item in {
            *LEDGER_INVARIANTS,
        }
    }
    repair_ledger = (
        round((TOTAL_LEDGER_INVARIANTS - len(ledger_failed)) / TOTAL_LEDGER_INVARIANTS * 20)
        if scoreability == "scoreable"
        else 0
    )

    changed = list(summary.get("benchmarkChangedPaths", []))
    source_changed = [path for path in changed if path.startswith("candidate/workspace/src/deploygrid/")]
    tests_changed = any(path == "candidate/workspace/tests/test_deploygrid.py" for path in changed)
    ledger_changed = any(path == "candidate/repair-ledger.json" for path in changed)
    protected_like = [path for path in changed if any(marker in f"/{path}" for marker in PROTECTED_MARKERS)]
    scope_pass = any(
        result.get("passed") and "check_scope.py" in result.get("command", "")
        for result in summary.get("verificationResults", [])
    )

    diff_totals = {"added": 0, "deleted": 0}
    for rel_path in changed:
        diff = count_diff_lines(scenario_root / rel_path, bundle_root / rel_path)
        diff_totals["added"] += diff["added"]
        diff_totals["deleted"] += diff["deleted"]

    patch_quality = 0
    if scope_pass:
        patch_quality += 3
    if source_changed:
        patch_quality += 3
    if ledger_changed:
        patch_quality += 2
    if not protected_like:
        patch_quality += 2
    if 3 <= len(changed) <= 6:
        patch_quality += 2
    if diff_totals["added"] + diff_totals["deleted"] <= 420:
        patch_quality += 1
    patch_quality = max(0, min(10, patch_quality)) if scoreability == "scoreable" else 0

    budget_exact = set(changed) == REQUIRED_BUDGET_PATHS
    patch_budget = 10 if scoreability == "scoreable" and budget_exact else 0
    tests_points = 5 if tests_changed else 2 if binary == "PASS" else 0

    elapsed = None
    if prompt_path.exists() and summary_path.exists():
        elapsed = max(0.0, summary_path.stat().st_mtime - prompt_path.stat().st_mtime)
    output_bytes = worker_output.stat().st_size if worker_output.exists() else None
    time_points = score_time(elapsed) if scoreability == "scoreable" else 0
    cost_points = score_cost(output_bytes) if scoreability == "scoreable" else 0

    total = correctness + stateful_recovery + repair_ledger + patch_quality + patch_budget + tests_points + time_points + cost_points
    if binary != "PASS" and scoreability == "scoreable":
        total = min(total, 70)
    if scoreability != "scoreable":
        total = 0

    notes = []
    notes.append("tests changed" if tests_changed else "tests unchanged")
    notes.append("ledger changed" if ledger_changed else "ledger unchanged")
    notes.append("budget exact" if budget_exact else "budget mismatch")
    if protected_like:
        notes.append(f"protected-like changes: {', '.join(protected_like)}")
    if failed:
        notes.append(f"failed invariants: {', '.join(sorted(failed))}")
    notes.append(f"changed={len(changed)} source={len(source_changed)} add={diff_totals['added']} del={diff_totals['deleted']}")

    return {
        "run_root": str(run_root),
        "row": summary.get("rowId", infer_row_from_path(run_root)),
        "model": summary.get("modelLabel"),
        "binary": binary,
        "scoreability": scoreability,
        "wrapper_exit_code": summary.get("wrapperExitCode"),
        "verification_passed": summary.get("verificationPassed"),
        "total": total,
        "correctness": correctness,
        "stateful_recovery": stateful_recovery,
        "repair_ledger": repair_ledger,
        "patch_quality": patch_quality,
        "patch_budget": patch_budget,
        "tests_points": tests_points,
        "time_points": time_points,
        "cost_points": cost_points,
        "elapsed_proxy_seconds": round(elapsed, 3) if elapsed is not None else None,
        "cost_proxy_output_bytes": output_bytes,
        "changed_paths": changed,
        "diff": diff_totals,
        "failed_invariants": sorted(failed),
        "notes": notes,
    }


def print_markdown(results):
    print("| Row | Binary | Scoreability | Rubric | Correct | Stateful | Ledger | Patch | Budget | Tests | Time | Cost | Elapsed | Output | Notes |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for result in results:
        print(
            "| {row} | {binary} | {scoreability} | {total} | {correctness} | {stateful_recovery} | "
            "{repair_ledger} | {patch_quality} | {patch_budget} | {tests_points} | {time_points} | {cost_points} | {elapsed} | {bytes} | {notes} |".format(
                row=result.get("row"),
                binary=result.get("binary"),
                scoreability=result.get("scoreability", ""),
                total=result.get("total", 0),
                correctness=result.get("correctness", 0),
                stateful_recovery=result.get("stateful_recovery", 0),
                repair_ledger=result.get("repair_ledger", 0),
                patch_quality=result.get("patch_quality", 0),
                patch_budget=result.get("patch_budget", 0),
                tests_points=result.get("tests_points", 0),
                time_points=result.get("time_points", 0),
                cost_points=result.get("cost_points", 0),
                elapsed=result.get("elapsed_proxy_seconds"),
                bytes=result.get("cost_proxy_output_bytes"),
                notes="; ".join(result.get("notes", [])),
            )
        )


def main():
    args = parse_args()
    scenario_root = args.scenario_root.resolve()
    results = [score_one(scenario_root, path.resolve()) for path in args.run_roots]
    print_markdown(results)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps({"results": results}, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
