#!/usr/bin/env python3

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path


PROTECTED_MARKERS = ("/inputs/", "/oracle/", "/verifiers/", "/docs/", "/legacy/")


def parse_args():
    parser = argparse.ArgumentParser(description="Score N51 systems turnaround-budget run roots with a diagnostic rubric.")
    parser.add_argument("run_roots", nargs="+", type=Path)
    parser.add_argument(
        "--scenario-root",
        type=Path,
        default=Path("Scenarios-v2/N51-systems-turnaround-budget-hotfix"),
    )
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def display_path(path: Path):
    try:
        return path.relative_to(Path.cwd()).as_posix()
    except ValueError:
        return str(path)


def infer_row_from_path(run_root: Path):
    match = re.search(r"-(X\d)-", str(run_root))
    return match.group(1) if match else "unknown"


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


def score_time(seconds: float | None):
    if seconds is None:
        return 0
    if seconds <= 240:
        return 5
    if seconds <= 600:
        return 4
    if seconds <= 1200:
        return 2
    return 1


def score_cost(output_bytes: int | None):
    if output_bytes is None:
        return 0
    if output_bytes <= 5000:
        return 5
    if output_bytes <= 25000:
        return 4
    if output_bytes <= 75000:
        return 2
    return 1


def classify_binary(summary: dict, worker_text: str):
    if summary.get("wrapperExitCode") == 0 and summary.get("verificationPassed") is True:
        return "PASS", "scoreable"
    if summary.get("wrapperExitCode") != 0 and (
        "Tool \"run_shell_command\" not found" in worker_text or "AbortError" in worker_text
    ):
        return "ROUTE-FAIL", "runtime-route"
    if summary.get("wrapperExitCode") != 0:
        return "RUNTIME-FAIL", "runtime-wrapper"
    return "FAIL", "scoreable"


