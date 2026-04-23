#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Score N31 MoM cylinder run roots.")
    parser.add_argument("run_roots", nargs="+", type=Path)
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def infer_row_from_path(run_root: Path):
    match = re.search(r"-(X\d)-", str(run_root))
    return match.group(1) if match else "unknown"


def format_run_root(run_root: Path, display_base: Path):
    try:
        return run_root.relative_to(display_base).as_posix()
    except ValueError:
        return str(run_root)


def classify_binary(summary: dict, worker_text: str):
    if summary.get("wrapperExitCode") == 0 and summary.get("verificationPassed") is True:
        return "PASS", "scoreable"
    if summary.get("wrapperExitCode") != 0 and (
        "Tool \"run_shell_command\" not found" in worker_text
        or "AbortError" in worker_text
        or "RESOURCE_EXHAUSTED" in worker_text
        or "quota" in worker_text.lower()
    ):
        return "ROUTE-FAIL", "runtime-route"
    if summary.get("wrapperExitCode") != 0 and summary.get("verificationPassed") is not False:
        return "RUNTIME-FAIL", "runtime-wrapper"
    return "FAIL", "scoreable"


def import_verifier(bundle_root: Path):
    verifier_path = bundle_root / "verifiers" / "check_mom_cylinder_solver.py"
    spec = importlib.util.spec_from_file_location("n31_mom_verifier_for_scoring", verifier_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import verifier from {verifier_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def verifier_failure_ids(bundle_root: Path):
    try:
        verifier = import_verifier(bundle_root)
        contract = load_json(bundle_root / "oracle" / "mom-contract.json")
        failures = verifier.evaluate_bundle(bundle_root, contract)
    except Exception as exc:  # noqa: BLE001
        return {"scorer-verifier-error"}, [f"scorer verifier error: {exc}"]
    return {failure.get("id", "unknown") for failure in failures}, [failure.get("detail", "") for failure in failures]


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


def score_output_size(bytes_count: int | None):
    if bytes_count is None:
        return 0
    if bytes_count <= 25000:
        return 5
    if bytes_count <= 120000:
        return 4
    if bytes_count <= 350000:
        return 2
    return 1


def score_one(run_root: Path, display_base: Path):
    meta_root = run_root / "meta"
    bundle_root = run_root / "run"
    summary_path = meta_root / "summary.json"
    worker_output = meta_root / "worker-output.txt"
    prompt_path = meta_root / "prompt.txt"

    if not summary_path.exists():
        return {
            "run_root": format_run_root(run_root, display_base),
            "row": infer_row_from_path(run_root),
            "binary": "NOT-RUN",
            "scoreability": "runtime-no-summary",
            "total": 0,
            "notes": ["missing summary.json"],
        }

    summary = load_json(summary_path)
    worker_text = worker_output.read_text(encoding="utf-8", errors="replace") if worker_output.exists() else ""
    binary, scoreability = classify_binary(summary, worker_text)
    failure_ids, failure_details = verifier_failure_ids(bundle_root) if bundle_root.exists() else ({"missing-bundle"}, [])

    public_case_ids = {"solver-case-ka2-primary-coarse", "solver-case-ka2-primary-refined"}
    hidden_case_ids = {"solver-case-ka1925-hidden-angle"}

    static = 5 if "solver-forbidden-marker" not in failure_ids else 0
    public_cases = 25 if not (public_case_ids & failure_ids) else 12 if len(public_case_ids - failure_ids) == 1 else 0
    hidden_case = 15 if not (hidden_case_ids & failure_ids) else 0
    convergence = 5 if "convergence-failed" not in failure_ids else 0
    correctness = static + public_cases + hidden_case + convergence

    report_failure_ids = {
        "report-json-invalid",
        "report-missing-fields",
        "report-method",
        "report-oracle-use",
        "report-missing-cases",
        "report-case-values",
        "report-convergence",
    }
    report = 15 if not (report_failure_ids & failure_ids) else max(0, 15 - 4 * len(report_failure_ids & failure_ids))
    notes_score = 10 if "notes-missing-phrases" not in failure_ids else 0

    changed = list(summary.get("benchmarkChangedPaths", []))
    allowed = {
        "candidate/workspace/mom_solver.py",
        "candidate/workspace/validation-report.json",
        "candidate/workspace/validation-notes.md",
    }
    scope_clean = bool(changed) and set(changed).issubset(allowed)
    scope = 10 if scope_clean else 3 if scoreability == "scoreable" else 0

    elapsed = None
    if prompt_path.exists() and summary_path.exists():
        elapsed = max(0.0, summary_path.stat().st_mtime - prompt_path.stat().st_mtime)
    runtime = score_time(elapsed) if scoreability == "scoreable" else 0
    output = score_output_size(worker_output.stat().st_size if worker_output.exists() else None) if scoreability == "scoreable" else 0

    total = correctness + report + notes_score + scope + runtime + output
    if binary != "PASS" and scoreability == "scoreable":
        total = min(total, 70)
    if scoreability != "scoreable":
        total = 0

    result_notes = []
    if failure_ids:
        result_notes.append("failures=" + ",".join(sorted(failure_ids)))
    if not scope_clean:
        result_notes.append("scope not clean")
    if failure_details:
        result_notes.extend([detail for detail in failure_details[:2] if detail])

    return {
        "run_root": format_run_root(run_root, display_base),
        "row": summary.get("rowId", infer_row_from_path(run_root)),
        "model": summary.get("modelLabel"),
        "binary": binary,
        "scoreability": scoreability,
        "wrapper_exit_code": summary.get("wrapperExitCode"),
        "verification_passed": summary.get("verificationPassed"),
        "total": total,
        "correctness": correctness,
        "report": report,
        "notes_score": notes_score,
        "scope": scope,
        "runtime": runtime,
        "output": output,
        "elapsed_proxy_seconds": round(elapsed, 3) if elapsed is not None else None,
        "output_bytes": worker_output.stat().st_size if worker_output.exists() else None,
        "changed_paths": changed,
        "notes": result_notes,
    }


def print_markdown(results):
    print("| Row | Binary | Scoreability | Rubric | Correct | Report | Notes | Scope | Runtime | Output | Elapsed | Bytes | Notes |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for result in results:
        print(
            "| {row} | {binary} | {scoreability} | {total} | {correctness} | {report} | {notes_score} | "
            "{scope} | {runtime} | {output} | {elapsed} | {bytes_count} | {notes} |".format(
                row=result.get("row"),
                binary=result.get("binary"),
                scoreability=result.get("scoreability", ""),
                total=result.get("total", 0),
                correctness=result.get("correctness", 0),
                report=result.get("report", 0),
                notes_score=result.get("notes_score", 0),
                scope=result.get("scope", 0),
                runtime=result.get("runtime", 0),
                output=result.get("output", 0),
                elapsed=result.get("elapsed_proxy_seconds"),
                bytes_count=result.get("output_bytes"),
                notes="; ".join(result.get("notes", [])),
            )
        )


def main():
    args = parse_args()
    display_base = Path.cwd().resolve()
    results = [score_one(path.resolve(), display_base) for path in args.run_roots]
    print_markdown(results)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        with args.json_out.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump({"results": results}, handle, indent=2)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
