#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = (
    REPO_ROOT
    / "Scenarios-v2"
    / "N38-deterministic-ui-visual-state-integration-gauntlet"
    / "oracle"
    / "ui-visual-state-contract.json"
)

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
    parser = argparse.ArgumentParser(description="Score N38 staged UI/visual/state run roots.")
    parser.add_argument("case_roots", nargs="+", type=Path)
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def case_root_from_arg(path: Path):
    path = Path(path)
    if (path / "meta" / "summary.json").exists():
        return path
    if path.name == "meta" and (path / "summary.json").exists():
        return path.parent
    return path


def infer_row_from_path(run_root: Path):
    match = re.search(r"-(X\d)-", str(run_root))
    return match.group(1) if match else "unknown"


def format_run_root(run_root: Path, display_base: Path):
    try:
        return run_root.relative_to(display_base).as_posix()
    except ValueError:
        return str(run_root)


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
        "Tool \"run_shell_command\" not found" in worker_text
        or "AbortError" in worker_text
        or "RESOURCE_EXHAUSTED" in worker_text
        or "quota" in worker_text.lower()
        or "usage limit" in worker_text.lower()
    ):
        return "ROUTE-FAIL", "runtime-route"
    if summary.get("wrapperExitCode") != 0:
        return "RUNTIME-FAIL", "runtime-phase-fail"
    return "FAIL", "scoreable"


def failed_invariants(summary: dict):
    failed = []
    for result in summary.get("verificationResults", []):
        if result.get("passed"):
            continue
        log = Path(str(result.get("log", "")))
        if not log.exists():
            continue
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            marker = "Failed invariant: "
            if marker in line:
                failed.append(line.split(marker, 1)[1].split("::", 1)[0].strip())
            elif line.startswith("N38 scope FAIL"):
                failed.append("scope-contract")
            elif line.startswith("- Missing required changed paths"):
                failed.append("scope-missing-required-paths")
            elif line.startswith("- Changed paths outside exact N38 UI/visual patch budget"):
                failed.append("scope-extra-paths")
    return sorted(set(failed))


def proportional_score(max_points: int, failures: set[str], group: set[str]):
    missed = len(failures & group)
    if not group:
        return max_points
    return int(round(max_points * max(0, len(group) - missed) / len(group)))


def phase_rule_score(summary: dict, contract: dict):
    score = 0
    notes = []
    phases = {phase.get("phaseId"): phase for phase in summary.get("phases", [])}
    rules = contract["phasePathRules"]
    per_phase = 5 / max(1, len(rules))
    for phase_id, rule in rules.items():
        phase = phases.get(phase_id)
        if not phase:
            notes.append(f"missing phase summary {phase_id}")
            continue
        changed = set(phase.get("benchmarkChangedPaths", []))
        allowed = set(rule["allowed"])
        required_any = set(rule["requiredAny"])
        if changed and changed <= allowed and changed & required_any:
            score += per_phase
        else:
            notes.append(f"{phase_id} path rule miss: changed={sorted(changed)}")
    return int(round(score)), notes


def score_time(summary: dict):
    elapsed = sum(float(phase.get("elapsedSeconds") or 0) for phase in summary.get("phases", []))
    if elapsed <= 900:
        return 5, elapsed
    if elapsed <= 1800:
        return 3, elapsed
    return 1, elapsed


def score_output(summary: dict):
    total = 0
    missing = 0
    for phase in summary.get("phases", []):
        value = phase.get("outputBytes")
        if isinstance(value, int):
            total += value
        else:
            missing += 1
    if missing:
        return 0, total, [f"{missing} phase outputs missing"]
    if total <= 80000:
        return 5, total, []
    if total <= 220000:
        return 3, total, []
    return 1, total, []


