#!/usr/bin/env python3
"""Resolve effective Orchestrarium agents-mode values across precedence layers."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import os
import re
import stat
import sys
import tomllib
import unicodedata
from pathlib import Path
from typing import Any


PROVIDER_DIRS = {
    "codex": ".agents",
    "claude": ".claude",
}
REMOVED_EXTERNAL_PROVIDERS = frozenset({"gemini", "qwen"})
EXTERNAL_DISPATCH_PROVIDERS = ("kimi", "grok")
_EXTERNAL_ROLE_TAXONOMY_NAME = "external-role-taxonomy.v1.json"
_EXTERNAL_ROLE_TAXONOMY_MAX_BYTES = 64 * 1024
_EXTERNAL_ROLE_LANES = frozenset(
    {"consultant", "external-worker", "external-reviewer", "none"}
)
PROVIDER_CHOICES = tuple(sorted((*PROVIDER_DIRS, *EXTERNAL_DISPATCH_PROVIDERS)))
_EXTERNAL_EXECUTION_DISPOSITIONS = frozenset(
    {"explicit-wrapper", "classifier-only"}
)
_LEGACY_EXTERNAL_EXECUTION_DISPOSITIONS = {
    "explicit-read-only": "explicit-wrapper"
}
_EXTERNAL_AVAILABILITIES = frozenset({"available", "unavailable"})
_EXTERNAL_DISPOSITION_AVAILABILITY_PAIRS = frozenset(
    {
        ("explicit-wrapper", "available"),
        ("classifier-only", "unavailable"),
    }
)
_MECHANICAL_ROLES = frozenset({"mechanical-scout", "mechanical-worker"})
_MECHANICAL_TASK_CLASSES = frozenset({"micro", "mechanical-read", "mechanical"})
_LUNA_ALLOWED_REASONING_EFFORTS = ("high", "xhigh", "max")
_LUNA_OPERATION_SCHEMA_V1 = {
    "path-kind": frozenset({"path"}),
    "file-size": frozenset({"path"}),
    "sha256": frozenset({"path"}),
    "read-lines": frozenset({"path", "start", "count"}),
    "list-directory": frozenset({"path"}),
    "literal-equals": frozenset({"left", "right"}),
}
_MECHANICAL_EXECUTION_CONTRACT_V1 = {
    "schemaVersion": 1,
    "requiresFullySpecifiedTask": True,
    "decisionAuthority": "none",
    "ambiguity": "abort",
    "fallback": "none",
    "objectiveOracle": "caller-required",
    "defaultEffort": "high",
    "allowedCallerEfforts": list(_LUNA_ALLOWED_REASONING_EFFORTS),
    "scout": {
        "status": "native-required-when-feature-enabled",
        "planContract": "LunaExecutionContractV1",
        "outputContract": "ScoutFactsV1",
        "readProbeOrder": "caller-specified-exact-order",
        "targetBinding": "required-exact-git-root",
        "allowedTools": "caller-supplied-exact-runtime-ids",
        "allowedOperations": list(_LUNA_OPERATION_SCHEMA_V1),
        "toolAttestation": "caller-required-exact-equality",
        "factsOnly": True,
        "forbiddenOutputs": [
            "diagnosis",
            "design",
            "selection",
            "recommendation",
            "risk",
            "gate",
        ],
    },
    "worker": {
        "status": "native-required-when-feature-enabled",
        "planContract": "LunaExecutionContractV1",
        "sandboxMode": "workspace-write",
        "targetBinding": "required-exact-git-root",
        "allowedTools": "caller-supplied-exact-runtime-ids",
        "allowedOperations": ["apply-exact-patch"],
        "precondition": "caller-specified-exact-pre-image-sha256",
        "postcondition": "caller-verifies-exact-post-image-sha256",
        "forbiddenOperations": ["shell", "delete", "rename", "path-choice"],
        "directCodeOrPatchAuthoring": False,
    },
}

_LUNA_PLAN_COMMON_FIELDS = frozenset(
    {
        "version",
        "probeId",
        "role",
        "taskClass",
        "decisionAuthority",
        "exactRoot",
        "allowedTools",
        "operations",
        "objectiveOracle",
    }
)
_LUNA_SCOUT_PLAN_FIELDS = _LUNA_PLAN_COMMON_FIELDS | {"expectedFactsVersion"}
_LUNA_WORKER_OPERATION_FIELDS = frozenset({"ordinal", "op", "tool", "args"})
_LUNA_WORKER_PATCH_FIELDS = frozenset(
    {
        "path",
        "patch",
        "patchSha256",
        "preImageSha256",
        "postImageSha256",
        "preflight",
    }
)
_LUNA_WORKER_PREFLIGHT_FIELDS = frozenset({"kind", "expectedRoot"})
_LUNA_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_LUNA_RESERVED_TOOL_SURFACES = frozenset(
    {
        "runtimedefault",
        "default",
        "runtime",
        "inherit",
        "inherited",
        "auto",
        "all",
        "any",
        "none",
        "shell",
        "shellcommand",
        "execcommand",
        "bash",
        "powershell",
        "pwsh",
        "cmd",
        "terminal",
        "command",
        "exec",
    }
)
_SCOUT_FACTS_FIELDS = frozenset(
    {"version", "probeId", "role", "facts", "observedTools"}
)
_SCOUT_FACT_FIELDS = frozenset(
    {"ordinal", "op", "execution", "value", "errorId"}
)
_LUNA_ERROR_ID = re.compile(r"E_[A-Z0-9_]{1,120}\Z")
_LUNA_AUTHORITY_FIELDS = frozenset(
    {
        "pass",
        "status",
        "verdict",
        "decision",
        "recommendation",
        "risk",
        "gate",
        "publication",
        "authorizing",
        "nextstep",
    }
)

# Layer-provenance trust boundary (F9): ranks supplied by the user's own machine-global
# configuration vs. ranks a cloned repository can supply. Executable-bearing values
# (currently `reserveResolver: wrapper:<command>`) are honored only from user-global
# layers; a project-local executable value that user-global config does not also define
# is flagged `project-UNCONFIRMED` and requires explicit first-use user confirmation
# (recorded durably by writing the approved value into a user-global layer) before launch.
PROJECT_RANKS = frozenset({"local", "local-legacy"})
USER_GLOBAL_RANKS = frozenset({"global", "global-legacy", "shared-global"})


def _is_reparse_metadata(metadata: os.stat_result) -> bool:
    return bool(
        getattr(metadata, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _ordinary_file(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return (
        stat.S_ISREG(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and not _is_reparse_metadata(metadata)
    )


def _ordinary_directory(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    return (
        stat.S_ISDIR(metadata.st_mode)
        and not stat.S_ISLNK(metadata.st_mode)
        and not _is_reparse_metadata(metadata)
        and not getattr(os.path, "isjunction", lambda _path: False)(path)
    )


def _luna_validation_result(stable_id: str | None) -> dict[str, Any]:
    """Return a caller-owned, nonauthorizing validation outcome."""

    return {
        "schemaVersion": 1,
        "valid": stable_id is None,
        "stableId": stable_id,
        "fallback": "none",
        "authorizing": False,
    }


def _exact_fields(value: Any, fields: frozenset[str]) -> bool:
    return isinstance(value, dict) and set(value) == fields


def _valid_luna_identifier(value: Any) -> bool:
    return (
        isinstance(value, str)
        and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}", value))
    )


def _luna_tool_identity(value: Any) -> tuple[str, ...] | None:
    if not isinstance(value, str):
        return None
    normalized = unicodedata.normalize("NFKC", value).casefold()
    if not _valid_luna_identifier(normalized):
        return None
    tokens = tuple(
        token for token in re.split(r"[^a-z0-9]+", normalized) if token
    )
    if not tokens or any(token in _LUNA_RESERVED_TOOL_SURFACES for token in tokens):
        return None
    for start in range(len(tokens)):
        adjacent = ""
        for token in tokens[start:]:
            adjacent += token
            if adjacent in _LUNA_RESERVED_TOOL_SURFACES:
                return None
    return tokens


def _valid_luna_tool_id(value: Any) -> bool:
    return _luna_tool_identity(value) is not None


def _valid_luna_tools(value: Any, *, scalar_tool: Any = None) -> bool:
    if not isinstance(value, list):
        return False
    identities = [_luna_tool_identity(tool) for tool in value]
    if any(identity is None for identity in identities):
        return False
    if len(identities) != len(set(identities)):
        return False
    if scalar_tool is None:
        return True
    return _valid_luna_tool_id(scalar_tool) and value == [scalar_tool]


def _valid_relative_probe_path(value: Any) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or "\x00" in value
        or "\\" in value
        or ":" in value
        or value.startswith("/")
    ):
        return False
    components = value.split("/")
    return all(component not in {"", ".", ".."} for component in components)


def _luna_metadata_signature(metadata: Any) -> tuple[Any, ...]:
    identity = (
        metadata.st_mode,
        metadata.st_dev,
        metadata.st_ino,
        getattr(metadata, "st_file_attributes", 0),
    )
    if stat.S_ISDIR(metadata.st_mode):
        return identity
    return identity + (
        metadata.st_size,
        getattr(metadata, "st_mtime_ns", None),
        getattr(metadata, "st_ctime_ns", None),
    )


def _luna_component_metadata(
    path: Path,
    *,
    allow_anchor_mount: bool,
) -> Any | None:
    try:
        metadata = os.lstat(path)
        is_junction = getattr(os.path, "isjunction", lambda _path: False)(path)
        is_mount = os.path.ismount(path)
    except OSError:
        return None
    if (
        stat.S_ISLNK(metadata.st_mode)
        or _is_reparse_metadata(metadata)
        or is_junction
        or (is_mount and not allow_anchor_mount)
    ):
        return None
    return metadata


def _luna_absolute_chain(path: Path) -> list[Path] | None:
    if not path.is_absolute() or not path.anchor:
        return None
    anchor = Path(path.anchor)
    chain = [anchor]
    cursor = anchor
    for component in path.parts[1:]:
        cursor = cursor / component
        chain.append(cursor)
    return chain


def _luna_stable_ordinary_chain(
    chain: list[Path] | None,
    *,
    leaf_kind: str,
) -> tuple[Path, Any] | None:
    if not chain:
        return None
    snapshots: list[tuple[Path, tuple[Any, ...]]] = []
    leaf_metadata: Any = None
    for index, path in enumerate(chain):
        metadata = _luna_component_metadata(
            path,
            allow_anchor_mount=path == Path(path.anchor),
        )
        if metadata is None:
            return None
        is_leaf = index == len(chain) - 1
        if not is_leaf or leaf_kind == "directory":
            if not stat.S_ISDIR(metadata.st_mode):
                return None
        elif leaf_kind == "file":
            if not stat.S_ISREG(metadata.st_mode):
                return None
        elif leaf_kind == "ordinary":
            if not (stat.S_ISREG(metadata.st_mode) or stat.S_ISDIR(metadata.st_mode)):
                return None
        elif leaf_kind != "entry":
            return None
        snapshots.append((path, _luna_metadata_signature(metadata)))
        leaf_metadata = metadata
    for index, (path, signature) in enumerate(snapshots):
        metadata = _luna_component_metadata(
            path,
            allow_anchor_mount=path == Path(path.anchor),
        )
        if metadata is None or _luna_metadata_signature(metadata) != signature:
            return None
    return chain[-1], leaf_metadata


def _luna_existing_target(
    exact_root: Path,
    value: Any,
    *,
    leaf_kind: str,
    allow_missing_leaf: bool = False,
) -> tuple[Path, Any] | None:
    if not _valid_relative_probe_path(value):
        return None
    root_chain = _luna_absolute_chain(exact_root)
    if _luna_stable_ordinary_chain(root_chain, leaf_kind="directory") is None:
        return None
    components = value.split("/")
    candidate = exact_root.joinpath(*components)
    try:
        relative = candidate.relative_to(exact_root)
    except ValueError:
        return None
    if tuple(relative.parts) != tuple(components):
        return None
    target_chain = [exact_root]
    cursor = exact_root
    for component in components:
        cursor = cursor / component
        target_chain.append(cursor)
    existing = _luna_stable_ordinary_chain(target_chain, leaf_kind=leaf_kind)
    if existing is not None or not allow_missing_leaf:
        return existing
    parent_chain = target_chain[:-1]
    if _luna_stable_ordinary_chain(parent_chain, leaf_kind="directory") is None:
        return None
    try:
        os.lstat(candidate)
    except FileNotFoundError:
        if _luna_stable_ordinary_chain(parent_chain, leaf_kind="directory") is None:
            return None
        return candidate, None
    except OSError:
        return None
    return None


def _luna_existing_file_sha256(path: Path, expected_metadata: Any) -> str | None:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        expected_identity = (
            stat.S_IFMT(expected_metadata.st_mode),
            expected_metadata.st_dev,
            expected_metadata.st_ino,
        )
        opened_identity = (stat.S_IFMT(opened.st_mode), opened.st_dev, opened.st_ino)
        if not stat.S_ISREG(opened.st_mode) or opened_identity != expected_identity:
            return None
        digest = hashlib.sha256()
        captured_size = opened.st_size
        remaining = captured_size + 1
        observed_size = 0
        while remaining:
            chunk = os.read(descriptor, min(1024 * 1024, remaining))
            if not chunk:
                break
            observed_size += len(chunk)
            remaining -= len(chunk)
            if observed_size > captured_size:
                return None
            digest.update(chunk)
        if observed_size != captured_size:
            return None
        after = _luna_component_metadata(path, allow_anchor_mount=False)
        if (
            after is None
            or _luna_metadata_signature(after)
            != _luna_metadata_signature(expected_metadata)
            or os.fstat(descriptor).st_size != captured_size
        ):
            return None
        return digest.hexdigest()
    except OSError:
        return None
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _normalized_absolute_path(value: Any) -> str | None:
    if isinstance(value, os.PathLike):
        value = os.fspath(value)
    if not isinstance(value, str) or not value:
        return None
    path = Path(value)
    if not path.is_absolute():
        return None
    return os.path.normcase(os.path.normpath(str(path)))


def _validate_luna_operation(
    operation: Any,
    expected_ordinal: int,
    *,
    exact_root: Path,
) -> str | None:
    if not _exact_fields(operation, frozenset({"ordinal", "op", "args"})):
        return "E_LUNA_PLAN_INVALID"
    if operation["ordinal"] != expected_ordinal:
        return "E_LUNA_PLAN_INVALID"
    op = operation["op"]
    if op not in _LUNA_OPERATION_SCHEMA_V1:
        return "E_LUNA_FORBIDDEN_OPERATION"
    args = operation["args"]
    expected_fields = _LUNA_OPERATION_SCHEMA_V1[op]
    if not _exact_fields(args, expected_fields):
        return "E_LUNA_PLAN_INVALID"
    if "path" in args:
        leaf_kind = (
            "directory"
            if op == "list-directory"
            else "entry"
            if op == "path-kind"
            else "file"
        )
        if not _valid_relative_probe_path(args["path"]):
            return "E_LUNA_PLAN_INVALID"
        if _luna_existing_target(
            exact_root,
            args["path"],
            leaf_kind=leaf_kind,
            allow_missing_leaf=op == "path-kind",
        ) is None:
            return "E_LUNA_PRECONDITION_FAILED"
    if op == "read-lines" and (
        isinstance(args["start"], bool)
        or not isinstance(args["start"], int)
        or args["start"] < 0
        or isinstance(args["count"], bool)
        or not isinstance(args["count"], int)
        or args["count"] <= 0
    ):
        return "E_LUNA_PLAN_INVALID"
    if op == "literal-equals" and any(
        isinstance(item, (dict, list, tuple, set))
        for item in (args["left"], args["right"])
    ):
        return "E_LUNA_PLAN_INVALID"
    return None


def _valid_luna_plan_fields(plan: Any, required: frozenset[str]) -> bool:
    if not isinstance(plan, dict):
        return False
    fields = set(plan)
    return fields == required or fields == required | {"reasoningEffort"}


def _validate_luna_worker_operation(
    operation: Any,
    *,
    exact_root: str,
    allowed_tools: list[str],
) -> str | None:
    if not _exact_fields(operation, _LUNA_WORKER_OPERATION_FIELDS):
        return "E_LUNA_PLAN_INVALID"
    if operation["ordinal"] != 0 or operation["op"] != "apply-exact-patch":
        return "E_LUNA_FORBIDDEN_OPERATION"
    tool = operation["tool"]
    if not _valid_luna_tools(allowed_tools, scalar_tool=tool):
        return "E_LUNA_FORBIDDEN_OPERATION"

    args = operation["args"]
    if not _exact_fields(args, _LUNA_WORKER_PATCH_FIELDS):
        return "E_LUNA_PLAN_INVALID"
    path = args["path"]
    if not _valid_relative_probe_path(path):
        return "E_LUNA_PLAN_INVALID"
    preflight = args["preflight"]
    if (
        not _exact_fields(preflight, _LUNA_WORKER_PREFLIGHT_FIELDS)
        or preflight["kind"] != "exact-git-root"
        or _normalized_absolute_path(preflight["expectedRoot"]) != exact_root
    ):
        return "E_LUNA_PRECONDITION_FAILED"

    patch = args["patch"]
    patch_hash = args["patchSha256"]
    pre_hash = args["preImageSha256"]
    post_hash = args["postImageSha256"]
    if (
        not isinstance(patch, str)
        or not patch
        or "\x00" in patch
        or not isinstance(patch_hash, str)
        or not isinstance(pre_hash, str)
        or not isinstance(post_hash, str)
        or not _LUNA_SHA256.fullmatch(patch_hash)
        or not _LUNA_SHA256.fullmatch(pre_hash)
        or not _LUNA_SHA256.fullmatch(post_hash)
        or pre_hash == post_hash
        or hashlib.sha256(patch.encode("utf-8")).hexdigest() != patch_hash
    ):
        return "E_LUNA_PLAN_INVALID"

    target = _luna_existing_target(Path(exact_root), path, leaf_kind="file")
    if target is None:
        return "E_LUNA_PRECONDITION_FAILED"
    target_path, target_metadata = target
    observed_pre_hash = _luna_existing_file_sha256(target_path, target_metadata)
    if observed_pre_hash is None or observed_pre_hash != pre_hash:
        return "E_LUNA_PRECONDITION_FAILED"

    patch_lines = patch.splitlines()
    normalized_path = path.replace("\\", "/")
    update_header = f"*** Update File: {normalized_path}"
    if (
        len(patch_lines) < 4
        or patch_lines[0] != "*** Begin Patch"
        or patch_lines[-1] != "*** End Patch"
        or patch_lines.count(update_header) != 1
        or sum(line.startswith("*** Update File: ") for line in patch_lines) != 1
        or any(
            line.startswith(("*** Add File: ", "*** Delete File: ", "*** Move to: "))
            for line in patch_lines
        )
        or any(
            line.casefold().startswith(
                ("rename from ", "rename to ", "deleted file mode ", "new file mode ")
            )
            or line.strip() == "/dev/null"
            for line in patch_lines
        )
    ):
        return "E_LUNA_FORBIDDEN_OPERATION"
    return None


def validate_luna_execution_plan(
    plan: Any, *, observed_git_root: Any = None
) -> dict[str, Any]:
    """Validate one caller-authored Luna plan without launching it.

    The caller owns discovery of the actual Git root.  This function only
    checks the supplied observation against the exact, non-reparse plan root.
    """

    if not isinstance(plan, dict):
        return _luna_validation_result("E_LUNA_PLAN_INVALID")
    role = plan.get("role")
    required_fields = (
        _LUNA_SCOUT_PLAN_FIELDS
        if role == "mechanical-scout"
        else _LUNA_PLAN_COMMON_FIELDS
    )
    if not _valid_luna_plan_fields(plan, required_fields):
        return _luna_validation_result("E_LUNA_PLAN_INVALID")
    reasoning_effort = plan.get("reasoningEffort", "high")
    if (
        plan["version"] != "LunaExecutionContractV1"
        or not _valid_luna_identifier(plan["probeId"])
        or role not in _MECHANICAL_ROLES
        or plan["decisionAuthority"] != "none"
        or plan["objectiveOracle"] != "caller-required"
        or reasoning_effort not in _LUNA_ALLOWED_REASONING_EFFORTS
        or not _valid_luna_tools(plan["allowedTools"])
        or not isinstance(plan["operations"], list)
        or not plan["operations"]
    ):
        return _luna_validation_result("E_LUNA_PLAN_INVALID")
    expected_root = _normalized_absolute_path(plan["exactRoot"])
    observed_root = _normalized_absolute_path(observed_git_root)
    if expected_root is None:
        return _luna_validation_result("E_LUNA_PLAN_INVALID")
    if (
        observed_root != expected_root
        or _luna_stable_ordinary_chain(
            _luna_absolute_chain(Path(expected_root)),
            leaf_kind="directory",
        )
        is None
    ):
        return _luna_validation_result("E_LUNA_PRECONDITION_FAILED")

    if role == "mechanical-scout":
        if (
            plan["taskClass"] not in {"micro", "mechanical-read"}
            or plan["expectedFactsVersion"] != "ScoutFactsV1"
        ):
            return _luna_validation_result("E_LUNA_PLAN_INVALID")
        for ordinal, operation in enumerate(plan["operations"]):
            stable_id = _validate_luna_operation(
                operation,
                ordinal,
                exact_root=Path(expected_root),
            )
            if stable_id is not None:
                return _luna_validation_result(stable_id)
    else:
        if (
            plan["taskClass"] != "mechanical"
            or len(plan["allowedTools"]) != 1
            or len(plan["operations"]) != 1
        ):
            return _luna_validation_result("E_LUNA_PLAN_INVALID")
        stable_id = _validate_luna_worker_operation(
            plan["operations"][0],
            exact_root=expected_root,
            allowed_tools=plan["allowedTools"],
        )
        if stable_id is not None:
            return _luna_validation_result(stable_id)
    return _luna_validation_result(None)


def _valid_scout_fact_value(operation: str, value: Any) -> bool:
    if operation == "path-kind":
        return value in {"missing", "file", "directory", "other"}
    if operation == "file-size":
        return isinstance(value, int) and not isinstance(value, bool) and value >= 0
    if operation == "sha256":
        return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{64}", value))
    if operation == "read-lines":
        return isinstance(value, list) and all(isinstance(line, str) for line in value)
    if operation == "list-directory":
        return (
            isinstance(value, list)
            and all(
                _exact_fields(item, frozenset({"name", "kind"}))
                and isinstance(item["name"], str)
                and item["name"]
                and item["kind"] in {"file", "directory", "other"}
                for item in value
            )
            and value
            == sorted(value, key=lambda item: (item["name"], item["kind"]))
        )
    return isinstance(value, bool)


def validate_scout_facts(
    plan: Any,
    facts: Any,
    *,
    observed_tools: Any,
    consumer_purpose: Any,
    observed_git_root: Any = None,
) -> dict[str, Any]:
    """Validate facts against one exact Luna plan and caller-owned tool trace."""

    if consumer_purpose != "facts-only":
        return _luna_validation_result("E_LUNA_AUTHORITY_VIOLATION")
    plan_result = validate_luna_execution_plan(
        plan, observed_git_root=observed_git_root
    )
    if not plan_result["valid"]:
        return plan_result
    if not _valid_luna_tools(observed_tools):
        return _luna_validation_result("E_LUNA_EXECUTION_ATTESTATION_UNAVAILABLE")
    if any(tool not in plan["allowedTools"] for tool in observed_tools):
        return _luna_validation_result("E_LUNA_TOOL_SCOPE_VIOLATION")
    if isinstance(facts, dict) and any(
        isinstance(field, str) and field.casefold() in _LUNA_AUTHORITY_FIELDS
        for field in facts
    ):
        return _luna_validation_result("E_LUNA_AUTHORITY_VIOLATION")
    if not _exact_fields(facts, _SCOUT_FACTS_FIELDS):
        return _luna_validation_result("E_LUNA_FACTS_INVALID")
    if (
        facts["version"] != "ScoutFactsV1"
        or facts["probeId"] != plan["probeId"]
        or facts["role"] != "mechanical-scout"
        or facts["observedTools"] != observed_tools
        or not isinstance(facts["facts"], list)
        or len(facts["facts"]) != len(plan["operations"])
    ):
        return _luna_validation_result("E_LUNA_FACTS_INVALID")
    for ordinal, (operation, fact) in enumerate(zip(plan["operations"], facts["facts"])):
        if not _exact_fields(fact, _SCOUT_FACT_FIELDS):
            return _luna_validation_result("E_LUNA_FACTS_INVALID")
        if fact["ordinal"] != ordinal or fact["op"] != operation["op"]:
            return _luna_validation_result("E_LUNA_FACTS_INVALID")
        if fact["execution"] == "ok":
            if fact["errorId"] is not None or not _valid_scout_fact_value(
                operation["op"], fact["value"]
            ):
                return _luna_validation_result("E_LUNA_FACTS_INVALID")
            if (
                operation["op"] == "read-lines"
                and len(fact["value"]) > operation["args"]["count"]
            ):
                return _luna_validation_result("E_LUNA_AUTHORITY_VIOLATION")
        elif (
            fact["execution"] != "error"
            or fact["value"] is not None
            or not isinstance(fact["errorId"], str)
            or not _LUNA_ERROR_ID.fullmatch(fact["errorId"])
        ):
            return _luna_validation_result("E_LUNA_FACTS_INVALID")
    return _luna_validation_result(None)
def is_executable_bearing(key: str, value: Any) -> bool:
    """True when a resolved key/value names an arbitrary executable a repo could supply."""
    return key == "reserveResolver" and isinstance(value, str) and value.startswith("wrapper:")


def reserve_resolver_trust(
    effective_value: Any,
    winning_rank: str,
    layered_values: list[tuple[str, Any]],
) -> str:
    """Classify the trust provenance of the effective `reserveResolver` value.

    Returns one of:
    - ``not-executable``: the value carries no arbitrary executable; no trust gate applies.
    - ``user-global``: executable-bearing and defined (or identically confirmed) at a
      user-global layer — honored without further confirmation.
    - ``project-UNCONFIRMED``: executable-bearing and supplied only by a project-local
      layer — MUST NOT be launched before explicit first-use user confirmation.
    """
    if not is_executable_bearing("reserveResolver", effective_value):
        return "not-executable"
    if winning_rank in USER_GLOBAL_RANKS or winning_rank == "defaults":
        return "user-global"
    for rank, value in layered_values:
        if rank in USER_GLOBAL_RANKS and value == effective_value:
            return "user-global"
    return "project-UNCONFIRMED"


def _load_normalizer(repo_root: Path):
    normalizer_path = repo_root / "scripts" / "normalize-agents-mode.py"
    spec = importlib.util.spec_from_file_location("_agents_mode_normalizer", normalizer_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {normalizer_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def strip_comment(value: str) -> str:
    return value.split(" #", 1)[0].strip()


def parse_provider_list(value: str) -> list[str]:
    value = strip_comment(value)
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    return [provider.strip() for provider in value.split(",") if provider.strip()]


def parse_agents_mode_text(text: str, scalar_decoder: Any) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_block: str | None = None
    current_profile: str | None = None

    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" ") and ":" in line:
            key, rest = line.split(":", 1)
            current_block = key.strip()
            current_profile = None
            if current_block == "externalPriorityProfiles":
                result[current_block] = {}
            elif current_block == "externalOpinionCounts":
                result[current_block] = {}
            else:
                result[current_block] = scalar_decoder(strip_comment(rest))
            continue

        if current_block == "externalPriorityProfiles":
            if line.startswith("  ") and not line.startswith("    ") and ":" in line:
                current_profile = line.split(":", 1)[0].strip()
                result[current_block][current_profile] = {}
                continue
            if line.startswith("    ") and current_profile and ":" in line:
                lane, rest = line.split(":", 1)
                result[current_block][current_profile][lane.strip()] = parse_provider_list(rest)
                continue

        if current_block == "externalOpinionCounts":
            if line.startswith("  ") and ":" in line:
                lane, rest = line.split(":", 1)
                value = strip_comment(rest)
                try:
                    result[current_block][lane.strip()] = int(value)
                except ValueError:
                    result[current_block][lane.strip()] = value

    return result


def canonical_defaults(repo_root: Path, provider: str, normalizer: Any) -> dict[str, Any]:
    template = repo_root / "shared" / "agents-mode.defaults.yaml"
    missing_target = repo_root / ".scratch" / "__agents_mode_missing__"
    normalizer_provider = "codex" if provider == "codex" else "shared"
    content = normalizer.normalize_file(str(template), str(missing_target), normalizer_provider)
    return parse_agents_mode_text(content, normalizer.decode_supported_yaml_scalar)


def load_role_policy(repo_root: Path) -> tuple[dict[str, Any], Path]:
    path = repo_root / "shared" / "role-routing-policy.v1.json"
    if not _ordinary_file(path):
        raise ValueError(f"E_ROLE_POLICY_INVALID: policy input is not ordinary: {path}")
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"E_ROLE_POLICY_INVALID: cannot load {path}: {exc}") from exc
    if not isinstance(policy, dict) or policy.get("schemaVersion") != 1:
        raise ValueError("E_ROLE_POLICY_INVALID: schemaVersion must be 1")

    model_tiers = policy.get("modelTierOrder")
    efforts = policy.get("effortOrder")
    profiles = policy.get("profiles")
    task_classes = policy.get("taskClasses")
    roles = policy.get("roles")
    skill_only_roles = policy.get("skillOnlyRoles")
    eligibility = policy.get("taskRoleEligibility")
    realizations = policy.get("providerRealizations")
    final_authorizing_roles = policy.get("finalAuthorizingRoles")
    mechanical_execution_contract = policy.get("mechanicalExecutionContract")
    if not all(
        isinstance(value, dict)
        for value in (
            profiles,
            task_classes,
            roles,
            skill_only_roles,
            eligibility,
            realizations,
        )
    ):
        raise ValueError("E_ROLE_POLICY_INVALID: policy maps are required")
    if not isinstance(model_tiers, list) or len(model_tiers) != len(set(model_tiers)):
        raise ValueError("E_ROLE_POLICY_INVALID: modelTierOrder must be unique")
    if not isinstance(efforts, list) or len(efforts) != len(set(efforts)):
        raise ValueError("E_ROLE_POLICY_INVALID: effortOrder must be unique")
    if (
        not isinstance(final_authorizing_roles, list)
        or not final_authorizing_roles
        or len(final_authorizing_roles) != len(set(final_authorizing_roles))
    ):
        raise ValueError("E_ROLE_POLICY_INVALID: finalAuthorizingRoles must be unique")
    if mechanical_execution_contract != _MECHANICAL_EXECUTION_CONTRACT_V1:
        raise ValueError("E_ROLE_POLICY_INVALID: mechanical execution contract")

    model_index = {value: index for index, value in enumerate(model_tiers)}
    effort_index = {value: index for index, value in enumerate(efforts)}
    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            raise ValueError(f"E_ROLE_POLICY_INVALID: profile {name} is not an object")
        if profile.get("modelTier") not in model_index:
            raise ValueError(f"E_ROLE_POLICY_INVALID: profile {name} model tier")
        if profile.get("effort") not in effort_index:
            raise ValueError(f"E_ROLE_POLICY_INVALID: profile {name} effort")
        if not isinstance(profile.get("codexModel"), str):
            raise ValueError(f"E_ROLE_POLICY_INVALID: profile {name} Codex model")
        if name != "luna-high" and (
            not isinstance(profile.get("useCriteria"), str)
            or not profile["useCriteria"].strip()
        ):
            raise ValueError(f"E_ROLE_POLICY_INVALID: profile {name} use criteria")

    if set(roles).intersection(skill_only_roles):
        raise ValueError("E_ROLE_POLICY_INVALID: native and skill-only roles overlap")
    role_catalog = {**roles, **skill_only_roles}
    for role_name, role in role_catalog.items():
        if not isinstance(role, dict):
            raise ValueError(f"E_ROLE_POLICY_INVALID: role {role_name} is not an object")
        allowed = role.get("allowedProfiles")
        default = role.get("defaultProfile")
        if not isinstance(allowed, list) or not allowed or default not in allowed:
            raise ValueError(f"E_ROLE_POLICY_INVALID: role {role_name} corridor")
        if any(profile not in profiles for profile in allowed):
            raise ValueError(f"E_ROLE_POLICY_INVALID: role {role_name} profile")
    if any(role_name not in role_catalog for role_name in final_authorizing_roles):
        raise ValueError("E_ROLE_POLICY_INVALID: finalAuthorizingRoles role")

    for task_name, task in task_classes.items():
        if not isinstance(task, dict):
            raise ValueError(f"E_ROLE_POLICY_INVALID: task {task_name} is not an object")
        required_model = task.get("requiredModelTier")
        required_effort = task.get("requiredEffort")
        if required_model not in model_index or required_effort not in effort_index:
            raise ValueError(f"E_ROLE_POLICY_INVALID: task {task_name} floor")
        admissible_profiles = task.get("admissibleProfiles")
        if task_name in _MECHANICAL_TASK_CLASSES:
            if admissible_profiles is not None:
                raise ValueError(f"E_ROLE_POLICY_INVALID: task {task_name} mechanical corridor")
        elif (
            not isinstance(admissible_profiles, list)
            or not admissible_profiles
            or len(admissible_profiles) != len(set(admissible_profiles))
            or any(profile not in profiles for profile in admissible_profiles)
        ):
            raise ValueError(f"E_ROLE_POLICY_INVALID: task {task_name} admissible profiles")
        eligible_roles = eligibility.get(task_name)
        if not isinstance(eligible_roles, list) or not eligible_roles:
            raise ValueError(f"E_ROLE_POLICY_INVALID: task {task_name} eligibility")
        for role_name in eligible_roles:
            if role_name not in role_catalog:
                raise ValueError(
                    f"E_ROLE_POLICY_INVALID: task {task_name} unknown role {role_name}"
                )
            default_profile = role_catalog[role_name]["defaultProfile"]
            profile = profiles[default_profile]
            if task_name in _MECHANICAL_TASK_CLASSES and (
                model_index[profile["modelTier"]] < model_index[required_model]
                or effort_index[profile["effort"]] < effort_index[required_effort]
            ):
                raise ValueError(
                    f"E_ROLE_POLICY_INVALID: task {task_name} role {role_name} default"
                )
            if task_name not in _MECHANICAL_TASK_CLASSES and (
                default_profile not in admissible_profiles
                or not set(role_catalog[role_name]["allowedProfiles"])
                & set(admissible_profiles)
            ):
                raise ValueError(
                    f"E_ROLE_POLICY_INVALID: task {task_name} role {role_name} default"
                )

    if set(eligibility) != set(task_classes):
        raise ValueError("E_ROLE_POLICY_INVALID: task eligibility keys drifted")
    for provider in EXTERNAL_DISPATCH_PROVIDERS:
        realization = realizations.get(provider)
        if not isinstance(realization, dict):
            raise ValueError(f"E_ROLE_POLICY_INVALID: {provider} realization")
        disposition = realization.get("executionDisposition")
        if isinstance(disposition, str):
            realization["executionDisposition"] = (
                _LEGACY_EXTERNAL_EXECUTION_DISPOSITIONS.get(
                    disposition, disposition
                )
            )
        allowed = realization.get("allowedTaskClasses")
        advisory = realization.get("advisoryTaskClasses", [])
        mutation_policy = realization.get("requiredMutationClass")
        mutation_classes = (
            [mutation_policy]
            if isinstance(mutation_policy, str)
            else mutation_policy
        )
        if (
            not isinstance(allowed, list)
            or len(allowed) != len(set(allowed))
            or any(task not in task_classes for task in allowed)
            or not isinstance(mutation_classes, list)
            or not mutation_classes
            or len(mutation_classes) != len(set(mutation_classes))
            or any(
                mutation not in {"read-only", "bounded-write"}
                for mutation in mutation_classes
            )
            or realization.get("independentVerification") is not True
            or not isinstance(realization.get("executionDisposition"), str)
            or realization.get("executionDisposition")
            not in _EXTERNAL_EXECUTION_DISPOSITIONS
            or realization.get("availability") not in _EXTERNAL_AVAILABILITIES
            or (
                realization["executionDisposition"],
                realization["availability"],
            )
            not in _EXTERNAL_DISPOSITION_AVAILABILITY_PAIRS
            or not isinstance(realization.get("effortMappingLoss"), str)
            or not realization["effortMappingLoss"]
        ):
            raise ValueError(f"E_ROLE_POLICY_INVALID: {provider} realization shape")
        if (
            not isinstance(advisory, list)
            or any(not isinstance(task, str) for task in advisory)
            or len(advisory) != len(set(advisory))
            or any(task not in allowed for task in advisory)
            or any(
                task_classes[task].get("mutationClass") != "read-only"
                for task in advisory
            )
        ):
            raise ValueError(
                f"E_ROLE_POLICY_INVALID: {provider} advisory task classes"
            )
    return policy, path


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _role_dispatch_decision(
    *,
    status: str,
    stable_id: str | None,
    task_class: str,
    role: str,
    requested_profile: str | None,
    requested_model: str | None,
    requested_effort: str | None,
    sandbox: str | None,
    execution_contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    decision = {
        "schemaVersion": 1,
        "status": status,
        "stableId": stable_id,
        "taskClass": task_class,
        "role": role,
        "requestedProfile": requested_profile,
        "requestedModel": requested_model,
        "requestedEffort": requested_effort,
        "sandbox": sandbox,
        "fallback": "none",
    }
    if execution_contract is not None:
        decision["executionContract"] = copy.deepcopy(execution_contract)
    return decision


def _role_dispatch_invalid(
    task_class: Any, role: Any, _cause: str
) -> dict[str, Any]:
    safe_task = task_class if isinstance(task_class, str) else ""
    safe_role = role if isinstance(role, str) else ""
    return _role_dispatch_decision(
        status="denied",
        stable_id="E_ROLE_POLICY_INVALID",
        task_class=safe_task[:128],
        role=safe_role[:128],
        requested_profile=None,
        requested_model=None,
        requested_effort=None,
        sandbox=None,
    )


def _valid_role_dispatch_request(task_class: Any, role_name: Any) -> bool:
    return (
        isinstance(task_class, str)
        and bool(task_class)
        and len(task_class) <= 128
        and isinstance(role_name, str)
        and bool(role_name)
        and len(role_name) <= 128
    )


def _load_role_dispatch_contract(
    repo_root: Path,
    task_class: Any,
    role_name: Any,
    *,
    manifest_path: Path | None = None,
    role_root: Path | None = None,
    linked_authority: Any | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not _valid_role_dispatch_request(task_class, role_name):
        return None, _role_dispatch_invalid(task_class, role_name, "request")
    try:
        policy, policy_path = load_role_policy(repo_root)
        tasks = policy["taskClasses"]
        roles = policy["roles"]
        eligibility = policy["taskRoleEligibility"]
        if (
            task_class not in tasks
            or role_name not in roles
            or role_name not in eligibility.get(task_class, ())
        ):
            return None, _role_dispatch_decision(
                status="denied",
                stable_id="E_ROLE_CORRIDOR_DENIED",
                task_class=task_class,
                role=role_name,
                requested_profile=None,
                requested_model=None,
                requested_effort=None,
                sandbox=None,
            )
        profile_name = roles[role_name]["defaultProfile"]
        profile = policy["profiles"][profile_name]
        model_index = {
            value: index for index, value in enumerate(policy["modelTierOrder"])
        }
        effort_index = {
            value: index for index, value in enumerate(policy["effortOrder"])
        }
        task = tasks[task_class]
        if task_class in _MECHANICAL_TASK_CLASSES and (
            model_index[profile["modelTier"]]
            < model_index[task["requiredModelTier"]]
            or effort_index[profile["effort"]]
            < effort_index[task["requiredEffort"]]
        ):
            return None, _role_dispatch_decision(
                status="denied",
                stable_id="E_ROLE_CORRIDOR_DENIED",
                task_class=task_class,
                role=role_name,
                requested_profile=profile_name,
                requested_model=profile["codexModel"],
                requested_effort=profile["effort"],
                sandbox=None,
            )

        manifest_path = manifest_path or (
            repo_root / "src.codex" / "agents" / "orchestrarium-role-manifest.json"
        )
        role_root = role_root or manifest_path.parent
        if linked_authority is not None:
            linked_authority.assert_current()
        if (
            not _ordinary_directory(role_root)
            or not _ordinary_file(manifest_path)
        ):
            raise ValueError("manifest or role root type")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if (
            not isinstance(manifest, dict)
            or manifest.get("schemaVersion") != 1
            or set(manifest) != {
                "schemaVersion",
                "packRevision",
                "policySha256",
                "roles",
            }
            or manifest.get("policySha256") != _file_sha256(policy_path)
            or not isinstance(manifest.get("roles"), dict)
        ):
            raise ValueError("manifest")
        record = manifest["roles"].get(role_name)
        if not isinstance(record, dict) or set(record) != {"relativePath", "sha256"}:
            raise ValueError("role record")
        if record["relativePath"] != f"{role_name}.toml":
            raise ValueError("role path")
        role_path = (
            linked_authority.ordinary_file(Path(record["relativePath"]))
            if linked_authority is not None
            else role_root / record["relativePath"]
        )
        if not _ordinary_file(role_path):
            raise ValueError("role type")
        role_bytes = role_path.read_bytes()
        if linked_authority is not None:
            linked_authority.assert_current()
        if record["sha256"] != hashlib.sha256(role_bytes).hexdigest():
            raise ValueError("role digest")
        role_toml = tomllib.loads(role_bytes.decode("utf-8"))
        sandbox = role_toml.get("sandbox_mode")
        expected_sandbox = (
            "read-only"
            if task["mutationClass"] == "read-only"
            else "workspace-write"
        )
        if (
            role_toml.get("name") != role_name
            or role_toml.get("model") != profile["codexModel"]
            or role_toml.get("model_reasoning_effort") != profile["effort"]
            or sandbox != expected_sandbox
        ):
            raise ValueError("role TOML contract")
        return {
            "taskClass": task_class,
            "role": role_name,
            "profile": profile_name,
            "model": profile["codexModel"],
            "effort": profile["effort"],
            "sandbox": sandbox,
            "roleSha256": record["sha256"],
            "policySha256": manifest["policySha256"],
            "executionContract": (
                policy["mechanicalExecutionContract"]
                if role_name in _MECHANICAL_ROLES
                else None
            ),
            "policy": policy,
            "task": task,
            "roleConfig": roles[role_name],
            "developerInstructions": str(role_toml.get("developer_instructions", "")),
        }, None
    except (KeyError, OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        return None, _role_dispatch_invalid(task_class, role_name, str(exc))


_ORDINARY_NATIVE_FAILURE_POLICY = {
    "hostRejection": "E_ORDINARY_NATIVE_SELECTION_REJECTED",
    "executionDrift": "E_ORDINARY_NATIVE_EXECUTION_DRIFT",
    "missingActualMetadata": "unspecified by runtime",
}


def _ordinary_native_denied(task_class: Any, role: Any, stable_id: str) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "status": "denied",
        "stableId": stable_id,
        "taskClass": task_class if isinstance(task_class, str) else "",
        "role": role if isinstance(role, str) else "",
        "fallback": "none",
    }


def _profession_skill_metadata(repo_root: Path, role: str, instructions: str) -> dict[str, Any]:
    candidates = (
        repo_root / "src.codex" / "skills" / role / "SKILL.md",
        repo_root.parent / role / "SKILL.md",
    )
    skill_path = next((path for path in candidates if _ordinary_file(path)), None)
    return {
        "skill": f"${role}" if skill_path is not None else None,
        "skillSha256": _file_sha256(skill_path) if skill_path is not None else None,
        "instructions": instructions,
        "instructionsSha256": hashlib.sha256(instructions.encode("utf-8")).hexdigest(),
    }


def _describe_ordinary_native_role_options_in_layout(
    role: Any,
    task_class: Any,
    host_observation: Any,
    *,
    repo_root: Path,
    manifest_path: Path | None = None,
    role_root: Path | None = None,
    linked_authority: Any | None = None,
) -> dict[str, Any]:
    if not _valid_role_dispatch_request(task_class, role):
        return _ordinary_native_denied(
            task_class, role, "E_ORDINARY_NATIVE_SELECTION_INVALID"
        )
    try:
        policy, _policy_path = load_role_policy(repo_root)
    except (OSError, ValueError):
        return _ordinary_native_denied(
            task_class, role, "E_ORDINARY_NATIVE_SELECTION_INVALID"
        )
    skill_only = policy["skillOnlyRoles"].get(role) if isinstance(role, str) else None
    if isinstance(skill_only, dict):
        if (
            task_class not in policy["taskClasses"]
            or role not in policy["taskRoleEligibility"].get(task_class, ())
            or task_class in _MECHANICAL_TASK_CLASSES
        ):
            return _ordinary_native_denied(
                task_class, role, "E_ORDINARY_NATIVE_SELECTION_INVALID"
            )
        profile_name = skill_only["defaultProfile"]
        profile = policy["profiles"][profile_name]
        instructions = (
            f"Activate ${role} and apply its current SKILL.md contract under AGENTS.md "
            "without widening the caller's authority, scope, or allowed tools."
        )
        contract = {
            "taskClass": task_class,
            "role": role,
            "profile": profile_name,
            "model": profile["codexModel"],
            "effort": profile["effort"],
            "policy": policy,
            "task": policy["taskClasses"][task_class],
            "roleConfig": skill_only,
            "developerInstructions": instructions,
            "roleKind": "skill-only",
        }
        early = None
    else:
        contract, early = _load_role_dispatch_contract(
            repo_root,
            task_class,
            role,
            manifest_path=manifest_path,
            role_root=role_root,
            linked_authority=linked_authority,
        )
        if contract is not None:
            contract["roleKind"] = "native"
    if early is not None or contract is None or contract["role"] in _MECHANICAL_ROLES:
        return _ordinary_native_denied(task_class, role, "E_ORDINARY_NATIVE_SELECTION_INVALID")
    if not isinstance(host_observation, dict) or set(host_observation) - {
        "explicitModelControl",
        "explicitReasoningEffortControl",
        "reportedModels",
        "reportedEfforts",
        "reportedAgentTypes",
    }:
        return _ordinary_native_denied(task_class, role, "E_ORDINARY_NATIVE_SELECTION_INVALID")
    if not isinstance(host_observation.get("explicitModelControl"), bool) or not isinstance(
        host_observation.get("explicitReasoningEffortControl"), bool
    ):
        return _ordinary_native_denied(task_class, role, "E_ORDINARY_NATIVE_SELECTION_INVALID")
    reported_models = host_observation.get("reportedModels")
    reported_efforts = host_observation.get("reportedEfforts")
    reported_agent_types = host_observation.get("reportedAgentTypes")
    for reported in (reported_models, reported_efforts, reported_agent_types):
        if reported is not None and (
            not isinstance(reported, list)
            or len(reported) != len(set(reported))
            or any(not isinstance(value, str) or not value for value in reported)
        ):
            return _ordinary_native_denied(task_class, role, "E_ORDINARY_NATIVE_SELECTION_INVALID")

    policy = contract["policy"]
    admissible = set(contract["task"]["admissibleProfiles"])
    option_names = [
        name for name in contract["roleConfig"]["allowedProfiles"] if name in admissible
    ]
    options = []
    explicit_controls = (
        host_observation["explicitModelControl"]
        and host_observation["explicitReasoningEffortControl"]
    )
    for name in option_names:
        profile = policy["profiles"][name]
        if reported_models is not None and profile["codexModel"] not in reported_models:
            continue
        if reported_efforts is not None and profile["effort"] not in reported_efforts:
            continue
        capability = (
            "controls-unavailable"
            if not explicit_controls
            else "reported"
            if reported_models is not None and reported_efforts is not None
            else "capability-unknown"
        )
        options.append(
            {
                "profile": name,
                "modelTier": profile["modelTier"],
                "model": profile["codexModel"],
                "effort": profile["effort"],
                "useCriteria": profile["useCriteria"],
                "hostCapability": capability,
            }
        )
    if not options:
        return _ordinary_native_denied(
            task_class, role, "E_ORDINARY_NATIVE_SELECTION_INVALID"
        )
    profession = _profession_skill_metadata(
        repo_root, contract["role"], contract["developerInstructions"]
    )
    if contract["roleKind"] == "skill-only" and profession["skill"] is None:
        return _ordinary_native_denied(
            task_class, role, "E_ORDINARY_NATIVE_SELECTION_INVALID"
        )
    default_agent_type_capability = (
        "not-applicable"
        if contract["roleKind"] == "skill-only"
        else "capability-unknown"
        if reported_agent_types is None
        else "reported"
        if contract["role"] in reported_agent_types
        else "reported-absent"
    )
    default_invocation = {
        "mode": "named-role-default",
        "agentType": contract["role"],
    }
    if contract["roleKind"] == "skill-only":
        default_invocation = {
            "mode": "generic-explicit-profile",
            "forkTurns": "none",
            "model": contract["model"],
            "reasoningEffort": contract["effort"],
            "professionSkill": profession["skill"],
            "promptPreamble": profession["instructions"],
        }
    return {
        "schemaVersion": 1,
        "status": "available",
        "stableId": None,
        "taskClass": contract["taskClass"],
        "role": contract["role"],
        "roleKind": contract["roleKind"],
        "mutationClass": contract["task"]["mutationClass"],
        "defaultProfile": contract["profile"],
        "defaultModelTier": policy["profiles"][contract["profile"]]["modelTier"],
        "defaultModel": contract["model"],
        "defaultEffort": contract["effort"],
        "profession": profession,
        "options": options,
        "hostObservation": copy.deepcopy(host_observation),
        "defaultAgentTypeCapability": default_agent_type_capability,
        "defaultInvocation": default_invocation,
        "explicitInvocation": {
            "mode": "generic-explicit-profile",
            "omitAgentType": True,
            "forkTurns": "none",
        },
        "failurePolicy": copy.deepcopy(_ORDINARY_NATIVE_FAILURE_POLICY),
        "fallback": "none",
    }


def describe_ordinary_native_role_options(
    role: Any,
    task_class: Any,
    host_observation: Any,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    source_root = Path(repo_root).resolve() if repo_root is not None else Path(__file__).resolve().parents[1]
    return _describe_ordinary_native_role_options_in_layout(
        role, task_class, host_observation, repo_root=source_root
    )


def resolve_ordinary_native_dispatch(
    description: Any,
    *,
    requested_model: Any = None,
    requested_effort: Any = None,
    caller_rationale: Any,
    approved_execution_scope: Any,
    user_approved_max: bool = False,
) -> dict[str, Any]:
    if (
        not isinstance(description, dict)
        or description.get("status") != "available"
        or not isinstance(caller_rationale, str)
        or not caller_rationale.strip()
        or not isinstance(approved_execution_scope, dict)
        or not approved_execution_scope
        or (requested_model is None) != (requested_effort is None)
    ):
        return _ordinary_native_denied("", "", "E_ORDINARY_NATIVE_SELECTION_INVALID")
    explicit = requested_model is not None
    selected = None
    if not explicit and description.get("roleKind") == "native" and (
        description.get("defaultAgentTypeCapability") == "reported-absent"
    ):
        return _ordinary_native_denied(
            description.get("taskClass"),
            description.get("role"),
            "E_ORDINARY_NATIVE_AGENT_TYPE_UNAVAILABLE",
        )
    if not explicit and description.get("roleKind") == "skill-only":
        if not (
            description["hostObservation"].get("explicitModelControl")
            and description["hostObservation"].get("explicitReasoningEffortControl")
        ):
            return _ordinary_native_denied(
                description.get("taskClass"),
                description.get("role"),
                "E_ORDINARY_NATIVE_CONTROLS_UNAVAILABLE",
            )
        selected = next(
            (
                option
                for option in description.get("options", ())
                if option.get("profile") == description.get("defaultProfile")
            ),
            None,
        )
        if selected is None:
            return _ordinary_native_denied(
                description.get("taskClass"),
                description.get("role"),
                "E_ORDINARY_NATIVE_SELECTION_INVALID",
            )
    if explicit:
        if not (
            description["hostObservation"].get("explicitModelControl")
            and description["hostObservation"].get("explicitReasoningEffortControl")
        ):
            return _ordinary_native_denied(
                description.get("taskClass"),
                description.get("role"),
                "E_ORDINARY_NATIVE_CONTROLS_UNAVAILABLE",
            )
        selected = next(
            (
                option
                for option in description.get("options", ())
                if option.get("model") == requested_model
                and option.get("effort") == requested_effort
            ),
            None,
        )
        if selected is None or (requested_effort == "max" and user_approved_max is not True):
            return _ordinary_native_denied(
                description.get("taskClass"),
                description.get("role"),
                "E_ORDINARY_NATIVE_SELECTION_INVALID",
            )
    invocation = copy.deepcopy(description["defaultInvocation"])
    resolved_profile = description["defaultProfile"]
    resolved_model_tier = description["defaultModelTier"]
    resolved_model = description["defaultModel"]
    resolved_effort = description["defaultEffort"]
    host_capability = description.get(
        "defaultAgentTypeCapability", "capability-unknown"
    )
    if selected is not None:
        resolved_profile = selected["profile"]
        resolved_model_tier = selected["modelTier"]
        resolved_model = selected["model"]
        resolved_effort = selected["effort"]
        host_capability = selected["hostCapability"]
        invocation = {
            "mode": "generic-explicit-profile",
            "forkTurns": "none",
            "model": resolved_model,
            "reasoningEffort": resolved_effort,
            "professionSkill": description["profession"]["skill"],
            "promptPreamble": description["profession"]["instructions"],
        }
    return {
        "schemaVersion": 1,
        "status": "resolved",
        "stableId": None,
        "taskClass": description["taskClass"],
        "role": description["role"],
        "requestedModel": requested_model,
        "requestedEffort": requested_effort,
        "modelTier": resolved_model_tier,
        "resolvedProfile": resolved_profile,
        "resolvedModel": resolved_model,
        "resolvedEffort": resolved_effort,
        "hostCapability": host_capability,
        "profession": copy.deepcopy(description["profession"]),
        "callerRationale": caller_rationale,
        "approvedExecutionScope": copy.deepcopy(approved_execution_scope),
        "invocation": invocation,
        "failurePolicy": copy.deepcopy(_ORDINARY_NATIVE_FAILURE_POLICY),
        "fallback": "none",
    }


def _resolve_role_dispatch_in_layout(
    task_class: Any,
    role: Any,
    effective_feature_state: Any,
    *,
    repo_root: Path,
    manifest_path: Path | None = None,
    role_root: Path | None = None,
    linked_authority: Any | None = None,
) -> dict[str, Any]:
    contract, early = _load_role_dispatch_contract(
        repo_root,
        task_class,
        role,
        manifest_path=manifest_path,
        role_root=role_root,
        linked_authority=linked_authority,
    )
    if early is not None:
        return early
    assert contract is not None
    if (
        contract["role"] not in _MECHANICAL_ROLES
        or contract["taskClass"] not in _MECHANICAL_TASK_CLASSES
        or contract["model"] != "gpt-5.6-luna"
    ):
        return _role_dispatch_decision(
            status="denied",
            stable_id="E_ROLE_CORRIDOR_DENIED",
            task_class=contract["taskClass"],
            role=contract["role"],
            requested_profile=contract["profile"],
            requested_model=contract["model"],
            requested_effort=contract["effort"],
            sandbox=None,
        )
    if effective_feature_state not in {"enabled", "disabled"}:
        return _role_dispatch_invalid(task_class, role, "feature-state")
    if effective_feature_state == "disabled":
        return _role_dispatch_decision(
            status="unavailable",
            stable_id="E_NATIVE_V2_DISABLED",
            task_class=contract["taskClass"],
            role=contract["role"],
            requested_profile=contract["profile"],
            requested_model=contract["model"],
            requested_effort=contract["effort"],
            sandbox=contract["sandbox"],
            execution_contract=contract["executionContract"],
        )
    return _role_dispatch_decision(
        status="native-required",
        stable_id=None,
        task_class=contract["taskClass"],
        role=contract["role"],
        requested_profile=contract["profile"],
        requested_model=contract["model"],
        requested_effort=contract["effort"],
        sandbox=contract["sandbox"],
        execution_contract=contract["executionContract"],
    )


def resolve_role_dispatch(
    task_class: Any,
    role: Any,
    effective_feature_state: Any,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Resolve one caller-neutral native policy without launching a provider."""

    source_root = (
        Path(repo_root).resolve()
        if repo_root is not None
        else Path(__file__).resolve().parents[1]
    )
    return _resolve_role_dispatch_in_layout(
        task_class,
        role,
        effective_feature_state,
        repo_root=source_root,
    )


