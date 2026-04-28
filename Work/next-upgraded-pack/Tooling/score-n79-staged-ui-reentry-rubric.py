#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
SCENARIO_ROOT = REPO_ROOT / "Scenarios-v2" / "N79-staged-ui-visual-state-reentry-v2"
VERIFIER = SCENARIO_ROOT / "verifiers" / "check_ui_visual_state.py"
CONTRACT_PATH = SCENARIO_ROOT / "oracle" / "ui-visual-state-contract.json"
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
    parser = argparse.ArgumentParser(description="Score N79 staged UI visual-state reentry run roots.")
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


def locate_summary(case_root: Path):
    for candidate in [case_root / "meta" / "summary.json", case_root / "summary.json"]:
        if candidate.exists():
            return candidate
    return None


def infer_row_from_path(path: Path):
    match = re.search(r"-(X\d)-", str(path))
    return match.group(1) if match else "unknown"


def read_worker_outputs(summary: dict):
    chunks = []
    if summary.get("staged"):
        for phase in summary.get("phases", []):
            output_path = Path(str(phase.get("workerOutputPath") or ""))
            if output_path.exists():
                chunks.append(output_path.read_text(encoding="utf-8", errors="replace"))
    else:
        output_path = Path(str(summary.get("workerOutputPath") or ""))
        if output_path.exists():
            chunks.append(output_path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def classify_binary(summary: dict, worker_text: str):
    if summary.get("wrapperExitCode") == 0 and summary.get("verificationPassed") is True:
        return "PASS", "scoreable"
    lower = worker_text.lower()
    if summary.get("wrapperExitCode") != 0 and (
        "aborterror" in lower
        or "resource_exhausted" in lower
        or "quota" in lower
        or "usage limit" in lower
        or "ineligibletiererror" in lower
        or "tool \"run_shell_command\" not found" in worker_text
    ):
        return "ROUTE-FAIL", "runtime-route"
    if summary.get("wrapperExitCode") != 0:
        return "RUNTIME-FAIL", "runtime-phase-fail"
    return "FAIL", "scoreable"


def run_metrics(bundle_root: Path, meta_root: Path):
    metrics_path = meta_root / "n79-score-metrics.json"
    cmd = [sys.executable, str(VERIFIER), "--bundle-root", str(bundle_root), "--metrics-out", str(metrics_path)]
    completed = subprocess.run(cmd, cwd=REPO_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    metrics = load_json(metrics_path) or {}
    metrics["score_verifier_exit"] = completed.returncode
    metrics["score_verifier_output"] = completed.stdout
    return metrics


def verifier_passed(summary: dict, script_name: str):
    for result in summary.get("verificationResults", []):
        if script_name in result.get("command", ""):
            return bool(result.get("passed"))
    return False


def proportional(max_points: int, failures: set[str], group: set[str]):
    missed = len(failures & group)
    return int(round(max_points * max(0, len(group) - missed) / len(group)))


def phase_path_score(summary: dict, contract: dict):
    rules = contract.get("phasePathRules", {})
    if not rules:
        return 0, ["phasePathRules missing"]
    notes = []
    score = 0.0
    per_phase = 10 / max(1, len(rules))
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
    if summary.get("staged"):
        phase_outputs = summary.get("phases", [])
        for phase in phase_outputs:
            value = phase.get("outputBytes")
            if isinstance(value, int):
                total += value
            else:
                missing += 1
            elapsed += float(phase.get("elapsedSeconds") or 0)
    else:
        output_path = Path(str(summary.get("workerOutputPath") or ""))
        if output_path.exists():
            total = output_path.stat().st_size
        else:
            missing += 1
        elapsed = float(summary.get("elapsedSeconds") or 0)
    if missing:
        return 0, elapsed, total, [f"{missing} worker outputs missing"]
    if total <= 120000 and elapsed <= 1200:
        return 5, elapsed, total, []
    if total <= 300000 and elapsed <= 2400:
        return 3, elapsed, total, []
    return 1, elapsed, total, []


def failure_buckets(failure_ids: set[str], scope_pass: bool, phase_score: int):
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
    if phase_score < 10:
        buckets.append("phase")
    return buckets


def score_one(case_root: Path, contract: dict):
    case_root = case_root_from_arg(case_root.resolve())
    summary_path = locate_summary(case_root)
    if summary_path is None:
        row = infer_row_from_path(case_root)
        return {
            "run_root": str(case_root),
            "row": row,
            "model": ROW_MODELS.get(row, "unknown"),
            "binary": "NOT-RUN",
            "scoreability": "runtime-no-summary",
            "rubric": 0,
            "failure_ids": ["summary-missing"],
            "failure_buckets": ["runtime"],
        }

    summary = load_json(summary_path) or {}
    worker_text = read_worker_outputs(summary)
    binary, scoreability = classify_binary(summary, worker_text)
    metrics = run_metrics(Path(summary["runRoot"]), Path(summary["metaRoot"]))
    failure_ids = set(metrics.get("failure_ids", []))
    scope_pass = verifier_passed(summary, "check_scope.py")
    visual_pass = verifier_passed(summary, "check_ui_visual_state.py")
    phase, phase_notes = phase_path_score(summary, contract)
    cost, elapsed, output_bytes, output_notes = output_cost(summary)

    state = proportional(20, failure_ids, STATE_FAILURES)
    raster = proportional(20, failure_ids, RASTER_FAILURES)
    accessibility = proportional(15, failure_ids, ACCESSIBILITY_FAILURES)
    layout = proportional(10, failure_ids, LAYOUT_FAILURES)
    patch = 10 if scope_pass and sorted(summary.get("benchmarkChangedPaths", [])) == sorted(contract["requiredChangedPaths"]) else 0
    tests = 5 if "candidate/workspace/tests/console-contract.test.mjs" in summary.get("benchmarkChangedPaths", []) and "direct-tests" not in failure_ids else 0
    evidence = 5 if not (failure_ids & LEDGER_FAILURES) else 0

    if scoreability != "scoreable":
        state = raster = accessibility = layout = patch = tests = evidence = phase = cost = 0
    rubric = state + raster + accessibility + layout + patch + tests + evidence + phase + cost
    if binary != "PASS" and scoreability == "scoreable":
        rubric = min(rubric, 78)

    notes = []
    if not visual_pass:
        notes.append("ui visual-state verifier failed")
    if not scope_pass:
        notes.append("scope verifier failed")
    if phase_notes:
        notes.extend(phase_notes)
    notes.extend(output_notes)
    if output_bytes is not None:
        notes.append(f"output_bytes={output_bytes}")

    return {
        "run_root": str(case_root),
        "row": summary.get("rowId", infer_row_from_path(case_root)),
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
        "phase": phase,
        "cost": cost,
        "elapsed_seconds": round(elapsed, 3),
        "output_bytes": output_bytes,
        "changed_paths": summary.get("benchmarkChangedPaths", []),
        "auxiliary_changed_paths": summary.get("auxiliaryChangedPaths", []),
        "failure_buckets": failure_buckets(failure_ids, scope_pass, phase),
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
        "Phase",
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
            item.get("phase"),
            item.get("cost"),
            item.get("output_bytes"),
            ", ".join(item.get("failure_buckets", [])),
            ", ".join(item.get("failure_ids", [])),
        ]
        print("| " + " | ".join(str(value) for value in row) + " |")


def main():
    args = parse_args()
    contract = load_json(CONTRACT_PATH) or {}
    results = [score_one(run_root, contract) for run_root in args.case_roots]
    print_table(results)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps({"scenario": "N79", "surface": "E69", "results": results}, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
