#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


SCENARIO_ROOT = Path("Scenarios-v2/N60-ui-visual-state-reentry-packet")
VERIFIER = SCENARIO_ROOT / "verifiers" / "check_ui_visual_state.py"
ROW_MODELS = {
    "X1": "gpt-5.5",
    "X2": "gpt-5.3-codex-spark",
    "X3": "opus 4.7max",
    "X4": "Claude China",
    "X5": "gemini3.1pro",
    "X6": "gemini3.1flash-lite-preview",
}

STATE_FAILURES = {
    "command-focus-skip",
    "command-filter-owner",
    "dirty-state-per-record",
    "navigation-guard-target",
    "validation-and-save",
    "focus-return",
}
ACCESSIBILITY_FAILURES = {"render-accessibility"}
LAYOUT_FAILURES = {"layout-responsive-containment", "layout-target-overlap", "css-stability"}
RASTER_FAILURES = {
    "raster-transparent-gap",
    "raster-selected-alert-layer",
    "raster-legend-order",
    "ppm-metadata",
}
LEDGER_FAILURES = {"ledger-complete", "closure-complete"}


def parse_args():
    parser = argparse.ArgumentParser(description="Score N60 UI visual-state reentry run roots.")
    parser.add_argument("run_roots", nargs="+")
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def locate_summary(root: Path):
    candidates = [
        root / "meta" / "summary.json",
        root / "summary.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def infer_row_from_path(path: str):
    normalized = path.replace("\\", "/")
    match = re.search(r"-(X\d)-", normalized)
    return match.group(1) if match else "unknown"


def verifier_passed(summary: dict, script_name: str) -> bool:
    for result in summary.get("verificationResults", []):
        if script_name in result.get("command", ""):
            return bool(result.get("passed"))
    return False


def worker_output(summary: dict) -> tuple[str, int | None]:
    path = summary.get("workerOutputPath")
    if not path:
        return "", None
    worker_output_path = Path(path)
    if not worker_output_path.exists():
        return "", None
    return worker_output_path.read_text(encoding="utf-8", errors="replace"), worker_output_path.stat().st_size


def run_metrics(bundle_root: Path, meta_root: Path):
    metrics_path = meta_root / "n60-score-metrics.json"
    cmd = [sys.executable, str(VERIFIER), "--bundle-root", str(bundle_root), "--metrics-out", str(metrics_path)]
    completed = subprocess.run(cmd, cwd=Path.cwd(), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    metrics = {}
    if metrics_path.exists():
        metrics = load_json(metrics_path)
    metrics["score_verifier_exit"] = completed.returncode
    metrics["score_verifier_output"] = completed.stdout
    return metrics


def proportional(max_points: int, failures: set[str], group: set[str]):
    missed = len(failures & group)
    return int(round(max_points * max(0, len(group) - missed) / len(group)))


def classify_scoreability(summary: dict, worker_text: str):
    lowered = worker_text.lower()
    short_output = len(worker_text.strip()) <= 2000
    route_message = (
        "you've hit your limit" in lowered
        or "you have hit your limit" in lowered
        or "resource_exhausted" in lowered
        or (short_output and ("usage limit" in lowered or "quota" in lowered))
    )
    wrapper_route = summary.get("wrapperExitCode") != 0 and (
        "quota" in lowered
        or "usage limit" in lowered
        or "aborterror" in lowered
        or "tool \"run_shell_command\" not found" in worker_text
    )
    if route_message or wrapper_route:
        return "runtime-route"
    if summary.get("wrapperExitCode") == 0:
        return "scoreable"
    return "runtime-wrapper"


def failure_buckets(failure_ids: set[str], scope_pass: bool):
    buckets = []
    if failure_ids & STATE_FAILURES:
        buckets.append("state")
    if failure_ids & ACCESSIBILITY_FAILURES:
        buckets.append("accessibility")
    if failure_ids & LAYOUT_FAILURES:
        buckets.append("layout")
    if failure_ids & RASTER_FAILURES:
        buckets.append("raster")
    if failure_ids & LEDGER_FAILURES or "direct-tests" in failure_ids or "hardcoding" in failure_ids:
        buckets.append("evidence")
    if not scope_pass:
        buckets.append("scope")
    return buckets


def score_one(root_arg: str):
    root = Path(root_arg)
    summary_path = locate_summary(root)
    if summary_path is None:
        row = infer_row_from_path(root_arg)
        return {
            "run_root": root_arg,
            "row": row,
            "model": ROW_MODELS.get(row, "unknown"),
            "binary": "NOT-RUN",
            "scoreability": "runtime-no-summary",
            "wrapper_exit_code": None,
            "verification_passed": False,
            "rubric": 0,
            "state": 0,
            "raster": 0,
            "accessibility": 0,
            "layout": 0,
            "patch": 0,
            "tests": 0,
            "evidence": 0,
            "time": 0,
            "cost": 0,
            "output_bytes": None,
            "changed_paths": [],
            "failure_buckets": [],
            "failure_ids": [],
            "notes": ["summary.json missing"],
        }

    summary = load_json(summary_path)
    bundle_root = Path(summary["runRoot"])
    meta_root = Path(summary["metaRoot"])
    metrics = run_metrics(bundle_root, meta_root)
    failure_ids = set(metrics.get("failure_ids", []))
    scope_pass = verifier_passed(summary, "check_scope.py")
    visual_pass = verifier_passed(summary, "check_ui_visual_state.py")
    worker_text, output_bytes = worker_output(summary)
    scoreability = classify_scoreability(summary, worker_text)
    changed_paths = list(summary.get("benchmarkChangedPaths", summary.get("changedPaths", [])))

    state = proportional(20, failure_ids, STATE_FAILURES)
    raster = proportional(25, failure_ids, RASTER_FAILURES)
    accessibility = proportional(15, failure_ids, ACCESSIBILITY_FAILURES)
    layout = proportional(10, failure_ids, LAYOUT_FAILURES)
    required = {
        "candidate/workspace/src/console-state.mjs",
        "candidate/workspace/src/console-view.mjs",
        "candidate/workspace/src/console-layout.mjs",
        "candidate/workspace/src/console-raster.mjs",
        "candidate/workspace/src/console.css",
        "candidate/workspace/tests/console-contract.test.mjs",
        "candidate/workspace/implementation-ledger.json",
        "candidate/workspace/closure.json",
    }
    observed = set(changed_paths)
    patch = 10 if scope_pass and observed == required else 5 if scope_pass and required <= observed else 0
    tests = 5 if "candidate/workspace/tests/console-contract.test.mjs" in observed and "direct-tests" not in failure_ids else 0
    evidence = 5 if not (failure_ids & LEDGER_FAILURES) else 0
    time = 5 if summary.get("wrapperExitCode") == 0 else 0
    if output_bytes is None:
        cost = 0
    elif output_bytes <= 80000 and len(changed_paths) <= 8:
        cost = 5
    elif output_bytes <= 220000 and len(changed_paths) <= 10:
        cost = 3
    else:
        cost = 1

    binary = "PASS" if summary.get("verificationPassed") else "FAIL"
    rubric = state + raster + accessibility + layout + patch + tests + evidence + time + cost
    if scoreability != "scoreable":
        binary = "NOT-RUN"
        rubric = 0
    elif binary != "PASS":
        rubric = min(rubric, 78)

    notes = []
    if not visual_pass:
        notes.append("ui visual-state verifier failed")
    if not scope_pass:
        notes.append("scope verifier failed")
    if output_bytes is not None:
        notes.append(f"output_bytes={output_bytes}")

    return {
        "run_root": root_arg,
        "row": summary.get("rowId", infer_row_from_path(root_arg)),
        "model": summary.get("modelLabel"),
        "binary": binary,
        "scoreability": scoreability,
        "wrapper_exit_code": summary.get("wrapperExitCode"),
        "verification_passed": bool(summary.get("verificationPassed")),
        "rubric": rubric,
        "state": state,
        "raster": raster,
        "accessibility": accessibility,
        "layout": layout,
        "patch": patch,
        "tests": tests,
        "evidence": evidence,
        "time": time,
        "cost": cost,
        "output_bytes": output_bytes,
        "changed_paths": changed_paths,
        "failure_buckets": failure_buckets(failure_ids, scope_pass),
        "failure_ids": sorted(failure_ids),
        "notes": notes,
    }


def print_table(results: list[dict]):
    headers = [
        "Row",
        "Binary",
        "Scoreability",
        "Rubric",
        "State",
        "Raster",
        "A11y",
        "Layout",
        "Patch",
        "Tests",
        "Evidence",
        "Time",
        "Cost",
        "Bytes",
        "Buckets",
        "Failures",
    ]
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join(["---"] * len(headers)) + "|")
    for item in results:
        row = [
            item.get("row"),
            item.get("binary"),
            item.get("scoreability"),
            item.get("rubric"),
            item.get("state"),
            item.get("raster"),
            item.get("accessibility"),
            item.get("layout"),
            item.get("patch"),
            item.get("tests"),
            item.get("evidence"),
            item.get("time"),
            item.get("cost"),
            item.get("output_bytes"),
            ", ".join(item.get("failure_buckets", [])),
            ", ".join(item.get("failure_ids", [])),
        ]
        print("| " + " | ".join(str(value) for value in row) + " |")


def main():
    args = parse_args()
    results = [score_one(run_root) for run_root in args.run_roots]
    print_table(results)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps({"scenario": "N60", "surface": "E50", "results": results}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
