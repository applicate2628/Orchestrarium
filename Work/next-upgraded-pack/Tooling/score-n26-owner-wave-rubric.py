#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SOURCE_STALE_ANCHORS = [
    "Current source of truth: Work/next-upgraded-pack/Results-drafts/role-fit-scorecard-v1-2026-04-22.md",
    "Systems/toolchain: X3 primary, X1 secondary",
    "UI implementation: X3 primary versus X1; X5 contender only",
    "Owner recovery: X3 provisional-primary pending N26 repeat",
    "Review/security: X1 and X3 near-tie",
    "| `ST1` |",
    "| `ST2` |",
    "| `ST3` |",
    "| `ST4` |",
    "| `ST5` |",
    "| `ST6` |",
    "| `ST7` |",
    "| `ST8` |",
]

CONTINUITY_ANCHORS = [
    "| `I1` |",
    "| `I2` |",
    "| `I3` |",
    "| `I4` |",
    "| `I5` |",
    "| `I6` |",
    "| `I7` |",
    "| `I8` |",
    "Next scenario: N26-owner-recovery-wave-roadmap-reconciliation-gauntlet",
]

ROUTING_ANCHORS = [
    "Next owner now: $lead",
    "QA gate only after N26 bundle, verifier, scorer, and reference pass validate",
    "Architecture-reviewer gate only after routing-policy surface changes",
    "| `systems/toolchain` |",
    "| `UI implementation` |",
    "| `owner recovery` |",
    "| `review/security` |",
]

CALIBRATION_RUNTIME_ANCHORS = [
    "X1 and X3 run first",
    "X2 and X6 calibrate only when lane policy may change",
    "X5 requires same-session smoke that writes worker-output.txt before semantic run",
    "Runtime failures stay NOT-RUN, REQUEUE, RUNTIME-FAIL, or ROUTE-FAIL, not model FAIL",
    "Read-only explorers may propose disjoint designs; main owner keeps roadmap and live result surfaces",
    "No stale parallel result files",
]

CITATION_DENOMINATOR_ANCHORS = [
    "N16..N25 are diagnostic overlays, not a merged old full-v2 denominator",
    "Work/next-upgraded-pack/Results-drafts/role-fit-scorecard-v1-2026-04-22.md:57",
    "Work/next-upgraded-pack/Results-drafts/role-fit-scorecard-v1-2026-04-22.md:58",
    "Work/next-upgraded-pack/Results-drafts/role-fit-scorecard-v1-2026-04-22.md:79",
    "Work/next-upgraded-pack/Results-drafts/role-fit-scorecard-v1-2026-04-22.md:96",
    "Work/next-upgraded-pack/Results-drafts/role-fit-scorecard-v1-2026-04-22.md:130",
    "Work/next-upgraded-pack/Planning/next-phase/hardening-wave-roadmap-2026-04-22.md:62",
    "Work/next-upgraded-pack/Planning/next-phase/hardening-wave-roadmap-2026-04-22.md:78",
    "Work/next-upgraded-pack/Planning/next-phase/hardening-wave-roadmap-2026-04-22.md:116",
    "Work/next-upgraded-pack/Checkpoints/status-2026-04-16.md:12",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Score N26 owner wave reconciliation run roots.")
    parser.add_argument("run_roots", nargs="+", type=Path)
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def infer_row_from_path(run_root: Path):
    match = re.search(r"-(X\d)-", str(run_root))
    return match.group(1) if match else "unknown"


def classify_binary(summary: dict, worker_text: str):
    if summary.get("wrapperExitCode") == 0 and summary.get("verificationPassed") is True:
        return "PASS", "scoreable"
    if summary.get("wrapperExitCode") != 0 and (
        "Tool \"run_shell_command\" not found" in worker_text or "AbortError" in worker_text
    ):
        return "ROUTE-FAIL", "runtime-route"
    if summary.get("wrapperExitCode") != 0 and "quota" in worker_text.lower():
        return "REQUEUE", "runtime-quota"
    if summary.get("wrapperExitCode") != 0:
        return "RUNTIME-FAIL", "runtime-wrapper"
    return "FAIL", "scoreable"


def proportional_score(text: str, anchors: list[str], maximum: int):
    hits = sum(1 for anchor in anchors if anchor in text)
    return round(hits / len(anchors) * maximum)


def compactness_score(output_bytes: int | None):
    if output_bytes is None:
        return 0
    if output_bytes <= 4000:
        return 10
    if output_bytes <= 12000:
        return 8
    if output_bytes <= 40000:
        return 5
    return 2


def score_one(run_root: Path):
    meta_root = run_root / "meta"
    bundle_root = run_root / "run"
    summary_path = meta_root / "summary.json"
    packet_path = bundle_root / "candidate" / "owner-recovery-wave-roadmap-decision.md"
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
    worker_text = worker_output.read_text(encoding="utf-8", errors="replace") if worker_output.exists() else ""
    text = packet_path.read_text(encoding="utf-8", errors="replace") if packet_path.exists() else ""
    binary, scoreability = classify_binary(summary, worker_text)
    output_bytes = worker_output.stat().st_size if worker_output.exists() else None

    source_stale = proportional_score(text, SOURCE_STALE_ANCHORS, 25)
    continuity = proportional_score(text, CONTINUITY_ANCHORS, 20)
    routing = proportional_score(text, ROUTING_ANCHORS, 20)
    calibration_runtime = proportional_score(text, CALIBRATION_RUNTIME_ANCHORS, 15)
    citations_denominator = proportional_score(text, CITATION_DENOMINATOR_ANCHORS, 10)
    compactness = compactness_score(output_bytes)

    total = source_stale + continuity + routing + calibration_runtime + citations_denominator + compactness
    if binary != "PASS" and scoreability == "scoreable":
        total = min(total, 70)
    if scoreability != "scoreable":
        total = 0

    elapsed = None
    if prompt_path.exists() and summary_path.exists():
        elapsed = max(0.0, summary_path.stat().st_mtime - prompt_path.stat().st_mtime)

    return {
        "run_root": str(run_root),
        "row": summary.get("rowId", infer_row_from_path(run_root)),
        "model": summary.get("modelLabel"),
        "binary": binary,
        "scoreability": scoreability,
        "wrapper_exit_code": summary.get("wrapperExitCode"),
        "verification_passed": summary.get("verificationPassed"),
        "total": total,
        "source_stale": source_stale,
        "continuity": continuity,
        "routing": routing,
        "calibration_runtime": calibration_runtime,
        "citations_denominator": citations_denominator,
        "compactness": compactness,
        "elapsed_proxy_seconds": round(elapsed, 3) if elapsed is not None else None,
        "output_bytes": output_bytes,
        "changed_paths": summary.get("benchmarkChangedPaths", []),
    }


def print_markdown(results):
    print("| Row | Binary | Scoreability | Rubric | Source/Stale | Continuity | Routing | Cal/Runtime | Citation/Denom | Compact | Elapsed | Output |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for result in results:
        print(
            "| {row} | {binary} | {scoreability} | {total} | {source_stale} | {continuity} | {routing} | "
            "{calibration_runtime} | {citations_denominator} | {compactness} | {elapsed} | {output} |".format(
                row=result.get("row"),
                binary=result.get("binary"),
                scoreability=result.get("scoreability", ""),
                total=result.get("total", 0),
                source_stale=result.get("source_stale", 0),
                continuity=result.get("continuity", 0),
                routing=result.get("routing", 0),
                calibration_runtime=result.get("calibration_runtime", 0),
                citations_denominator=result.get("citations_denominator", 0),
                compactness=result.get("compactness", 0),
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
