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
    / "N36-realrepo-staged-api-migration-gauntlet"
    / "oracle"
    / "staged-api-contract.json"
)


def parse_args():
    parser = argparse.ArgumentParser(description="Score N36 staged API-migration run roots.")
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
                invariant = line.split(marker, 1)[1].split("::", 1)[0].strip()
                failed.append(invariant)
            elif line.startswith("ERROR: Top-level bundle entries drifted"):
                failed.append("bundle-shape")
            elif line.startswith("N36 scope FAIL"):
                failed.append("scope-contract")
            elif line.startswith("- Missing required changed paths"):
                failed.append("scope-missing-required-paths")
            elif line.startswith("- Changed paths outside exact N36 patch budget"):
                failed.append("scope-extra-paths")
    return sorted(set(failed))


def phase_rule_score(summary: dict, contract: dict):
    score = 0
    notes = []
    phases = {phase.get("phaseId"): phase for phase in summary.get("phases", [])}
    rules = contract["phasePathRules"]
    if len(phases) == len(contract["expectedPhaseIds"]):
        score += 3
    else:
        notes.append("phase count mismatch")

    per_phase_points = 12 / max(1, len(rules))
    for phase_id, rule in rules.items():
        phase = phases.get(phase_id)
        if not phase:
            notes.append(f"missing phase summary {phase_id}")
            continue
        changed = set(phase.get("benchmarkChangedPaths", []))
        allowed = set(rule["allowed"])
        required_any = set(rule["requiredAny"])
        if changed and changed <= allowed and changed & required_any:
            score += per_phase_points
        else:
            notes.append(f"{phase_id} path rule miss: changed={sorted(changed)}")
    return int(round(score)), notes


def text_contains_all(text: str, terms: list[str]):
    return all(term in text for term in terms)


def score_artifacts(case_root: Path, contract: dict):
    state = load_json(case_root / "run" / "candidate" / "migration-state.json") or {}
    review = load_json(case_root / "run" / "candidate" / "review-response.json") or {}
    closure = load_json(case_root / "run" / "candidate" / "closure.json") or {}

    state_text = json.dumps(state, sort_keys=True)
    review_text = json.dumps(review, sort_keys=True)
    closure_text = json.dumps(closure, sort_keys=True)
    notes = []

    ledger = 0
    if contract["planFingerprint"] in state_text and contract["planFingerprint"] in closure_text:
        ledger += 3
    else:
        notes.append("plan fingerprint incomplete")
    phase_ids = {
        item.get("id") or item.get("phase") or item.get("phaseId")
        for item in state.get("phases", [])
        if isinstance(item, dict)
    }
    if set(contract["expectedPhaseIds"]) <= phase_ids:
        ledger += 3
    else:
        notes.append("phase ledger incomplete")
    if text_contains_all(state_text, contract["expectedSourceIds"]):
        ledger += 2
    else:
        notes.append("source bindings incomplete")
    if text_contains_all(state_text, contract["requiredLedgerRows"]["staleRejections"]):
        ledger += 2
    else:
        notes.append("stale-source rejections incomplete")
    for section in ["interfaceMap", "callSites", "compatibilityCases", "validationMarkers"]:
        terms = contract["requiredLedgerRows"][section]
        if text_contains_all(state_text, terms):
            ledger += 1
        else:
            notes.append(f"{section} incomplete")

    responses = review.get("responses", [])
    response_by_id = {
        (item.get("id") or item.get("reviewId")): item
        for item in responses
        if isinstance(item, dict) and (item.get("id") or item.get("reviewId"))
    }
    review_score = 0
    per_review = 10 / max(1, len(contract["reviewDecisions"]))
    for review_id, decision in contract["reviewDecisions"].items():
        item = response_by_id.get(review_id)
        owner = None if not item else item.get("owner") or item.get("ownerPath")
        if item and str(item.get("decision", "")).lower() == decision and owner and item.get("validationCue"):
            review_score += per_review
        else:
            notes.append(f"review decision miss {review_id}")

    closure_exact_paths = sorted(closure.get("changedPaths", [])) == sorted(contract["requiredChangedPaths"])
    if "python candidate/workspace/tests/test_billingmesh.py" not in closure_text:
        notes.append("closure validation command missing")
    if not closure.get("reviewOutcome"):
        notes.append("closure review outcome missing")
    if "residualRisk" not in closure:
        notes.append("closure residualRisk missing")

    return {
        "ledger": min(15, int(round(ledger))),
        "review": min(10, int(round(review_score))),
        "closure_exact_paths": closure_exact_paths,
        "notes": notes,
    }