def score_one(scenario_root: Path, run_root: Path):
    meta_root = run_root / "meta"
    bundle_root = run_root / "run"
    summary_path = meta_root / "summary.json"
    worker_output = meta_root / "worker-output.txt"
    prompt_path = meta_root / "prompt.txt"

    if not summary_path.exists():
        launched = prompt_path.exists() or worker_output.exists() or bundle_root.exists()
        elapsed = None
        if prompt_path.exists():
            end_time = worker_output.stat().st_mtime if worker_output.exists() else prompt_path.stat().st_mtime
            elapsed = max(0.0, end_time - prompt_path.stat().st_mtime)
        return {
            "run_root": display_path(run_root),
            "row": infer_row_from_path(run_root),
            "binary": "RUNTIME-FAIL" if launched else "NOT-RUN",
            "scoreability": "runtime-no-summary",
            "total": 0,
            "elapsed_proxy_seconds": round(elapsed, 3) if elapsed is not None else None,
            "cost_proxy_output_bytes": worker_output.stat().st_size if worker_output.exists() else None,
            "notes": ["missing summary.json after launch" if launched else "missing summary.json"],
        }

    summary = load_json(summary_path)
    worker_text = worker_output.read_text(encoding="utf-8", errors="replace") if worker_output.exists() else ""
    binary, scoreability = classify_binary(summary, worker_text)
    semantic_pass = any(
        result.get("passed") and "check_stagegate_systems.py" in result.get("command", "")
        for result in summary.get("verificationResults", [])
    )
    operator_budget_pass = any(
        result.get("passed") and "check_operator_budget.py" in result.get("command", "")
        for result in summary.get("verificationResults", [])
    )
    turnaround_budget_pass = any(
        result.get("passed") and "check_turnaround_budget.py" in result.get("command", "")
        for result in summary.get("verificationResults", [])
    )
    correctness = 45 if semantic_pass else 10 if scoreability == "scoreable" else 0

    changed = list(summary.get("benchmarkChangedPaths", []))
    tests_changed = any(path == "candidate/workspace/tests/test_stagegate.py" for path in changed)
    source_changed = [path for path in changed if path.startswith("candidate/workspace/src/stagegate/")]
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
        patch_quality += 6
    if source_changed:
        patch_quality += 6
    if not tests_changed:
        patch_quality += 4
    if not protected_like:
        patch_quality += 4
    if 3 <= len(changed) <= 7:
        patch_quality += 2
    if diff_totals["added"] + diff_totals["deleted"] <= 180:
        patch_quality += 2
    patch_quality = max(0, min(20, patch_quality))

    elapsed = None
    if prompt_path.exists() and summary_path.exists():
        elapsed = max(0.0, summary_path.stat().st_mtime - prompt_path.stat().st_mtime)
    turnaround_elapsed = None
    if prompt_path.exists() and worker_output.exists():
        turnaround_elapsed = max(0.0, worker_output.stat().st_mtime - prompt_path.stat().st_mtime)
    output_bytes = worker_output.stat().st_size if worker_output.exists() else None
    time_points = score_time(elapsed) if scoreability == "scoreable" else 0
    cost_points = score_cost(output_bytes) if scoreability == "scoreable" else 0
    operator_budget = 5 if scoreability == "scoreable" and operator_budget_pass else 0
    turnaround_budget = 10 if scoreability == "scoreable" and turnaround_budget_pass else 0
    test_points = 10 if semantic_pass and not tests_changed else 0
    total = (
        correctness
        + patch_quality
        + test_points
        + operator_budget
        + turnaround_budget
        + time_points
        + cost_points
        if scoreability == "scoreable"
        else 0
    )
    if binary != "PASS" and scoreability == "scoreable":
        total = min(total, 70)

    notes = []
    notes.append("operator budget pass" if operator_budget_pass else "operator budget fail")
    notes.append("turnaround budget pass" if turnaround_budget_pass else "turnaround budget fail")
    notes.append("tests changed" if tests_changed else "tests unchanged")
    if protected_like:
        notes.append(f"protected-like changes: {', '.join(protected_like)}")
    notes.append(f"changed={len(changed)} source={len(source_changed)} add={diff_totals['added']} del={diff_totals['deleted']}")

    return {
        "run_root": display_path(run_root),
        "row": summary.get("rowId", infer_row_from_path(run_root)),
        "model": summary.get("modelLabel"),
        "binary": binary,
        "scoreability": scoreability,
        "wrapper_exit_code": summary.get("wrapperExitCode"),
        "verification_passed": summary.get("verificationPassed"),
        "total": total,
        "correctness": correctness,
        "patch_quality": patch_quality,
        "tests": test_points,
        "operator_budget": operator_budget,
        "turnaround_budget": turnaround_budget,
        "time_points": time_points,
        "cost_points": cost_points,
        "elapsed_proxy_seconds": round(elapsed, 3) if elapsed is not None else None,
        "turnaround_elapsed_seconds": round(turnaround_elapsed, 3) if turnaround_elapsed is not None else None,
        "cost_proxy_output_bytes": output_bytes,
        "changed_paths": changed,
        "diff": diff_totals,
        "notes": notes,
    }


def print_markdown(results):
    print("| Row | Binary | Scoreability | Rubric | Correctness | Patch quality | Tests | Output budget | Turnaround | Time | Cost | Elapsed | Output | Notes |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for result in results:
        print(
            "| {row} | {binary} | {scoreability} | {total} | {correctness} | {patch_quality} | "
            "{tests} | {operator_budget} | {turnaround_budget} | {time_points} | {cost_points} | {elapsed} | {bytes} | {notes} |".format(
                row=result.get("row"),
                binary=result.get("binary"),
                scoreability=result.get("scoreability", ""),
                total=result.get("total", 0),
                correctness=result.get("correctness", 0),
                patch_quality=result.get("patch_quality", 0),
                tests=result.get("tests", 0),
                operator_budget=result.get("operator_budget", 0),
                turnaround_budget=result.get("turnaround_budget", 0),
                time_points=result.get("time_points", 0),
                cost_points=result.get("cost_points", 0),
                elapsed=result.get("turnaround_elapsed_seconds"),
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
