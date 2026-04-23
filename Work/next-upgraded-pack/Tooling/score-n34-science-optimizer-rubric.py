#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = (
    REPO_ROOT
    / "Scenarios-v2"
    / "N34-high-load-science-optimizer-gauntlet"
    / "oracle"
    / "optimizer-contract.json"
)


def parse_args():
    parser = argparse.ArgumentParser(description="Score N34 staged high-load science optimizer run roots.")
    parser.add_argument("run_roots", nargs="+", type=Path)
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def infer_row_from_path(run_root: Path):
    match = re.search(r"-(X\d)-", str(run_root))
    return match.group(1) if match else "unknown"


def format_run_root(run_root: Path, display_base: Path):
    try:
        return run_root.relative_to(display_base).as_posix()
    except ValueError:
        return str(run_root)


def case_root_from_arg(path: Path):
    path = Path(path)
    if (path / "meta" / "summary.json").exists():
        return path
    if path.name == "meta" and (path / "summary.json").exists():
        return path.parent
    return path


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
    verifier_path = bundle_root / "verifiers" / "check_science_optimizer.py"
    spec = importlib.util.spec_from_file_location("n34_science_optimizer_verifier_for_scoring", verifier_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import verifier from {verifier_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def verifier_result(bundle_root: Path):
    try:
        verifier = import_verifier(bundle_root)
        contract = load_json(bundle_root / "oracle" / "optimizer-contract.json")
        failures, metrics = verifier.evaluate_with_metrics(bundle_root, contract)
    except Exception as exc:  # noqa: BLE001
        return {"scorer-verifier-error"}, [], [f"scorer verifier error: {exc}"]
    return {failure.get("id", "unknown") for failure in failures}, metrics, [failure.get("detail", "") for failure in failures]


def score_runtime(metrics: list[dict], contract: dict):
    total = sum(float(item.get("runtime_seconds", 0.0)) for item in metrics if item.get("case_id") != "em-convergence")
    if total <= 2.5:
        return 20, total
    if total <= 6.0:
        return 16, total
    if total <= float(contract.get("max_total_solver_runtime_seconds", 11.5)):
        return 12, total
    return 0, total


def score_output(bytes_count: int | None):
    if bytes_count is None:
        return 0
    if bytes_count <= 60000:
        return 5
    if bytes_count <= 180000:
        return 3
    return 1


def score_one(run_root: Path, contract: dict, display_base: Path):
    run_root = case_root_from_arg(run_root.resolve())
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
            "rubric": 0,
            "notes": ["missing summary.json"],
        }

    summary = load_json(summary_path) or {}
    worker_text = worker_output.read_text(encoding="utf-8", errors="replace") if worker_output.exists() else ""
    binary, scoreability = classify_binary(summary, worker_text)
    failure_ids, metrics, failure_details = verifier_result(bundle_root) if bundle_root.exists() else ({"missing-bundle"}, [], [])

    em_failures = {item for item in failure_ids if item.startswith("em-case-") or item.startswith("em-density-") or item == "em-convergence-failed"}
    hydrogen_failures = {item for item in failure_ids if item.startswith("hydrogen-case-")}
    runtime_failures = {item for item in failure_ids if item.startswith("em-runtime-") or item.startswith("hydrogen-runtime-") or item == "total-solver-runtime"}
    stage_failures = {item for item in failure_ids if item.startswith("stage-ledger-")}
    perf_failures = {item for item in failure_ids if item.startswith("perf-ledger-")}
    report_failures = {item for item in failure_ids if item.startswith("report-")}

    em_correctness = 20 if not em_failures else max(0, 20 - 5 * len(em_failures))
    hydrogen_correctness = 20 if not hydrogen_failures else max(0, 20 - 6 * len(hydrogen_failures))
    correctness = em_correctness + hydrogen_correctness
    runtime, runtime_seconds = score_runtime(metrics, contract)
    if runtime_failures:
        runtime = min(runtime, 5)
    staged = (8 if not stage_failures else 0) + (7 if not perf_failures else 0)
    report = 5 if not report_failures else max(0, 5 - len(report_failures))
    notes = 5 if "notes-missing-phrases" not in failure_ids else 0

    changed = list(summary.get("benchmarkChangedPaths", []))
    required = set(contract.get("expected_metadata", {}).get("allowed_change_surface", []))
    scope = 10 if sorted(changed) == sorted(required) else 6 if changed and set(changed).issubset(required) else 0
    output = score_output(worker_output.stat().st_size if worker_output.exists() else None) if scoreability == "scoreable" else 0

    rubric = correctness + runtime + staged + report + notes + scope + output
    if binary != "PASS" and scoreability == "scoreable":
        rubric = min(rubric, 72)
    if scoreability != "scoreable":
        rubric = 0

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
        "rubric": rubric,
        "correctness": correctness,
        "em_correctness": em_correctness,
        "hydrogen_correctness": hydrogen_correctness,
        "runtime": runtime,
        "runtime_seconds": round(runtime_seconds, 3),
        "staged": staged,
        "report": report,
        "notes_score": notes,
        "scope": scope,
        "output": output,
        "output_bytes": worker_output.stat().st_size if worker_output.exists() else None,
        "changed_paths": changed,
        "failure_ids": sorted(failure_ids),
        "notes": result_notes,
    }


def print_markdown(results):
    print("| Row | Binary | Scoreability | Rubric | Correct | EM | H | Runtime | Runtime s | Staged | Report | Notes | Scope | Output | Bytes | Failures |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for result in results:
        print(
            "| {row} | {binary} | {scoreability} | {rubric} | {correctness} | {em} | {hydrogen} | "
            "{runtime} | {runtime_seconds} | {staged} | {report} | {notes_score} | {scope} | {output} | {bytes_count} | {failures} |".format(
                row=result.get("row"),
                binary=result.get("binary"),
                scoreability=result.get("scoreability", ""),
                rubric=result.get("rubric", 0),
                correctness=result.get("correctness", 0),
                em=result.get("em_correctness", 0),
                hydrogen=result.get("hydrogen_correctness", 0),
                runtime=result.get("runtime", 0),
                runtime_seconds=result.get("runtime_seconds"),
                staged=result.get("staged", 0),
                report=result.get("report", 0),
                notes_score=result.get("notes_score", 0),
                scope=result.get("scope", 0),
                output=result.get("output", 0),
                bytes_count=result.get("output_bytes"),
                failures=", ".join(result.get("failure_ids", [])),
            )
        )


def main():
    args = parse_args()
    contract = load_json(CONTRACT_PATH) or {}
    display_base = Path.cwd().resolve()
    results = [score_one(path, contract, display_base) for path in args.run_roots]
    print_markdown(results)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        with args.json_out.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump({"results": results}, handle, indent=2)
            handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
