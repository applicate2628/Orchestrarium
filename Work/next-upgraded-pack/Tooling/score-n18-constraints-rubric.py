#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


CRITERIA = {
    "decision_correctness": [
        "Decision: Option C - keyed index plus exact ledger replay",
        "Reject Option A - linear exact ledger scan: p95 latency 280ms exceeds <= 200ms",
        "Reject Option B - probabilistic sketch gate: rollback false negatives 1.8% violates 0 allowed",
    ],
    "evidence_binding": [
        "Option C measured p95 latency 118ms",
        "Option C measured memory 164MB",
        "Option C measured false-negative risk 0",
        "Option C measured source trace 100%",
    ],
    "non_claim_discipline": [
        "UI badge smoothness is not release safety evidence",
        "stale benchmark notes cannot override current measured profiles",
        "synthetic fixtures only; no production secrets in prompt/cache",
    ],
    "falsification_coverage": [
        "p95 gate decision latency <= 200ms",
        "rollback false negatives 0 allowed",
        "audit source trace 100% preserved",
        "memory budget <= 256MB",
    ],
    "risk_ownership": [
        "R1 latency regression",
        "R2 replay drift",
        "R3 index corruption",
        "R4 secret exposure",
    ],
}


def parse_args():
    parser = argparse.ArgumentParser(description="Score N18 scientist/constraint run roots.")
    parser.add_argument("run_roots", nargs="+", type=Path)
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def infer_row_from_path(run_root: Path):
    match = re.search(r"-(X\d)-", str(run_root))
    return match.group(1) if match else "unknown"


def score_one(run_root: Path):
    meta_root = run_root / "meta"
    bundle_root = run_root / "run"
    summary_path = meta_root / "summary.json"
    memo_path = bundle_root / "candidate" / "constraint-decision-memo.md"
    worker_output = meta_root / "worker-output.txt"
    prompt_path = meta_root / "prompt.txt"

    if not summary_path.exists():
        return {
            "run_root": str(run_root),
            "row": infer_row_from_path(run_root),
            "binary": "NOT-RUN",
            "scoreability": "runtime-no-summary",
            "total": 0,
        }

    summary = load_json(summary_path)
    text = memo_path.read_text(encoding="utf-8", errors="replace") if memo_path.exists() else ""
    worker_text = worker_output.read_text(encoding="utf-8", errors="replace") if worker_output.exists() else ""
    binary_pass = summary.get("wrapperExitCode") == 0 and summary.get("verificationPassed") is True
    runtime_route_fail = summary.get("wrapperExitCode") != 0 and (
        "Tool \"run_shell_command\" not found" in worker_text or "AbortError" in worker_text
    )

    criterion_scores = {}
    for name, needles in CRITERIA.items():
        hits = sum(1 for needle in needles if needle in text)
        criterion_scores[name] = round(hits / len(needles) * 20)

    artifact_score = sum(criterion_scores.values())
    total = 100 if binary_pass else min(artifact_score, 60)
    binary = "PASS" if binary_pass else "ROUTE-FAIL" if runtime_route_fail else "FAIL"
    scoreability = "scoreable" if summary.get("wrapperExitCode") == 0 else "runtime-route"

    elapsed = None
    if prompt_path.exists() and summary_path.exists():
        elapsed = max(0.0, summary_path.stat().st_mtime - prompt_path.stat().st_mtime)

    return {
        "run_root": str(run_root),
        "row": summary.get("rowId", "unknown"),
        "model": summary.get("modelLabel"),
        "binary": binary,
        "scoreability": scoreability,
        "wrapper_exit_code": summary.get("wrapperExitCode"),
        "verification_passed": summary.get("verificationPassed"),
        "total": total,
        "criteria": criterion_scores,
        "elapsed_proxy_seconds": round(elapsed, 3) if elapsed is not None else None,
        "output_bytes": worker_output.stat().st_size if worker_output.exists() else None,
        "changed_paths": summary.get("benchmarkChangedPaths", []),
    }


def print_markdown(results):
    print("| Row | Binary | Scoreability | Rubric | Decision | Evidence | Non-claim | Falsification | Risk | Elapsed | Output |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for result in results:
        criteria = result.get("criteria", {})
        print(
            "| {row} | {binary} | {scoreability} | {total} | {decision} | {evidence} | {nonclaim} | {falsification} | {risk} | {elapsed} | {output} |".format(
                row=result.get("row"),
                binary=result.get("binary"),
                scoreability=result.get("scoreability", ""),
                total=result.get("total"),
                decision=criteria.get("decision_correctness", 0),
                evidence=criteria.get("evidence_binding", 0),
                nonclaim=criteria.get("non_claim_discipline", 0),
                falsification=criteria.get("falsification_coverage", 0),
                risk=criteria.get("risk_ownership", 0),
                elapsed=result.get("elapsed_proxy_seconds"),
                output=result.get("output_bytes"),
            )
        )


def main():
    args = parse_args()
    results = [score_one(path.resolve()) for path in args.run_roots]
    print_markdown(results)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps({"results": results}, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