def score_tests(case_root: Path, contract: dict, changed: list[str]):
    test_path = case_root / "run" / "candidate" / "workspace" / "tests" / "test_billingmesh.py"
    if not test_path.exists():
        return 0, ["test file missing"]
    text = test_path.read_text(encoding="utf-8", errors="replace")
    if "candidate/workspace/tests/test_billingmesh.py" not in changed:
        return 2, ["tests not changed"]
    missing = [marker for marker in contract["requiredTestMarkers"] if marker not in text]
    if missing:
        return 2, [f"missing test markers: {', '.join(missing)}"]
    return 5, []


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
    if total <= 60000:
        return 2, total, []
    if total <= 180000:
        return 1, total, []
    return 0, total, []


def score_semantic(failed: list[str]):
    failed_set = set(failed)
    interface_failures = {
        "legacy-api-static",
        "result-models",
        "legacy-api-removed",
    }
    runtime_failures = {
        "account-lookup-contract",
        "entitlement-contract",
        "publisher-contract",
        "integration-contract",
        "reporting-contract",
        "import-billingmesh",
    }
    interface = max(0, 15 - 5 * len(failed_set & interface_failures))
    hidden = max(0, 25 - 5 * len(failed_set & runtime_failures))
    return interface, hidden


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
    interface, hidden = score_semantic(failed)
    phase, phase_notes = phase_rule_score(summary, contract)
    artifacts = score_artifacts(case_root, contract)
    changed = list(summary.get("benchmarkChangedPaths", []))
    patch = 10 if sorted(changed) == sorted(contract["requiredChangedPaths"]) and artifacts["closure_exact_paths"] else 0
    tests, test_notes = score_tests(case_root, contract, changed)
    time_score, elapsed = score_time(summary)
    output_score, output_bytes, output_notes = score_output(summary)

    notes = []
    if failed:
        notes.append("failed invariants: " + ", ".join(failed))
    if patch == 0:
        notes.append("patch budget mismatch")
    notes.extend(phase_notes)
    notes.extend(artifacts["notes"])
    notes.extend(test_notes)
    notes.extend(output_notes)

    rubric = (
        interface
        + hidden
        + phase
        + artifacts["ledger"]
        + artifacts["review"]
        + patch
        + tests
        + time_score
        + output_score
    )
    if binary != "PASS" and scoreability == "scoreable":
        rubric = min(rubric, 78)
    if scoreability != "scoreable":
        rubric = 0

    return {
        "run_root": format_run_root(case_root, display_base),
        "row": summary.get("rowId", infer_row_from_path(case_root)),
        "model": summary.get("modelLabel"),
        "binary": binary,
        "scoreability": scoreability,
        "wrapper_exit_code": summary.get("wrapperExitCode"),
        "verification_passed": summary.get("verificationPassed"),
        "rubric": rubric,
        "interface": interface,
        "hidden": hidden,
        "phase": phase,
        "ledger": artifacts["ledger"],
        "review": artifacts["review"],
        "patch": patch,
        "tests": tests,
        "time": time_score,
        "output": output_score,
        "elapsedSeconds": round(elapsed, 3),
        "outputBytes": output_bytes,
        "changedCount": len(changed),
        "changedPaths": changed,
        "failed_invariants": failed,
        "notes": notes,
        "summaryPath": str(summary_path),
    }


def print_markdown(results):
    headers = [
        "Row",
        "Binary",
        "Scoreability",
        "Rubric",
        "Interface",
        "Hidden",
        "Phase",
        "Ledger",
        "Review",
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
            "| {row} | {binary} | {scoreability} | {rubric} | {interface} | {hidden} | "
            "{phase} | {ledger} | {review} | {patch} | {tests} | {time} | {output} | "
            "{elapsed} | {bytes_count} | {failed} |".format(
                row=result.get("row"),
                binary=result.get("binary"),
                scoreability=result.get("scoreability", ""),
                rubric=result.get("rubric", 0),
                interface=result.get("interface", 0),
                hidden=result.get("hidden", 0),
                phase=result.get("phase", 0),
                ledger=result.get("ledger", 0),
                review=result.get("review", 0),
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
            json.dump({"scenario": "N36", "surface": "E26", "results": results}, handle, indent=2)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
