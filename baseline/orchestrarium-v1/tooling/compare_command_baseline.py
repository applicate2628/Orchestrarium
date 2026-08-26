#!/usr/bin/env python3
"""Compare one candidate command result with its immutable baseline result.

Stage 0 permits an already-existing failure only when the candidate preserves
its normalized exit code and diagnostics. Successful diagnostics are compared
too, so dropped subchecks or new warnings cannot silently pass. Exit 0 = PASS,
exit 1 = semantic regression, exit 2 = invalid input or evidence-write failure.
Pure stdlib.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from typing import Pattern, Sequence

SCHEMA_VERSION = 1


class CommandBaselineError(RuntimeError):
    """Stable user-facing command-baseline error."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _read_log(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise CommandBaselineError(f"cannot read command log {path}: {exc}") from exc


def _compile_patterns(
    values: Sequence[str], *, label: str
) -> list[Pattern[str]]:
    compiled: list[Pattern[str]] = []
    for value in values:
        try:
            pattern = re.compile(value)
        except re.error as exc:
            raise CommandBaselineError(
                f"invalid {label} pattern {value!r}: {exc}"
            ) from exc
        if pattern.search("") is not None:
            raise CommandBaselineError(
                f"{label} pattern must not match empty text: {value!r}"
            )
        compiled.append(pattern)
    return compiled


def _normalized_text(
    data: bytes,
    *,
    root: str,
    ref: str,
    volatile_patterns: Sequence[Pattern[str]],
) -> bytes:
    text = data.decode("utf-8", errors="surrogateescape")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    root_variants = {
        root,
        root.rstrip("/\\"),
        root.replace("\\", "/"),
        root.replace("/", "\\"),
    }
    for variant in sorted(
        (item for item in root_variants if item), key=len, reverse=True
    ):
        text = text.replace(variant, "<ROOT>")

    if ref:
        text = text.replace(ref, "<REF>")

    for pattern in volatile_patterns:
        text = pattern.sub("<VOLATILE>", text)

    lines = [line.rstrip(" \t") for line in text.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    normalized = "\n".join(lines)
    if normalized:
        normalized += "\n"
    return normalized.encode("utf-8", errors="surrogateescape")


def _has_terminal_success_marker(
    text: str, patterns: Sequence[Pattern[str]]
) -> bool:
    terminal_text = text.rstrip("\n")
    if not terminal_text or not patterns:
        return False
    return any(
        match.end() == len(terminal_text)
        for pattern in patterns
        for match in pattern.finditer(terminal_text)
    )


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _result_record(
    raw: bytes, normalized: bytes, exit_code: int
) -> dict[str, object]:
    return {
        "exitCode": exit_code,
        "normalizedSha256": _sha256(normalized),
        "normalizedSizeBytes": len(normalized),
        "rawSha256": _sha256(raw),
        "rawSizeBytes": len(raw),
    }


def compare(args: argparse.Namespace) -> tuple[int, dict[str, object]]:
    if args.baseline_exit < 0 or args.candidate_exit < 0:
        raise CommandBaselineError("exit codes must be non-negative")

    patterns = _compile_patterns(args.volatile_pattern, label="volatile")
    success_patterns = _compile_patterns(args.success_pattern, label="success")
    baseline_raw = _read_log(args.baseline_log)
    candidate_raw = _read_log(args.candidate_log)
    baseline_normalized = _normalized_text(
        baseline_raw,
        root=args.baseline_root,
        ref=args.baseline_ref,
        volatile_patterns=patterns,
    )
    candidate_normalized = _normalized_text(
        candidate_raw,
        root=args.candidate_root,
        ref=args.candidate_ref,
        volatile_patterns=patterns,
    )

    same_diagnostics = baseline_normalized == candidate_normalized
    same_result = args.baseline_exit == args.candidate_exit and same_diagnostics

    if args.baseline_exit == 0 and args.candidate_exit == 0:
        if same_diagnostics:
            status = "PASS"
            classification = "preserved-success"
            return_code = 0
        else:
            status = "FAIL"
            classification = "drifted-success"
            return_code = 1
    elif args.baseline_exit == 0:
        status = "FAIL"
        classification = "new-failure"
        return_code = 1
    elif args.candidate_exit == 0:
        candidate_text = candidate_normalized.decode(
            "utf-8", errors="surrogateescape"
        )
        if _has_terminal_success_marker(candidate_text, success_patterns):
            status = "PASS"
            classification = "resolved-failure"
            return_code = 0
        else:
            status = "FAIL"
            classification = "unverified-resolution"
            return_code = 1
    elif same_result:
        status = "PASS"
        classification = "preserved-failure"
        return_code = 0
    else:
        status = "FAIL"
        classification = "drifted-failure"
        return_code = 1

    payload: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "name": args.name,
        "baselineRef": args.baseline_ref,
        "candidateRef": args.candidate_ref,
        "baseline": _result_record(
            baseline_raw,
            baseline_normalized,
            args.baseline_exit,
        ),
        "candidate": _result_record(
            candidate_raw,
            candidate_normalized,
            args.candidate_exit,
        ),
        "classification": classification,
        "status": status,
        "normalization": {
            "volatilePatterns": list(args.volatile_pattern),
        },
        "successVerification": {
            "patterns": list(args.success_pattern),
            "requiredForResolvedFailure": True,
            "markerMustTerminateDiagnostics": True,
        },
        "policy": {
            "baselineSuccessRequiresCandidateSuccess": True,
            "historicalFailureMayResolveWithDeclaredTerminalSuccessPattern": True,
            "historicalFailureMayRemainOnlyIfNormalizedResultMatches": True,
            "successfulDiagnosticsMustMatch": True,
        },
    }
    return return_code, payload


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", required=True)
    parser.add_argument("--baseline-exit", type=int, required=True)
    parser.add_argument("--candidate-exit", type=int, required=True)
    parser.add_argument("--baseline-log", type=Path, required=True)
    parser.add_argument("--candidate-log", type=Path, required=True)
    parser.add_argument("--baseline-root", required=True)
    parser.add_argument("--candidate-root", required=True)
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--candidate-ref", required=True)
    parser.add_argument("--volatile-pattern", action="append", default=[])
    parser.add_argument("--success-pattern", action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return_code, payload = compare(args)
        _atomic_write(args.output, _canonical_json(payload).encode("utf-8"))
    except (CommandBaselineError, OSError) as exc:
        print(f"COMMAND_BASELINE_INVALID: {exc}", file=sys.stderr)
        return 2

    marker = (
        f"RESULT: {payload['status']} command-baseline "
        f"name={payload['name']} classification={payload['classification']}"
    )
    stream = sys.stdout if return_code == 0 else sys.stderr
    print(marker, file=stream)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
