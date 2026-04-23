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
    / "N41-staged-incident-budget-reentry-gauntlet"
    / "oracle"
    / "staged-incident-budget-contract.json"
)


def parse_args():
    parser = argparse.ArgumentParser(description="Score N41 staged incident-budget run roots.")
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
            elif line.startswith("N41 scope FAIL"):
                failed.append("scope-contract")
            elif line.startswith("- Missing required changed paths"):
                failed.append("scope-missing-required-paths")
            elif line.startswith("- Changed paths outside exact N41 incident budget"):
                failed.append("scope-extra-paths")
    return sorted(set(failed))


def contains_all(text: str, markers: list[str]):
    lower = text.lower()
    return all(marker.lower() in lower for marker in markers)


def phase_rule_score(summary: dict, contract: dict):
    score = 0
    notes = []
    phases = {phase.get("phaseId"): phase for phase in summary.get("phases", [])}
    rules = contract["phasePathRules"]
    per_phase = 10 / max(1, len(rules))
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


def artifact_score(case_root: Path, contract: dict):
    notes = []
    ledger = load_json(case_root / "run" / "candidate" / "repair-ledger.json") or {}
    reentry = load_json(case_root / "run" / "candidate" / "reentry-state.json") or {}
    closure = load_json(case_root / "run" / "candidate" / "closure.json") or {}

    ledger_text = json.dumps(ledger, sort_keys=True)
    reentry_text = json.dumps(reentry, sort_keys=True)
    closure_text = json.dumps(closure, sort_keys=True)

    source = 30 if contains_all(ledger_text, contract["expectedSourceIds"] + contract["expectedStaleIds"]) else 0
    if not source:
        notes.append("source arbitration incomplete")
    stale = 20 if contains_all(ledger_text, contract["expectedReviewIds"]) and contains_all(ledger_text, contract["requiredChangedPaths"]) else 0
    if not stale:
        notes.append("review or patch budget incomplete")
    route = 15 if contains_all(reentry_text, contract["expectedPhaseIds"]) and contains_all(reentry_text, contract["runtimeClassificationMarkers"]) else 0
    if not route:
        notes.append("reentry state incomplete")
    runtime_score = 15 if contains_all(reentry_text, contract["expectedSourceIds"] + contract["expectedStaleIds"]) else 0
    if not runtime_score:
        notes.append("reentry source state incomplete")
    closure_score = 10 if (
        sorted(closure.get("changedPaths", [])) == sorted(contract["requiredChangedPaths"])
        and contains_all(closure_text, contract["closeoutMarkers"])
    ) else 0
    if not closure_score:
        notes.append("closure incomplete")
    return source, stale, route, runtime_score, closure_score, notes


def score_time(summary: dict):
    elapsed = sum(float(phase.get("elapsedSeconds") or 0) for phase in summary.get("phases", []))
    if elapsed <= 900:
        return 3, elapsed
    if elapsed <= 1800:
        return 2, elapsed
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
        return 2, total, []
    if total <= 220000:
        return 1, total, []
    return 0, total, []


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
    failed = failed_invariants(summary)
    changed = list(summary.get("benchmarkChangedPaths", []))
    changed_exact = sorted(changed) == sorted(contract["requiredChangedPaths"])
    source, stale, route, runtime_score, closure_score, artifact_notes = artifact_score(case_root, contract)
    phase, phase_notes = phase_rule_score(summary, contract)
    patch = 5 if changed_exact else 0
    time_score, elapsed = score_time(summary)
    output_score, output_bytes, output_notes = score_output(summary)

    rubric = source + stale + route + runtime_score + closure_score + phase + patch + time_score + output_score
    rubric = max(0, min(100, rubric))
    if binary != "PASS" and scoreability == "scoreable":
        rubric = min(rubric, 78)
    if scoreability != "scoreable":
        rubric = 0

    notes = []
    if failed:
        notes.append("failed invariants: " + ", ".join(failed))
    notes.extend(artifact_notes)
    notes.extend(phase_notes)
    notes.extend(output_notes)

    return {
        "run_root": format_run_root(case_root, display_base),
        "row": summary.get("rowId", infer_row_from_path(case_root)),
        "model": summary.get("modelLabel"),
        "binary": binary,
        "scoreability": scoreability,
        "wrapper_exit_code": summary.get("wrapperExitCode"),
        "verification_passed": summary.get("verificationPassed"),
        "rubric": rubric,
        "source": source,
        "stale": stale,
        "route": route,
        "runtime": runtime_score,
        "closure": closure_score,
        "phase": phase,
        "patch": patch,
        "time": time_score,
        "output": output_score,
        "elapsedSeconds": round(elapsed, 3),
        "outputBytes": output_bytes,
        "changedPaths": changed,
        "failed_invariants": failed,
        "notes": notes,
        "summaryPath": str(summary_path),
    }


def print_markdown(results):
    print("| Row | Binary | Scoreability | Rubric | Source | Review/Budget | Reentry | Runtime Class | Closure | Phase | Patch | Time | Output | Failed invariants |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for result in results:
        print(
            "| {row} | {binary} | {scoreability} | {rubric} | {source} | {stale} | {route} | "
            "{runtime} | {closure} | {phase} | {patch} | {time} | {output} | {failed} |".format(
                row=result.get("row"),
                binary=result.get("binary"),
                scoreability=result.get("scoreability", ""),
                rubric=result.get("rubric", 0),
                source=result.get("source", 0),
                stale=result.get("stale", 0),
                route=result.get("route", 0),
                runtime=result.get("runtime", 0),
                closure=result.get("closure", 0),
                phase=result.get("phase", 0),
                patch=result.get("patch", 0),
                time=result.get("time", 0),
                output=result.get("output", 0),
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
            json.dump({"scenario": "N41", "surface": "E31", "results": results}, handle, indent=2)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
