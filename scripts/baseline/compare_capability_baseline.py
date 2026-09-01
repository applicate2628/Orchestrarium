#!/usr/bin/env python3
"""Compare complete candidate capability inventory with reviewed identities."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path

SCHEMA_VERSION = 2
INVENTORY_SCHEMA_VERSION = 2
DISPOSITIONS_PATH = "baseline/orchestrarium-v1/reviewed-dispositions.json"
OBJECT_ID = re.compile(r"[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?")
SHA256 = re.compile(r"[0-9a-f]{64}")
ALLOWED_CHANGES = {"added", "modified", "removed"}
ALLOWED_MODES = {"100644", "100755", "120000", "160000"}


class CapabilityComparisonError(RuntimeError):
    pass


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _exact_ref(value: str, *, label: str) -> str:
    if not OBJECT_ID.fullmatch(value):
        raise CapabilityComparisonError(
            f"{label} must be an exact 40- or 64-character object ID"
        )
    return value.lower()


def _identity(raw: object, *, label: str, allow_none: bool = False):
    if raw is None and allow_none:
        return None
    if not isinstance(raw, dict) or set(raw) != {"gitObject", "mode", "objectType"}:
        raise CapabilityComparisonError(f"invalid {label} identity")
    git_object = raw.get("gitObject")
    mode = raw.get("mode")
    object_type = raw.get("objectType")
    if not isinstance(git_object, str) or not OBJECT_ID.fullmatch(git_object):
        raise CapabilityComparisonError(f"invalid {label} Git object")
    if mode not in ALLOWED_MODES:
        raise CapabilityComparisonError(f"invalid {label} Git mode: {mode!r}")
    expected_type = "commit" if mode == "160000" else "blob"
    if object_type != expected_type:
        raise CapabilityComparisonError(
            f"invalid {label} objectType: mode={mode!r}, objectType={object_type!r}"
        )
    return {
        "gitObject": git_object.lower(),
        "mode": mode,
        "objectType": object_type,
    }


def _load_inventory(path: Path, *, expected_ref: str, label: str):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CapabilityComparisonError(
            f"cannot read {label} inventory {path}: {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise CapabilityComparisonError(f"{label} inventory top level must be an object")
    if payload.get("schemaVersion") != INVENTORY_SCHEMA_VERSION:
        raise CapabilityComparisonError(
            f"unsupported {label} inventory schemaVersion: {payload.get('schemaVersion')!r}"
        )
    declared = payload.get("inventorySha256")
    semantic = dict(payload)
    semantic.pop("inventorySha256", None)
    computed = hashlib.sha256(_canonical_json(semantic).encode()).hexdigest()
    if (
        not isinstance(declared, str)
        or not SHA256.fullmatch(declared)
        or computed != declared
    ):
        raise CapabilityComparisonError(
            f"{label} inventory inventorySha256 mismatch"
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
    tree_sha = baseline.get("treeSha")
    if not isinstance(tree_sha, str) or not OBJECT_ID.fullmatch(tree_sha):
        raise CapabilityComparisonError(f"invalid {label} inventory treeSha")
    result = {}
    for raw in entries:
        if not isinstance(raw, dict):
            raise CapabilityComparisonError(f"{label} inventory contains non-object entry")
        path_value = raw.get("path")
        if (
            not isinstance(path_value, str)
            or not path_value
            or path_value.startswith("/")
        ):
            raise CapabilityComparisonError(
                f"invalid {label} inventory path: {path_value!r}"
            )
        if path_value in result:
            raise CapabilityComparisonError(
                f"duplicate {label} inventory path: {path_value}"
            )
        result[path_value] = _identity(
            {
                "gitObject": raw.get("gitObject"),
                "mode": raw.get("mode"),
                "objectType": raw.get("objectType"),
            },
            label=f"{label} inventory {path_value!r}",
        )
    return tree_sha.lower(), result


def _load_dispositions(
    path: Path, *, baseline_ref: str, baseline_tree: str
):
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CapabilityComparisonError(f"cannot read dispositions {path}: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("schemaVersion") != SCHEMA_VERSION:
        raise CapabilityComparisonError(
            "dispositions top level/schemaVersion is invalid; schemaVersion 2 is required"
        )
    if payload.get("baselineRef") != baseline_ref:
        raise CapabilityComparisonError("dispositions baselineRef mismatch")
    if payload.get("baselineTree") != baseline_tree:
        raise CapabilityComparisonError("dispositions baselineTree mismatch")
    if payload.get("scope") != "ORCHE-IMPL-000":
        raise CapabilityComparisonError("dispositions scope must be ORCHE-IMPL-000")
    candidate_ref = _exact_ref(
        str(payload.get("candidateRef", "")), label="dispositions candidateRef"
    )
    candidate_tree = _exact_ref(
        str(payload.get("candidateTree", "")), label="dispositions candidateTree"
    )
    if payload.get("reviewEnvelope") != {
        "kind": "manifest-only-child",
        "path": DISPOSITIONS_PATH,
    }:
        raise CapabilityComparisonError("dispositions reviewEnvelope is invalid")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise CapabilityComparisonError("dispositions entries must be an array")
    result = {}
    for raw in entries:
        if not isinstance(raw, dict):
            raise CapabilityComparisonError("dispositions contain a non-object entry")
        path_value = raw.get("path")
        change = raw.get("change")
        reason = raw.get("reason")
        contracts = raw.get("contractIds")
        if (
            not isinstance(path_value, str)
            or not path_value
            or path_value.startswith("/")
            or path_value == DISPOSITIONS_PATH
        ):
            raise CapabilityComparisonError(
                f"invalid disposition path: {path_value!r}"
            )
        if change not in ALLOWED_CHANGES:
            raise CapabilityComparisonError(
                f"invalid disposition change for {path_value!r}: {change!r}"
            )
        if not isinstance(reason, str) or not reason.strip():
            raise CapabilityComparisonError(
                f"disposition reason is required for {path_value!r}"
            )
        if (
            not isinstance(contracts, list)
            or not contracts
            or not all(isinstance(item, str) and item for item in contracts)
        ):
            raise CapabilityComparisonError(
                f"one or more contractIds are required for {path_value!r}"
            )
        if path_value in result:
            raise CapabilityComparisonError(f"duplicate disposition path: {path_value}")
        result[path_value] = {
            "change": change,
            "expectedBaselineIdentity": _identity(
                raw.get("expectedBaselineIdentity"),
                label=f"baseline disposition {path_value!r}",
                allow_none=True,
            ),
            "expectedCandidateIdentity": _identity(
                raw.get("expectedCandidateIdentity"),
                label=f"candidate disposition {path_value!r}",
                allow_none=True,
            ),
        }
    return candidate_ref, candidate_tree, result


def compare(
    baseline,
    candidate,
    dispositions,
    *,
    baseline_ref: str,
    candidate_ref: str,
    candidate_content_ref: str,
    candidate_content_tree: str,
):
    baseline = dict(baseline)
    candidate = dict(candidate)
    baseline.pop(DISPOSITIONS_PATH, None)
    candidate.pop(DISPOSITIONS_PATH, None)
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
    missing = sorted(set(actual) - set(dispositions))
    stale = sorted(set(dispositions) - set(actual))
    mismatched = sorted(
        path
        for path in set(actual) & set(dispositions)
        if actual[path] != dispositions[path]["change"]
    )
    identity_mismatches = []
    for path in sorted(set(actual) & set(dispositions)):
        record = dispositions[path]
        actual_baseline = baseline.get(path)
        actual_candidate = candidate.get(path)
        if (
            record["expectedBaselineIdentity"] != actual_baseline
            or record["expectedCandidateIdentity"] != actual_candidate
        ):
            identity_mismatches.append(path)
    blockers = {
        "missingDispositions": missing,
        "staleDispositions": stale,
        "mismatchedDispositions": mismatched,
        "mismatchedDispositionIdentities": identity_mismatches,
    }
    verdict = "PASS" if all(not value for value in blockers.values()) else "BLOCKED"
    return {
        "schemaVersion": 2,
        "baselineRef": baseline_ref,
        "candidateRef": candidate_ref,
        "candidateContentRef": candidate_content_ref,
        "candidateContentTree": candidate_content_tree,
        "changes": {"added": added, "modified": modified, "removed": removed},
        "reviewedDispositions": [
            {
                "path": path,
                "change": dispositions[path]["change"],
                "expectedBaselineIdentity": dispositions[path][
                    "expectedBaselineIdentity"
                ],
                "expectedCandidateIdentity": dispositions[path][
                    "expectedCandidateIdentity"
                ],
            }
            for path in sorted(dispositions)
        ],
        "blockers": blockers,
        "verdict": verdict,
    }


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        Path(temporary_name).unlink(missing_ok=True)


def parse_args(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-inventory", type=Path, required=True)
    parser.add_argument("--candidate-inventory", type=Path, required=True)
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--candidate-ref", required=True)
    parser.add_argument("--dispositions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        baseline_ref = _exact_ref(args.baseline_ref, label="baseline ref")
        candidate_ref = _exact_ref(args.candidate_ref, label="candidate ref")
        if baseline_ref == candidate_ref:
            raise CapabilityComparisonError(
                "candidate ref must differ from baseline ref"
            )
        baseline_tree, baseline = _load_inventory(
            args.baseline_inventory,
            expected_ref=baseline_ref,
            label="baseline",
        )
        _candidate_tree, candidate = _load_inventory(
            args.candidate_inventory,
            expected_ref=candidate_ref,
            label="candidate",
        )
        candidate_content_ref, candidate_content_tree, dispositions = _load_dispositions(
            args.dispositions,
            baseline_ref=baseline_ref,
            baseline_tree=baseline_tree,
        )
        result = compare(
            baseline,
            candidate,
            dispositions,
            baseline_ref=baseline_ref,
            candidate_ref=candidate_ref,
            candidate_content_ref=candidate_content_ref,
            candidate_content_tree=candidate_content_tree,
        )
        _atomic_write(args.output, _canonical_json(result).encode())
        print(
            f"RESULT: {result['verdict']} capability-baseline "
            f"added={len(result['changes']['added'])} "
            f"modified={len(result['changes']['modified'])} "
            f"removed={len(result['changes']['removed'])}"
        )
        return 0 if result["verdict"] == "PASS" else 1
    except (CapabilityComparisonError, OSError, ValueError) as exc:
        print(f"RESULT: FAIL capability-baseline: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
