#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


SCENARIO_ROOT = Path("Scenarios-v2/N77-security-capability-runtime-scorecard")
VERIFIER = SCENARIO_ROOT / "verifiers" / "check_security_capability_runtime.py"
ROW_MODELS = {
    "X1": "gpt-5.5",
    "X2": "gpt-5.3-codex-spark",
    "X3": "opus 4.7max",
    "X4": "Claude China",
    "X5": "gemini3.1pro",
    "X6": "gemini3.1flash-lite-preview",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Score N77 security capability runtime run roots.")
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


def worker_output_text(summary: dict) -> str:
    path = summary.get("workerOutputPath")
    if not path:
        return ""
    output = Path(path)
    if not output.exists():
        return ""
    return output.read_text(encoding="utf-8", errors="replace")


def worker_output_bytes(summary: dict) -> int | None:
    path = summary.get("workerOutputPath")
    if not path:
        return None
    output = Path(path)
    if not output.exists():
        return None
    return output.stat().st_size


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
    return bool(summary.get("verificationPassed"))


def run_metrics(bundle_root: Path, meta_root: Path, changed: list[str]):
    metrics_path = meta_root / "n77-score-metrics.json"
    args = []
    for path in changed:
        args.extend(["--changed-path", path])
    cmd = [sys.executable, str(VERIFIER), "--bundle-root", str(bundle_root), "--metrics-out", str(metrics_path), *args]
    completed = subprocess.run(cmd, cwd=Path.cwd(), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    metrics = load_json(metrics_path) if metrics_path.exists() else {}
    metrics["score_verifier_exit"] = completed.returncode
    metrics["score_verifier_output"] = completed.stdout
    return metrics


def classify(summary: dict, worker_text: str):
    if summary.get("wrapperExitCode") == 0 and summary.get("verificationPassed") is True:
        return "PASS", "scoreable"
    if summary.get("wrapperExitCode") != 0 and (
        "resource_exhausted" in worker_text.lower()
        or "quota" in worker_text.lower()
        or "usage limit" in worker_text.lower()
        or "aborterror" in worker_text.lower()
    ):
        return "ROUTE-FAIL", "runtime-route"
    if summary.get("wrapperExitCode") != 0:
        return "RUNTIME-FAIL", "runtime-wrapper"
    return "FAIL", "scoreable"


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
    worker_text = worker_output_text(summary)
    binary, scoreability = classify(summary, worker_text)
    changed = summary.get("benchmarkChangedPaths", summary.get("changedPaths", []))
    metrics = run_metrics(Path(summary["runRoot"]), Path(summary["metaRoot"]), changed)
    failure_ids = list(metrics.get("failure_ids", []))
    output_bytes = worker_output_bytes(summary)
    wall_seconds = elapsed_seconds(summary)
    auxiliary_paths = summary.get("auxiliaryChangedPaths", [])

    exploit_fail = any(item.startswith(("runtime-", "import", "tests-visible")) for item in failure_ids)
    test_fail = any(item.startswith("test-") for item in failure_ids)
    artifact_fail = any(item.startswith(("scope", "ledger", "static")) for item in failure_ids)

    runtime_security = 55 if not exploit_fail else 0
    regression_test = 15 if not test_fail else 0
    artifact_quality = 15
    if artifact_fail or not verifier_passed(summary, "check_security_capability_runtime.py"):
        artifact_quality = 0
    elif auxiliary_paths:
        artifact_quality = 8
        failure_ids.append("patch-auxiliary-churn")

    if output_bytes is None:
        cost = 0
    elif output_bytes <= 70000 and (wall_seconds or 999999) <= 600:
        cost = 15
    elif output_bytes <= 180000 and (wall_seconds or 999999) <= 1200:
        cost = 8
    else:
        cost = 0

    if scoreability != "scoreable":
        runtime_security = regression_test = artifact_quality = cost = 0
    rubric = runtime_security + regression_test + artifact_quality + cost
    if binary != "PASS" and scoreability == "scoreable":
        rubric = min(rubric, 78)

    return {
        "run_root": root_arg,
        "row": summary.get("rowId", infer_row_from_path(root_arg)),
        "model": summary.get("modelLabel"),
        "binary": binary,
        "scoreability": scoreability,
        "wrapper_exit_code": summary.get("wrapperExitCode"),
        "verification_passed": bool(summary.get("verificationPassed")),
        "rubric": rubric,
        "runtime_security": runtime_security,
        "regression_test": regression_test,
        "artifact_quality": artifact_quality,
        "cost": cost,
        "elapsed_seconds": wall_seconds,
        "output_bytes": output_bytes,
        "changed_paths": changed,
        "auxiliary_changed_paths": auxiliary_paths,
        "failure_ids": failure_ids,
        "notes": metrics.get("failures", []),
    }


def print_table(results: list[dict]):
    headers = ["Row", "Binary", "Rubric", "Runtime", "Test", "Artifact", "Cost", "Wall s", "Bytes", "Failures"]
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join(["---"] * len(headers)) + "|")
    for item in results:
        row = [
            item.get("row"),
            item.get("binary"),
            item.get("rubric"),
            item.get("runtime_security"),
            item.get("regression_test"),
            item.get("artifact_quality"),
            item.get("cost"),
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
