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
    / "N39-staged-systems-toolchain-reentry-gauntlet"
    / "oracle"
    / "toolchain-staging-contract.json"
)

SYSTEMS_FAILURES = {
    "active-channel-precedence",
    "valid-env-override",
    "invalid-env-fallback",
    "dependency-order",
    "mode-conflict-rejected",
}
CACHE_TRACE_FAILURES = {
    "fingerprint-portable",
    "lease-release-on-failure",
    "cache-restore-source-trace",
    "summary-source-trace",
}
RECOVERY_FAILURES = {
    "recovery-source-arbitration",
    "resume-continuity",
    "runtime-failure-classification",
}
LEDGER_FAILURES = {"ledger-complete", "closure-complete"}


def parse_args():
    parser = argparse.ArgumentParser(description="Score N39 staged systems/toolchain run roots.")
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
            elif line.startswith("N39 scope FAIL"):
                failed.append("scope-contract")
            elif line.startswith("- Missing required changed paths"):
                failed.append("scope-missing-required-paths")
            elif line.startswith("- Changed paths outside exact N39"):
                failed.append("scope-extra-paths")
    return sorted(set(failed))


def changed_paths_match_scope(changed_paths: list[str], contract: dict):
    observed = {path.replace("\\", "/") for path in changed_paths}
    allowed = set(contract["allowedChangedPaths"])
    required_core = set(contract["requiredChangedCorePaths"])
    any_groups = [set(group) for group in contract.get("requiredChangedAnyOf", [])]

    missing_core = sorted(required_core - observed)
    extra = sorted(observed - allowed)
    if missing_core:
        return False, f"missing core paths: {missing_core}"
    for group in any_groups:
        if not observed & group:
            return False, f"missing one-of paths: {sorted(group)}"
    if extra:
        return False, f"extra paths: {extra}"
    return True, ""


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
    if total <= 100000:
        return 5, total, []
    if total <= 260000:
        return 3, total, []
    return 1, total, []


def score_one(case_root: Path, contract: dict):
    case_root = case_root_from_arg(case_root.resolve())
    summary_path = case_root / "meta" / "summary.json"
    if not summary_path.exists():
        return {
            "run_root": str(case_root),
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
    changed_matches_scope, changed_scope_note = changed_paths_match_scope(changed, contract)
    scope_pass = any(
        result.get("passed") and "check_scope.py" in result.get("command", "")
        for result in summary.get("verificationResults", [])
    )

    systems = proportional_score(25, failed, SYSTEMS_FAILURES)
    cache_trace = proportional_score(20, failed, CACHE_TRACE_FAILURES)
    recovery = proportional_score(20, failed, RECOVERY_FAILURES)
    phase, phase_notes = phase_rule_score(summary, contract)
    patch = 15 if changed_matches_scope and scope_pass else 8 if scope_pass else 0
    tests = 5 if "candidate/workspace/tests/test_stagegate.py" in changed else 0
    time_score, elapsed = score_time(summary)
    output_score, output_bytes, output_notes = score_output(summary)
    ledger_penalty = 0 if not (failed & LEDGER_FAILURES) else 10

    rubric = systems + cache_trace + recovery + patch + tests + phase + time_score + output_score - ledger_penalty
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
    if not changed_matches_scope and changed_scope_note:
        notes.append(changed_scope_note)

    return {
        "run_root": str(case_root),
        "row": summary.get("rowId", infer_row_from_path(case_root)),
        "model": summary.get("modelLabel"),
        "binary": binary,
        "scoreability": scoreability,
        "wrapper_exit_code": summary.get("wrapperExitCode"),
        "verification_passed": summary.get("verificationPassed"),
        "rubric": rubric,
        "systems": systems,
        "cache_trace": cache_trace,
        "recovery": recovery,
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
    headers = ["Row", "Binary", "Scoreability", "Rubric", "Systems", "Cache/Trace", "Recovery", "Notes"]
    print("| " + " | ".join(headers) + " |")
    print("|" + "|".join(["---"] * len(headers)) + "|")
    for item in results:
        notes = "; ".join(item.get("notes", []))
        print(
            "| {row} | {binary} | {scoreability} | {rubric} | {systems} | {cache_trace} | {recovery} | {notes} |".format(
                row=item.get("row"),
                binary=item.get("binary"),
                scoreability=item.get("scoreability"),
                rubric=item.get("rubric"),
                systems=item.get("systems", ""),
                cache_trace=item.get("cache_trace", ""),
                recovery=item.get("recovery", ""),
                notes=notes.replace("|", "/"),
            )
        )


def main():
    args = parse_args()
    contract = load_json(CONTRACT_PATH)
    results = [score_one(path, contract) for path in args.case_roots]
    print_markdown(results)
    if args.json_out:
        args.json_out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
