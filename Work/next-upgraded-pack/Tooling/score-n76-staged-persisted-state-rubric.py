#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIO_ROOT = REPO_ROOT / "Scenarios-v2" / "N76-staged-persisted-state-reentry-gauntlet"
VERIFIER = SCENARIO_ROOT / "verifiers" / "check_persisted_state_replay_migration.py"
CONTRACT_PATH = SCENARIO_ROOT / "oracle" / "persistence-contract.json"
ROW_MODELS = {
    "X1": "gpt-5.5",
    "X2": "gpt-5.3-codex-spark",
    "X3": "opus 4.7max",
    "X4": "Claude China",
    "X5": "gemini3.1pro",
    "X6": "gemini3.1flash-lite-preview",
}


def parse_args():
    parser = argparse.ArgumentParser(description="Score N76 staged persisted-state reentry run roots.")
    parser.add_argument("case_roots", nargs="+", type=Path)
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def case_root_from_arg(path: Path):
    if (path / "meta" / "summary.json").exists():
        return path
    if path.name == "meta" and (path / "summary.json").exists():
        return path.parent
    return path


def infer_row_from_path(path: Path):
    match = re.search(r"-(X\d)-", str(path))
    return match.group(1) if match else "unknown"


def read_phase_outputs(summary: dict):
    chunks = []
    for phase in summary.get("phases", []):
        output_path = Path(str(phase.get("workerOutputPath") or ""))
        if output_path.exists():
            chunks.append(output_path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def classify_binary(summary: dict, worker_text: str):
    if summary.get("wrapperExitCode") == 0 and summary.get("verificationPassed") is True:
        return "PASS", "scoreable"
    if summary.get("wrapperExitCode") != 0 and (
        "AbortError" in worker_text
        or "RESOURCE_EXHAUSTED" in worker_text
        or "quota" in worker_text.lower()
        or "usage limit" in worker_text.lower()
    ):
        return "ROUTE-FAIL", "runtime-route"
    if summary.get("wrapperExitCode") != 0:
        return "RUNTIME-FAIL", "runtime-phase-fail"
    return "FAIL", "scoreable"


def run_metrics(bundle_root: Path, meta_root: Path):
    metrics_path = meta_root / "n76-score-metrics.json"
    changed = []
    summary = load_json(meta_root / "summary.json") or {}
    for path in summary.get("benchmarkChangedPaths", []):
        changed += ["--changed-path", path]
    cmd = [sys.executable, str(VERIFIER), "--bundle-root", str(bundle_root), "--metrics-out", str(metrics_path), *changed]
    completed = subprocess.run(cmd, cwd=REPO_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    metrics = load_json(metrics_path) or {}
    metrics["score_verifier_exit"] = completed.returncode
    metrics["score_verifier_output"] = completed.stdout
    return metrics


def phase_path_score(summary: dict, contract: dict):
    rules = contract["phasePathRules"]
    notes = []
    score = 0.0
    per_phase = 15 / max(1, len(rules))
    for phase in summary.get("phases", []):
        rule = rules.get(phase.get("phaseId"))
        if not rule:
            continue
        changed = set(phase.get("benchmarkChangedPaths", []))
        allowed = set(rule["allowed"])
        required_any = set(rule["requiredAny"])
        if changed and changed <= allowed and changed & required_any:
            score += per_phase
        else:
            notes.append(f"{phase.get('phaseId')} path rule miss: {sorted(changed)}")
    return int(round(score)), notes


def output_cost(summary: dict):
    total = 0
    elapsed = 0.0
    missing = 0
    for phase in summary.get("phases", []):
        value = phase.get("outputBytes")
        if isinstance(value, int):
            total += value
        else:
            missing += 1
        elapsed += float(phase.get("elapsedSeconds") or 0)
    if missing:
        return 0, elapsed, total, [f"{missing} phase outputs missing"]
    if total <= 80000 and elapsed <= 900:
        return 15, elapsed, total, []
    if total <= 220000 and elapsed <= 1800:
        return 8, elapsed, total, []
    return 0, elapsed, total, []


def score_one(case_root: Path, contract: dict):
    case_root = case_root_from_arg(case_root.resolve())
    summary_path = case_root / "meta" / "summary.json"
    if not summary_path.exists():
        row = infer_row_from_path(case_root)
        return {
            "run_root": str(case_root),
            "row": row,
            "model": ROW_MODELS.get(row, "unknown"),
            "binary": "NOT-RUN",
            "scoreability": "runtime-no-summary",
            "rubric": 0,
            "failure_ids": ["summary-missing"],
        }

    summary = load_json(summary_path) or {}
    worker_text = read_phase_outputs(summary)
    binary, scoreability = classify_binary(summary, worker_text)
    metrics = run_metrics(Path(summary["runRoot"]), Path(summary["metaRoot"]))
    failure_ids = list(metrics.get("failure_ids", []))

    semantic_fail = any(
        item.startswith(("import", "tests", "normalization", "migration", "behavior", "persist"))
        for item in failure_ids
    )
    source_fail = any(item.startswith("source-ledger") for item in failure_ids)
    reentry_fail = any(item.startswith(("ledger", "reentry", "closeout")) for item in failure_ids)
    scope_fail = any(item.startswith(("scope", "static")) for item in failure_ids)

    semantic = 45 if not semantic_fail else 0
    governance = 25
    if source_fail:
        governance -= 10
    if reentry_fail:
        governance -= 15
    governance = max(0, governance)
    phase, phase_notes = phase_path_score(summary, contract)
    if scope_fail:
        phase = 0
    cost, elapsed, output_bytes, output_notes = output_cost(summary)

    if scoreability != "scoreable":
        semantic = governance = phase = cost = 0
    rubric = semantic + governance + phase + cost
    if binary != "PASS" and scoreability == "scoreable":
        rubric = min(rubric, 78)

    notes = []
    if failure_ids:
        notes.append("failed invariants: " + ", ".join(sorted(set(failure_ids))))
    notes.extend(phase_notes)
    notes.extend(output_notes)

    return {
        "run_root": str(case_root),
        "row": summary.get("rowId", infer_row_from_path(case_root)),
        "model": summary.get("modelLabel"),
        "binary": binary,
        "scoreability": scoreability,
        "wrapper_exit_code": summary.get("wrapperExitCode"),
        "verification_passed": summary.get("verificationPassed"),
        "rubric": rubric,
        "semantic": semantic,
        "governance": governance,
        "phase": phase,
        "cost": cost,
        "elapsed_seconds": round(elapsed, 3),
        "output_bytes": output_bytes,
        "changed_paths": summary.get("benchmarkChangedPaths", []),
        "auxiliary_changed_paths": summary.get("auxiliaryChangedPaths", []),
        "failure_ids": failure_ids,
        "notes": notes,
    }


def print_table(results: list[dict]):
    headers = ["Row", "Binary", "Rubric", "Semantic", "Governance", "Phase", "Cost", "Wall s", "Bytes", "Failures"]
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join(["---"] * len(headers)) + "|")
    for item in results:
        row = [
            item.get("row"),
            item.get("binary"),
            item.get("rubric"),
            item.get("semantic"),
            item.get("governance"),
            item.get("phase"),
            item.get("cost"),
            item.get("elapsed_seconds"),
            item.get("output_bytes"),
            ", ".join(item.get("failure_ids", [])),
        ]
        print("| " + " | ".join(str(value) for value in row) + " |")


def main():
    args = parse_args()
    contract = load_json(CONTRACT_PATH) or {}
    results = [score_one(root, contract) for root in args.case_roots]
    print_table(results)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps({"results": results}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
