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
    / "N52-interface-refactor-compact-operator-budget"
    / "oracle"
    / "interface-refactor-contract.json"
)


def parse_args():
    parser = argparse.ArgumentParser(description="Score N52 interface-refactor compact operator-budget run roots.")
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


def failed_invariants(summary: dict):
    failed = []
    for result in summary.get("verificationResults", []):
        if result.get("passed"):
            continue
        log = Path(result.get("log", ""))
        if not log.exists():
            continue
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            marker = "Failed invariant: "
            if marker in line:
                invariant = line.split(marker, 1)[1].split("::", 1)[0].strip()
                failed.append(invariant)
    return sorted(set(failed))


def score_one(run_root: Path, contract: dict, display_base: Path):
    run_root = case_root_from_arg(run_root.resolve())
    meta_root = run_root / "meta"
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
    failed = failed_invariants(summary)
    failed_set = set(failed)
    operator_budget_pass = any(
        result.get("passed") and "check_operator_budget.py" in result.get("command", "")
        for result in summary.get("verificationResults", [])
    )

    interface_failures = {
        "legacy-interface-static",
        "result-models",
        "legacy-interface-removed",
    }
    hidden_failures = {
        "session-lookup-contract",
        "policy-contract",
        "router-contract",
        "integration-contract",
        "report-contract",
    }
    ledger_failures = {
        "refactor-ledger-schema",
        "refactor-ledger-interface-map",
        "refactor-ledger-call-sites",
        "refactor-ledger-compatibility",
        "refactor-ledger-validation",
        "refactor-ledger-patch-budget",
    }

    interface = max(0, 30 - 10 * len(failed_set & interface_failures))
    hidden = max(0, 30 - 6 * len(failed_set & hidden_failures))
    ledger = max(0, 15 - 3 * len(failed_set & ledger_failures))
    tests = 10 if "visible-test-markers" not in failed_set else 0

    changed = list(summary.get("benchmarkChangedPaths", []))
    patch = 10 if sorted(changed) == sorted(contract["requiredChangedPaths"]) else 0
    operator_budget = 5 if scoreability == "scoreable" and operator_budget_pass else 0
    rubric = interface + hidden + ledger + tests + patch + operator_budget
    if binary != "PASS" and scoreability == "scoreable":
        rubric = min(rubric, 70)
    if scoreability != "scoreable":
        rubric = 0

    return {
        "run_root": format_run_root(run_root, display_base),
        "row": summary.get("rowId", infer_row_from_path(run_root)),
        "model": summary.get("modelLabel"),
        "binary": binary,
        "scoreability": scoreability,
        "wrapper_exit_code": summary.get("wrapperExitCode"),
        "verification_passed": summary.get("verificationPassed"),
        "rubric": rubric,
        "interface": interface,
        "hidden": hidden,
        "ledger": ledger,
        "tests": tests,
        "patch": patch,
        "operator_budget": operator_budget,
        "output_bytes": worker_output.stat().st_size if worker_output.exists() else None,
        "changed_paths": changed,
        "failed_invariants": failed,
        "notes": (["operator budget pass" if operator_budget_pass else "operator budget fail"]
                  + (["failed invariants: " + ", ".join(failed)] if failed else [])),
    }


def print_markdown(results):
    print("| Row | Binary | Scoreability | Rubric | Interface | Hidden | Ledger | Tests | Patch | Budget | Bytes | Failed invariants |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
    for result in results:
        print(
            "| {row} | {binary} | {scoreability} | {rubric} | {interface} | {hidden} | "
            "{ledger} | {tests} | {patch} | {budget} | {bytes_count} | {failed} |".format(
                row=result.get("row"),
                binary=result.get("binary"),
                scoreability=result.get("scoreability", ""),
                rubric=result.get("rubric", 0),
                interface=result.get("interface", 0),
                hidden=result.get("hidden", 0),
                ledger=result.get("ledger", 0),
                tests=result.get("tests", 0),
                patch=result.get("patch", 0),
                budget=result.get("operator_budget", 0),
                bytes_count=result.get("output_bytes"),
                failed=", ".join(result.get("failed_invariants", [])),
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
