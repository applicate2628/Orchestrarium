#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Score N32 dual physics analytical-oracle run roots.")
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
    verifier_path = bundle_root / "verifiers" / "check_dual_physics_oracle.py"
    spec = importlib.util.spec_from_file_location("n32_dual_physics_verifier_for_scoring", verifier_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import verifier from {verifier_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def verifier_result(bundle_root: Path):
    try:
        verifier = import_verifier(bundle_root)
        contract = load_json(bundle_root / "oracle" / "dual-physics-contract.json")
        failures, metrics = verifier.evaluate_with_metrics(bundle_root, contract)
    except Exception as exc:  # noqa: BLE001
        return {"scorer-verifier-error"}, [], [f"scorer verifier error: {exc}"]
    return {failure.get("id", "unknown") for failure in failures}, metrics, [failure.get("detail", "") for failure in failures]


def score_solver_runtime(metrics: list[dict]):
    total = sum(float(item.get("runtime_seconds", 0.0)) for item in metrics if item.get("case_id") != "em-convergence")
    if total <= 2.5:
        return 25, total
    if total <= 5.0:
        return 20, total
    if total <= 9.0:
        return 12, total
    if total <= 15.0:
        return 6, total
    return 0, total


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
    failure_ids, metrics, failure_details = verifier_result(bundle_root) if bundle_root.exists() else ({"missing-bundle"}, [], [])

    em_failures = {item for item in failure_ids if item.startswith("em-case-") or item.startswith("em-density-") or item == "em-convergence-failed"}
    hydrogen_failures = {item for item in failure_ids if item.startswith("hydrogen-case-")}
    runtime_failures = {item for item in failure_ids if item.startswith("em-runtime-") or item.startswith("hydrogen-runtime-")}
    report_failures = {item for item in failure_ids if item.startswith("report-")}

    em_correctness = 25 if not em_failures else max(0, 25 - 8 * len(em_failures))
    hydrogen_correctness = 25 if not hydrogen_failures else max(0, 25 - 8 * len(hydrogen_failures))
    correctness = em_correctness + hydrogen_correctness

    solver_runtime, solver_runtime_seconds = score_solver_runtime(metrics)
    if runtime_failures:
        solver_runtime = min(solver_runtime, 5)
    report = 5 if not report_failures else max(0, 5 - len(report_failures))
    notes_score = 5 if "notes-missing-phrases" not in failure_ids else 0

    changed = list(summary.get("benchmarkChangedPaths", []))
    allowed = {
        "candidate/workspace/dual_physics.py",
        "candidate/workspace/validation-report.json",
        "candidate/workspace/validation-notes.md",
    }
    scope_clean = bool(changed) and set(changed).issubset(allowed)
    scope = 10 if scope_clean else 3 if scoreability == "scoreable" else 0
    output = score_output_size(worker_output.stat().st_size if worker_output.exists() else None) if scoreability == "scoreable" else 0

    total = correctness + solver_runtime + report + notes_score + scope + output
    if binary != "PASS" and scoreability == "scoreable":
        total = min(total, 72)
    if scoreability != "scoreable":
        total = 0

    result_notes = []
    if failure_ids:
        result_notes.append("failures=" + ",".join(sorted(failure_ids)))
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
        "em_correctness": em_correctness,
        "hydrogen_correctness": hydrogen_correctness,
        "solver_runtime": solver_runtime,
        "solver_runtime_seconds": round(solver_runtime_seconds, 3),
        "report": report,
        "notes_score": notes_score,
        "scope": scope,
        "output": output,
        "output_bytes": worker_output.stat().st_size if worker_output.exists() else None,
        "changed_paths": changed,
        "notes": result_notes,
    }


def print_markdown(results):
    print("| Row | Binary | Scoreability | Rubric | Correct | EM | H | Solver runtime | Solver s | Report | Notes | Scope | Output | Bytes | Notes |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for result in results:
        print(
            "| {row} | {binary} | {scoreability} | {total} | {correctness} | {em} | {hydrogen} | "
            "{solver_runtime} | {solver_seconds} | {report} | {notes_score} | {scope} | {output} | {bytes_count} | {notes} |".format(
                row=result.get("row"),
                binary=result.get("binary"),
                scoreability=result.get("scoreability", ""),
                total=result.get("total", 0),
                correctness=result.get("correctness", 0),
                em=result.get("em_correctness", 0),
                hydrogen=result.get("hydrogen_correctness", 0),
                solver_runtime=result.get("solver_runtime", 0),
                solver_seconds=result.get("solver_runtime_seconds"),
                report=result.get("report", 0),
                notes_score=result.get("notes_score", 0),
                scope=result.get("scope", 0),
                output=result.get("output", 0),
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
