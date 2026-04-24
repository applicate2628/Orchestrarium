#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


SCENARIO_ROOT = Path("Scenarios-v2/N59-realrepo-perf-cache-budget")
VERIFIER = SCENARIO_ROOT / "verifiers" / "check_performance_cache.py"
ROW_MODELS = {
    "X1": "gpt-5.5",
    "X2": "gpt-5.3-codex-spark",
    "X3": "opus 4.7max",
    "X4": "Claude China",
    "X5": "gemini3.1pro",
    "X6": "gemini3.1flash-lite-preview",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Score N59 real-repo performance-cache run roots.")
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
    for row in ROW_MODELS:
        if f"-{row}-" in normalized or f"/{row}-" in normalized:
            return row
    return "unknown"


def verifier_passed(summary: dict, script_name: str) -> bool:
    for result in summary.get("verificationResults", []):
        if script_name in result.get("command", ""):
            return bool(result.get("passed"))
    return False


def worker_output_bytes(summary: dict) -> int | None:
    path = summary.get("workerOutputPath")
    if not path:
        return None
    worker_output = Path(path)
    if not worker_output.exists():
        return None
    return worker_output.stat().st_size


def run_perf_metrics(bundle_root: Path, meta_root: Path):
    metrics_path = meta_root / "n59-score-metrics.json"
    cmd = [sys.executable, str(VERIFIER), "--bundle-root", str(bundle_root), "--metrics-out", str(metrics_path)]
    completed = subprocess.run(cmd, cwd=Path.cwd(), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    metrics = {}
    if metrics_path.exists():
        metrics = load_json(metrics_path)
    metrics["score_verifier_exit"] = completed.returncode
    metrics["score_verifier_output"] = completed.stdout
    return metrics


def buckets_from_failures(failure_ids: list[str], scope_pass: bool):
    buckets = []
    if any(item.startswith("correctness") or item.startswith("import") for item in failure_ids):
        buckets.append("correctness")
    if any(item.startswith("performance") for item in failure_ids):
        buckets.append("runtime")
    if any(item.startswith("state") or item.startswith("ledger") or item.startswith("closure") or item.startswith("tests") for item in failure_ids):
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
            "correctness": 0,
            "runtime": 0,
            "patch_quality": 0,
            "evidence": 0,
            "cost": 0,
            "runtime_seconds": None,
            "max_seconds": None,
            "output_bytes": None,
            "changed_paths": [],
            "failure_buckets": [],
            "failure_ids": [],
            "notes": ["summary.json missing"],
        }

    summary = load_json(summary_path)
    bundle_root = Path(summary["runRoot"])
    meta_root = Path(summary["metaRoot"])
    metrics = run_perf_metrics(bundle_root, meta_root)
    failure_ids = list(metrics.get("failure_ids", []))
    scope_pass = verifier_passed(summary, "check_scope.py")
    perf_pass = verifier_passed(summary, "check_performance_cache.py")
    output_bytes = worker_output_bytes(summary)
    changed_paths = list(summary.get("benchmarkChangedPaths", summary.get("changedPaths", [])))

    correctness = 0 if any(item.startswith("correctness") or item.startswith("import") for item in failure_ids) else 40
    runtime = 25 if perf_pass and not any(item.startswith("performance") for item in failure_ids) else 0
    patch_quality = 15 if scope_pass else 0
    evidence_failures = [item for item in failure_ids if item.startswith(("state", "ledger", "closure", "tests"))]
    evidence = max(0, 10 - 3 * len(evidence_failures))
    if output_bytes is None:
        cost = 0
    elif output_bytes <= 40000 and len(changed_paths) <= 6:
        cost = 10
    elif output_bytes <= 120000 and len(changed_paths) <= 8:
        cost = 5
    else:
        cost = 0

    scoreability = "scoreable" if summary.get("wrapperExitCode") == 0 else "runtime-wrapper"
    binary = "PASS" if summary.get("verificationPassed") else "FAIL"
    if scoreability != "scoreable":
        binary = "NOT-RUN"

    buckets = buckets_from_failures(failure_ids, scope_pass)
    notes = []
    if metrics.get("runtime_seconds") is not None:
        comparator = "<=" if metrics.get("max_seconds") is not None and metrics["runtime_seconds"] <= metrics["max_seconds"] else ">"
        notes.append(f"runtime={metrics['runtime_seconds']}s {comparator} {metrics.get('max_seconds')}s")
    if not perf_pass:
        notes.append("performance verifier failed")
    if not scope_pass:
        notes.append("scope verifier failed")
    if output_bytes is not None:
        notes.append(f"output_bytes={output_bytes}")

    return {
        "run_root": root_arg,
        "row": summary.get("rowId"),
        "model": summary.get("modelLabel"),
        "binary": binary,
        "scoreability": scoreability,
        "wrapper_exit_code": summary.get("wrapperExitCode"),
        "verification_passed": bool(summary.get("verificationPassed")),
        "rubric": correctness + runtime + patch_quality + evidence + cost,
        "correctness": correctness,
        "runtime": runtime,
        "patch_quality": patch_quality,
        "evidence": evidence,
        "cost": cost,
        "runtime_seconds": metrics.get("runtime_seconds"),
        "max_seconds": metrics.get("max_seconds"),
        "output_bytes": output_bytes,
        "changed_paths": changed_paths,
        "failure_buckets": buckets,
        "failure_ids": failure_ids,
        "notes": notes,
    }


def print_table(results: list[dict]):
    headers = [
        "Row",
        "Binary",
        "Scoreability",
        "Rubric",
        "Correct",
        "Runtime",
        "Patch",
        "Evidence",
        "Cost",
        "Runtime s",
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
            item.get("correctness"),
            item.get("runtime"),
            item.get("patch_quality"),
            item.get("evidence"),
            item.get("cost"),
            item.get("runtime_seconds"),
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
        args.json_out.write_text(json.dumps({"results": results}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
