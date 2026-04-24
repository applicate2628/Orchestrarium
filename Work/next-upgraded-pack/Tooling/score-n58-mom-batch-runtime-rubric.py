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
    / "N58-mom-batch-runtime-analytic-oracle"
    / "oracle"
    / "optimizer-contract.json"
)
SCIENCE_VERIFIER = "check_science_optimizer.py"
MOM_BATCH_VERIFIER = "check_mom_batch_runtime.py"


def parse_args():
    parser = argparse.ArgumentParser(description="Score N58 MoM batch-runtime operator-budget run roots.")
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
        'Tool "run_shell_command" not found' in worker_text
        or "AbortError" in worker_text
        or "RESOURCE_EXHAUSTED" in worker_text
        or "quota" in worker_text.lower()
    ):
        return "ROUTE-FAIL", "runtime-route"
    if summary.get("wrapperExitCode") != 0 and summary.get("verificationPassed") is not False:
        return "RUNTIME-FAIL", "runtime-wrapper"
    return "FAIL", "scoreable"


def import_verifier(bundle_root: Path, verifier_name: str, module_name: str):
    verifier_path = bundle_root / "verifiers" / verifier_name
    spec = importlib.util.spec_from_file_location(module_name, verifier_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not import verifier from {verifier_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def normalize_failures(failures):
    ids = set()
    details = []
    for failure in failures or []:
        if isinstance(failure, dict):
            ids.add(str(failure.get("id", "unknown")))
            details.append(str(failure.get("detail", "")))
        else:
            ids.add(str(failure))
            details.append(str(failure))
    return ids, details


def run_verifier(bundle_root: Path, contract: dict, verifier_name: str, module_name: str, missing_id: str):
    verifier_path = bundle_root / "verifiers" / verifier_name
    if not verifier_path.exists():
        return {missing_id}, [], [f"missing verifier: {verifier_name}"], False
    try:
        verifier = import_verifier(bundle_root, verifier_name, module_name)
        metrics = []
        if hasattr(verifier, "evaluate_with_metrics"):
            failures, metrics = verifier.evaluate_with_metrics(bundle_root, contract)
        elif hasattr(verifier, "evaluate_bundle"):
            failures = verifier.evaluate_bundle(bundle_root, contract)
            last_metrics = getattr(verifier, "LAST_METRICS", {})
            if isinstance(last_metrics, dict):
                metrics = last_metrics.get("metrics", [])
        elif hasattr(verifier, "evaluate"):
            failures = verifier.evaluate(bundle_root, contract)
        else:
            return {f"{missing_id}-entrypoint"}, [], [f"{verifier_name} has no evaluator entrypoint"], False
    except Exception as exc:  # noqa: BLE001
        return {f"{missing_id}-error"}, [], [f"{verifier_name} scorer error: {exc}"], False
    ids, details = normalize_failures(failures)
    return ids, metrics or [], details, True


def read_metrics_json(path: Path):
    data = load_json(path)
    if not isinstance(data, dict):
        return set(), [], []
    failures = data.get("failures") or data.get("failure_ids") or []
    metrics = data.get("metrics") or data.get("mom_batch_metrics") or []
    ids, details = normalize_failures(failures)
    return ids, metrics if isinstance(metrics, list) else [], details


def metrics_artifact_result(meta_root: Path, bundle_root: Path):
    ids = set()
    metrics = []
    details = []
    seen = set()
    for root in (meta_root, bundle_root):
        if not root.exists():
            continue
        for path in root.glob("**/*metrics*.json"):
            if path in seen:
                continue
            seen.add(path)
            path_ids, path_metrics, path_details = read_metrics_json(path)
            if path_ids or path_metrics:
                ids.update(path_ids)
                metrics.extend(path_metrics)
                details.extend([f"{path.name}: {detail}" for detail in path_details if detail])
    return ids, metrics, details


def extract_failure_ids_from_text(text: str):
    ids = set(re.findall(r"ERROR\[([^\]]+)\]", text))
    ids.update(re.findall(r"Failed invariant:\s*([A-Za-z0-9_.:-]+)", text))
    return ids


def extract_mom_batch_metrics_from_text(text: str, contract: dict):
    metrics = []
    case_ids = {case.get("case_id") for case in contract.get("mom_batch_cases", []) if isinstance(case, dict)}
    case_pattern = re.compile(
        r"(?P<case>batch-[A-Za-z0-9_.-]+).*?(?:runtime_seconds|runtime)\D+(?P<seconds>\d+(?:\.\d+)?)\s*s?",
        re.IGNORECASE,
    )
    for match in case_pattern.finditer(text):
        case_id = match.group("case")
        if case_id in case_ids:
            metrics.append({"domain": "mom_batch", "case_id": case_id, "runtime_seconds": float(match.group("seconds"))})
    total_match = re.search(
        r"(?:total[-_ ]*)?batch[-_ ]runtime(?:_seconds)?\D+(?P<seconds>\d+(?:\.\d+)?)\s*s?",
        text,
        re.IGNORECASE,
    )
    if total_match:
        metrics.append({"domain": "mom_batch", "case_id": "total-batch-runtime", "runtime_seconds": float(total_match.group("seconds"))})
    return metrics


def verifier_log_result(summary: dict, contract: dict):
    ids = set()
    metrics = []
    details = []
    for result in summary.get("verificationResults", []):
        command = str(result.get("command", ""))
        log_path = str(result.get("log", ""))
        if MOM_BATCH_VERIFIER not in command and MOM_BATCH_VERIFIER not in log_path:
            continue
        text = ""
        if log_path:
            path = Path(log_path)
            if path.exists():
                text = path.read_text(encoding="utf-8", errors="replace")
        local_ids = extract_failure_ids_from_text(text)
        ids.update(local_ids)
        metrics.extend(extract_mom_batch_metrics_from_text(text, contract))
        if result.get("passed") is False and not local_ids:
            ids.add("mom-batch-verifier-failed")
        details.append("mom batch verifier log pass" if result.get("passed") else "mom batch verifier log fail")
    return ids, metrics, details


def verifier_result(bundle_root: Path, meta_root: Path, summary: dict):
    contract = load_json(bundle_root / "oracle" / "optimizer-contract.json") or {}
    science_ids, science_metrics, science_details, _ = run_verifier(
        bundle_root,
        contract,
        SCIENCE_VERIFIER,
        "n58_science_optimizer_verifier_for_scoring",
        "science-verifier-missing",
    )
    batch_ids, batch_metrics, batch_details, batch_ran = run_verifier(
        bundle_root,
        contract,
        MOM_BATCH_VERIFIER,
        "n58_mom_batch_runtime_verifier_for_scoring",
        "mom-batch-verifier-missing",
    )
    artifact_ids, artifact_metrics, artifact_details = metrics_artifact_result(meta_root, bundle_root)
    log_ids, log_metrics, log_details = verifier_log_result(summary, contract)
    ids = science_ids | batch_ids | artifact_ids | log_ids
    metrics = science_metrics + batch_metrics + artifact_metrics + log_metrics
    details = science_details + batch_details + artifact_details + log_details
    sources = []
    if batch_ran:
        sources.append("import")
    if batch_metrics or artifact_metrics:
        sources.append("metrics-json")
    if log_ids or log_metrics or log_details:
        sources.append("verifier-log")
    return ids, metrics, details, sorted(set(sources))


def is_mom_batch_metric(item: dict, contract: dict):
    case_ids = {case.get("case_id") for case in contract.get("mom_batch_cases", []) if isinstance(case, dict)}
    case_id = item.get("case_id")
    domain = str(item.get("domain", "")).replace("_", "-")
    return case_id in case_ids or case_id == "total-batch-runtime" or domain == "mom-batch"


def score_runtime(metrics: list[dict], contract: dict):
    total = sum(
        float(item.get("runtime_seconds", 0.0))
        for item in metrics
        if item.get("case_id") not in {"em-convergence", "total-solver-runtime", "total-batch-runtime"}
        and not is_mom_batch_metric(item, contract)
    )
    if total <= 2.5:
        return 20, total
    if total <= 6.0:
        return 16, total
    if total <= float(contract.get("max_total_solver_runtime_seconds", 11.5)):
        return 12, total
    return 0, total


def mom_batch_runtime_seconds(metrics: list[dict], contract: dict):
    totals = [
        float(item.get("runtime_seconds", 0.0))
        for item in metrics
        if item.get("case_id") == "total-batch-runtime" or str(item.get("domain", "")).replace("_", "-") == "mom-batch-total"
    ]
    if totals:
        return max(totals)
    batch_values = [
        float(item.get("runtime_seconds", 0.0))
        for item in metrics
        if is_mom_batch_metric(item, contract) and item.get("case_id") != "total-batch-runtime"
    ]
    return sum(batch_values) if batch_values else None


def score_mom_batch_runtime(seconds: float | None, contract: dict):
    if seconds is None:
        return None
    budget = float(contract.get("max_total_batch_runtime_seconds", 13.0))
    if seconds <= 0.5 * budget:
        return 20
    if seconds <= budget:
        return 16
    if seconds <= 1.25 * budget:
        return 8
    return 0


def classify_failure_buckets(failure_ids: set[str], operator_budget_pass: bool):
    buckets = set()
    api_markers = {
        "mom-batch-api-missing",
        "solver-missing-marker-em_batch_factor_reuse",
        "mom-batch-verifier-missing",
        "mom-batch-verifier-missing-entrypoint",
        "mom-batch-verifier-missing-error",
    }
    runtime_markers = {"total-batch-runtime", "mom-batch-total-runtime"}
    for item in failure_ids:
        lowered = item.lower()
        if item in api_markers or lowered.startswith("mom-batch-api") or "factor_reuse" in lowered:
            buckets.add("mom-batch-api")
        elif item in runtime_markers or (("runtime" in lowered) and ("batch" in lowered or lowered.startswith("em-runtime") or lowered.startswith("hydrogen-runtime"))):
            buckets.add("mom-batch-runtime" if "batch" in lowered else "runtime")
        elif lowered.startswith("mom-batch") or lowered.startswith("batch-") or "batch" in lowered:
            buckets.add("mom-batch-accuracy")
        elif "operator" in lowered and "budget" in lowered:
            buckets.add("operator-budget")
    if not operator_budget_pass:
        buckets.add("operator-budget")
    return sorted(buckets)


def score_mom_batch(failure_ids: set[str], evidence_sources: list[str]):
    buckets = classify_failure_buckets(failure_ids, operator_budget_pass=True)
    if "mom-batch-api" in buckets:
        return 0
    if "mom-batch-accuracy" in buckets:
        accuracy_failures = [item for item in failure_ids if "batch" in item.lower()]
        return max(0, 20 - 8 * len(accuracy_failures))
    if "mom-batch-runtime" in buckets:
        return 14
    if evidence_sources:
        return 20
    return 0


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
    failure_ids, metrics, failure_details, mom_evidence_sources = (
        verifier_result(bundle_root, meta_root, summary) if bundle_root.exists() else ({"missing-bundle"}, [], [], [])
    )
    operator_budget_pass = any(
        result.get("passed") and "check_operator_budget.py" in result.get("command", "")
        for result in summary.get("verificationResults", [])
    )

    em_failures = {item for item in failure_ids if item.startswith("em-case-") or item.startswith("em-density-") or item == "em-convergence-failed"}
    hydrogen_failures = {item for item in failure_ids if item.startswith("hydrogen-case-")}
    runtime_failures = {
        item
        for item in failure_ids
        if item.startswith("em-runtime-")
        or item.startswith("hydrogen-runtime-")
        or item in {"total-solver-runtime", "solver-total-runtime", "total-batch-runtime"}
        or (item.startswith("mom-batch") and "runtime" in item)
    }
    stage_failures = {item for item in failure_ids if item.startswith("stage-ledger-")}
    perf_failures = {item for item in failure_ids if item.startswith("perf-ledger-")}
    report_failures = {item for item in failure_ids if item.startswith("report-")}

    em_correctness = 15 if not em_failures else max(0, 15 - 4 * len(em_failures))
    hydrogen_correctness = 15 if not hydrogen_failures else max(0, 15 - 5 * len(hydrogen_failures))
    mom_batch = score_mom_batch(failure_ids, mom_evidence_sources)
    correctness = em_correctness + hydrogen_correctness + mom_batch
    runtime, runtime_seconds = score_runtime(metrics, contract)
    batch_runtime_seconds = mom_batch_runtime_seconds(metrics, contract)
    batch_runtime_score = score_mom_batch_runtime(batch_runtime_seconds, contract)
    if batch_runtime_score is not None:
        runtime = min(runtime, batch_runtime_score)
    if runtime_failures:
        runtime = min(runtime, 5)
    staged = (5 if not stage_failures else 0) + (5 if not perf_failures else 0)
    report = 5 if not report_failures else max(0, 5 - len(report_failures))
    notes = 5 if "notes-missing-phrases" not in failure_ids else 0

    changed = list(summary.get("benchmarkChangedPaths", []))
    required = set(contract.get("expected_metadata", {}).get("allowed_change_surface", []))
    scope = 5 if sorted(changed) == sorted(required) else 3 if changed and set(changed).issubset(required) else 0
    operator_budget = 5 if scoreability == "scoreable" and operator_budget_pass else 0

    rubric = correctness + runtime + staged + report + notes + scope + operator_budget
    failure_buckets = classify_failure_buckets(failure_ids, operator_budget_pass)
    if binary == "PASS" and scoreability == "scoreable" and failure_ids:
        binary = "FAIL"
    if binary != "PASS" and scoreability == "scoreable":
        rubric = min(rubric, 70)
    if scoreability != "scoreable":
        rubric = 0

    result_notes = []
    if failure_ids:
        result_notes.append("failures=" + ",".join(sorted(failure_ids)))
    result_notes.append("operator budget pass" if operator_budget_pass else "operator budget fail")
    if mom_evidence_sources:
        result_notes.append("mom batch evidence=" + ",".join(mom_evidence_sources))
    if batch_runtime_seconds is not None:
        result_notes.append(f"mom batch runtime={batch_runtime_seconds:.3f}s")
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
        "mom_batch": mom_batch,
        "mom_batch_pass": bool(mom_evidence_sources) and not any(bucket.startswith("mom-batch") for bucket in failure_buckets),
        "runtime": runtime,
        "runtime_seconds": round(runtime_seconds, 3),
        "mom_batch_runtime_seconds": round(batch_runtime_seconds, 3) if batch_runtime_seconds is not None else None,
        "staged": staged,
        "report": report,
        "notes_score": notes,
        "scope": scope,
        "operator_budget": operator_budget,
        "operator_budget_pass": operator_budget_pass,
        "output_bytes": worker_output.stat().st_size if worker_output.exists() else None,
        "changed_paths": changed,
        "failure_buckets": failure_buckets,
        "mom_batch_evidence_sources": mom_evidence_sources,
        "failure_ids": sorted(failure_ids),
        "notes": result_notes,
    }


def print_markdown(results):
    print("| Row | Binary | Scoreability | Rubric | Correct | EM | H | Batch | Runtime | Runtime s | Batch s | Staged | Report | Notes | Scope | Budget | Bytes | Buckets | Failures |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|")
    for result in results:
        print(
            "| {row} | {binary} | {scoreability} | {rubric} | {correctness} | {em} | {hydrogen} | {mom_batch} | "
            "{runtime} | {runtime_seconds} | {batch_runtime_seconds} | {staged} | {report} | {notes_score} | {scope} | "
            "{operator_budget} | {bytes_count} | {buckets} | {failures} |".format(
                row=result.get("row"),
                binary=result.get("binary"),
                scoreability=result.get("scoreability", ""),
                rubric=result.get("rubric", 0),
                correctness=result.get("correctness", 0),
                em=result.get("em_correctness", 0),
                hydrogen=result.get("hydrogen_correctness", 0),
                mom_batch=result.get("mom_batch", 0),
                runtime=result.get("runtime", 0),
                runtime_seconds=result.get("runtime_seconds"),
                batch_runtime_seconds=result.get("mom_batch_runtime_seconds"),
                staged=result.get("staged", 0),
                report=result.get("report", 0),
                notes_score=result.get("notes_score", 0),
                scope=result.get("scope", 0),
                operator_budget=result.get("operator_budget", 0),
                bytes_count=result.get("output_bytes"),
                buckets=", ".join(result.get("failure_buckets", [])),
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
