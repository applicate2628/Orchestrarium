#!/usr/bin/env python3
"""Compare one candidate validator result with its immutable baseline result.

Exit 0 means the declared validator contract is preserved or a historical
failure is verifiably resolved. Exit 1 means semantic drift. Exit 2 means
invalid or unavailable evidence. Only Python's standard library is used.
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

SCHEMA_VERSION = 2
OBJECT_ID = re.compile(r"[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?")
HEX = frozenset("0123456789abcdefABCDEF")
PATH_WORD = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")


class CommandBaselineError(RuntimeError):
    """Stable user-facing command-baseline error."""


def _semantic_failure_exit(value: str) -> int:
    try:
        exit_code = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"semantic failure exit must be an integer: {value!r}"
        ) from exc
    if not 1 <= exit_code <= 123:
        raise argparse.ArgumentTypeError(
            "semantic failure exit must be between 1 and 123"
        )
    return exit_code


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _read_log(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise CommandBaselineError(f"cannot read command log {path}: {exc}") from exc


def _compile_patterns(values: Sequence[str], *, label: str) -> tuple[Pattern[str], ...]:
    compiled: list[Pattern[str]] = []
    for value in values:
        try:
            pattern = re.compile(value)
        except re.error as exc:
            raise CommandBaselineError(f"invalid {label} pattern {value!r}: {exc}") from exc
        if pattern.search("") is not None:
            raise CommandBaselineError(f"{label} pattern must not match empty text: {value!r}")
        compiled.append(pattern)
    return tuple(compiled)


def _exact_ref(value: str, *, label: str) -> str:
    if not OBJECT_ID.fullmatch(value):
        raise CommandBaselineError(
            f"{label} ref must be an exact 40- or 64-character hexadecimal object ID"
        )
    return value.lower()


def _canonical_root(value: str, *, label: str) -> str:
    root = value.rstrip("/\\")
    if not root:
        raise CommandBaselineError(f"{label} root must be non-empty")
    return root


def _root_variants(root: str) -> tuple[str, ...]:
    variants = {root, root.replace("\\", "/"), root.replace("/", "\\")}
    return tuple(sorted((item for item in variants if item), key=len, reverse=True))


def _replace_bounded(text: str, needle: str, replacement: str, *, hex_token: bool) -> str:
    if not needle:
        return text
    result: list[str] = []
    cursor = 0
    while True:
        index = text.find(needle, cursor)
        if index < 0:
            result.append(text[cursor:])
            break
        end = index + len(needle)
        before = text[index - 1] if index else ""
        after = text[end] if end < len(text) else ""
        if hex_token:
            bounded = (not before or before not in HEX) and (not after or after not in HEX)
        else:
            bounded = (not before or before not in PATH_WORD) and (not after or after not in PATH_WORD)
        if bounded:
            result.append(text[cursor:index])
            result.append(replacement)
            cursor = end
        else:
            result.append(text[cursor:end])
            cursor = end
    return "".join(result)


def _normalized_text(data: bytes, *, root: str, ref: str, volatile_patterns: Sequence[Pattern[str]]) -> bytes:
    text = data.decode("utf-8", errors="surrogateescape")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    for variant in _root_variants(root):
        text = _replace_bounded(text, variant, "<ROOT>", hex_token=False)
    text = _replace_bounded(text, ref, "<REF>", hex_token=True)
    for pattern in volatile_patterns:
        text = pattern.sub("<VOLATILE>", text)
    lines = [line.rstrip(" \t") for line in text.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    normalized = "\n".join(lines)
    if normalized:
        normalized += "\n"
    return normalized.encode("utf-8", errors="surrogateescape")


def _has_terminal_marker(text: str, patterns: Sequence[Pattern[str]]) -> bool:
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
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
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


def _result_record(raw: bytes, normalized: bytes, exit_code: int) -> dict[str, object]:
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
    baseline_ref = _exact_ref(args.baseline_ref, label="baseline")
    candidate_ref = _exact_ref(args.candidate_ref, label="candidate")
    baseline_root = _canonical_root(args.baseline_root, label="baseline")
    candidate_root = _canonical_root(args.candidate_root, label="candidate")
    if baseline_root.replace("\\", "/") == candidate_root.replace("\\", "/"):
        raise CommandBaselineError("baseline and candidate roots must be distinct")

    semantic_failure_exits = sorted(set(args.semantic_failure_exit))
    volatile_patterns = _compile_patterns(args.volatile_pattern, label="volatile")
    success_patterns = _compile_patterns(args.success_pattern, label="success")
    failure_patterns = _compile_patterns(args.failure_pattern, label="failure")
    baseline_raw = _read_log(args.baseline_log)
    candidate_raw = _read_log(args.candidate_log)
    baseline_normalized = _normalized_text(
        baseline_raw, root=baseline_root, ref=baseline_ref, volatile_patterns=volatile_patterns
    )
    candidate_normalized = _normalized_text(
        candidate_raw, root=candidate_root, ref=candidate_ref, volatile_patterns=volatile_patterns
    )
    baseline_text = baseline_normalized.decode("utf-8", errors="surrogateescape")
    candidate_text = candidate_normalized.decode("utf-8", errors="surrogateescape")
    same_diagnostics = baseline_normalized == candidate_normalized
    allowed_result_exits = {0, *semantic_failure_exits}
    operational_exit: dict[str, int] = {}
    if args.baseline_exit not in allowed_result_exits:
        operational_exit["baseline"] = args.baseline_exit
    if args.candidate_exit not in allowed_result_exits:
        operational_exit["candidate"] = args.candidate_exit

    baseline_success_verified = (
        args.baseline_exit == 0
        and _has_terminal_marker(baseline_text, success_patterns)
    )
    candidate_success_verified = (
        args.candidate_exit == 0
        and _has_terminal_marker(candidate_text, success_patterns)
    )
    baseline_failure_verified = (
        args.baseline_exit in semantic_failure_exits
        and _has_terminal_marker(baseline_text, failure_patterns)
    )
    candidate_failure_verified = (
        args.candidate_exit in semantic_failure_exits
        and _has_terminal_marker(candidate_text, failure_patterns)
    )

    missing_success_marker = (
        (args.baseline_exit == 0 and not baseline_success_verified)
        or (args.candidate_exit == 0 and not candidate_success_verified)
    )
    missing_failure_marker = (
        (args.baseline_exit in semantic_failure_exits and not baseline_failure_verified)
        or (args.candidate_exit in semantic_failure_exits and not candidate_failure_verified)
    )

    if operational_exit:
        status, classification, return_code = "FAIL", "operational-exit", 2
    elif missing_success_marker:
        status, classification, return_code = "FAIL", "unverified-success", 2
    elif missing_failure_marker:
        status, classification, return_code = (
            "FAIL",
            "unverified-semantic-failure",
            2,
        )
    elif args.baseline_exit == 0 and args.candidate_exit == 0:
        if same_diagnostics:
            status, classification, return_code = "PASS", "preserved-success", 0
        else:
            status, classification, return_code = "FAIL", "drifted-success", 1
    elif args.baseline_exit == 0:
        status, classification, return_code = "FAIL", "new-failure", 1
    elif args.candidate_exit == 0:
        status, classification, return_code = "PASS", "resolved-failure", 0
    elif args.baseline_exit == args.candidate_exit and same_diagnostics:
        status, classification, return_code = "PASS", "preserved-failure", 0
    else:
        status, classification, return_code = "FAIL", "drifted-failure", 1

    payload: dict[str, object] = {
        "schemaVersion": SCHEMA_VERSION,
        "name": args.name,
        "baselineRef": baseline_ref,
        "candidateRef": candidate_ref,
        "baseline": _result_record(baseline_raw, baseline_normalized, args.baseline_exit),
        "candidate": _result_record(candidate_raw, candidate_normalized, args.candidate_exit),
        "classification": classification,
        "status": status,
        "operationalExit": operational_exit,
        "normalization": {
            "pathBoundaries": True,
            "gitObjectIdBoundaries": True,
            "volatilePatterns": list(args.volatile_pattern),
        },
        "successVerification": {
            "patterns": list(args.success_pattern),
            "baselineVerified": baseline_success_verified,
            "candidateVerified": candidate_success_verified,
            "requiredForEverySuccessfulLane": True,
            "markerMustTerminateDiagnostics": True,
        },
        "failureVerification": {
            "patterns": list(args.failure_pattern),
            "baselineVerified": baseline_failure_verified,
            "candidateVerified": candidate_failure_verified,
            "requiredForSemanticFailure": True,
            "markerMustTerminateDiagnostics": True,
        },
        "policy": {
            "semanticFailureExits": semantic_failure_exits,
            "operationalExitsAlwaysBlock": True,
            "operationalExitsUseInvalidEvidenceExitTwo": True,
            "baselineSuccessRequiresCandidateSuccess": True,
            "historicalFailureMayResolveWithDeclaredTerminalSuccessPattern": True,
            "historicalFailureMayRemainOnlyWithTerminalFailureMarker": True,
            "everySuccessfulLaneRequiresTerminalSuccessMarker": True,
            "missingTerminalMarkersUseInvalidEvidenceExitTwo": True,
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
    parser.add_argument("--failure-pattern", action="append", default=[])
    parser.add_argument(
        "--semantic-failure-exit", action="append", type=_semantic_failure_exit, required=True
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        return_code, payload = compare(args)
        _atomic_write(args.output, _canonical_json(payload).encode("utf-8"))
    except (CommandBaselineError, OSError, ValueError) as exc:
        print(f"COMMAND_BASELINE_INVALID: {exc}", file=sys.stderr)
        return 2
    marker = (
        f"RESULT: {payload['status']} command-baseline "
        f"name={payload['name']} classification={payload['classification']}"
    )
    print(marker, file=sys.stdout if return_code == 0 else sys.stderr)
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
