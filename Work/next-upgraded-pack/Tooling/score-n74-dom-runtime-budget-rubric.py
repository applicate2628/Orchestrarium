#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


SCENARIO_ROOT = Path("Scenarios-v2/N74-dom-runtime-output-budget-scorecard")
VERIFIER = SCENARIO_ROOT / "verifiers" / "check_dom_runtime_output_budget.py"
ROW_MODELS = {
    "X1": "gpt-5.5",
    "X2": "gpt-5.3-codex-spark",
    "X3": "opus 4.7max",
    "X4": "Claude China",
    "X5": "gemini3.1pro",
    "X6": "gemini3.1flash-lite-preview",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Score N74 DOM runtime output budget run roots.")
    parser.add_argument("run_roots", nargs="+")
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def locate_summary(root: Path):
    for path in [root / "meta" / "summary.json", root / "summary.json"]:
        if path.exists():
            return path
    return None


def infer_row_from_path(path: str):
    normalized = path.replace("\\", "/")
    for row in ROW_MODELS:
        if f"-{row}-" in normalized or f"/{row}-" in normalized:
            return row
    return "unknown"


def worker_output_bytes(summary: dict) -> int | None:
    path = summary.get("workerOutputPath")
    if not path:
        return None
    worker_output = Path(path)
    if not worker_output.exists():
        return None
    return worker_output.stat().st_size


def elapsed_seconds(summary: dict) -> float | None:
    explicit = summary.get("elapsedSeconds")
    if isinstance(explicit, (int, float)):
        return float(explicit)
    prompt_path = summary.get("promptPath")
    output_path = summary.get("workerOutputPath")
    if not prompt_path or not output_path:
        return None
    prompt = Path(prompt_path)
    output = Path(output_path)
    if not prompt.exists() or not output.exists():
        return None
    elapsed = output.stat().st_mtime - prompt.stat().st_mtime
    return round(elapsed, 3) if elapsed >= 0 else None


def verifier_passed(summary: dict, script_name: str) -> bool:
    for result in summary.get("verificationResults", []):
        if script_name in result.get("command", ""):
            return bool(result.get("passed"))
    return False


def run_metrics(bundle_root: Path, meta_root: Path):
    metrics_path = meta_root / "n74-score-metrics.json"
    cmd = [sys.executable, str(VERIFIER), "--bundle-root", str(bundle_root), "--metrics-out", str(metrics_path)]
    completed = subprocess.run(cmd, cwd=Path.cwd(), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    metrics = load_json(metrics_path) if metrics_path.exists() else {}
    metrics["score_verifier_exit"] = completed.returncode
    metrics["score_verifier_output"] = completed.stdout
    return metrics


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
            "rubric": 0,
            "failure_ids": ["summary-missing"],
        }

    summary = load_json(summary_path)
    bundle_root = Path(summary["runRoot"])
    meta_root = Path(summary["metaRoot"])
    metrics = run_metrics(bundle_root, meta_root)
    failure_ids = list(metrics.get("failure_ids", []))
    output_bytes = worker_output_bytes(summary)
    wall_seconds = elapsed_seconds(summary)
    auxiliary_paths = summary.get("auxiliaryChangedPaths", [])

    runtime_fail = any(item.startswith(("runtime", "tests-visible")) or item == "import" for item in failure_ids)
    keyboard_fail = any(item in failure_ids for item in ["runtime-keyboard-dirty", "runtime-dirty-status", "runtime-save-enabled", "runtime-save-clears-dirty", "runtime-save-disabled", "runtime-save-status"])
    patch_fail = any(item.startswith(("scope", "ledger", "static")) for item in failure_ids)

    operator_budget_pass = verifier_passed(summary, "check_operator_budget.py")
    if summary.get("wrapperExitCode") == 0 and not operator_budget_pass:
        failure_ids.append("operator-budget-fail")

    runtime = 40 if not runtime_fail else 0
    keyboard_state = 20 if not keyboard_fail else 0
    if patch_fail or not verifier_passed(summary, "check_dom_runtime_output_budget.py"):
        patch_quality = 0
    elif auxiliary_paths:
        patch_quality = 10
        failure_ids.append("patch-auxiliary-churn")
    else:
        patch_quality = 20

    budget = 20 if operator_budget_pass else 0

    scoreability = "scoreable" if summary.get("wrapperExitCode") == 0 else "runtime-wrapper"
    binary = "PASS" if summary.get("verificationPassed") else "FAIL"
    if scoreability != "scoreable":
        binary = "NOT-RUN"
        runtime = 0
        keyboard_state = 0
        patch_quality = 0
        budget = 0

    return {
        "run_root": root_arg,
        "row": summary.get("rowId"),
        "model": summary.get("modelLabel"),
        "binary": binary,
        "scoreability": scoreability,
        "wrapper_exit_code": summary.get("wrapperExitCode"),
        "verification_passed": bool(summary.get("verificationPassed")),
        "rubric": runtime + keyboard_state + patch_quality + budget,
        "runtime": runtime,
        "keyboard_state": keyboard_state,
        "patch_quality": patch_quality,
        "operator_budget": budget,
        "elapsed_seconds": wall_seconds,
        "output_bytes": output_bytes,
        "changed_paths": summary.get("benchmarkChangedPaths", summary.get("changedPaths", [])),
        "auxiliary_changed_paths": auxiliary_paths,
        "failure_ids": failure_ids,
    }


def print_table(results: list[dict]):
    headers = ["Row", "Binary", "Rubric", "Runtime", "Keys", "Patch", "Budget", "Wall s", "Bytes", "Failures"]
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join(["---"] * len(headers)) + "|")
    for item in results:
        row = [
            item.get("row"),
            item.get("binary"),
            item.get("rubric"),
            item.get("runtime"),
            item.get("keyboard_state"),
            item.get("patch_quality"),
            item.get("operator_budget"),
            item.get("elapsed_seconds"),
            item.get("output_bytes"),
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
