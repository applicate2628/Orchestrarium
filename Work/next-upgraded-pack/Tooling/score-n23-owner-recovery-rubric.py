#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SOURCE_ANCHORS = [
    "Current source of truth: Work/next-upgraded-pack/Results-drafts/role-fit-scorecard-v1-2026-04-22.md",
    "No global winner is admitted",
    "N16 is diagnostic E6, not a routing lane",
    "N17 did not split owner correctness",
    "W3 / E13 / N23 is the admitted next wave",
]

CONTINUITY_ANCHORS = [
    "Primary task: X1/X3 lane-fit hardening by waves",
    "Resume from Work/next-upgraded-pack/Planning/next-phase/hardening-wave-roadmap-2026-04-22.md",
    "| `I1` |",
    "| `I2` |",
    "| `I3` |",
    "| `I4` |",
    "| `I5` |",
    "| `I6` |",
]

ROUTING_ANCHORS = [
    "Next owner now: $lead",
    "QA gate only after N23 bundle, verifier, scorer, and reference pass validate",
    "Architecture-reviewer gate only after routing-policy surface changes",
]

CALIBRATION_ANCHORS = [
    "X1 and X3 run first",
    "X2 and X6 calibrate only when lane policy may change",
    "X5 requires same-session smoke that writes worker-output.txt before semantic run",
    "Runtime failures stay NOT-RUN or ROUTE-FAIL, not model FAIL",
]

CITATION_ANCHORS = [
    "Work/next-upgraded-pack/Results-drafts/role-fit-scorecard-v1-2026-04-22.md:49",
    "Work/next-upgraded-pack/Results-drafts/role-fit-scorecard-v1-2026-04-22.md:80",
    "Work/next-upgraded-pack/Planning/next-phase/hardening-wave-roadmap-2026-04-22.md:38",
    "Work/next-upgraded-pack/Checkpoints/status-2026-04-16.md:12",
    "Work/next-upgraded-pack/Evidence/n22-numerical-stability-rubric-2026-04-22.json:1",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Score N23 owner recovery run roots.")
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
    packet_path = bundle_root / "candidate" / "owner-recovery-routing-decision.md"
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

    source = proportional_score(text, SOURCE_ANCHORS, 25)
    continuity = proportional_score(text, CONTINUITY_ANCHORS, 20)
    routing = proportional_score(text, ROUTING_ANCHORS, 20)
    calibration = proportional_score(text, CALIBRATION_ANCHORS, 15)
    citations = proportional_score(text, CITATION_ANCHORS, 10)
    compactness = compactness_score(output_bytes)

    total = source + continuity + routing + calibration + citations + compactness
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
        "source_discrimination": source,
        "continuity": continuity,
        "routing": routing,
        "calibration": calibration,
        "citations": citations,
        "compactness": compactness,
        "elapsed_proxy_seconds": round(elapsed, 3) if elapsed is not None else None,
        "output_bytes": output_bytes,
        "changed_paths": summary.get("benchmarkChangedPaths", []),
    }


def print_markdown(results):
    print("| Row | Binary | Scoreability | Rubric | Source | Continuity | Routing | Calibration | Citations | Compact | Elapsed | Output |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for result in results:
        print(
            "| {row} | {binary} | {scoreability} | {total} | {source} | {continuity} | {routing} | "
            "{calibration} | {citations} | {compactness} | {elapsed} | {output} |".format(
                row=result.get("row"),
                binary=result.get("binary"),
                scoreability=result.get("scoreability", ""),
                total=result.get("total", 0),
                source=result.get("source_discrimination", 0),
                continuity=result.get("continuity", 0),
                routing=result.get("routing", 0),
                calibration=result.get("calibration", 0),
                citations=result.get("citations", 0),
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
