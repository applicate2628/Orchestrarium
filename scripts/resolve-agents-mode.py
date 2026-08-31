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
PROVIDER_CHOICES = tuple(sorted((*PROVIDER_DIRS, *EXTERNAL_DISPATCH_PROVIDERS)))
_EXTERNAL_EXECUTION_DISPOSITIONS = frozenset(
    {"explicit-read-only", "classifier-only"}
)
_EXTERNAL_AVAILABILITIES = frozenset({"available", "unavailable"})
_EXTERNAL_DISPOSITION_AVAILABILITY_PAIRS = frozenset(
    {
        ("explicit-read-only", "available"),
        ("classifier-only", "unavailable"),
    }
)
_MECHANICAL_ROLES = frozenset({"mechanical-scout", "mechanical-worker"})
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


def parse_agents_mode_text(text: str) -> dict[str, Any]:
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
                result[current_block] = strip_comment(rest)
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


def canonical_defaults(repo_root: Path, provider: str) -> dict[str, Any]:
    normalizer = _load_normalizer(repo_root)
    template = repo_root / "shared" / "agents-mode.defaults.yaml"
    missing_target = repo_root / ".scratch" / "__agents_mode_missing__"
    normalizer_provider = "codex" if provider == "codex" else "shared"
    content = normalizer.normalize_file(str(template), str(missing_target), normalizer_provider)
    return parse_agents_mode_text(content)


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
    eligibility = policy.get("taskRoleEligibility")
    realizations = policy.get("providerRealizations")
    final_authorizing_roles = policy.get("finalAuthorizingRoles")
    mechanical_execution_contract = policy.get("mechanicalExecutionContract")
    if not all(
        isinstance(value, dict)
        for value in (profiles, task_classes, roles, eligibility, realizations)
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

    for role_name, role in roles.items():
        if not isinstance(role, dict):
            raise ValueError(f"E_ROLE_POLICY_INVALID: role {role_name} is not an object")
        allowed = role.get("allowedProfiles")
        default = role.get("defaultProfile")
        if not isinstance(allowed, list) or not allowed or default not in allowed:
            raise ValueError(f"E_ROLE_POLICY_INVALID: role {role_name} corridor")
        if any(profile not in profiles for profile in allowed):
            raise ValueError(f"E_ROLE_POLICY_INVALID: role {role_name} profile")
    if any(role_name not in roles for role_name in final_authorizing_roles):
        raise ValueError("E_ROLE_POLICY_INVALID: finalAuthorizingRoles role")

    for task_name, task in task_classes.items():
        if not isinstance(task, dict):
            raise ValueError(f"E_ROLE_POLICY_INVALID: task {task_name} is not an object")
        required_model = task.get("requiredModelTier")
        required_effort = task.get("requiredEffort")
        if required_model not in model_index or required_effort not in effort_index:
            raise ValueError(f"E_ROLE_POLICY_INVALID: task {task_name} floor")
        eligible_roles = eligibility.get(task_name)
        if not isinstance(eligible_roles, list) or not eligible_roles:
            raise ValueError(f"E_ROLE_POLICY_INVALID: task {task_name} eligibility")
        for role_name in eligible_roles:
            if role_name not in roles:
                raise ValueError(
                    f"E_ROLE_POLICY_INVALID: task {task_name} unknown role {role_name}"
                )
            default_profile = roles[role_name]["defaultProfile"]
            profile = profiles[default_profile]
            if (
                model_index[profile["modelTier"]] < model_index[required_model]
                or effort_index[profile["effort"]] < effort_index[required_effort]
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
        allowed = realization.get("allowedTaskClasses")
        if (
            not isinstance(allowed, list)
            or len(allowed) != len(set(allowed))
            or any(task not in task_classes for task in allowed)
            or realization.get("requiredMutationClass") != "read-only"
            or realization.get("independentVerification") is not True
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


def _load_role_dispatch_contract(
    repo_root: Path,
    task_class: Any,
    role_name: Any,
    *,
    manifest_path: Path | None = None,
    role_root: Path | None = None,
    linked_authority: Any | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if (
        not isinstance(task_class, str)
        or not task_class
        or len(task_class) > 128
        or not isinstance(role_name, str)
        or not role_name
        or len(role_name) > 128
    ):
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
        if (
            model_index[profile["modelTier"]]
            < model_index[task["requiredModelTier"]]
            or effort_index[profile["effort"]]
            < effort_index[task["requiredEffort"]]
            or profile["codexModel"] != "gpt-5.6-luna"
            or role_name not in {"mechanical-scout", "mechanical-worker"}
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
        }, None
    except (KeyError, OSError, UnicodeDecodeError, ValueError, json.JSONDecodeError, tomllib.TOMLDecodeError) as exc:
        return None, _role_dispatch_invalid(task_class, role_name, str(exc))


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
        base_admitted = (
            isinstance(task, dict)
            and isinstance(eligible, list)
            and task_name in realization["allowedTaskClasses"]
            and role_name in eligible
            and task.get("mutationClass")
            == realization["requiredMutationClass"]
            == "read-only"
            and independent_verification
        )
        admitted = base_admitted and not final_authorizing_role
        execution_authorized = (
            admitted
            and realization["executionDisposition"] == "explicit-read-only"
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
        ),
        (
            home,
            (".agents", "skills", "lead", "scripts"),
        ),
        (
            project_root,
            (".claude", "agents", "scripts"),
        ),
        (
            home,
            (".claude", "agents", "scripts"),
        ),
    )
    selected = [
        (base, directories)
        for base, directories in candidates
        if _same_path(
            resolver,
            base.joinpath(*directories, "resolve-agents-mode.py"),
        )
    ]
    if len(selected) != 1:
        raise ValueError("installed external resolver layout is missing or ambiguous")

    base, directories = selected[0]
    current = base
    for directory in directories:
        current /= directory
        if not _ordinary_directory(current):
            raise ValueError("installed external resolver layout contains a reparse or missing root")

    policy_root = resolver.parent.parent
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

    for rank, path in layer_paths(provider, project_root, home):
        if not path.is_file():
            continue
        parsed = parse_agents_mode_text(path.read_text(encoding="utf-8"))
        if "reserveResolver" in parsed:
            reserve_resolver_layers.append((rank, parsed["reserveResolver"]))
        for key, value in parsed.items():
            if key in values:
                continue
            values[key] = value
            sources[key] = {"rank": rank, "path": str(path)}

    for key, value in canonical_defaults(repo_root, provider).items():
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
    parser.add_argument("--task-class")
    parser.add_argument("--role")
    parser.add_argument("--feature-state", choices=("enabled", "disabled"))
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
    if args.resolve_role_dispatch and args.resolve_external_dispatch:
        parser.error("choose exactly one dispatch resolver")
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
