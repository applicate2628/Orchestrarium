#!/usr/bin/env python3

from __future__ import annotations

import argparse
import difflib
import json
import re
from pathlib import Path


PROTECTED_MARKERS = ("/inputs/", "/oracle/", "/verifiers/", "/legacy-preview/", "/drafts/", "/reference-assets/")


def parse_args():
    parser = argparse.ArgumentParser(description="Score N21 visual raster run roots with a diagnostic rubric.")
    parser.add_argument("run_roots", nargs="+", type=Path)
    parser.add_argument(
        "--scenario-root",
        type=Path,
        default=Path("Scenarios-v2/N21-visual-provider-fit-raster-gauntlet"),
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
    if output_bytes <= 4000:
        return 15
    if output_bytes <= 12000:
        return 12
    if output_bytes <= 40000:
        return 8
    return 4


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
            "elapsed_proxy_seconds": round(max(0.0, (worker_output.stat().st_mtime if worker_output.exists() else prompt_path.stat().st_mtime) - prompt_path.stat().st_mtime), 3) if prompt_path.exists() else None,
            "output_bytes": worker_output.stat().st_size if worker_output.exists() else None,
            "notes": ["missing summary.json after launch" if launched else "missing summary.json"],
        }

    summary = load_json(summary_path)
    worker_text = worker_output.read_text(encoding="utf-8", errors="replace") if worker_output.exists() else ""
    binary, scoreability = classify_binary(summary, worker_text)
    binary_pass = binary == "PASS"
    visual_correctness = 45 if binary_pass else 10 if scoreability == "scoreable" else 0

    changed = list(summary.get("benchmarkChangedPaths", []))
    protected_like = [path for path in changed if any(marker in f"/{path}" for marker in PROTECTED_MARKERS)]
    source_changed = any(path == "candidate/visual-owned/src/visual_panel/renderer.py" for path in changed)
    tests_changed = any(path == "candidate/visual-owned/tests/test_renderer.py" for path in changed)
    scope_pass = any(result.get("passed") and "check_scope.py" in result.get("command", "") for result in summary.get("verificationResults", []))

    diff_totals = {"added": 0, "deleted": 0}
    for rel_path in changed:
        diff = count_diff_lines(scenario_root / rel_path, bundle_root / rel_path)
        diff_totals["added"] += diff["added"]
        diff_totals["deleted"] += diff["deleted"]

    patch_quality = 0
    if scope_pass:
        patch_quality += 7
    if source_changed:
        patch_quality += 8
    if not protected_like:
        patch_quality += 5
    if 1 <= len(changed) <= 2:
        patch_quality += 3
    if diff_totals["added"] + diff_totals["deleted"] <= 180:
        patch_quality += 2
    patch_quality = min(25, patch_quality)

    test_points = 10 if tests_changed else 6 if binary_pass else 0

    elapsed = None
    if prompt_path.exists() and summary_path.exists():
        elapsed = max(0.0, summary_path.stat().st_mtime - prompt_path.stat().st_mtime)
    output_bytes = worker_output.stat().st_size if worker_output.exists() else None
    runtime = score_time(elapsed) if scoreability == "scoreable" else 0
    cost = score_cost(output_bytes) if scoreability == "scoreable" else 0

    total = visual_correctness + patch_quality + test_points + runtime + cost
    if binary != "PASS" and scoreability == "scoreable":
        total = min(total, 70)
    if scoreability != "scoreable":
        total = 0

    notes = []
    notes.append("tests changed" if tests_changed else "tests unchanged")
    if protected_like:
        notes.append(f"protected-like changes: {', '.join(protected_like)}")
    notes.append(f"changed={len(changed)} add={diff_totals['added']} del={diff_totals['deleted']}")

    return {
        "run_root": str(run_root),
        "row": summary.get("rowId", infer_row_from_path(run_root)),
        "model": summary.get("modelLabel"),
        "binary": binary,
        "scoreability": scoreability,
        "wrapper_exit_code": summary.get("wrapperExitCode"),
        "verification_passed": summary.get("verificationPassed"),
        "total": total,
        "visual_correctness": visual_correctness,
        "patch_quality": patch_quality,
        "tests": test_points,
        "runtime": runtime,
        "cost": cost,
        "elapsed_proxy_seconds": round(elapsed, 3) if elapsed is not None else None,
        "output_bytes": output_bytes,
        "changed_paths": changed,
        "diff": diff_totals,
        "notes": notes,
    }


def print_markdown(results):
    print("| Row | Binary | Scoreability | Rubric | Visual | Patch | Tests | Runtime | Cost | Elapsed | Output | Notes |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for result in results:
        print(
            "| {row} | {binary} | {scoreability} | {total} | {visual} | {patch} | {tests} | "
            "{runtime} | {cost} | {elapsed} | {output} | {notes} |".format(
                row=result.get("row"),
                binary=result.get("binary"),
                scoreability=result.get("scoreability", ""),
                total=result.get("total", 0),
                visual=result.get("visual_correctness", 0),
                patch=result.get("patch_quality", 0),
                tests=result.get("tests", 0),
                runtime=result.get("runtime", 0),
                cost=result.get("cost", 0),
                elapsed=result.get("elapsed_proxy_seconds"),
                output=result.get("output_bytes"),
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
