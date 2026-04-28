#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


QUOTA_TERMS = [
    "quota",
    "rate limit",
    "resource exhausted",
    "usage limit",
    "too many requests",
    "insufficient_quota",
]


def parse_args():
    parser = argparse.ArgumentParser(description="Summarize N80 visual grounding runs.")
    parser.add_argument("summaries", nargs="+", type=Path, help="summary.json paths or run directories")
    parser.add_argument("--json-out", type=Path)
    return parser.parse_args()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def resolve_summary_path(path: Path) -> Path:
    if path.is_dir():
        return path / "summary.json"
    return path


def load_summary_entries(path: Path):
    summary_path = resolve_summary_path(path)
    payload = load_json(summary_path)
    if isinstance(payload, list):
        return summary_path, payload
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        return summary_path, payload["results"]
    raise ValueError(f"Unsupported summary format: {summary_path}")


def read_optional_text(path_text: str | None) -> str:
    if not path_text:
        return ""
    path = Path(path_text)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def load_optional_metrics(path_text: str | None):
    if not path_text:
        return {}
    path = Path(path_text)
    if not path.exists():
        return {}
    return load_json(path)


def repo_relative(path_text: str | None):
    if not path_text:
        return path_text
    path = Path(path_text)
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except (OSError, ValueError):
        return path_text


def has_quota_signature(text: str) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in QUOTA_TERMS)


def classify(entry: dict, metrics: dict):
    wrapper_exit = entry.get("wrapperExitCode")
    verifier_exit = entry.get("verifierExitCode")
    timed_out = bool(entry.get("timedOut"))
    output_text = read_optional_text(entry.get("workerOutput"))
    verify_text = read_optional_text(entry.get("verifyLog"))

    runtime_reason = None
    if timed_out:
        runtime_reason = "timeout"
    elif wrapper_exit not in (0, None):
        if has_quota_signature(output_text) or has_quota_signature(verify_text):
            runtime_reason = "quota/runtime"
        else:
            runtime_reason = "wrapper-nonzero"

    if runtime_reason:
        binary = "NOT-RUN"
        scoreable = False
    elif verifier_exit == 0 and metrics.get("verdict") == "PASS":
        binary = "PASS"
        scoreable = True
    else:
        binary = "FAIL"
        scoreable = True

    return binary, scoreable, runtime_reason


def normalize_entry(entry: dict, summary_path: Path):
    metrics = load_optional_metrics(entry.get("metrics"))
    binary, scoreable, runtime_reason = classify(entry, metrics)
    failures = metrics.get("failures") or []
    return {
        "rowId": entry.get("rowId"),
        "scenarioId": entry.get("scenarioId"),
        "model": entry.get("model"),
        "binary": binary,
        "scoreable": scoreable,
        "runtimeReason": runtime_reason,
        "wrapperExitCode": entry.get("wrapperExitCode"),
        "verifierExitCode": entry.get("verifierExitCode"),
        "score_0_100": metrics.get("score_0_100", entry.get("score_0_100")),
        "matched_count": metrics.get("matched_count"),
        "expected_count": metrics.get("expected_count"),
        "mean_error_px": metrics.get("mean_error_px", entry.get("mean_error_px")),
        "max_error_px": metrics.get("max_error_px", entry.get("max_error_px")),
        "false_positive_count": metrics.get("false_positive_count"),
        "failures": failures,
        "unmatched_expected": metrics.get("unmatched_expected", []),
        "outputBytes": entry.get("outputBytes"),
        "elapsedSeconds": entry.get("elapsedSeconds"),
        "summary": repo_relative(str(summary_path)),
        "workerOutput": repo_relative(entry.get("workerOutput")),
        "metrics": repo_relative(entry.get("metrics")),
        "verifyLog": repo_relative(entry.get("verifyLog")),
    }


def print_table(results: list[dict]):
    headers = ["row", "model", "binary", "score", "matched", "mean_px", "max_px", "output_bytes", "reason"]
    rows = []
    for result in results:
        matched = ""
        if result.get("matched_count") is not None and result.get("expected_count") is not None:
            matched = f"{result['matched_count']}/{result['expected_count']}"
        reason = result.get("runtimeReason") or ",".join(result.get("failures") or [])[:80]
        rows.append(
            [
                str(result.get("rowId") or ""),
                str(result.get("model") or ""),
                str(result.get("binary") or ""),
                str(result.get("score_0_100") if result.get("score_0_100") is not None else ""),
                matched,
                str(result.get("mean_error_px") if result.get("mean_error_px") is not None else ""),
                str(result.get("max_error_px") if result.get("max_error_px") is not None else ""),
                str(result.get("outputBytes") if result.get("outputBytes") is not None else ""),
                reason,
            ]
        )
    widths = [len(header) for header in headers]
    for row in rows:
        for index, value in enumerate(row):
            widths[index] = max(widths[index], len(value))
    print(" | ".join(header.ljust(widths[index]) for index, header in enumerate(headers)))
    print("-+-".join("-" * width for width in widths))
    for row in rows:
        print(" | ".join(value.ljust(widths[index]) for index, value in enumerate(row)))


def main():
    args = parse_args()
    results = []
    for path in args.summaries:
        summary_path, entries = load_summary_entries(path)
        for entry in entries:
            results.append(normalize_entry(entry, summary_path))

    payload = {
        "scenarioId": "N80",
        "generatedAtUtc": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_bytes((json.dumps(payload, indent=2) + "\n").encode("utf-8"))

    print_table(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
