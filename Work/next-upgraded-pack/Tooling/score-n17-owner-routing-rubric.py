#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path


CRITERIA = {
    "primary_continuity": [
        "Primary task: role-fit routing read for X1/X3 by lane",
        "Resume from Results-drafts/role-fit-scorecard-v1-2026-04-22.md",
    ],
    "diagnostic_separation": [
        "Do not promote N16 into a routing lane yet",
        "Use N16 as E6 diagnostic rubric only",
        "Runtime failures remain NOT-RUN, not model FAIL",
    ],
    "role_routing": [
        "Next role now: $lead",
        "QA gate: after the pilot bundle and scorer validate",
        "Architecture-reviewer gate: after a routing-policy surface changes",
    ],
    "calibration_discipline": [
        "X2 calibration: run when lane policy could change",
        "X5 calibration: require a direct smoke that writes worker-output.txt before semantic runs",
        "X6 calibration: run as lower-cost calibration after X2 or when runtime is healthy",
    ],
    "interruption_classification": ["| `I1` |", "| `I2` |", "| `I3` |", "| `I4` |", "| `I5` |"],
}


def parse_args():
    parser = argparse.ArgumentParser(description="Score N17 owner routing run roots.")
    parser.add_argument("run_roots", nargs="+", type=Path)
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def score_one(run_root: Path):
    meta_root = run_root / "meta"
    bundle_root = run_root / "run"
    summary_path = meta_root / "summary.json"
    packet_path = bundle_root / "candidate" / "owner-routing-decision.md"
    worker_output = meta_root / "worker-output.txt"
    prompt_path = meta_root / "prompt.txt"

    if not summary_path.exists():
        return {"run_root": str(run_root), "row": "unknown", "binary": "NOT-RUN", "total": 0}

    summary = load_json(summary_path)
    text = packet_path.read_text(encoding="utf-8", errors="replace") if packet_path.exists() else ""
    binary_pass = summary.get("wrapperExitCode") == 0 and summary.get("verificationPassed") is True

    criterion_scores = {}
    for name, needles in CRITERIA.items():
        hits = sum(1 for needle in needles if needle in text)
        criterion_scores[name] = round(hits / len(needles) * 20)

    artifact_score = sum(criterion_scores.values())
    correctness = 100 if binary_pass else min(artifact_score, 60)

    elapsed = None
    if prompt_path.exists() and summary_path.exists():
        elapsed = max(0.0, summary_path.stat().st_mtime - prompt_path.stat().st_mtime)

    return {
        "run_root": str(run_root),
        "row": summary.get("rowId", "unknown"),
        "model": summary.get("modelLabel"),
        "binary": "PASS" if binary_pass else "FAIL",
        "total": correctness,
        "criteria": criterion_scores,
        "elapsed_proxy_seconds": round(elapsed, 3) if elapsed is not None else None,
        "output_bytes": worker_output.stat().st_size if worker_output.exists() else None,
        "changed_paths": summary.get("benchmarkChangedPaths", []),
    }


def print_markdown(results):
    print("| Row | Binary | Rubric | Primary | Diagnostic | Routing | Calibration | Interruptions | Elapsed | Output |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for result in results:
        criteria = result.get("criteria", {})
        print(
            "| {row} | {binary} | {total} | {primary} | {diagnostic} | {routing} | {calibration} | {interruptions} | {elapsed} | {output} |".format(
                row=result.get("row"),
                binary=result.get("binary"),
                total=result.get("total"),
                primary=criteria.get("primary_continuity", 0),
                diagnostic=criteria.get("diagnostic_separation", 0),
                routing=criteria.get("role_routing", 0),
                calibration=criteria.get("calibration_discipline", 0),
                interruptions=criteria.get("interruption_classification", 0),
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
