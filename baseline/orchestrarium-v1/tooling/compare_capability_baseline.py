#!/usr/bin/env python3
"""Compare complete candidate capability inventory with the immutable baseline.

Every added, modified, or removed tracked path must have one exact reviewed
disposition. Exit 0 means all changes are explicitly accounted for; exit 1 means
unreviewed or stale dispositions; exit 2 means invalid evidence.
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
from typing import Mapping, Sequence

SCHEMA_VERSION = 1
INVENTORY_SCHEMA_VERSION = 2
OBJECT_ID = re.compile(r"[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?")
SHA256 = re.compile(r"[0-9a-f]{64}")
ALLOWED_CHANGES = {"added", "modified", "removed"}


class CapabilityComparisonError(RuntimeError):
    """Stable capability-comparison error."""


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _exact_ref(value: str, *, label: str) -> str:
    if not OBJECT_ID.fullmatch(value):
        raise CapabilityComparisonError(
            f"{label} ref must be an exact 40- or 64-character object ID"
        )
    return value.lower()


def _load_inventory(path: Path, *, expected_ref: str, label: str) -> dict[str, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CapabilityComparisonError(f"cannot read {label} inventory {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise CapabilityComparisonError(f"{label} inventory top level must be an object")
    if payload.get("schemaVersion") != INVENTORY_SCHEMA_VERSION:
        raise CapabilityComparisonError(
            f"unsupported {label} inventory schemaVersion: {payload.get('schemaVersion')!r}"
        )
    declared = payload.get("inventorySha256")
    if not isinstance(declared, str) or not SHA256.fullmatch(declared):
        raise CapabilityComparisonError(f"{label} inventory lacks a valid inventorySha256")
    semantic = dict(payload)
    semantic.pop("inventorySha256", None)
    computed = hashlib.sha256(_canonical_json(semantic).encode("utf-8")).hexdigest()
    if computed != declared:
        raise CapabilityComparisonError(
            f"{label} inventory inventorySha256 mismatch: declared={declared}, computed={computed}"
        )
    baseline = payload.get("baseline")
    entries = payload.get("entries")
    if not isinstance(baseline, dict) or not isinstance(entries, list):
        raise CapabilityComparisonError(f"{label} inventory lacks baseline or entries")
    if baseline.get("commitSha") != expected_ref:
        raise CapabilityComparisonError(
            f"{label} inventory commit mismatch: expected={expected_ref}, "
            f"actual={baseline.get('commitSha')!r}"
        )
    result: dict[str, str] = {}
    for raw in entries:
        if not isinstance(raw, dict):
            raise CapabilityComparisonError(f"{label} inventory contains non-object entry")
        path_value = raw.get("path")
        digest = raw.get("contentSha256")
        if not isinstance(path_value, str) or not path_value or path_value.startswith("/"):
            raise CapabilityComparisonError(f"invalid {label} inventory path: {path_value!r}")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise CapabilityComparisonError(f"invalid {label} digest for {path_value!r}")
        if path_value in result:
            raise CapabilityComparisonError(f"duplicate {label} inventory path: {path_value}")
        result[path_value] = digest
    return result


def _load_dispositions(path: Path, *, baseline_ref: str) -> dict[str, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CapabilityComparisonError(f"cannot read dispositions {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schemaVersion") != SCHEMA_VERSION:
        raise CapabilityComparisonError("dispositions top level/schemaVersion is invalid")
    if payload.get("baselineRef") != baseline_ref:
        raise CapabilityComparisonError(
            f"dispositions baselineRef mismatch: expected={baseline_ref}, "
            f"actual={payload.get('baselineRef')!r}"
        )
    if payload.get("scope") != "ORCHE-IMPL-000":
        raise CapabilityComparisonError("dispositions scope must be ORCHE-IMPL-000")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise CapabilityComparisonError("dispositions entries must be an array")
    result: dict[str, str] = {}
    for raw in entries:
        if not isinstance(raw, dict):
            raise CapabilityComparisonError("dispositions contain a non-object entry")
        path_value = raw.get("path")
        change = raw.get("change")
        reason = raw.get("reason")
        contracts = raw.get("contractIds")
        if not isinstance(path_value, str) or not path_value or path_value.startswith("/"):
            raise CapabilityComparisonError(f"invalid disposition path: {path_value!r}")
        if change not in ALLOWED_CHANGES:
            raise CapabilityComparisonError(
                f"invalid disposition change for {path_value!r}: {change!r}"
            )
        if not isinstance(reason, str) or not reason.strip():
            raise CapabilityComparisonError(f"disposition reason is required for {path_value!r}")
        if not isinstance(contracts, list) or not contracts or not all(
            isinstance(item, str) and item for item in contracts
        ):
            raise CapabilityComparisonError(
                f"one or more contractIds are required for {path_value!r}"
            )
        if path_value in result:
            raise CapabilityComparisonError(f"duplicate disposition path: {path_value}")
        result[path_value] = str(change)
    return result


def compare(
    baseline: Mapping[str, str],
    candidate: Mapping[str, str],
    dispositions: Mapping[str, str],
    *,
    baseline_ref: str,
    candidate_ref: str,
) -> dict[str, object]:
    added = sorted(set(candidate) - set(baseline))
    removed = sorted(set(baseline) - set(candidate))
    modified = sorted(
        path
        for path in set(baseline) & set(candidate)
        if baseline[path] != candidate[path]
    )
    actual = {
        **{path: "added" for path in added},
        **{path: "modified" for path in modified},
        **{path: "removed" for path in removed},
    }
    missing_dispositions = sorted(set(actual) - set(dispositions))
    stale_dispositions = sorted(set(dispositions) - set(actual))
    mismatched_dispositions = sorted(
        path
        for path in set(actual) & set(dispositions)
        if actual[path] != dispositions[path]
    )
    blockers = {
        "missingDispositions": missing_dispositions,
        "staleDispositions": stale_dispositions,
        "mismatchedDispositions": mismatched_dispositions,
    }
    verdict = "PASS" if all(not values for values in blockers.values()) else "BLOCKED"
    return {
        "schemaVersion": SCHEMA_VERSION,
        "baselineRef": baseline_ref,
        "candidateRef": candidate_ref,
        "changes": {"added": added, "modified": modified, "removed": removed},
        "reviewedDispositions": [
            {"path": path, "change": dispositions[path]} for path in sorted(dispositions)
        ],
        "blockers": blockers,
        "verdict": verdict,
    }


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


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-inventory", type=Path, required=True)
    parser.add_argument("--candidate-inventory", type=Path, required=True)
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--candidate-ref", required=True)
    parser.add_argument("--dispositions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        baseline_ref = _exact_ref(args.baseline_ref, label="baseline")
        candidate_ref = _exact_ref(args.candidate_ref, label="candidate")
        if baseline_ref == candidate_ref:
            raise CapabilityComparisonError("candidate ref must differ from baseline ref")
        report = compare(
            _load_inventory(
                args.baseline_inventory, expected_ref=baseline_ref, label="baseline"
            ),
            _load_inventory(
                args.candidate_inventory, expected_ref=candidate_ref, label="candidate"
            ),
            _load_dispositions(args.dispositions, baseline_ref=baseline_ref),
            baseline_ref=baseline_ref,
            candidate_ref=candidate_ref,
        )
        _atomic_write(args.output, _canonical_json(report).encode("utf-8"))
        print(
            f"RESULT: {report['verdict']} capability-baseline "
            f"added={len(report['changes']['added'])} "
            f"modified={len(report['changes']['modified'])} "
            f"removed={len(report['changes']['removed'])}"
        )
        return 0 if report["verdict"] == "PASS" else 1
    except (CapabilityComparisonError, OSError, ValueError) as exc:
        print(f"RESULT: FAIL capability-baseline: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
