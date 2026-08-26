#!/usr/bin/env python3
"""Build deterministic Stage 0 target-effect metrics from capability inventory.

This captures repository-shape metrics available before Orche 2.0 runtime
instrumentation exists. Runtime token, handoff, latency, and rework metrics are
explicitly left pending rather than guessed. Pure stdlib.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

SCHEMA_VERSION = 1


class TargetEffectError(RuntimeError):
    """Stable user-facing target-effect baseline error."""


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _load_inventory(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TargetEffectError(f"cannot read capability inventory {path}: {exc}") from exc
    if payload.get("schemaVersion") != 1:
        raise TargetEffectError(
            f"unsupported capability inventory schemaVersion: {payload.get('schemaVersion')!r}"
        )
    entries = payload.get("entries")
    baseline = payload.get("baseline")
    if not isinstance(entries, list) or not isinstance(baseline, dict):
        raise TargetEffectError("capability inventory lacks entries or baseline")

    declared_digest = payload.get("inventorySha256")
    if not isinstance(declared_digest, str):
        raise TargetEffectError("capability inventory lacks inventorySha256")
    semantic_payload = dict(payload)
    semantic_payload.pop("inventorySha256", None)
    computed_digest = _sha256_bytes(
        _canonical_json(semantic_payload).encode("utf-8")
    )
    if computed_digest != declared_digest:
        raise TargetEffectError(
            "capability inventory inventorySha256 mismatch: "
            f"declared={declared_digest}, computed={computed_digest}"
        )
    return payload


def _entry_size(entry: Mapping[str, object]) -> int:
    value = entry.get("sizeBytes")
    if not isinstance(value, int) or value < 0:
        raise TargetEffectError(f"invalid sizeBytes for {entry.get('path')!r}: {value!r}")
    return value


def _entry_path(entry: Mapping[str, object]) -> str:
    value = entry.get("path")
    if not isinstance(value, str) or not value:
        raise TargetEffectError(f"invalid entry path: {value!r}")
    return value


def _entry_surfaces(entry: Mapping[str, object]) -> list[str]:
    value = entry.get("surfaces")
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise TargetEffectError(f"invalid surfaces for {_entry_path(entry)!r}")
    return value


def _is_instruction_entrypoint(path_text: str) -> bool:
    path = PurePosixPath(path_text)
    if path.name.lower() not in {
        "agents.md",
        "agents.shared.md",
        "claude.md",
        "gemini.md",
        "qwen.md",
    }:
        return False
    if any(
        part in {"skills", "agents", "references", "tests", "docs"}
        for part in path.parts[:-1]
    ):
        return False
    return (
        len(path.parts) == 1
        or path.parts[0] == "shared"
        or path.parts[0].startswith("src.")
    )


def _is_manual_reconciliation_artifact(
    path_text: str, surfaces: Sequence[str]
) -> bool:
    return (
        "reconciliation" in path_text.lower()
        and "documentation" in surfaces
        and "test" not in surfaces
    )


def build_payload(inventory_path: Path) -> dict[str, object]:
    inventory = _load_inventory(inventory_path)
    entries = inventory["entries"]
    assert isinstance(entries, list)
    typed_entries: list[Mapping[str, object]] = []
    for raw_entry in entries:
        if not isinstance(raw_entry, dict):
            raise TargetEffectError("capability inventory contains a non-object entry")
        typed_entries.append(raw_entry)

    baseline = inventory["baseline"]
    assert isinstance(baseline, dict)
    providers: dict[str, dict[str, int]] = {}
    skill_digests: list[str] = []
    instruction_entrypoints: list[dict[str, object]] = []
    legacy_settings: list[dict[str, object]] = []
    reconciliation_artifacts: list[dict[str, object]] = []

    tracked_bytes = 0
    surface_counts: Counter[str] = Counter()
    for entry in typed_entries:
        path = _entry_path(entry)
        size = _entry_size(entry)
        surfaces = _entry_surfaces(entry)
        digest = entry.get("contentSha256")
        if not isinstance(digest, str):
            raise TargetEffectError(f"invalid contentSha256 for {path!r}")

        tracked_bytes += size
        surface_counts.update(surfaces)
        for surface in surfaces:
            if not surface.startswith("provider:"):
                continue
            provider = surface.split(":", 1)[1]
            metrics = providers.setdefault(
                provider,
                {
                    "agentFiles": 0,
                    "bytes": 0,
                    "commandFiles": 0,
                    "files": 0,
                    "skillBodies": 0,
                },
            )
            metrics["files"] += 1
            metrics["bytes"] += size
            if "agent" in surfaces:
                metrics["agentFiles"] += 1
            if "command" in surfaces:
                metrics["commandFiles"] += 1
            if "skill" in surfaces:
                metrics["skillBodies"] += 1

        if "skill" in surfaces:
            skill_digests.append(digest)
        if _is_instruction_entrypoint(path):
            instruction_entrypoints.append(
                {"contentSha256": digest, "path": path, "sizeBytes": size}
            )
        if "agents-mode" in path.lower():
            legacy_settings.append(
                {"contentSha256": digest, "path": path, "sizeBytes": size}
            )
        if _is_manual_reconciliation_artifact(path, surfaces):
            reconciliation_artifacts.append(
                {"contentSha256": digest, "path": path, "sizeBytes": size}
            )

    skill_digest_counts = Counter(skill_digests)
    duplicate_bodies = sum(
        count - 1 for count in skill_digest_counts.values() if count > 1
    )
    test_entries = [entry for entry in typed_entries if "test" in _entry_surfaces(entry)]

    inventory_bytes = inventory_path.read_bytes()
    inventory_digest = _sha256_bytes(inventory_bytes)
    declared_inventory_digest = inventory.get("inventorySha256")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "status": "BASELINE_MEASURED_WITH_RUNTIME_GAPS",
        "baseline": {
            "commitSha": baseline.get("commitSha"),
            "repository": baseline.get("repository"),
            "treeSha": baseline.get("treeSha"),
        },
        "measurement": {
            "deterministic": True,
            "inputInventoryFileSha256": inventory_digest,
            "inputInventorySemanticSha256": declared_inventory_digest,
            "method": "tracked-git-leaf-metadata",
            "rawSourceBodiesStored": False,
        },
        "repositoryShape": {
            "trackedBytes": tracked_bytes,
            "trackedLeafEntries": len(typed_entries),
            "testBytes": sum(_entry_size(entry) for entry in test_entries),
            "testEntries": len(test_entries),
            "providerPackCount": len(providers),
            "providerPacks": {key: providers[key] for key in sorted(providers)},
            "skillBodies": {
                "bytes": sum(
                    _entry_size(entry)
                    for entry in typed_entries
                    if "skill" in _entry_surfaces(entry)
                ),
                "duplicateBodiesByDigest": duplicate_bodies,
                "total": len(skill_digests),
                "uniqueContentDigests": len(skill_digest_counts),
            },
            "instructionEntrypoints": sorted(
                instruction_entrypoints, key=lambda item: str(item["path"])
            ),
            "legacySettingsStack": {
                "bytes": sum(int(item["sizeBytes"]) for item in legacy_settings),
                "files": len(legacy_settings),
                "paths": sorted(str(item["path"]) for item in legacy_settings),
            },
            "manualReconciliationArtifacts": {
                "bytes": sum(int(item["sizeBytes"]) for item in reconciliation_artifacts),
                "files": len(reconciliation_artifacts),
                "paths": sorted(
                    str(item["path"]) for item in reconciliation_artifacts
                ),
            },
            "surfaceCounts": dict(sorted(surface_counts.items())),
        },
        "runtimeMeasurements": {
            "status": "MEASUREMENT_PENDING_RUNTIME_INSTRUMENTATION",
            "alwaysLoadedPromptTokens": None,
            "canonicalChangeSemanticAgentCalls": None,
            "quickFixAcceptedOutcomeInputTokensP50": None,
            "quickFixAcceptedOutcomeInputTokensP95": None,
            "quickFixAgentHandoffsP50": None,
            "quickFixAgentHandoffsP95": None,
            "quickFixReworkRate": None,
            "typicalFeatureAcceptedOutcomeInputTokensP50": None,
            "typicalFeatureAcceptedOutcomeInputTokensP95": None,
            "typicalFeatureAgentHandoffsP50": None,
            "typicalFeatureAgentHandoffsP95": None,
            "typicalFeatureReworkRate": None,
        },
        "interpretationRules": [
            "Null runtime metrics are unknown, not zero.",
            "Repository-shape metrics are descriptive baseline evidence, not release targets.",
            "Later runtime measurements must reference the same immutable baseline commit.",
        ],
    }


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        expected = _canonical_json(build_payload(args.inventory)).encode("utf-8")
        if args.check:
            if not args.output.is_file():
                print(f"DRIFT: missing {args.output}", file=sys.stderr)
                return 1
            actual = args.output.read_bytes()
            if actual != expected:
                print(
                    f"DRIFT: {args.output}: expected sha256={_sha256_bytes(expected)}, "
                    f"actual sha256={_sha256_bytes(actual)}",
                    file=sys.stderr,
                )
                return 1
            print(f"RESULT: PASS target-effect-baseline check {args.output}")
            return 0
        _atomic_write(args.output, expected)
        print(f"RESULT: PASS target-effect-baseline write {args.output}")
        return 0
    except (TargetEffectError, OSError, ValueError) as exc:
        print(f"RESULT: FAIL target-effect-baseline: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