def score_one(case_root: Path, contract: dict, display_base: Path):
    case_root = case_root_from_arg(case_root.resolve())
    summary_path = case_root / "meta" / "summary.json"
    if not summary_path.exists():
        return {
            "run_root": format_run_root(case_root, display_base),
            "row": infer_row_from_path(case_root),
            "binary": "NOT-RUN",
            "scoreability": "runtime-no-summary",
            "rubric": 0,
            "notes": ["missing staged summary.json"],
        }

    summary = load_json(summary_path) or {}
    worker_text = read_phase_outputs(summary)
    binary, scoreability = classify_binary(summary, worker_text)
    failed = set(failed_invariants(summary))
    changed = list(summary.get("benchmarkChangedPaths", []))
    changed_exact = sorted(changed) == sorted(contract["requiredChangedPaths"])
    scope_pass = any(
        result.get("passed") and "check_scope.py" in result.get("command", "")
        for result in summary.get("verificationResults", [])
    )

    state = proportional_score(20, failed, STATE_FAILURES)
    raster = proportional_score(25, failed, RASTER_FAILURES)
    accessibility = proportional_score(15, failed, ACCESSIBILITY_FAILURES)
    layout = proportional_score(10, failed, LAYOUT_FAILURES)
    ledger_penalty = 0 if not (failed & LEDGER_FAILURES) else 8

    phase, phase_notes = phase_rule_score(summary, contract)
    patch = 10 if changed_exact and scope_pass else 4 if scope_pass else 0
    tests = 5 if "candidate/workspace/tests/console-contract.test.mjs" in changed else 0
    time_score, elapsed = score_time(summary)
    output_score, output_bytes, output_notes = score_output(summary)

    rubric = state + raster + accessibility + layout + phase + patch + tests + time_score + output_score - ledger_penalty
    rubric = max(0, min(100, rubric))
    if binary != "PASS" and scoreability == "scoreable":
        rubric = min(rubric, 78)
    if scoreability != "scoreable":
        rubric = 0

    notes = []
    if failed:
        notes.append("failed invariants: " + ", ".join(sorted(failed)))
    notes.extend(phase_notes)
    notes.extend(output_notes)
    if not changed_exact:
        notes.append("changed paths not exact")

    return {
        "run_root": format_run_root(case_root, display_base),
        "row": summary.get("rowId", infer_row_from_path(case_root)),
        "model": summary.get("modelLabel"),
        "binary": binary,
        "scoreability": scoreability,
        "wrapper_exit_code": summary.get("wrapperExitCode"),
        "verification_passed": summary.get("verificationPassed"),
        "rubric": rubric,
        "state": state,
        "raster": raster,
        "accessibility": accessibility,
        "layout": layout,
        "phase": phase,
        "patch": patch,
        "tests": tests,
        "time": time_score,
        "output": output_score,
        "elapsedSeconds": round(elapsed, 3),
        "outputBytes": output_bytes,
        "changedCount": len(changed),
        "changedPaths": changed,
        "failed_invariants": sorted(failed),
        "notes": notes,
        "summaryPath": str(summary_path),
    }


def print_markdown(results):
    headers = [
        "Row",
        "Binary",
        "Scoreability",
        "Rubric",
        "State",
        "Raster",
        "A11y",
        "Layout",
        "Phase",
        "Patch",
        "Tests",
        "Time",
        "Output",
        "Elapsed",
        "Bytes",
        "Failed invariants",
    ]
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join(["---"] * len(headers)) + "|")
    for result in results:
        print(
            "| {row} | {binary} | {scoreability} | {rubric} | {state} | {raster} | "
            "{accessibility} | {layout} | {phase} | {patch} | {tests} | {time} | "
            "{output} | {elapsed} | {bytes_count} | {failed} |".format(
                row=result.get("row"),
                binary=result.get("binary"),
                scoreability=result.get("scoreability", ""),
                rubric=result.get("rubric", 0),
                state=result.get("state", 0),
                raster=result.get("raster", 0),
                accessibility=result.get("accessibility", 0),
                layout=result.get("layout", 0),
                phase=result.get("phase", 0),
                patch=result.get("patch", 0),
                tests=result.get("tests", 0),
                time=result.get("time", 0),
                output=result.get("output", 0),
                elapsed=result.get("elapsedSeconds"),
                bytes_count=result.get("outputBytes"),
                failed=", ".join(result.get("failed_invariants", [])),
            )
        )


def main():
    args = parse_args()
    contract = load_json(CONTRACT_PATH) or {}
    display_base = Path.cwd().resolve()
    results = [score_one(path, contract, display_base) for path in args.case_roots]
    print_markdown(results)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        with args.json_out.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump({"scenario": "N38", "surface": "E28", "results": results}, handle, indent=2)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