def _external_dispatch_decision(
    *,
    status: str,
    stable_id: str | None,
    provider: str,
    task_class: str,
    role: str,
    required_model_tier: str | None,
    required_effort: str | None,
    mutation_class: str | None,
    native_effort: str | None,
    effort_mapping_loss: str | None,
    final_authorizing_role: bool,
    execution_authorized: bool,
    independent_verification: bool,
) -> dict[str, Any]:
    return {
        "schemaVersion": 1,
        "status": status,
        "stableId": stable_id,
        "provider": provider,
        "taskClass": task_class,
        "role": role,
        "requiredModelTier": required_model_tier,
        "requiredEffort": required_effort,
        "mutationClass": mutation_class,
        "nativeEffort": native_effort,
        "effortMappingLoss": effort_mapping_loss,
        "finalAuthorizingRole": final_authorizing_role,
        "executionAuthorized": execution_authorized,
        "independentVerification": independent_verification,
        "fallback": "none",
    }


def _external_role_mapping(policy_root: Path) -> dict[str, str]:
    """Load the paired external role taxonomy without retyping its membership."""

    candidates = (
        policy_root / "shared" / _EXTERNAL_ROLE_TAXONOMY_NAME,
        policy_root / "scripts" / _EXTERNAL_ROLE_TAXONOMY_NAME,
    )
    taxonomy_paths = [path for path in candidates if _ordinary_file(path)]
    if len(taxonomy_paths) != 1:
        raise ValueError("external role taxonomy is missing or ambiguous")
    taxonomy_path = taxonomy_paths[0]
    metadata = taxonomy_path.lstat()
    descriptor = os.open(
        taxonomy_path,
        os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0),
    )
    try:
        opened = os.fstat(descriptor)
        if (opened.st_dev, opened.st_ino, opened.st_mode) != (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_mode,
        ):
            raise ValueError("external role taxonomy identity changed")
        payload = os.read(descriptor, _EXTERNAL_ROLE_TAXONOMY_MAX_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(payload) > _EXTERNAL_ROLE_TAXONOMY_MAX_BYTES:
        raise ValueError("external role taxonomy exceeds byte limit")
    document = json.loads(payload.decode("utf-8", errors="strict"))
    if (
        not isinstance(document, dict)
        or set(document) != {"schemaVersion", "roles"}
        or document.get("schemaVersion") != 1
        or not isinstance(document.get("roles"), dict)
    ):
        raise ValueError("external role taxonomy shape")
    mapping = document["roles"]
    if any(
        not isinstance(role, str)
        or not role
        or lane not in _EXTERNAL_ROLE_LANES
        for role, lane in mapping.items()
    ):
        raise ValueError("external role taxonomy membership")
    return mapping


def _external_consultant_role(policy_root: Path) -> str:
    """Derive the single advisory role from the paired external taxonomy."""

    mapping = _external_role_mapping(policy_root)
    consultant_roles = [role for role, lane in mapping.items() if lane == "consultant"]
    if len(consultant_roles) != 1:
        raise ValueError("external role taxonomy consultant lane")
    return consultant_roles[0]


def resolve_external_dispatch(
    provider: Any,
    task_class: Any,
    role: Any,
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Resolve one explicit external-provider policy without probing or launching."""

    provider_name = provider if isinstance(provider, str) else ""
    task_name = task_class if isinstance(task_class, str) else ""
    role_name = role if isinstance(role, str) else ""
    if provider_name not in EXTERNAL_DISPATCH_PROVIDERS:
        return _external_dispatch_decision(
            status="denied",
            stable_id="E_EXTERNAL_DISPATCH_DENIED",
            provider=provider_name,
            task_class=task_name,
            role=role_name,
            required_model_tier=None,
            required_effort=None,
            mutation_class=None,
            native_effort=None,
            effort_mapping_loss=None,
            final_authorizing_role=False,
            execution_authorized=False,
            independent_verification=False,
        )

    stable_id = f"E_{provider_name.upper()}_DISPATCH_DENIED"
    source_root = (
        Path(repo_root).resolve()
        if repo_root is not None
        else Path(__file__).resolve().parents[1]
    )
    try:
        policy, _policy_path = load_role_policy(source_root)
        realization = policy["providerRealizations"][provider_name]
        task = policy["taskClasses"].get(task_name)
        eligible = policy["taskRoleEligibility"].get(task_name)
        final_authorizing_role = role_name in policy["finalAuthorizingRoles"]
        independent_verification = realization["independentVerification"] is True
        role_lane = _external_role_mapping(source_root).get(role_name)
        ordinary_role_admitted = (
            isinstance(eligible, list)
            and role_name in eligible
            and role_lane != "consultant"
        )
        task_mutation = task.get("mutationClass") if isinstance(task, dict) else None
        mutation_policy = realization["requiredMutationClass"]
        admitted_mutations = (
            [mutation_policy]
            if isinstance(mutation_policy, str)
            else mutation_policy
        )
        bounded_role_admitted = True
        if task_mutation == "bounded-write":
            bounded_role_admitted = role_lane == "external-worker"
        advisory_role_admitted = False
        if (
            not ordinary_role_admitted
            and task_name in realization.get("advisoryTaskClasses", [])
        ):
            advisory_role_admitted = role_name == _external_consultant_role(source_root)
        base_admitted = (
            isinstance(task, dict)
            and isinstance(eligible, list)
            and task_name in realization["allowedTaskClasses"]
            and (ordinary_role_admitted or advisory_role_admitted)
            and task_mutation in admitted_mutations
            and bounded_role_admitted
            and independent_verification
        )
        admitted = base_admitted and not final_authorizing_role
        execution_authorized = (
            admitted
            and realization["executionDisposition"] == "explicit-wrapper"
            and realization["availability"] == "available"
        )
        unavailable = (
            admitted
            and realization["executionDisposition"] == "classifier-only"
            and realization["availability"] == "unavailable"
        )
    except (KeyError, OSError, TypeError, ValueError):
        realization = {}
        task = None
        admitted = False
        base_admitted = False
        final_authorizing_role = False
        execution_authorized = False
        independent_verification = False
        unavailable = False

    return _external_dispatch_decision(
        status=(
            "external-authorized"
            if execution_authorized
            else (
                "unavailable"
                if unavailable
                else ("external-required" if admitted else "denied")
            )
        ),
        stable_id=(
            None
            if admitted
            else (
                f"E_{provider_name.upper()}_FINAL_OWNER_DENIED"
                if base_admitted and final_authorizing_role
                else stable_id
            )
        ),
        provider=provider_name,
        task_class=task_name,
        role=role_name,
        required_model_tier=(task.get("requiredModelTier") if isinstance(task, dict) else None),
        required_effort=(task.get("requiredEffort") if isinstance(task, dict) else None),
        mutation_class=(task.get("mutationClass") if isinstance(task, dict) else None),
        native_effort=(realization.get("effort") if isinstance(realization, dict) else None),
        effort_mapping_loss=(
            realization.get("effortMappingLoss")
            if isinstance(realization, dict)
            else None
        ),
        final_authorizing_role=final_authorizing_role,
        execution_authorized=execution_authorized,
        independent_verification=independent_verification,
    )


def _same_path(left: Path, right: Path) -> bool:
    return os.path.normcase(os.path.abspath(left)) == os.path.normcase(
        os.path.abspath(right)
    )


def _linked_runtime_subroots_module(resolver: Path):
    path = resolver.parent / "linked_runtime_subroots.py"
    spec = importlib.util.spec_from_file_location(
        "orchestrarium_linked_runtime_subroots", path
    )
    if spec is None or spec.loader is None:
        raise ValueError("installed linked runtime authority is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _source_layout_root(resolver: Path, repo_root: Path) -> Path | None:
    expected = repo_root / "scripts" / "resolve-agents-mode.py"
    source_agents = repo_root / "src.codex" / "agents"
    return (
        repo_root
        if _same_path(resolver, expected) and _ordinary_directory(source_agents)
        else None
    )


def _installed_role_dispatch_layout(
    resolver: Path,
    project_root: Path,
    home: Path,
) -> tuple[Path, Path, Path, Any | None]:
    project_resolver = (
        project_root
        / ".agents"
        / "skills"
        / "lead"
        / "scripts"
        / "resolve-agents-mode.py"
    )
    global_resolver = (
        home
        / ".agents"
        / "skills"
        / "lead"
        / "scripts"
        / "resolve-agents-mode.py"
    )
    matches = [
        (project_resolver, project_root / ".codex" / "agents"),
        (global_resolver, home / ".codex" / "agents"),
    ]
    selected = [
        ("project" if candidate == project_resolver else "global", role_root)
        for candidate, role_root in matches
        if _same_path(resolver, candidate)
    ]
    if len(selected) != 1:
        raise ValueError("installed resolver layout is missing or ambiguous")
    scope, selected_root = selected[0]
    authority = _linked_runtime_subroots_module(resolver).LinkedRuntimeSubrootAuthority.bind(
        selected_root,
        scope=scope,
        trusted_global_roots=(home / ".codex" / "agents",),
    )
    role_root = authority.resolved_root if authority is not None else selected_root
    lead_root = resolver.parent.parent
    shared_root = lead_root / "shared"
    if (
        not _ordinary_file(resolver)
        or not _ordinary_directory(lead_root)
        or not _ordinary_directory(shared_root)
        or not _ordinary_directory(role_root)
    ):
        raise ValueError("installed resolver layout contains a reparse or missing root")
    return (
        lead_root,
        shared_root / "orchestrarium-role-manifest.json",
        role_root,
        authority,
    )


def _installed_external_policy_root(
    resolver: Path,
    project_root: Path,
    home: Path,
) -> Path:
    candidates = (
        (
            project_root,
            (".agents", "skills", "lead", "scripts"),
            "project",
        ),
        (
            home,
            (".agents", "skills", "lead", "scripts"),
            "global",
        ),
        (
            project_root,
            (".claude", "agents", "scripts"),
            "project",
        ),
        (
            home,
            (".claude", "agents", "scripts"),
            "global",
        ),
    )
    selected = [
        (base, directories, scope)
        for base, directories, scope in candidates
        if _same_path(
            resolver,
            base.joinpath(*directories, "resolve-agents-mode.py"),
        )
    ]
    if len(selected) != 1:
        raise ValueError("installed external resolver layout is missing or ambiguous")

    base, directories, scope = selected[0]
    logical_policy_root = base.joinpath(*directories[:-1])
    authority = None
    if scope == "global":
        authority = _linked_runtime_subroots_module(
            resolver
        ).LinkedRuntimeSubrootAuthority.bind(
            logical_policy_root,
            scope=scope,
            trusted_global_roots=(logical_policy_root,),
            allow_linked_ancestors=True,
        )
    if authority is None:
        current = base
        for directory in directories:
            current /= directory
            if not _ordinary_directory(current):
                raise ValueError(
                    "installed external resolver layout contains a reparse or missing root"
                )
        policy_root = logical_policy_root
    else:
        policy_root = authority.resolved_root
        authority.ordinary_file(Path("scripts") / "resolve-agents-mode.py")
        authority.ordinary_file(Path("shared") / "role-routing-policy.v1.json")
    shared_root = policy_root / "shared"
    policy_path = shared_root / "role-routing-policy.v1.json"
    if (
        not _ordinary_file(resolver)
        or not _ordinary_directory(policy_root)
        or not _ordinary_directory(shared_root)
        or not _ordinary_file(policy_path)
    ):
        raise ValueError("installed external resolver layout contains a reparse or missing root")
    return policy_root


def layer_paths(provider: str, project_root: Path, home: Path) -> list[tuple[str, Path]]:
    provider_dir = PROVIDER_DIRS[provider]
    return [
        ("local", project_root / provider_dir / ".agents-mode.yaml"),
        ("local-legacy", project_root / provider_dir / ".agents-mode"),
        ("global", home / f".{provider}" / ".agents-mode.yaml"),
        ("global-legacy", home / f".{provider}" / ".agents-mode"),
        ("shared-global", home / ".agents-mode.yaml"),
    ]


def resolve(provider: str, project_root: Path, home: Path, repo_root: Path) -> dict[str, Any]:
    if provider in REMOVED_EXTERNAL_PROVIDERS:
        raise ValueError(
            "E_EXTERNAL_PROVIDER_REMOVED: "
            f"provider '{provider}' was removed; choose codex, claude, or explicit kimi"
        )
    if provider not in PROVIDER_DIRS:
        raise ValueError(f"unsupported agents-mode provider: {provider}")
    values: dict[str, Any] = {}
    sources: dict[str, dict[str, str]] = {}
    reserve_resolver_layers: list[tuple[str, Any]] = []
    normalizer = _load_normalizer(repo_root)

    for rank, path in layer_paths(provider, project_root, home):
        if not path.is_file():
            continue
        parsed = parse_agents_mode_text(
            path.read_text(encoding="utf-8"),
            normalizer.decode_supported_yaml_scalar,
        )
        if "reserveResolver" in parsed:
            reserve_resolver_layers.append((rank, parsed["reserveResolver"]))
        for key, value in parsed.items():
            if key in values:
                continue
            values[key] = value
            sources[key] = {"rank": rank, "path": str(path)}

    for key, value in canonical_defaults(repo_root, provider, normalizer).items():
        if key in values:
            continue
        values[key] = value
        sources[key] = {"rank": "defaults", "path": str(repo_root / "shared" / "agents-mode.defaults.yaml")}

    trust = reserve_resolver_trust(
        values.get("reserveResolver"),
        sources.get("reserveResolver", {}).get("rank", "defaults"),
        reserve_resolver_layers,
    )

    role_policy, role_policy_path = load_role_policy(repo_root)
    return {
        "provider": provider,
        "projectRoot": str(project_root),
        "home": str(home),
        "values": values,
        "sources": sources,
        "reserveResolverTrust": trust,
        "rolePolicy": role_policy,
        "rolePolicySource": str(role_policy_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--home", default=str(Path.home()))
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--resolve-role-dispatch", action="store_true")
    parser.add_argument("--resolve-external-dispatch", action="store_true")
    parser.add_argument("--ordinary-native-action", choices=("describe", "resolve"))
    parser.add_argument("--task-class")
    parser.add_argument("--role")
    parser.add_argument("--feature-state", choices=("enabled", "disabled"))
    parser.add_argument("--host-controls", choices=("explicit", "unavailable"))
    parser.add_argument("--reported-model", action="append")
    parser.add_argument("--reported-effort", action="append")
    parser.add_argument("--reported-agent-type", action="append")
    parser.add_argument("--requested-model")
    parser.add_argument("--requested-effort")
    parser.add_argument("--caller-rationale")
    parser.add_argument("--approved-scope-json")
    parser.add_argument("--user-approved-max", action="store_true")
    parser.add_argument("--json", action="store_true", help="emit JSON output")
    args = parser.parse_args()

    if args.provider in REMOVED_EXTERNAL_PROVIDERS:
        parser.error(
            "E_EXTERNAL_PROVIDER_REMOVED: "
            f"provider '{args.provider}' was removed; choose codex, claude, or explicit kimi"
        )
    if args.provider not in PROVIDER_CHOICES:
        parser.error(
            f"unsupported provider '{args.provider}'; expected one of "
            + ", ".join(PROVIDER_CHOICES)
        )

    resolver_path = Path(os.path.abspath(__file__))
    repo_root = Path(args.repo_root).resolve()
    project_root = Path(args.project_root).resolve()
    home = Path(os.path.expanduser(args.home)).resolve()
    source_root = _source_layout_root(resolver_path, repo_root)
    dispatch_modes = sum(
        bool(value)
        for value in (
            args.resolve_role_dispatch,
            args.resolve_external_dispatch,
            args.ordinary_native_action,
        )
    )
    if dispatch_modes > 1:
        parser.error("choose exactly one dispatch resolver")
    if args.ordinary_native_action:
        if (
            args.provider != "codex"
            or not args.json
            or args.task_class is None
            or args.role is None
            or args.host_controls is None
            or args.feature_state is not None
        ):
            parser.error(
                "--ordinary-native-action requires provider codex, task class, role, "
                "host controls, no feature state, and --json"
            )
        host_observation: dict[str, Any] = {
            "explicitModelControl": args.host_controls == "explicit",
            "explicitReasoningEffortControl": args.host_controls == "explicit",
        }
        if args.reported_model is not None:
            host_observation["reportedModels"] = args.reported_model
        if args.reported_effort is not None:
            host_observation["reportedEfforts"] = args.reported_effort
        if args.reported_agent_type is not None:
            host_observation["reportedAgentTypes"] = args.reported_agent_type
        if source_root is not None:
            description = describe_ordinary_native_role_options(
                args.role,
                args.task_class,
                host_observation,
                repo_root=source_root,
            )
        else:
            try:
                installed_root, manifest_path, role_root, authority = (
                    _installed_role_dispatch_layout(resolver_path, project_root, home)
                )
            except (OSError, ValueError):
                description = _ordinary_native_denied(
                    args.task_class, args.role, "E_ORDINARY_NATIVE_SELECTION_INVALID"
                )
            else:
                description = _describe_ordinary_native_role_options_in_layout(
                    args.role,
                    args.task_class,
                    host_observation,
                    repo_root=installed_root,
                    manifest_path=manifest_path,
                    role_root=role_root,
                    linked_authority=authority,
                )
        decision = description
        if args.ordinary_native_action == "resolve":
            if args.caller_rationale is None or args.approved_scope_json is None:
                parser.error(
                    "ordinary native resolve requires caller rationale and approved scope JSON"
                )
            try:
                approved_scope = json.loads(args.approved_scope_json)
            except json.JSONDecodeError:
                parser.error("approved scope JSON is invalid")
            decision = resolve_ordinary_native_dispatch(
                description,
                requested_model=args.requested_model,
                requested_effort=args.requested_effort,
                caller_rationale=args.caller_rationale,
                approved_execution_scope=approved_scope,
                user_approved_max=args.user_approved_max,
            )
        json.dump(decision, sys.stdout, sort_keys=True, separators=(",", ":"))
        sys.stdout.write("\n")
        return 0
    if args.resolve_role_dispatch:
        if (
            args.provider != "codex"
            or not args.json
            or args.task_class is None
            or args.role is None
            or args.feature_state is None
        ):
            parser.error(
                "--resolve-role-dispatch requires provider codex, task class, role, "
                "feature state, and --json"
            )

        if source_root is not None:
            decision = resolve_role_dispatch(
                args.task_class,
                args.role,
                args.feature_state,
                repo_root=source_root,
            )
        else:
            try:
                installed_root, manifest_path, role_root, authority = (
                    _installed_role_dispatch_layout(
                        resolver_path,
                        project_root,
                        home,
                    )
                )
            except (OSError, ValueError) as exc:
                decision = _role_dispatch_invalid(
                    args.task_class, args.role, str(exc)
                )
            else:
                decision = _resolve_role_dispatch_in_layout(
                    args.task_class,
                    args.role,
                    args.feature_state,
                    repo_root=installed_root,
                    manifest_path=manifest_path,
                    role_root=role_root,
                    linked_authority=authority,
                )
        json.dump(decision, sys.stdout, sort_keys=True, separators=(",", ":"))
        sys.stdout.write("\n")
        return 0

    if args.resolve_external_dispatch:
        if (
            args.provider not in EXTERNAL_DISPATCH_PROVIDERS
            or not args.json
            or args.task_class is None
            or args.role is None
            or args.feature_state is not None
        ):
            parser.error(
                "--resolve-external-dispatch requires provider kimi or grok, "
                "task class, role, no feature state, and --json"
            )
        if source_root is not None:
            external_root = source_root
        else:
            try:
                external_root = _installed_external_policy_root(
                    resolver_path,
                    project_root,
                    home,
                )
            except (OSError, ValueError):
                external_root = repo_root / "__invalid_external_layout__"
        decision = resolve_external_dispatch(
            args.provider,
            args.task_class,
            args.role,
            repo_root=external_root,
        )
        json.dump(decision, sys.stdout, sort_keys=True, separators=(",", ":"))
        sys.stdout.write("\n")
        return 0

    if source_root is None:
        parser.error("installed layout supports dispatch resolution only")
    if args.provider not in PROVIDER_DIRS:
        parser.error("explicit-only providers support external dispatch resolution only")
    resolved = resolve(
        args.provider,
        project_root,
        home,
        source_root,
    )
    if args.json:
        json.dump(resolved, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
        return 0

    for key, value in resolved["values"].items():
        source = resolved["sources"][key]
        print(f"{key}: {value}  # {source['rank']} {source['path']}")
    print(f"reserveResolverTrust: {resolved['reserveResolverTrust']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
