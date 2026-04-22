#!/usr/bin/env python3

from __future__ import annotations

import argparse
import difflib
import json
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Score N16 run roots with a diagnostic rubric.")
    parser.add_argument("run_roots", nargs="+", type=Path, help="Scenario run roots such as .../N16")
    parser.add_argument(
        "--scenario-root",
        type=Path,
        default=Path("Scenarios-v2/N16-release-lane-integration-gauntlet"),
    )
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


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
    if seconds <= 900:
        return 15
    if seconds <= 1500:
        return 12
    if seconds <= 2400:
        return 8
    return 4


def score_cost(output_bytes: int | None):
    if output_bytes is None:
        return 0
    if output_bytes <= 25000:
        return 15
    if output_bytes <= 60000:
        return 12
    if output_bytes <= 120000:
        return 8
    return 4


def score_one(scenario_root: Path, run_root: Path):
    meta_root = run_root / "meta"
    bundle_root = run_root / "run"
    summary_path = meta_root / "summary.json"
    worker_output = meta_root / "worker-output.txt"
    prompt_path = meta_root / "prompt.txt"

    if not summary_path.exists():
        return {
            "run_root": str(run_root),
            "row": "unknown",
            "binary": "NOT-RUN",
            "total": 0,
            "notes": ["missing summary.json"],
        }

    summary = load_json(summary_path)
    row = summary.get("rowId", "unknown")
    binary_pass = summary.get("wrapperExitCode") == 0 and summary.get("verificationPassed") is True
    correctness = 40 if binary_pass else 10 if summary.get("wrapperExitCode") == 0 else 0

    changed = list(summary.get("benchmarkChangedPaths", []))
    tests_changed = any(path.startswith("candidate/workspace/tests/") for path in changed)
    protected_like = [path for path in changed if "/docs/" in path or "/legacy/" in path or "/ui/" in path]
    scope_pass = any(
        result.get("passed") and "check_scope.py" in result.get("command", "")
        for result in summary.get("verificationResults", [])
    )

    diff_totals = {"added": 0, "deleted": 0}
    for rel_path in changed:
        original = scenario_root / rel_path
        candidate = bundle_root / rel_path
        diff = count_diff_lines(original, candidate)
        diff_totals["added"] += diff["added"]
        diff_totals["deleted"] += diff["deleted"]

    patch_quality = 0
    if scope_pass:
        patch_quality += 10
    if not protected_like:
        patch_quality += 5
    if tests_changed:
        patch_quality += 5
    if 6 <= len(changed) <= 13:
        patch_quality += 5
    elif len(changed) < 6:
        patch_quality += 2
    if diff_totals["added"] + diff_totals["deleted"] <= 260:
        patch_quality += 5
    patch_quality = max(0, min(30, patch_quality))

    elapsed = None
    if prompt_path.exists() and summary_path.exists():
        elapsed = max(0.0, summary_path.stat().st_mtime - prompt_path.stat().st_mtime)
    output_bytes = worker_output.stat().st_size if worker_output.exists() else None
    time_points = score_time(elapsed)
    cost_points = score_cost(output_bytes)

    total = correctness + patch_quality + time_points + cost_points
    notes = []
    if tests_changed:
        notes.append("tests changed")
    else:
        notes.append("tests unchanged")
    if protected_like:
        notes.append(f"protected-like changes: {', '.join(protected_like)}")
    notes.append(f"changed={len(changed)} add={diff_totals['added']} del={diff_totals['deleted']}")

    return {
        "run_root": str(run_root),
        "row": row,
        "model": summary.get("modelLabel"),
        "binary": "PASS" if binary_pass else "FAIL",
        "total": total,
        "correctness": correctness,
        "patch_quality": patch_quality,
        "time_points": time_points,
        "cost_points": cost_points,
        "elapsed_proxy_seconds": round(elapsed, 3) if elapsed is not None else None,
        "cost_proxy_output_bytes": output_bytes,
        "changed_paths": changed,
        "diff": diff_totals,
        "notes": notes,
    }


def print_markdown(results):
    print("| Row | Binary | Rubric | Correctness | Patch quality | Time | Cost | Elapsed proxy | Output bytes | Notes |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for result in results:
        print(
            "| {row} | {binary} | {total} | {correctness} | {patch_quality} | {time_points} | "
            "{cost_points} | {elapsed} | {bytes} | {notes} |".format(
                row=result.get("row"),
                binary=result.get("binary"),
                total=result.get("total"),
                correctness=result.get("correctness", 0),
                patch_quality=result.get("patch_quality", 0),
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
        args.json_out.write_text(json.dumps({"results": results}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
