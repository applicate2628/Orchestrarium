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
    / "N37-staged-adversarial-review-gate-gauntlet"
    / "oracle"
    / "review-gate-contract.json"
)


def parse_args():
    parser = argparse.ArgumentParser(description="Score N37 staged ADR/review-gate run roots.")
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
            elif line.startswith("ERROR: Top-level bundle entries drifted"):
                failed.append("bundle-shape")
            elif line.startswith("N37 scope FAIL"):
                failed.append("scope-contract")
            elif line.startswith("- Missing required changed paths"):
                failed.append("scope-missing-required-paths")
            elif line.startswith("- Changed paths outside exact N37 review artifact budget"):
                failed.append("scope-extra-paths")
    return sorted(set(failed))


def contains_all(text: str, markers: list[str]):
    lower = text.lower()
    return all(marker.lower() in lower for marker in markers)


def item_id(item: dict):
    return item.get("id") or item.get("findingId") or item.get("responseId") or item.get("reviewId")


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


def score_artifacts(case_root: Path, contract: dict):
    state = load_json(case_root / "run" / "candidate" / "review-state.json") or {}
    findings_doc = load_json(case_root / "run" / "candidate" / "findings.json") or {}
    response_doc = load_json(case_root / "run" / "candidate" / "response-gate.json") or {}
    closure = load_json(case_root / "run" / "candidate" / "closure.json") or {}
    adr_path = case_root / "run" / "candidate" / "decision-adr.md"
    adr_text = adr_path.read_text(encoding="utf-8", errors="replace") if adr_path.exists() else ""

    notes = []
    state_text = json.dumps(state, sort_keys=True)
    findings_text = json.dumps(findings_doc, sort_keys=True)
    response_text = json.dumps(response_doc, sort_keys=True)
    closure_text = json.dumps(closure, sort_keys=True)

    evidence = 0
    if contract["planFingerprint"] in state_text and contains_all(state_text, contract["expectedSourceIds"]):
        evidence += 5
    else:
        notes.append("source ledger incomplete")
    if contains_all(state_text, contract["requiredLedgerRows"]["staleRejections"]):
        evidence += 5
    else:
        notes.append("stale rejection ledger incomplete")
    if contains_all(state_text, contract["requiredLedgerRows"]["findings"]):
        evidence += 5
    else:
        notes.append("finding ledger incomplete")
    if contains_all(state_text, contract["requiredLedgerRows"]["falsePositives"]):
        evidence += 5
    else:
        notes.append("false-positive ledger incomplete")

    adr = 15 if (
        contract["planFingerprint"] in adr_text
        and contains_all(adr_text, contract["expectedSourceIds"])
        and contains_all(adr_text, contract["requiredLedgerRows"]["adrMarkers"])
    ) else 0
    if not adr:
        notes.append("ADR source binding incomplete")

    findings_score = 0
    findings = findings_doc.get("findings", [])
    by_id = {item_id(item): item for item in findings if isinstance(item, dict) and item_id(item)}
    for finding_id, expected in contract["expectedFindings"].items():
        item = by_id.get(finding_id)
        if not item:
            notes.append(f"missing finding {finding_id}")
            continue
        item_text = json.dumps(item, sort_keys=True)
        exact = all(item.get(field) == expected[field] for field in ["severity", "owner", "file", "symbol"])
        cues = expected["evidenceCue"].lower() in item_text.lower() and expected["remediationCue"].lower() in item_text.lower()
        source_ids = item.get("source_ids") or item.get("sourceIds")
        if exact and cues and isinstance(source_ids, list) and source_ids:
            findings_score += 25 / max(1, len(contract["expectedFindings"]))
        else:
            notes.append(f"inexact finding {finding_id}")

    nonclaims = 10 if (
        contains_all(findings_text, contract["forbiddenFalsePositiveIds"])
        and contains_all(findings_text, contract["requiredNonClaimMarkers"])
        and not any(forbidden in by_id for forbidden in contract["forbiddenFalsePositiveIds"])
    ) else 0
    if not nonclaims:
        notes.append("non-claim ledger incomplete")

    responses = response_doc.get("responses", [])
    response_by_id = {item_id(item): item for item in responses if isinstance(item, dict) and item_id(item)}
    response_score = 0
    per_response = 15 / max(1, len(contract["responseDecisions"]))
    for response_id, decision in contract["responseDecisions"].items():
        item = response_by_id.get(response_id)
        if item and str(item.get("decision", "")).lower() == decision and (item.get("owner") or item.get("ownerPath")) and (item.get("visibleReturnCue") or item.get("validationCue")):
            response_score += per_response
        else:
            notes.append(f"response decision miss {response_id}")

    closure_exact_paths = sorted(closure.get("changedPaths", [])) == sorted(contract["requiredChangedPaths"])
    if not closure_exact_paths:
        notes.append("closure changed paths mismatch")
    if not contains_all(closure_text, contract["requiredClosureMarkers"]):
        notes.append("closure markers incomplete")

    return {
        "evidence": min(20, int(round(evidence))),
        "adr": adr,
        "findings": min(25, int(round(findings_score))),
        "nonclaims": nonclaims,
        "response": min(15, int(round(response_score))),
        "closure_exact_paths": closure_exact_paths,
        "notes": notes,
    }


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
    phase, phase_notes = phase_rule_score(summary, contract)
    artifacts = score_artifacts(case_root, contract)
    changed = list(summary.get("benchmarkChangedPaths", []))
    patch = 5 if sorted(changed) == sorted(contract["requiredChangedPaths"]) and artifacts["closure_exact_paths"] else 0
    time_score, elapsed = score_time(summary)
    output_score, output_bytes, output_notes = score_output(summary)

    notes = []
    if failed:
        notes.append("failed invariants: " + ", ".join(failed))
    notes.extend(phase_notes)
    notes.extend(artifacts["notes"])
    notes.extend(output_notes)

    rubric = (
        artifacts["evidence"]
        + artifacts["adr"]
        + artifacts["findings"]
        + artifacts["nonclaims"]
        + artifacts["response"]
        + phase
        + patch
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
        "evidence": artifacts["evidence"],
        "adr": artifacts["adr"],
        "findings": artifacts["findings"],
        "nonclaims": artifacts["nonclaims"],
        "response": artifacts["response"],
        "phase": phase,
        "patch": patch,
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
        "Evidence",
        "ADR",
        "Findings",
        "NonClaims",
        "Response",
        "Phase",
        "Patch",
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
            "| {row} | {binary} | {scoreability} | {rubric} | {evidence} | {adr} | "
            "{findings} | {nonclaims} | {response} | {phase} | {patch} | {time} | "
            "{output} | {elapsed} | {bytes_count} | {failed} |".format(
                row=result.get("row"),
                binary=result.get("binary"),
                scoreability=result.get("scoreability", ""),
                rubric=result.get("rubric", 0),
                evidence=result.get("evidence", 0),
                adr=result.get("adr", 0),
                findings=result.get("findings", 0),
                nonclaims=result.get("nonclaims", 0),
                response=result.get("response", 0),
                phase=result.get("phase", 0),
                patch=result.get("patch", 0),
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
            json.dump({"scenario": "N37", "surface": "E27", "results": results}, handle, indent=2)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
