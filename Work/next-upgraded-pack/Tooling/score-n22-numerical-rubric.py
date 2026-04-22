#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_INVARIANTS = [
    "I-P95-UPPER-RANK",
    "I-BOUNDED-HISTOGRAM-EXACT",
    "I-WELFORD-CHAN-MERGE",
    "I-NO-CLAMPED-VARIANCE",
    "I-STALE-NOTES-NON-AUTHORITATIVE",
]

SYNTHESIS_ANCHORS = [
    "Reject Option A - naive sum/sum_sq variance plus rounded-rank p95",
    "Reject Option B - full sort plus Decimal replay",
    "Reject Option D - approximate sketch p95",
    "stale benchmark notes cannot override current adversarial cases",
    "clamping negative variance to zero is forbidden",
]

FALSIFICATION_ANCHORS = [
    "cancellation",
    "percentile boundary",
    "shard imbalance",
    "memory",
    "stale-source",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Score N22 numerical stability run roots with a diagnostic rubric.")
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


def score_time(seconds: float | None):
    if seconds is None:
        return 0
    if seconds <= 240:
        return 5
    if seconds <= 600:
        return 4
    if seconds <= 1200:
        return 2
    return 1


def score_witness(witness_path: Path):
    if not witness_path.exists():
        return 0, ["missing witness"]
    try:
        witness = load_json(witness_path)
    except Exception as exc:  # noqa: BLE001
        return 0, [f"invalid witness json: {exc}"]

    notes = []
    points = 0
    if witness.get("selected_option") == "Option C - exact bounded histogram p95 plus Welford/Chan variance merge with compensated summation":
        points += 5
    cases = witness.get("cases") if isinstance(witness.get("cases"), list) else []
    points += min(15, len(cases) * 3)
    rejected = witness.get("rejected_options")
    if isinstance(rejected, dict):
        points += min(6, len(rejected) * 2)
    invariant_hits = set()
    for case in cases:
        if isinstance(case, dict):
            invariant_hits.update(case.get("invariant_ids") or [])
    points += min(4, len([item for item in REQUIRED_INVARIANTS[:3] if item in invariant_hits]) * 2)
    if len(cases) != 5:
        notes.append(f"case count {len(cases)}")
    return min(points, 30), notes


def score_one(run_root: Path):
    meta_root = run_root / "meta"
    bundle_root = run_root / "run"
    summary_path = meta_root / "summary.json"
    worker_output = meta_root / "worker-output.txt"
    prompt_path = meta_root / "prompt.txt"
    memo_path = bundle_root / "candidate" / "numerical-stability-decision-memo.md"
    witness_path = bundle_root / "candidate" / "witness-ledger.json"

    if not summary_path.exists():
        return {
            "run_root": str(run_root),
            "row": infer_row_from_path(run_root),
            "binary": "NOT-RUN",
            "scoreability": "runtime-no-summary",
            "total": 0,
            "notes": ["missing summary.json"],
        }

    summary = load_json(summary_path)
    worker_text = worker_output.read_text(encoding="utf-8", errors="replace") if worker_output.exists() else ""
    memo_text = memo_path.read_text(encoding="utf-8", errors="replace") if memo_path.exists() else ""
    binary, scoreability = classify_binary(summary, worker_text)
    binary_pass = binary == "PASS"

    correctness, witness_notes = score_witness(witness_path)
    if binary_pass:
        correctness = 30

    invariant_hits = sum(1 for anchor in REQUIRED_INVARIANTS if anchor in memo_text)
    role_fidelity = round(invariant_hits / len(REQUIRED_INVARIANTS) * 20)

    changed = list(summary.get("benchmarkChangedPaths", []))
    allowed = {"candidate/numerical-stability-decision-memo.md", "candidate/witness-ledger.json"}
    scope_clean = set(changed).issubset(allowed) and bool(changed)
    scope = 15 if scope_clean else 5 if scoreability == "scoreable" else 0

    synthesis_hits = sum(1 for anchor in SYNTHESIS_ANCHORS if anchor in memo_text)
    synthesis = round(synthesis_hits / len(SYNTHESIS_ANCHORS) * 20)

    lower_memo = memo_text.lower()
    falsification_hits = sum(1 for anchor in FALSIFICATION_ANCHORS if anchor in lower_memo)
    verification = round(falsification_hits / len(FALSIFICATION_ANCHORS) * 10)

    elapsed = None
    if prompt_path.exists() and summary_path.exists():
        elapsed = max(0.0, summary_path.stat().st_mtime - prompt_path.stat().st_mtime)
    runtime = score_time(elapsed) if scoreability == "scoreable" else 0

    total = correctness + role_fidelity + scope + synthesis + verification + runtime
    if not binary_pass and scoreability == "scoreable":
        total = min(total, 65)
    if scoreability != "scoreable":
        total = 0

    notes = list(witness_notes)
    notes.append(f"changed={len(changed)}")
    if not scope_clean:
        notes.append("scope not clean")

    return {
        "run_root": str(run_root),
        "row": summary.get("rowId", infer_row_from_path(run_root)),
        "model": summary.get("modelLabel"),
        "binary": binary,
        "scoreability": scoreability,
        "wrapper_exit_code": summary.get("wrapperExitCode"),
        "verification_passed": summary.get("verificationPassed"),
        "total": total,
        "correctness": correctness,
        "role_fidelity": role_fidelity,
        "scope": scope,
        "synthesis": synthesis,
        "verification": verification,
        "runtime": runtime,
        "elapsed_proxy_seconds": round(elapsed, 3) if elapsed is not None else None,
        "output_bytes": worker_output.stat().st_size if worker_output.exists() else None,
        "changed_paths": changed,
        "notes": notes,
    }


def print_markdown(results):
    print("| Row | Binary | Scoreability | Rubric | Correct | Role | Scope | Synthesis | Verify | Runtime | Elapsed | Output | Notes |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for result in results:
        print(
            "| {row} | {binary} | {scoreability} | {total} | {correctness} | {role} | {scope} | "
            "{synthesis} | {verification} | {runtime} | {elapsed} | {output} | {notes} |".format(
                row=result.get("row"),
                binary=result.get("binary"),
                scoreability=result.get("scoreability", ""),
                total=result.get("total", 0),
                correctness=result.get("correctness", 0),
                role=result.get("role_fidelity", 0),
                scope=result.get("scope", 0),
                synthesis=result.get("synthesis", 0),
                verification=result.get("verification", 0),
                runtime=result.get("runtime", 0),
                elapsed=result.get("elapsed_proxy_seconds"),
                output=result.get("output_bytes"),
                notes="; ".join(result.get("notes", [])),
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
