#!/usr/bin/env python3
"""Shared Python owner for file-based provider prompt transports."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import re
import subprocess
import secrets
import shutil
import stat
import sys
import tempfile
import time
import types
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from process_supervision.process_runner import (
        CapturePolicyV1,
        EnvironmentRowV1,
        ExecutableBindingV1,
        KimiWindowsProfileV1,
        ProcessRequestV1,
        ProcessResultV1,
        ProcessRunnerV1,
        ProcessSupervisionError,
        SettlePolicyV1,
        resolve_executable_identity,
    )
except ModuleNotFoundError:
    from scripts.process_supervision.process_runner import (
        CapturePolicyV1,
        EnvironmentRowV1,
        ExecutableBindingV1,
        KimiWindowsProfileV1,
        ProcessRequestV1,
        ProcessResultV1,
        ProcessRunnerV1,
        ProcessSupervisionError,
        SettlePolicyV1,
        resolve_executable_identity,
    )

EFFORTS = frozenset({"low", "medium", "high", "xhigh", "max"})
ERROR_MARKER = re.compile(
    r"^([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(\.[0-9]+)?Z? )?(ERROR|FATAL|API Error)"
    r"(: | [A-Za-z0-9_]+(::[A-Za-z0-9_]+)*: )"
)
KIMI_TERMINAL_VERDICTS = ("PASS", "REVISE", "BLOCKED")
KIMI_GATE_PREFIX = "GATE: "
_KIMI_TERMINAL_PATTERN = "|".join(re.escape(verdict) for verdict in KIMI_TERMINAL_VERDICTS)
KIMI_RENDERED_GATE = re.compile(
    rf"^(?:\u2022 |  )?{re.escape(KIMI_GATE_PREFIX)}({_KIMI_TERMINAL_PATTERN})$"
)
KIMI_AGENT_TERMINAL_INSTRUCTION = (
    "Your final nonblank line must be exactly one of: "
    + ", ".join(KIMI_GATE_PREFIX + verdict for verdict in KIMI_TERMINAL_VERDICTS)
    + ". Do not emit any other gate-like line.\n"
).encode("utf-8")
KIMI_GATE_LIKE = re.compile(r"^[ \t]*GATE[ \t]*:")
INVALID_SLUG = re.compile(r'[\\/:\*\?"<>\|\x00]')
RESULT_MAX_BYTES_DEFAULT = 1024 * 1024
RESULT_MAX_BYTES_HARD = 16 * 1024 * 1024
CAPTURE_MAX_BYTES_DEFAULT = 16 * 1024 * 1024
CAPTURE_MAX_BYTES_HARD = 256 * 1024 * 1024
RESULT_PREFIX = "ORCHESTRARIUM_PROVIDER_RESULT_V2="
E_EXTERNAL_PROVIDER_WINDOWS_NATIVE_ARGV_UNAVAILABLE = (
    "E_EXTERNAL_PROVIDER_WINDOWS_NATIVE_ARGV_UNAVAILABLE"
)
EXTERNAL_PROVIDER_NAMES = frozenset({"codex", "claude", "kimi"})
POLICY_BOUND_EXTERNAL_PROVIDERS = frozenset({"kimi", "grok"})
_EXTERNAL_DISPATCH_DECISION_FIELDS = frozenset(
    {
        "schemaVersion",
        "status",
        "stableId",
        "provider",
        "taskClass",
        "role",
        "requiredModelTier",
        "requiredEffort",
        "mutationClass",
        "nativeEffort",
        "effortMappingLoss",
        "finalAuthorizingRole",
        "executionAuthorized",
        "independentVerification",
        "fallback",
    }
)
KIMI_WINDOWS_PROFILE_V1 = KimiWindowsProfileV1
KIMI_EXECUTABLE_BINDING_SCHEMA_V2 = "orchestrarium.kimi-executable-binding.v2"
KIMI_EXECUTABLE_BINDING_FILENAME_V2 = "executable-binding-v2.json"
KIMI_EXECUTABLE_ADMISSION_LOCK_FILENAME_V2 = ".kimi-binding-v2.lock"
KIMI_ADMISSION_LOCK_MARKER_V2 = b"orchestrarium-kimi-admission-v2\n"
KIMI_V2_TRANSACTION_FILENAME = ".kimi-v2-receipt.txn.json"
KIMI_V2_CANDIDATE_FILENAME = ".kimi-v2-receipt.candidate"
KIMI_V2_ROLLBACK_FILENAME = ".kimi-v2-receipt.rollback"
KIMI_V2_UPDATE_FILENAME = ".kimi-v2-receipt.txn.update"
KIMI_LATEST_URL_V2 = "https://code.kimi.com/kimi-code/latest"
KIMI_CDN_LATEST_URL_V2 = "https://cdn.kimi.com/kimi-code/latest"
KIMI_MANIFEST_MAX_BYTES_V2 = 16 * 1024
KIMI_LATEST_MAX_BYTES_V2 = 32
KIMI_PROBE_MAX_BYTES_V2 = 64 * 1024
KIMI_EXECUTABLE_MAX_BYTES_V2 = 512 * 1024 * 1024
KIMI_OFFLINE_DURATIONS_V2 = {
    "disabled": timedelta(0),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
}
KIMI_VERSION_PATTERN_V2 = re.compile(
    r"^(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})\.(0|[1-9][0-9]{0,5})$",
    re.ASCII,
)
SETTINGS_SNAPSHOT_MAX_BYTES = 1024 * 1024
CLEANUP_ISSUE_LIMIT = 32
CLEANUP_ISSUE_TOKEN_MAX = 64
PROVIDER_AUTH_SECRET_ENV_KEYS_V1 = {
    "codex-api-key": ("OPENAI_API_KEY",),
    "codex-auth-file": (),
    "claude-bedrock": (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN",
        "AWS_BEARER_TOKEN_BEDROCK",
        "AWS_CONTAINER_AUTHORIZATION_TOKEN",
    ),
    "claude-vertex": (
        "GOOGLE_API_KEY",
        "GOOGLE_OAUTH_ACCESS_TOKEN",
        "CLOUDSDK_AUTH_ACCESS_TOKEN",
    ),
    "claude-direct": ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"),
    "claude-subscription-override": (),
}
AUTH_OUTPUT_SCAN_ENVIRONMENT_EXACT = "environment-exact"
AUTH_OUTPUT_SCAN_CREDENTIAL_FILE_UNSCANNABLE = "credential-file-unscannable"
AUTH_OUTPUT_SCAN_OPAQUE_PROVIDER_SESSION = "opaque-provider-session"
_NONSECRET_CHILD_ENV_NAMES = (
    "COMSPEC", "SystemRoot", "SYSTEMROOT", "WINDIR", "PATH", "PATHEXT",
    "TEMP", "TMP", "TMPDIR", "USERPROFILE", "LOCALAPPDATA", "APPDATA",
    "HOME", "LANG", "LC_ALL",
)
PROVIDER_AUTH_CONTROL_ENV_KEYS_V1 = types.MappingProxyType(
    {
        "claude-bedrock": types.MappingProxyType(
            {
                "selector": "CLAUDE_CODE_USE_BEDROCK",
                "scalar": ("AWS_PROFILE", "AWS_REGION", "AWS_ROLE_ARN"),
                "file": (
                    "AWS_CONFIG_FILE",
                    "AWS_SHARED_CREDENTIALS_FILE",
                    "AWS_WEB_IDENTITY_TOKEN_FILE",
                ),
                "directory": (),
            }
        ),
        "claude-vertex": types.MappingProxyType(
            {
                "selector": "CLAUDE_CODE_USE_VERTEX",
                "scalar": (
                    "CLOUD_ML_REGION",
                    "ANTHROPIC_VERTEX_PROJECT_ID",
                    "GCLOUD_PROJECT",
                    "GOOGLE_CLOUD_PROJECT",
                ),
                "file": ("GOOGLE_APPLICATION_CREDENTIALS",),
                "directory": ("CLOUDSDK_CONFIG",),
            }
        ),
        "claude-direct": types.MappingProxyType(
            {"selector": None, "scalar": (), "file": (), "directory": ()}
        ),
        "claude-subscription-override": types.MappingProxyType(
            {"selector": None, "scalar": (), "file": (), "directory": ()}
        ),
    }
)
PROMPT_SNAPSHOT_MAX_BYTES = 16 * 1024 * 1024
EXTERNAL_GOVERNANCE_CAPSULE_NAME = "external-prompt-governance.md"
EXTERNAL_GOVERNANCE_CAPSULE_SHA256 = (
    "c7a59ccec7d6e46be76584a107b0a5b30b249368b4f0958cb78177962dc34b00"
)
EXTERNAL_GOVERNANCE_BEGIN = b"ORCHESTRARIUM_EXTERNAL_GOVERNANCE_V1\n"
EXTERNAL_GOVERNANCE_END = b"END_ORCHESTRARIUM_EXTERNAL_GOVERNANCE_V1\n\n"
EXTERNAL_UNAVAILABLE_IDS = {
    "grok": "E_GROK_CONTAINMENT_UNAVAILABLE",
}
E_EXTERNAL_PROVIDER_REPOSITORY_EXECUTABLE = "E_EXTERNAL_PROVIDER_REPOSITORY_EXECUTABLE"
KIMI_CHILD_NONZERO_CATEGORIES = frozenset(
    {"rate_limit", "auth", "vendor", "invocation", "unknown"}
)
EXTERNAL_ROLE_TAXONOMY_NAME = "external-role-taxonomy.v1.json"
EXTERNAL_ROLE_TAXONOMY_MAX_BYTES = 64 * 1024
EXTERNAL_ROLE_TAXONOMY_SHA256 = "51192eca72784dfcbc2d53596e143ea25856db9e7336031a25d89e9e4fdf85ce"
LAUNCH_FLAGS_MAX_COUNT = 64
LAUNCH_FLAGS_MAX_TOKEN_BYTES = 2048
LAUNCH_FLAGS_MAX_TOTAL_BYTES = 16 * 1024
AGENT_RUN_MAX_LINE_CHARS = 128 * 1024
AGENT_RUN_MAX_EVENTS = 4096
_MODEL_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$", re.ASCII)
_CLAUDE_TOOL_LIST = re.compile(
    r"^[A-Za-z][A-Za-z0-9_*:-]*(?:,[A-Za-z][A-Za-z0-9_*:-]*)*$",
    re.ASCII,
)
_CODEX_SANDBOXES = frozenset({"read-only", "workspace-write", "danger-full-access"})
_CLAUDE_IO_FORMATS = frozenset({"text", "json", "stream-json"})
_CLAUDE_PERMISSION_MODES = frozenset(
    {"default", "acceptEdits", "plan", "dontAsk", "bypassPermissions"}
)


@dataclass
class Control:
    topic: str | None = None
    prompt_file: Path | None = None
    terminal_receipt: Path | None = None
    ledger: str | None = None
    ledger_role: str | None = None
    ledger_role_explicit: bool = False
    ledger_lane: str | None = None
    ledger_artifact: str | None = None
    ledger_closes: list[str] = field(default_factory=list)
    timeout_secs: float = 3600.0
    result_max_bytes: int = RESULT_MAX_BYTES_DEFAULT
    capture_max_bytes: int = CAPTURE_MAX_BYTES_DEFAULT
    task_class: str | None = None
    role: str | None = None
    live_root: Path | None = None
    provider_flags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ResolvedProviderCommand:
    command: tuple[str, ...]
    target: Path
    provenance: str


@dataclass(frozen=True)
class ExternalRoleProvenance:
    """The caller assignment and actual external adapter lane are distinct facts."""

    assigned_role: str
    execution_role: str


@dataclass(frozen=True)
class ExecutionProvenance:
    """One immutable external execution identity, owned at policy admission."""

    work_item: str
    assigned_internal_role: str
    provider: str
    model: str
    effort: str
    launch_flags: tuple[str, ...]
    artifact_identity: str
    external_dispatch_id: str
    external_evidence_run_id: str
    effort_mapping_loss: str
    actual_execution_path: str = "direct-external-cli"

    def __post_init__(self) -> None:
        if any(
            not isinstance(value, str) or not value
            for value in (
                self.work_item,
                self.assigned_internal_role,
                self.provider,
                self.model,
                self.effort,
                self.artifact_identity,
                self.external_dispatch_id,
                self.external_evidence_run_id,
                self.effort_mapping_loss,
                self.actual_execution_path,
            )
        ):
            raise ValueError("E_EXTERNAL_PROVENANCE_INVALID")
        try:
            frozen, model, effort = normalize_launch_profile(
                self.provider, self.launch_flags
            )
        except ValueError as exc:
            raise ValueError("E_EXTERNAL_PROVENANCE_INVALID") from exc
        if (
            frozen != self.launch_flags
            or model != self.model
            or effort != self.effort
        ):
            raise ValueError("E_EXTERNAL_PROVENANCE_INVALID")

    def payload(self) -> dict[str, object]:
        return {
            "workItem": self.work_item,
            "assignedInternalRole": self.assigned_internal_role,
            "provider": self.provider,
            "model": self.model,
            "effort": self.effort,
            "launchFlags": list(self.launch_flags),
            "artifactIdentity": self.artifact_identity,
            "externalDispatchId": self.external_dispatch_id,
            "externalEvidenceRunId": self.external_evidence_run_id,
            "effortMappingLoss": self.effort_mapping_loss,
            "actualExecutionPath": self.actual_execution_path,
        }

    def terminal_projection(self) -> dict[str, object]:
        """Exact immutable provenance fields persisted by an external terminal."""

        return {
            "workItem": self.work_item,
            "assignedRole": self.assigned_internal_role,
            "provider": self.provider,
            "model": self.model,
            "effort": self.effort,
            "launchFlags": list(self.launch_flags),
            "artifactIdentity": self.artifact_identity,
            "externalDispatchId": self.external_dispatch_id,
            "externalEvidenceRunId": self.external_evidence_run_id,
            "effortMappingLoss": self.effort_mapping_loss,
            "actualExecutionPath": self.actual_execution_path,
        }


@dataclass(frozen=True)
class PolicyBoundLaunch:
    control: Control
    topic: str
    flags: tuple[str, ...]
    model: str
    effort: str
    role_provenance: ExternalRoleProvenance
    provenance: ExecutionProvenance | None


@dataclass(frozen=True)
class TerminalResult:
    evidence_path: Path
    status: str
    gate: str
    note: str
    token: str
    stderr_marker_count: int


@dataclass(frozen=True)
class CleanupResult:
    issues: tuple[str, ...]
    recovery_retained: bool = False

    @property
    def clean(self) -> bool:
        return not self.issues


@dataclass(frozen=True)
class FinalOutcome:
    exit_code: int
    token: str
    status: str
    gate: str
    note: str
    primary_exit_code: int
    primary_token: str
    primary_status: str
    primary_gate: str
    primary_note: str
    cleanup_status: str
    cleanup_issue_count: int
    cleanup_diagnostic: str
    recovery_retained: bool
    stderr_marker_count: int


@dataclass(frozen=True)
class StreamCaptureResult:
    overflow: bool
    observed_bytes: int
    persisted_bytes: int
    digest: str
    issues: tuple[str, ...]


@dataclass(frozen=True)
class ProviderAuthConfiguration:
    mode: str
    child_environment: dict[str, str]
    needles: tuple[bytes, ...]
    output_scan_disposition: str


@dataclass(frozen=True)
class ClaudeUserSettingsSurface:
    root: Path
    settings_path: Path
    forwarded_config_dir: str | None


class ResultMaterializationError(RuntimeError):
    pass


class ClaudeSubscriptionRefusal(ValueError):
    pass


class KimiOfficialChannelUnavailableV2(RuntimeError):
    """The pinned Moonshot channel could not be reached, without relaxing trust."""


@dataclass(frozen=True)
class KimiHttpResponseV2:
    status: int
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class KimiV1SnapshotV2:
    path: Path
    payload: bytes
    identity: tuple[int, int, int, int]


@dataclass
class TerminalReceiptV1:
    """One caller-owned, exclusively reserved durable terminal result file."""

    path: Path
    file_handle: int
    parent_handle: int
    windows: bool
    ancestor_handles: tuple[int, ...] = ()
    ancestor_identities: tuple[tuple[int, int], ...] = ()
    leaf_identity: tuple[int, int] | None = None
    committed: bool = False

    @staticmethod
    def _validated_path(path: Path) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute() or not candidate.name:
            raise ValueError("E_EXTERNAL_TERMINAL_RECEIPT_PATH_INVALID")
        if os.name == "nt":
            raw = str(candidate)
            lowered = raw.lower()
            if lowered.startswith(("\\\\?\\", "\\\\.\\", "\\??\\")):
                raise ValueError("E_EXTERNAL_TERMINAL_RECEIPT_PATH_INVALID")
            drive_colons = 1 if candidate.drive and candidate.drive.endswith(":") else 0
            if raw.count(":") != drive_colons:
                raise ValueError("E_EXTERNAL_TERMINAL_RECEIPT_PATH_INVALID")
            reserved = re.compile(r"^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$", re.I)
            for component in candidate.parts[1:]:
                if (
                    component in {".", ".."}
                    or component.endswith((" ", "."))
                    or reserved.fullmatch(component)
                ):
                    raise ValueError("E_EXTERNAL_TERMINAL_RECEIPT_PATH_INVALID")
        return candidate

    @classmethod
    def reserve(cls, path: Path) -> "TerminalReceiptV1":
        candidate = cls._validated_path(path)
        try:
            return cls._reserve_windows(candidate) if os.name == "nt" else cls._reserve_posix(candidate)
        except FileExistsError as exc:
            raise ValueError("E_EXTERNAL_TERMINAL_RECEIPT_EXISTS") from exc
        except ValueError:
            raise
        except OSError as exc:
            raise ValueError("E_EXTERNAL_TERMINAL_RECEIPT_UNAVAILABLE") from exc

    @classmethod
    def _validate_posix_namespace_authority(cls, chain: list[object]) -> None:
        if not chain:
            raise OSError("terminal receipt requires a private owner-controlled namespace")
        effective_uid = os.geteuid()
        for index, metadata in enumerate(chain):
            if metadata.st_uid not in {0, effective_uid}:
                raise OSError(
                    "terminal receipt requires a private owner-controlled namespace"
                )
            mode = stat.S_IMODE(metadata.st_mode)
            writable_by_another_principal = bool(mode & (stat.S_IWGRP | stat.S_IWOTH))
            if not writable_by_another_principal:
                continue
            next_is_private_caller_boundary = (
                index + 1 < len(chain)
                and chain[index + 1].st_uid == effective_uid
                and not stat.S_IMODE(chain[index + 1].st_mode)
                & (stat.S_IWGRP | stat.S_IWOTH)
            )
            if (
                metadata.st_uid != 0
                or not mode & stat.S_ISVTX
                or not next_is_private_caller_boundary
            ):
                raise OSError(
                    "terminal receipt requires a private owner-controlled namespace"
                )
        parent = chain[-1]
        if (
            parent.st_uid != effective_uid
            or stat.S_IMODE(parent.st_mode) & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise OSError("terminal receipt requires a private owner-controlled namespace")

    @classmethod
    def _cleanup_posix_provisional_leaf(
        cls,
        parent: int,
        name: str,
        descriptor: int,
        descriptor_identity: tuple[int, int] | None,
    ) -> None:
        identity = descriptor_identity
        last_identity_error: OSError | None = None
        if identity is None:
            for _attempt in range(2):
                try:
                    metadata = os.fstat(descriptor)
                    if not stat.S_ISREG(metadata.st_mode):
                        raise OSError("terminal receipt provisional leaf type")
                    identity = (metadata.st_dev, metadata.st_ino)
                    break
                except OSError as exc:
                    last_identity_error = exc
        if identity is None:
            raise ValueError(
                "E_EXTERNAL_TERMINAL_RECEIPT_CLEANUP_UNVERIFIED"
            ) from last_identity_error
        try:
            current = os.stat(name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return
        except OSError as exc:
            raise ValueError(
                "E_EXTERNAL_TERMINAL_RECEIPT_CLEANUP_UNVERIFIED"
            ) from exc
        if (current.st_dev, current.st_ino) != identity:
            raise ValueError("E_EXTERNAL_TERMINAL_RECEIPT_CLEANUP_UNVERIFIED")
        try:
            os.unlink(name, dir_fd=parent)
            os.fsync(parent)
        except OSError as exc:
            raise ValueError(
                "E_EXTERNAL_TERMINAL_RECEIPT_CLEANUP_UNVERIFIED"
            ) from exc

    @classmethod
    def _reserve_posix(cls, path: Path) -> "TerminalReceiptV1":
        nofollow = getattr(os, "O_NOFOLLOW", None)
        directory = getattr(os, "O_DIRECTORY", None)
        required_dir_fd = (os.open, os.stat, os.unlink)
        if (
            nofollow is None
            or directory is None
            or not all(operation in os.supports_dir_fd for operation in required_dir_fd)
            or os.stat not in os.supports_follow_symlinks
            or not hasattr(os, "geteuid")
        ):
            raise ValueError("E_EXTERNAL_TERMINAL_RECEIPT_UNSUPPORTED")
        parts = path.parts
        held = [os.open(parts[0], os.O_RDONLY | directory | nofollow)]
        identities: list[tuple[int, int]] = []
        descriptor = -1
        leaf_identity: tuple[int, int] | None = None
        chain_metadata: list[object] = []
        try:
            root_metadata = os.fstat(held[0])
            if not stat.S_ISDIR(root_metadata.st_mode):
                raise OSError("terminal receipt root type")
            identities.append((root_metadata.st_dev, root_metadata.st_ino))
            chain_metadata.append(root_metadata)
            for component in parts[1:-1]:
                if component in {"", ".", ".."}:
                    raise ValueError("E_EXTERNAL_TERMINAL_RECEIPT_PATH_INVALID")
                next_parent = os.open(
                    component,
                    os.O_RDONLY | directory | nofollow,
                    dir_fd=held[-1],
                )
                held.append(next_parent)
                metadata = os.fstat(next_parent)
                if not stat.S_ISDIR(metadata.st_mode):
                    raise OSError("terminal receipt ancestor type")
                identities.append((metadata.st_dev, metadata.st_ino))
                chain_metadata.append(metadata)
            parent = held[-1]
            cls._validate_posix_namespace_authority(chain_metadata)
            descriptor = os.open(
                parts[-1],
                os.O_CREAT | os.O_EXCL | os.O_RDWR | nofollow,
                0o600,
                dir_fd=parent,
            )
            try:
                descriptor_metadata = os.fstat(descriptor)
                if not stat.S_ISREG(descriptor_metadata.st_mode):
                    raise OSError("terminal receipt provisional leaf type")
                leaf_identity = (
                    descriptor_metadata.st_dev,
                    descriptor_metadata.st_ino,
                )
                named_metadata = os.stat(
                    parts[-1], dir_fd=parent, follow_symlinks=False
                )
                if (named_metadata.st_dev, named_metadata.st_ino) != leaf_identity:
                    raise OSError("terminal receipt provisional leaf identity")
                os.set_inheritable(descriptor, False)
                os.fchmod(descriptor, 0o600)
                metadata = os.fstat(descriptor)
                if (
                    not stat.S_ISREG(metadata.st_mode)
                    or stat.S_IMODE(metadata.st_mode) != 0o600
                    or (metadata.st_dev, metadata.st_ino) != leaf_identity
                ):
                    raise OSError("terminal receipt permissions")
            except BaseException as setup_error:
                cleanup_error: ValueError | None = None
                try:
                    cls._cleanup_posix_provisional_leaf(
                        parent,
                        parts[-1],
                        descriptor,
                        leaf_identity,
                    )
                except ValueError as exc:
                    cleanup_error = exc
                finally:
                    os.close(descriptor)
                    descriptor = -1
                if cleanup_error is not None:
                    raise cleanup_error from setup_error
                raise
            return cls(
                path,
                descriptor,
                parent,
                False,
                ancestor_handles=tuple(held),
                ancestor_identities=tuple(identities),
                leaf_identity=leaf_identity,
            )
        except BaseException:
            if descriptor >= 0:
                os.close(descriptor)
            for handle in reversed(held):
                os.close(handle)
            raise

    def _revalidate_posix_namespace(self) -> None:
        nofollow = os.O_NOFOLLOW
        directory = os.O_DIRECTORY
        parts = self.path.parts
        reopened = [os.open(parts[0], os.O_RDONLY | directory | nofollow)]
        leaf = -1
        current_chain: list[object] = []
        try:
            for component in parts[1:-1]:
                reopened.append(
                    os.open(
                        component,
                        os.O_RDONLY | directory | nofollow,
                        dir_fd=reopened[-1],
                    )
                )
            if len(reopened) != len(self.ancestor_handles):
                raise OSError("terminal receipt namespace identity changed")
            for current, held, expected in zip(
                reopened, self.ancestor_handles, self.ancestor_identities
            ):
                current_metadata = os.fstat(current)
                held_metadata = os.fstat(held)
                current_chain.append(current_metadata)
                current_identity = (current_metadata.st_dev, current_metadata.st_ino)
                held_identity = (held_metadata.st_dev, held_metadata.st_ino)
                if (
                    not stat.S_ISDIR(current_metadata.st_mode)
                    or current_identity != expected
                    or held_identity != expected
                ):
                    raise OSError("terminal receipt namespace identity changed")
            self._validate_posix_namespace_authority(current_chain)
            leaf = os.open(parts[-1], os.O_RDONLY | nofollow, dir_fd=reopened[-1])
            current_leaf = os.fstat(leaf)
            held_leaf = os.fstat(self.file_handle)
            current_identity = (current_leaf.st_dev, current_leaf.st_ino)
            held_identity = (held_leaf.st_dev, held_leaf.st_ino)
            if (
                self.leaf_identity is None
                or not stat.S_ISREG(current_leaf.st_mode)
                or current_identity != self.leaf_identity
                or held_identity != self.leaf_identity
            ):
                raise OSError("terminal receipt namespace identity changed")
        except (FileNotFoundError, NotADirectoryError) as exc:
            raise OSError("terminal receipt namespace identity changed") from exc
        finally:
            if leaf >= 0:
                os.close(leaf)
            for handle in reversed(reopened):
                os.close(handle)

    @staticmethod
    def _windows_file_information(handle: int):
        import ctypes
        from ctypes import wintypes

        class BY_HANDLE_FILE_INFORMATION(ctypes.Structure):
            _fields_ = [
                ("dwFileAttributes", wintypes.DWORD),
                ("ftCreationTime", wintypes.FILETIME),
                ("ftLastAccessTime", wintypes.FILETIME),
                ("ftLastWriteTime", wintypes.FILETIME),
                ("dwVolumeSerialNumber", wintypes.DWORD),
                ("nFileSizeHigh", wintypes.DWORD),
                ("nFileSizeLow", wintypes.DWORD),
                ("nNumberOfLinks", wintypes.DWORD),
                ("nFileIndexHigh", wintypes.DWORD),
                ("nFileIndexLow", wintypes.DWORD),
            ]

        info = BY_HANDLE_FILE_INFORMATION()
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetFileInformationByHandle.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(BY_HANDLE_FILE_INFORMATION),
        ]
        kernel32.GetFileInformationByHandle.restype = wintypes.BOOL
        if not kernel32.GetFileInformationByHandle(wintypes.HANDLE(handle), ctypes.byref(info)):
            raise OSError(ctypes.get_last_error(), "GetFileInformationByHandle")
        return info

    @classmethod
    def _reserve_windows(cls, path: Path) -> "TerminalReceiptV1":
        import ctypes
        from ctypes import wintypes

        GENERIC_READ = 0x80000000
        GENERIC_WRITE = 0x40000000
        FILE_READ_ATTRIBUTES = 0x0080
        SYNCHRONIZE = 0x00100000
        FILE_SHARE_READ = 0x00000001
        FILE_SHARE_WRITE = 0x00000002
        OPEN_EXISTING = 3
        FILE_ATTRIBUTE_NORMAL = 0x00000080
        FILE_ATTRIBUTE_DIRECTORY = 0x00000010
        FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
        FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
        FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
        HANDLE_FLAG_INHERIT = 0x00000001
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
        OBJ_CASE_INSENSITIVE = 0x00000040
        FILE_OPEN = 1
        FILE_CREATE = 2
        FILE_DIRECTORY_FILE = 0x00000001
        FILE_WRITE_THROUGH = 0x00000002
        FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
        FILE_NON_DIRECTORY_FILE = 0x00000040
        FILE_OPEN_REPARSE_POINT = 0x00200000
        STATUS_OBJECT_NAME_COLLISION = ctypes.c_long(0xC0000035).value

        class UNICODE_STRING(ctypes.Structure):
            _fields_ = [
                ("Length", wintypes.USHORT),
                ("MaximumLength", wintypes.USHORT),
                ("Buffer", wintypes.LPWSTR),
            ]

        class OBJECT_ATTRIBUTES(ctypes.Structure):
            _fields_ = [
                ("Length", wintypes.ULONG),
                ("RootDirectory", wintypes.HANDLE),
                ("ObjectName", ctypes.POINTER(UNICODE_STRING)),
                ("Attributes", wintypes.ULONG),
                ("SecurityDescriptor", ctypes.c_void_p),
                ("SecurityQualityOfService", ctypes.c_void_p),
            ]

        class IO_STATUS_BLOCK(ctypes.Structure):
            _fields_ = [
                ("Status", ctypes.c_longlong),
                ("Information", ctypes.c_size_t),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        ntdll = ctypes.WinDLL("ntdll")
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.SetHandleInformation.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
        ]
        kernel32.SetHandleInformation.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        ntdll.NtCreateFile.argtypes = [
            ctypes.POINTER(wintypes.HANDLE),
            wintypes.DWORD,
            ctypes.POINTER(OBJECT_ATTRIBUTES),
            ctypes.POINTER(IO_STATUS_BLOCK),
            ctypes.c_void_p,
            wintypes.ULONG,
            wintypes.ULONG,
            wintypes.ULONG,
            wintypes.ULONG,
            ctypes.c_void_p,
            wintypes.ULONG,
        ]
        ntdll.NtCreateFile.restype = ctypes.c_long

        root = kernel32.CreateFileW(
            path.anchor,
            FILE_READ_ATTRIBUTES,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            None,
            OPEN_EXISTING,
            FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        if root == INVALID_HANDLE_VALUE:
            raise OSError(ctypes.get_last_error(), "CreateFileW(root)")
        held: list[int] = [int(root)]
        descriptor = None
        leaf = INVALID_HANDLE_VALUE

        def open_relative(
            parent: int,
            name: str,
            *,
            directory: bool,
            create: bool,
            security_descriptor: int | None = None,
        ) -> int:
            buffer = ctypes.create_unicode_buffer(name)
            object_name = UNICODE_STRING(
                len(name.encode("utf-16-le")),
                len(name.encode("utf-16-le")) + 2,
                ctypes.cast(buffer, wintypes.LPWSTR),
            )
            attributes = OBJECT_ATTRIBUTES(
                ctypes.sizeof(OBJECT_ATTRIBUTES),
                wintypes.HANDLE(parent),
                ctypes.pointer(object_name),
                OBJ_CASE_INSENSITIVE,
                security_descriptor,
                None,
            )
            io_status = IO_STATUS_BLOCK()
            opened = wintypes.HANDLE()
            options = FILE_OPEN_REPARSE_POINT | FILE_SYNCHRONOUS_IO_NONALERT | (
                FILE_DIRECTORY_FILE if directory else FILE_NON_DIRECTORY_FILE | FILE_WRITE_THROUGH
            )
            desired = (
                FILE_READ_ATTRIBUTES | SYNCHRONIZE
                if directory
                else GENERIC_READ | GENERIC_WRITE | SYNCHRONIZE
            )
            status = ntdll.NtCreateFile(
                ctypes.byref(opened),
                desired,
                ctypes.byref(attributes),
                ctypes.byref(io_status),
                None,
                FILE_ATTRIBUTE_NORMAL,
                FILE_SHARE_READ | FILE_SHARE_WRITE if directory else 0,
                FILE_CREATE if create else FILE_OPEN,
                options,
                None,
                0,
            )
            if status < 0:
                if status == STATUS_OBJECT_NAME_COLLISION:
                    raise FileExistsError(183, "NtCreateFile(receipt)", str(path))
                raise OSError(f"NtCreateFile status=0x{status & 0xFFFFFFFF:08x}")
            return int(opened.value)

        try:
            root_info = cls._windows_file_information(int(root))
            if (
                not root_info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY
                or root_info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT
            ):
                raise OSError("terminal receipt root type")
            for component in path.parts[1:-1]:
                current = open_relative(held[-1], component, directory=True, create=False)
                held.append(current)
                current_info = cls._windows_file_information(current)
                if (
                    not current_info.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY
                    or current_info.dwFileAttributes & FILE_ATTRIBUTE_REPARSE_POINT
                ):
                    raise OSError("terminal receipt ancestor type")
            parent = held[-1]
            parent_info = cls._windows_file_information(parent)
            descriptor, expected_sddl = (
                WindowsPrivateObjectOwnerV1.current_user_security_descriptor()
            )
            leaf = open_relative(
                parent,
                path.name,
                directory=False,
                create=True,
                security_descriptor=descriptor,
            )
            if not kernel32.SetHandleInformation(
                wintypes.HANDLE(leaf), HANDLE_FLAG_INHERIT, 0
            ):
                raise OSError(ctypes.get_last_error(), "SetHandleInformation")
            leaf_info = cls._windows_file_information(leaf)
            if leaf_info.dwFileAttributes & (
                FILE_ATTRIBUTE_DIRECTORY | FILE_ATTRIBUTE_REPARSE_POINT
            ):
                raise OSError("terminal receipt leaf type")
            WindowsPrivateObjectOwnerV1.verify_handle_dacl(leaf, expected_sddl)
            current_parent = cls._windows_file_information(parent)
            before_identity = (
                parent_info.dwVolumeSerialNumber,
                parent_info.nFileIndexHigh,
                parent_info.nFileIndexLow,
            )
            after_identity = (
                current_parent.dwVolumeSerialNumber,
                current_parent.nFileIndexHigh,
                current_parent.nFileIndexLow,
            )
            if before_identity != after_identity:
                raise OSError("terminal receipt parent identity changed")
            return cls(
                path,
                int(leaf),
                int(parent),
                True,
                ancestor_handles=tuple(held),
            )
        except BaseException:
            if leaf != INVALID_HANDLE_VALUE:
                kernel32.CloseHandle(leaf)
            for handle in reversed(held):
                kernel32.CloseHandle(handle)
            raise
        finally:
            if descriptor:
                kernel32.LocalFree(descriptor)

    def commit(self, line: bytes) -> None:
        if self.committed or not line or not line.endswith(b"\n"):
            raise ValueError("E_EXTERNAL_TERMINAL_RECEIPT_COMMIT_INVALID")
        if self.windows:
            self._commit_windows(line)
        else:
            self._commit_posix(line)
        self.committed = True

    def _commit_posix(self, line: bytes) -> None:
        self._revalidate_posix_namespace()
        view = memoryview(line)
        while view:
            written = os.write(self.file_handle, view)
            if written <= 0:
                raise OSError("terminal receipt write")
            view = view[written:]
        os.fsync(self.file_handle)
        os.fsync(self.parent_handle)
        self._revalidate_posix_namespace()
        os.lseek(self.file_handle, 0, os.SEEK_SET)
        readback = bytearray()
        while len(readback) <= len(line):
            chunk = os.read(self.file_handle, len(line) + 1 - len(readback))
            if not chunk:
                break
            readback.extend(chunk)
        if bytes(readback) != line:
            raise OSError("terminal receipt exact readback")
        self._revalidate_posix_namespace()

    def _commit_windows(self, line: bytes) -> None:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        offset = 0
        while offset < len(line):
            chunk = line[offset : offset + 0x7FFFFFFF]
            written = wintypes.DWORD()
            buffer = ctypes.create_string_buffer(chunk)
            if not kernel32.WriteFile(
                wintypes.HANDLE(self.file_handle),
                buffer,
                len(chunk),
                ctypes.byref(written),
                None,
            ) or written.value != len(chunk):
                raise OSError(ctypes.get_last_error(), "WriteFile(receipt)")
            offset += written.value
        if not kernel32.FlushFileBuffers(wintypes.HANDLE(self.file_handle)):
            raise OSError(ctypes.get_last_error(), "FlushFileBuffers(receipt)")
        position = ctypes.c_longlong()
        if not kernel32.SetFilePointerEx(
            wintypes.HANDLE(self.file_handle), ctypes.c_longlong(0), ctypes.byref(position), 0
        ):
            raise OSError(ctypes.get_last_error(), "SetFilePointerEx(receipt)")
        buffer = ctypes.create_string_buffer(len(line) + 1)
        read = wintypes.DWORD()
        if not kernel32.ReadFile(
            wintypes.HANDLE(self.file_handle),
            buffer,
            len(line) + 1,
            ctypes.byref(read),
            None,
        ):
            raise OSError(ctypes.get_last_error(), "ReadFile(receipt)")
        if read.value != len(line) or buffer.raw[: read.value] != line:
            raise OSError("terminal receipt exact readback")

    def close(self) -> None:
        if self.file_handle < 0:
            return
        if self.windows:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CloseHandle(wintypes.HANDLE(self.file_handle))
            handles = self.ancestor_handles or (self.parent_handle,)
            for handle in reversed(handles):
                kernel32.CloseHandle(wintypes.HANDLE(handle))
        else:
            os.close(self.file_handle)
            handles = self.ancestor_handles or (self.parent_handle,)
            for handle in reversed(handles):
                os.close(handle)
        self.file_handle = -1
        self.parent_handle = -1

    def __enter__(self) -> "TerminalReceiptV1":
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        self.close()


class WindowsPrivateObjectOwnerV1:
    """One Windows owner for protected current-user-only files and directories."""

    @staticmethod
    def current_user_security_descriptor():
        import ctypes
        from ctypes import wintypes

        TOKEN_QUERY = 0x0008
        TOKEN_USER_CLASS = 1

        class SID_AND_ATTRIBUTES(ctypes.Structure):
            _fields_ = [("Sid", ctypes.c_void_p), ("Attributes", wintypes.DWORD)]

        class TOKEN_USER(ctypes.Structure):
            _fields_ = [("User", SID_AND_ATTRIBUTES)]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32.GetCurrentProcess.argtypes = []
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        advapi32.OpenProcessToken.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        advapi32.GetTokenInformation.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        advapi32.ConvertSidToStringSidW.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.LPWSTR),
        ]
        advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(wintypes.DWORD),
        ]
        for function in (
            advapi32.OpenProcessToken,
            advapi32.GetTokenInformation,
            advapi32.ConvertSidToStringSidW,
            advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW,
        ):
            function.restype = wintypes.BOOL
        token = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(
            kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)
        ):
            raise OSError(ctypes.get_last_error(), "OpenProcessToken")
        sid_text = wintypes.LPWSTR()
        try:
            size = wintypes.DWORD()
            advapi32.GetTokenInformation(
                token, TOKEN_USER_CLASS, None, 0, ctypes.byref(size)
            )
            if not size.value:
                raise OSError(ctypes.get_last_error(), "GetTokenInformation(size)")
            buffer = ctypes.create_string_buffer(size.value)
            if not advapi32.GetTokenInformation(
                token, TOKEN_USER_CLASS, buffer, size, ctypes.byref(size)
            ):
                raise OSError(ctypes.get_last_error(), "GetTokenInformation")
            token_user = ctypes.cast(buffer, ctypes.POINTER(TOKEN_USER)).contents
            if not advapi32.ConvertSidToStringSidW(
                token_user.User.Sid, ctypes.byref(sid_text)
            ):
                raise OSError(ctypes.get_last_error(), "ConvertSidToStringSidW")
            sid = sid_text.value
        finally:
            if sid_text:
                kernel32.LocalFree(sid_text)
            kernel32.CloseHandle(token)
        descriptor = ctypes.c_void_p()
        sddl = f"D:P(A;;FA;;;{sid})"
        if not advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW(
            sddl, 1, ctypes.byref(descriptor), None
        ):
            raise OSError(
                ctypes.get_last_error(),
                "ConvertStringSecurityDescriptorToSecurityDescriptorW",
            )
        # Windows can render a numeric SID with a well-known alias (for
        # example LA). Compare native canonical forms, not caller spelling;
        # the protected flag and the complete ACE remain part of the check.
        advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.LPWSTR),
            ctypes.POINTER(wintypes.DWORD),
        ]
        advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = wintypes.BOOL
        rendered = wintypes.LPWSTR()
        try:
            if not advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW(
                descriptor, 1, 0x00000004, ctypes.byref(rendered), None
            ) or not rendered.value:
                raise OSError(
                    ctypes.get_last_error(),
                    "ConvertSecurityDescriptorToStringSecurityDescriptorW(expected DACL)",
                )
            return descriptor, rendered.value
        except BaseException:
            kernel32.LocalFree(descriptor)
            raise
        finally:
            if rendered:
                kernel32.LocalFree(rendered)

    @staticmethod
    def verify_handle_dacl(handle: int, expected_sddl: str) -> None:
        import ctypes
        from ctypes import wintypes

        DACL_SECURITY_INFORMATION = 0x00000004
        SE_FILE_OBJECT = 1
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        advapi32.GetSecurityInfo.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        advapi32.GetSecurityInfo.restype = wintypes.DWORD
        advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.LPWSTR),
            ctypes.POINTER(wintypes.DWORD),
        ]
        advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = wintypes.BOOL
        descriptor = ctypes.c_void_p()
        dacl = ctypes.c_void_p()
        status = advapi32.GetSecurityInfo(
            wintypes.HANDLE(handle),
            SE_FILE_OBJECT,
            DACL_SECURITY_INFORMATION,
            None,
            None,
            ctypes.byref(dacl),
            None,
            ctypes.byref(descriptor),
        )
        if status != 0:
            raise OSError(status, "GetSecurityInfo")
        rendered = wintypes.LPWSTR()
        try:
            if not advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW(
                descriptor,
                1,
                DACL_SECURITY_INFORMATION,
                ctypes.byref(rendered),
                None,
            ):
                raise OSError(
                    ctypes.get_last_error(),
                    "ConvertSecurityDescriptorToStringSecurityDescriptorW",
                )
            if rendered.value != expected_sddl:
                raise OSError("private object DACL mismatch")
        finally:
            if rendered:
                kernel32.LocalFree(rendered)
            if descriptor:
                kernel32.LocalFree(descriptor)

    @classmethod
    def _open_verified_handle(
        cls,
        path: Path,
        *,
        directory: bool,
        share_delete: bool = True,
        write_dac: bool = False,
    ) -> int:
        import ctypes
        from ctypes import wintypes

        READ_CONTROL = 0x00020000
        WRITE_DAC = 0x00040000
        FILE_READ_ATTRIBUTES = 0x0080
        FILE_SHARE_READ = 0x00000001
        FILE_SHARE_WRITE = 0x00000002
        FILE_SHARE_DELETE = 0x00000004
        OPEN_EXISTING = 3
        FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
        FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        kernel32.CreateFileW.restype = wintypes.HANDLE
        flags = FILE_FLAG_OPEN_REPARSE_POINT | (
            FILE_FLAG_BACKUP_SEMANTICS if directory else 0
        )
        handle = kernel32.CreateFileW(
            str(path),
            READ_CONTROL
            | FILE_READ_ATTRIBUTES
            | 0x0001
            | (WRITE_DAC if write_dac else 0),
            FILE_SHARE_READ
            | FILE_SHARE_WRITE
            | (FILE_SHARE_DELETE if share_delete else 0),
            None,
            OPEN_EXISTING,
            flags,
            None,
        )
        if handle == INVALID_HANDLE_VALUE:
            raise OSError(ctypes.get_last_error(), "CreateFileW(private-object)")
        return int(handle)

    @classmethod
    def protect_handle_and_verify(cls, handle: int) -> None:
        import ctypes
        from ctypes import wintypes

        DACL_SECURITY_INFORMATION = 0x00000004
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        ntdll = ctypes.WinDLL("ntdll")
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        descriptor, expected_sddl = cls.current_user_security_descriptor()
        ntdll.NtSetSecurityObject.argtypes = [
            wintypes.HANDLE,
            wintypes.ULONG,
            ctypes.c_void_p,
        ]
        ntdll.NtSetSecurityObject.restype = ctypes.c_long
        try:
            status = ntdll.NtSetSecurityObject(
                wintypes.HANDLE(handle),
                DACL_SECURITY_INFORMATION,
                descriptor,
            )
            if status < 0:
                raise OSError(
                    f"NtSetSecurityObject status=0x{status & 0xFFFFFFFF:08x}"
                )
            cls.verify_handle_dacl(handle, expected_sddl)
        finally:
            if descriptor:
                kernel32.LocalFree(descriptor)

    @classmethod
    def protect_and_verify(cls, path: Path, *, directory: bool) -> None:
        import ctypes
        from ctypes import wintypes

        validate_no_reparse_components(path)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = cls._open_verified_handle(
            path, directory=directory, write_dac=True
        )
        try:
            cls.protect_handle_and_verify(handle)
        finally:
            kernel32.CloseHandle(wintypes.HANDLE(handle))

    @classmethod
    def verify_existing(cls, path: Path, *, directory: bool) -> None:
        import ctypes
        from ctypes import wintypes

        validate_no_reparse_components(path)
        metadata = path.lstat()
        if (
            stat.S_ISLNK(metadata.st_mode)
            or _metadata_is_reparse(metadata)
            or (directory and not stat.S_ISDIR(metadata.st_mode))
            or (not directory and not stat.S_ISREG(metadata.st_mode))
        ):
            raise OSError("private object type")
        descriptor, expected_sddl = cls.current_user_security_descriptor()
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        handle = cls._open_verified_handle(path, directory=directory)
        try:
            cls.verify_handle_dacl(handle, expected_sddl)
        finally:
            kernel32.CloseHandle(wintypes.HANDLE(handle))
            if descriptor:
                kernel32.LocalFree(descriptor)

    @classmethod
    def ensure_directory(cls, path: Path) -> None:
        if path.exists():
            cls.verify_existing(path, directory=True)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.mkdir()
        try:
            cls.protect_and_verify(path, directory=True)
        except BaseException:
            try:
                path.rmdir()
            except OSError:
                pass
            raise

    @staticmethod
    def reject_named_streams(path: Path) -> None:
        import ctypes
        from ctypes import wintypes

        FindStreamInfoStandard = 0
        ERROR_HANDLE_EOF = 38
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

        class WIN32_FIND_STREAM_DATA(ctypes.Structure):
            _fields_ = [
                ("StreamSize", ctypes.c_longlong),
                ("cStreamName", wintypes.WCHAR * 296),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.FindFirstStreamW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.POINTER(WIN32_FIND_STREAM_DATA),
            wintypes.DWORD,
        ]
        kernel32.FindFirstStreamW.restype = wintypes.HANDLE
        kernel32.FindNextStreamW.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(WIN32_FIND_STREAM_DATA),
        ]
        kernel32.FindNextStreamW.restype = wintypes.BOOL
        kernel32.FindClose.argtypes = [wintypes.HANDLE]
        data = WIN32_FIND_STREAM_DATA()
        handle = kernel32.FindFirstStreamW(
            str(path), FindStreamInfoStandard, ctypes.byref(data), 0
        )
        if handle == INVALID_HANDLE_VALUE:
            error = ctypes.get_last_error()
            if error == ERROR_HANDLE_EOF:
                return
            raise OSError(error, "FindFirstStreamW")
        try:
            while True:
                if data.cStreamName != "::$DATA":
                    raise OSError("named stream present")
                if not kernel32.FindNextStreamW(handle, ctypes.byref(data)):
                    error = ctypes.get_last_error()
                    if error != ERROR_HANDLE_EOF:
                        raise OSError(error, "FindNextStreamW")
                    break
        finally:
            kernel32.FindClose(handle)


@dataclass
class HeldWindowsObjectV2:
    path: Path
    handle: int
    kind: str
    identity: tuple[object, ...]


class WindowsHeldObjectApiV2:
    """Held no-share-delete identity API used by the Kimi migration corridor."""

    @staticmethod
    def identity(handle: int, kind: str) -> tuple[object, ...]:
        import ctypes
        from ctypes import wintypes

        class FILE_ID_128(ctypes.Structure):
            _fields_ = [("Identifier", ctypes.c_ubyte * 16)]

        class FILE_ID_INFO(ctypes.Structure):
            _fields_ = [
                ("VolumeSerialNumber", ctypes.c_ulonglong),
                ("FileId", FILE_ID_128),
            ]

        class FILE_ATTRIBUTE_TAG_INFO(ctypes.Structure):
            _fields_ = [
                ("FileAttributes", wintypes.DWORD),
                ("ReparseTag", wintypes.DWORD),
            ]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.GetFileInformationByHandleEx.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        kernel32.GetFileInformationByHandleEx.restype = wintypes.BOOL
        file_id = FILE_ID_INFO()
        tag = FILE_ATTRIBUTE_TAG_INFO()
        if not kernel32.GetFileInformationByHandleEx(
            wintypes.HANDLE(handle), 18, ctypes.byref(file_id), ctypes.sizeof(file_id)
        ) or not kernel32.GetFileInformationByHandleEx(
            wintypes.HANDLE(handle), 9, ctypes.byref(tag), ctypes.sizeof(tag)
        ):
            raise OSError(ctypes.get_last_error(), "GetFileInformationByHandleEx")
        return (
            int(file_id.VolumeSerialNumber),
            bytes(file_id.FileId.Identifier),
            kind,
            int(tag.FileAttributes),
            int(tag.ReparseTag),
        )

    @classmethod
    def open_path(cls, path: Path, kind: str, *, write_dac: bool = False) -> HeldWindowsObjectV2:
        import ctypes
        from ctypes import wintypes

        handle = WindowsPrivateObjectOwnerV1._open_verified_handle(
            path,
            directory=kind == "directory",
            share_delete=False,
            write_dac=write_dac,
        )
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.SetHandleInformation.argtypes = [
            wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD
        ]
        if not kernel32.SetHandleInformation(wintypes.HANDLE(handle), 1, 0):
            kernel32.CloseHandle(wintypes.HANDLE(handle))
            raise OSError(ctypes.get_last_error(), "SetHandleInformation")
        return HeldWindowsObjectV2(path, handle, kind, cls.identity(handle, kind))

    @classmethod
    def open_parent_chain_no_follow(cls, path: Path) -> HeldWindowsObjectV2:
        validate_no_reparse_components(path.parent)
        return cls.open_path(path.parent, "directory")

    @classmethod
    def open_relative(
        cls,
        parent: HeldWindowsObjectV2,
        name: str,
        kind: str,
        *,
        write_dac: bool = False,
        share_delete: bool = False,
    ) -> HeldWindowsObjectV2:
        if not name or name in {".", ".."} or Path(name).name != name:
            raise OSError("relative name invalid")
        import ctypes
        from ctypes import wintypes

        class UNICODE_STRING(ctypes.Structure):
            _fields_ = [
                ("Length", wintypes.USHORT),
                ("MaximumLength", wintypes.USHORT),
                ("Buffer", wintypes.LPWSTR),
            ]

        class OBJECT_ATTRIBUTES(ctypes.Structure):
            _fields_ = [
                ("Length", wintypes.ULONG),
                ("RootDirectory", wintypes.HANDLE),
                ("ObjectName", ctypes.POINTER(UNICODE_STRING)),
                ("Attributes", wintypes.ULONG),
                ("SecurityDescriptor", ctypes.c_void_p),
                ("SecurityQualityOfService", ctypes.c_void_p),
            ]

        class IO_STATUS_BLOCK(ctypes.Structure):
            _fields_ = [("Status", ctypes.c_longlong), ("Information", ctypes.c_size_t)]

        READ_CONTROL = 0x00020000
        WRITE_DAC = 0x00040000
        FILE_READ_ATTRIBUTES = 0x0080
        SYNCHRONIZE = 0x00100000
        FILE_SHARE_READ = 1
        FILE_SHARE_WRITE = 2
        FILE_OPEN = 1
        FILE_DIRECTORY_FILE = 1
        FILE_SYNCHRONOUS_IO_NONALERT = 0x20
        FILE_NON_DIRECTORY_FILE = 0x40
        FILE_OPEN_REPARSE_POINT = 0x00200000
        OBJ_CASE_INSENSITIVE = 0x40
        buffer = ctypes.create_unicode_buffer(name)
        encoded_length = len(name.encode("utf-16-le"))
        string = UNICODE_STRING(
            encoded_length,
            encoded_length + 2,
            ctypes.cast(buffer, wintypes.LPWSTR),
        )
        attributes = OBJECT_ATTRIBUTES(
            ctypes.sizeof(OBJECT_ATTRIBUTES),
            wintypes.HANDLE(parent.handle),
            ctypes.pointer(string),
            OBJ_CASE_INSENSITIVE,
            None,
            None,
        )
        iosb = IO_STATUS_BLOCK()
        opened = wintypes.HANDLE()
        ntdll = ctypes.WinDLL("ntdll")
        ntdll.NtCreateFile.restype = ctypes.c_long
        status = ntdll.NtCreateFile(
            ctypes.byref(opened),
            READ_CONTROL
            | FILE_READ_ATTRIBUTES
            | SYNCHRONIZE
            | 1
            | (WRITE_DAC if write_dac else 0),
            ctypes.byref(attributes),
            ctypes.byref(iosb),
            None,
            0x80,
            FILE_SHARE_READ | FILE_SHARE_WRITE | (4 if share_delete else 0),
            FILE_OPEN,
            FILE_OPEN_REPARSE_POINT
            | FILE_SYNCHRONOUS_IO_NONALERT
            | (FILE_DIRECTORY_FILE if kind == "directory" else FILE_NON_DIRECTORY_FILE),
            None,
            0,
        )
        if status < 0:
            raise OSError(f"NtCreateFile status=0x{status & 0xFFFFFFFF:08x}")
        path = parent.path / name
        return HeldWindowsObjectV2(
            path, int(opened.value), kind, cls.identity(int(opened.value), kind)
        )

    @classmethod
    def reopen_relative_and_match(
        cls,
        held: HeldWindowsObjectV2,
        parent: HeldWindowsObjectV2 | None = None,
        name: str | None = None,
    ) -> None:
        import ctypes
        from ctypes import wintypes

        reopened = (
            cls.open_relative(parent, name, held.kind)
            if parent is not None and name is not None
            else cls.open_path(held.path, held.kind)
        )
        try:
            if reopened.identity != held.identity:
                raise OSError("held object identity mismatch")
        finally:
            ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(
                wintypes.HANDLE(reopened.handle)
            )

    @staticmethod
    def enumerate_directory(held: HeldWindowsObjectV2) -> tuple[str, ...]:
        import ctypes
        from ctypes import wintypes

        class IO_STATUS_BLOCK(ctypes.Structure):
            _fields_ = [("Status", ctypes.c_longlong), ("Information", ctypes.c_size_t)]

        ntdll = ctypes.WinDLL("ntdll")
        ntdll.NtQueryDirectoryFile.argtypes = [
            wintypes.HANDLE, wintypes.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
            ctypes.POINTER(IO_STATUS_BLOCK), ctypes.c_void_p, wintypes.ULONG,
            ctypes.c_int, wintypes.BOOL, ctypes.c_void_p, wintypes.BOOL,
        ]
        ntdll.NtQueryDirectoryFile.restype = ctypes.c_long
        names: list[str] = []
        restart = True
        while True:
            buffer = ctypes.create_string_buffer(64 * 1024)
            iosb = IO_STATUS_BLOCK()
            status = ntdll.NtQueryDirectoryFile(
                wintypes.HANDLE(held.handle), None, None, None,
                ctypes.byref(iosb), buffer, len(buffer), 12, False, None, restart,
            )
            restart = False
            if status == ctypes.c_long(0x80000006).value:
                break
            if status < 0:
                raise OSError(f"NtQueryDirectoryFile status=0x{status & 0xFFFFFFFF:08x}")
            offset = 0
            while offset < iosb.Information:
                next_offset = int.from_bytes(buffer.raw[offset : offset + 4], "little")
                name_length = int.from_bytes(buffer.raw[offset + 8 : offset + 12], "little")
                name = buffer.raw[offset + 12 : offset + 12 + name_length].decode("utf-16-le")
                if name not in {".", ".."}:
                    names.append(name)
                if not next_offset:
                    break
                offset += next_offset
            if iosb.Information == 0:
                break
        return tuple(sorted(names))

    @staticmethod
    def read_exact(held: HeldWindowsObjectV2, limit: int) -> bytes:
        import ctypes
        from ctypes import wintypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        position = ctypes.c_longlong()
        if not kernel32.SetFilePointerEx(
            wintypes.HANDLE(held.handle), ctypes.c_longlong(0), ctypes.byref(position), 0
        ):
            raise OSError(ctypes.get_last_error(), "SetFilePointerEx")
        buffer = ctypes.create_string_buffer(limit + 1)
        read = wintypes.DWORD()
        if not kernel32.ReadFile(
            wintypes.HANDLE(held.handle), buffer, limit + 1,
            ctypes.byref(read), None,
        ):
            raise OSError(ctypes.get_last_error(), "ReadFile")
        if read.value > limit:
            raise OSError("held read limit")
        return bytes(buffer.raw[: read.value])

    @staticmethod
    def close(held: HeldWindowsObjectV2 | None) -> None:
        if held is None or held.handle < 0:
            return
        import ctypes
        from ctypes import wintypes

        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(
            wintypes.HANDLE(held.handle)
        )
        held.handle = -1


@dataclass
class KimiAdmissionLockV2:
    path: Path
    handle: int
    identity: tuple[object, ...]

    @classmethod
    def acquire(
        cls, runtime_root: Path, *, create: bool
    ) -> "KimiAdmissionLockV2 | None":
        if os.name != "nt":
            raise ValueError("E_KIMI_WINDOWS_ONLY")
        import ctypes
        from ctypes import wintypes

        GENERIC_READ = 0x80000000
        GENERIC_WRITE = 0x40000000
        READ_CONTROL = 0x00020000
        WRITE_DAC = 0x00040000
        FILE_READ_ATTRIBUTES = 0x0080
        OPEN_EXISTING = 3
        OPEN_ALWAYS = 4
        FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
        ERROR_FILE_NOT_FOUND = 2
        ERROR_PATH_NOT_FOUND = 3
        ERROR_SHARING_VIOLATION = 32
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
        path = runtime_root / KIMI_EXECUTABLE_ADMISSION_LOCK_FILENAME_V2
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.argtypes = [
            wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
            wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE,
        ]
        kernel32.CreateFileW.restype = wintypes.HANDLE
        handle = kernel32.CreateFileW(
            str(path),
            GENERIC_READ | GENERIC_WRITE | READ_CONTROL | WRITE_DAC | FILE_READ_ATTRIBUTES,
            0,
            None,
            OPEN_ALWAYS if create else OPEN_EXISTING,
            FILE_FLAG_OPEN_REPARSE_POINT,
            None,
        )
        if handle == INVALID_HANDLE_VALUE:
            error = ctypes.get_last_error()
            if error == ERROR_SHARING_VIOLATION:
                raise ValueError("E_KIMI_ADMISSION_BUSY")
            if not create and error in {ERROR_FILE_NOT_FOUND, ERROR_PATH_NOT_FOUND}:
                return None
            raise ValueError("E_KIMI_PRIVATE_STATE_INVALID")
        held = int(handle)
        create_error = ctypes.get_last_error()
        try:
            if not kernel32.SetHandleInformation(wintypes.HANDLE(held), 1, 0):
                raise OSError(ctypes.get_last_error(), "SetHandleInformation")
            identity = WindowsHeldObjectApiV2.identity(held, "file")
            if identity[3] & 0x10 or identity[4] != 0:
                raise OSError("lock type")
            existed = create_error == 183
            lock = cls(path, held, identity)
            if existed:
                descriptor, expected_sddl = (
                    WindowsPrivateObjectOwnerV1.current_user_security_descriptor()
                )
                try:
                    WindowsPrivateObjectOwnerV1.verify_handle_dacl(
                        held, expected_sddl
                    )
                finally:
                    kernel32.LocalFree(descriptor)
                if WindowsHeldObjectApiV2.read_exact(
                    HeldWindowsObjectV2(path, held, "file", identity), 128
                ) != KIMI_ADMISSION_LOCK_MARKER_V2:
                    raise OSError("lock marker")
            else:
                WindowsPrivateObjectOwnerV1.protect_handle_and_verify(held)
                written = wintypes.DWORD()
                buffer = ctypes.create_string_buffer(KIMI_ADMISSION_LOCK_MARKER_V2)
                if not kernel32.WriteFile(
                    wintypes.HANDLE(held), buffer, len(KIMI_ADMISSION_LOCK_MARKER_V2),
                    ctypes.byref(written), None,
                ) or written.value != len(KIMI_ADMISSION_LOCK_MARKER_V2):
                    raise OSError(ctypes.get_last_error(), "WriteFile(lock)")
                if not kernel32.FlushFileBuffers(wintypes.HANDLE(held)):
                    raise OSError(ctypes.get_last_error(), "FlushFileBuffers(lock)")
                if WindowsHeldObjectApiV2.read_exact(
                    HeldWindowsObjectV2(path, held, "file", identity), 128
                ) != KIMI_ADMISSION_LOCK_MARKER_V2:
                    raise OSError("lock marker readback")
            return lock
        except Exception as exc:
            kernel32.CloseHandle(wintypes.HANDLE(held))
            if isinstance(exc, ValueError):
                raise
            raise ValueError("E_KIMI_PRIVATE_STATE_INVALID") from exc

    def close(self) -> None:
        if self.handle < 0:
            return
        import ctypes
        from ctypes import wintypes

        ctypes.WinDLL("kernel32", use_last_error=True).CloseHandle(
            wintypes.HANDLE(self.handle)
        )
        self.handle = -1



def fail(message: str, code: int = 1) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return code


def stable_failure_id_from_exception(exc: BaseException, fallback: str) -> str:
    match = re.match(r"(E_[A-Z0-9_]{1,127})(?:\b|:)", str(exc), re.ASCII)
    return match.group(1) if match is not None else fallback


def parse_control(argv: list[str], *, external: bool = False) -> Control:
    result = Control()
    seen_values: dict[str, object] = {}
    value_flags = {
        "-promptfile": "prompt_file",
        "--prompt-file": "prompt_file",
        "--terminal-receipt": "terminal_receipt",
        "-ledger": "ledger",
        "--ledger": "ledger",
        "-ledgerrole": "ledger_role",
        "--ledger-role": "ledger_role",
        "-ledgerlane": "ledger_lane",
        "--ledger-lane": "ledger_lane",
        "-ledgerartifact": "ledger_artifact",
        "--ledger-artifact": "ledger_artifact",
        "-ledgercloses": "ledger_closes",
        "--ledger-closes": "ledger_closes",
        "-timeoutsecs": "timeout_secs",
        "--timeout-secs": "timeout_secs",
        "-resultmaxbytes": "result_max_bytes",
        "--result-max-bytes": "result_max_bytes",
        "-capturemaxbytes": "capture_max_bytes",
        "--capture-max-bytes": "capture_max_bytes",
    }
    if external:
        value_flags.update(
            {
                "--task-class": "task_class",
                "--role": "role",
                "--live-root": "live_root",
            }
        )
    index = 0
    while index < len(argv):
        token = argv[index]
        key = token.lower()
        if token == "--":
            result.provider_flags.extend(argv[index + 1 :])
            break
        if key in value_flags:
            if index + 1 >= len(argv):
                raise ValueError(f"{token} requires a value")
            value = argv[index + 1]
            attr = value_flags[key]
            if attr in {"prompt_file", "terminal_receipt"}:
                parsed_value: object = Path(value)
            elif attr in {"live_root"}:
                parsed_value = Path(value)
            elif attr == "timeout_secs":
                parsed_value = float(value)
                if not math.isfinite(parsed_value) or parsed_value <= 0:
                    raise ValueError(f"{token} must be a positive finite number")
            elif attr in {"result_max_bytes", "capture_max_bytes"}:
                parsed_value = int(value)
                if parsed_value <= 0:
                    raise ValueError(f"{token} must be a positive integer")
            elif attr == "ledger_closes":
                result.ledger_closes.append(value)
                index += 2
                continue
            else:
                parsed_value = value
            if external and attr in {"task_class", "role"} and attr in seen_values:
                raise ValueError(f"duplicate values for {token}")
            if attr in seen_values and seen_values[attr] != parsed_value:
                raise ValueError(f"conflicting values for {token}")
            seen_values[attr] = parsed_value
            setattr(result, attr, parsed_value)
            if attr == "ledger_role":
                result.ledger_role_explicit = True
            index += 2
            continue
        if result.topic is None:
            result.topic = token
        else:
            result.provider_flags.append(token)
        index += 1
    if result.result_max_bytes > RESULT_MAX_BYTES_HARD:
        raise ValueError(
            f"--result-max-bytes must not exceed {RESULT_MAX_BYTES_HARD}"
        )
    if result.capture_max_bytes > CAPTURE_MAX_BYTES_HARD:
        raise ValueError(
            f"--capture-max-bytes must not exceed {CAPTURE_MAX_BYTES_HARD}"
        )
    if result.result_max_bytes > result.capture_max_bytes:
        raise ValueError("--result-max-bytes must not exceed --capture-max-bytes")
    if external and (not result.task_class or not result.role):
        raise ValueError(
            "E_EXTERNAL_DISPATCH_POLICY_DENIED: --task-class and --role are required"
        )
    return result


def validate_topic(topic: str | None) -> str:
    if (
        not topic
        or len(topic) > 64
        or ".." in topic
        or INVALID_SLUG.search(topic)
    ):
        raise ValueError(
            f"invalid TopicSlug {topic!r} - must be 1-64 chars and exclude '..', "
            "path separators, drive/ADS separators, and Windows-invalid filename chars"
        )
    return topic


def _bounded_launch_flag_tokens(flags: object) -> tuple[str, ...]:
    """Freeze one bounded argv vector before provider grammar validation."""

    if not isinstance(flags, (list, tuple)) or len(flags) > LAUNCH_FLAGS_MAX_COUNT:
        raise ValueError("E_EXTERNAL_LAUNCH_FLAGS_INVALID")
    frozen: list[str] = []
    total = 0
    for token in flags:
        if not isinstance(token, str) or "\x00" in token or "\r" in token or "\n" in token:
            raise ValueError("E_EXTERNAL_LAUNCH_FLAGS_INVALID")
        encoded = token.encode("utf-8", errors="strict")
        total += len(encoded)
        if len(encoded) > LAUNCH_FLAGS_MAX_TOKEN_BYTES or total > LAUNCH_FLAGS_MAX_TOTAL_BYTES:
            raise ValueError("E_EXTERNAL_LAUNCH_FLAGS_INVALID")
        frozen.append(token)
    return tuple(frozen)


def normalize_launch_profile(
    provider: str, flags: object
) -> tuple[tuple[str, ...], str, str]:
    """Validate the closed non-sensitive flag grammar and derive its profile."""

    frozen = _bounded_launch_flag_tokens(flags)
    if provider == "kimi":
        if frozen:
            raise ValueError("E_EXTERNAL_LAUNCH_FLAGS_UNSAFE")
        return frozen, "kimi-code/k3", "unsupported"
    if provider not in {"codex", "claude"}:
        raise ValueError("E_EXTERNAL_LAUNCH_FLAGS_INVALID")

    model = ""
    effort = ""
    index = 0
    while index < len(frozen):
        token = frozen[index]
        if provider == "codex":
            if token == "--model" and index + 1 < len(frozen):
                value = frozen[index + 1]
                if _MODEL_TOKEN.fullmatch(value) is None:
                    raise ValueError("E_EXTERNAL_LAUNCH_FLAGS_UNSAFE")
                model = value
                index += 2
                continue
            if token == "-c" and index + 1 < len(frozen):
                matched = re.fullmatch(
                    r'model_reasoning_effort="?(low|medium|high|xhigh|max)"?',
                    frozen[index + 1],
                )
                if matched is None:
                    raise ValueError("E_EXTERNAL_LAUNCH_FLAGS_UNSAFE")
                effort = matched.group(1)
                index += 2
                continue
            if token == "--sandbox" and index + 1 < len(frozen):
                if frozen[index + 1] not in _CODEX_SANDBOXES:
                    raise ValueError("E_EXTERNAL_LAUNCH_FLAGS_UNSAFE")
                index += 2
                continue
            raise ValueError("E_EXTERNAL_LAUNCH_FLAGS_UNSAFE")

        if token == "-p":
            index += 1
            continue
        if token == "--model" and index + 1 < len(frozen):
            value = frozen[index + 1]
            if _MODEL_TOKEN.fullmatch(value) is None:
                raise ValueError("E_EXTERNAL_LAUNCH_FLAGS_UNSAFE")
            model = value
            index += 2
            continue
        if token == "--effort" and index + 1 < len(frozen):
            value = frozen[index + 1]
            if value not in EFFORTS:
                raise ValueError("E_EXTERNAL_LAUNCH_FLAGS_UNSAFE")
            effort = value
            index += 2
            continue
        if token in {"--input-format", "--output-format"} and index + 1 < len(frozen):
            if frozen[index + 1] not in _CLAUDE_IO_FORMATS:
                raise ValueError("E_EXTERNAL_LAUNCH_FLAGS_UNSAFE")
            index += 2
            continue
        if token == "--permission-mode" and index + 1 < len(frozen):
            if frozen[index + 1] not in _CLAUDE_PERMISSION_MODES:
                raise ValueError("E_EXTERNAL_LAUNCH_FLAGS_UNSAFE")
            index += 2
            continue
        if token in {
            "--tools", "--allowedTools", "--allowed-tools",
            "--disallowedTools", "--disallowed-tools",
        } and index + 1 < len(frozen):
            if _CLAUDE_TOOL_LIST.fullmatch(frozen[index + 1]) is None:
                raise ValueError("E_EXTERNAL_LAUNCH_FLAGS_UNSAFE")
            index += 2
            continue
        if token == "--setting-sources" and index + 1 < len(frozen):
            if frozen[index + 1] != "user":
                raise ValueError("E_EXTERNAL_LAUNCH_FLAGS_UNSAFE")
            index += 2
            continue
        raise ValueError("E_EXTERNAL_LAUNCH_FLAGS_UNSAFE")
    return frozen, model, effort


def normalize_launch_flags(provider: str, flags: object) -> tuple[str, ...]:
    return normalize_launch_profile(provider, flags)[0]


def resolved_profile(provider: str, flags: list[str]) -> tuple[list[str], str, str]:
    if provider == "kimi":
        if flags:
            raise ValueError(
                "E_KIMI_PROFILE_FIXED: Kimi 1.x accepts no caller-supplied provider flags"
            )
        return [], "kimi-code/k3", "unsupported"
    if not flags:
        flags = (
            ["--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=xhigh"]
            if provider == "codex"
            else [
                "-p",
                "--output-format",
                "text",
                "--model",
                "opus",
                "--effort",
                "xhigh",
            ]
        )
    if provider == "claude" and any(
        token in {"--setting-sources", "--settings"}
        or token.startswith("--setting-sources=")
        or token.startswith("--settings=")
        for token in flags
    ):
        raise ValueError(
            "E_EXTERNAL_PROVIDER_SETTINGS_OVERRIDE: automated Claude settings are fixed"
        )
    if provider == "claude":
        flags = [*flags, "--setting-sources", "user"]
    try:
        frozen, model, effort = normalize_launch_profile(provider, flags)
    except ValueError:
        raise
    if not model or not effort:
        example = (
            "--model gpt-5.6-sol -c model_reasoning_effort=xhigh"
            if provider == "codex"
            else "-p --output-format text --model opus --effort xhigh"
        )
        raise ValueError(
            f"A12 violation - resolved {provider} flags carry no explicit model "
            f"and/or effort. Pass the FULL per-profile flag set, e.g.: {example}"
        )
    return list(frozen), model, effort


def _lexically_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _external_role_taxonomy() -> tuple[set[str], set[str], set[str], set[str]]:
    """Load the dedicated complete taxonomy without executing another policy owner."""

    try:
        script = Path(__file__).resolve()
        source_candidate = script.parent.parent / "shared" / EXTERNAL_ROLE_TAXONOMY_NAME
        taxonomy_path = (
            source_candidate
            if script == script.parent.parent / "scripts" / script.name
            and source_candidate.is_file()
            else script.with_name(EXTERNAL_ROLE_TAXONOMY_NAME)
        )
        validate_no_reparse_components(taxonomy_path)
        metadata = taxonomy_path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or _metadata_is_reparse(metadata)
        ):
            raise ValueError("taxonomy is not ordinary")
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
                raise ValueError("taxonomy identity changed")
            payload = os.read(descriptor, EXTERNAL_ROLE_TAXONOMY_MAX_BYTES + 1)
        finally:
            os.close(descriptor)
        if len(payload) > EXTERNAL_ROLE_TAXONOMY_MAX_BYTES:
            raise ValueError("taxonomy exceeds byte limit")
        if hashlib.sha256(payload).hexdigest() != EXTERNAL_ROLE_TAXONOMY_SHA256:
            raise RuntimeError("E_EXTERNAL_PROVENANCE_ROLE_TAXONOMY_INTEGRITY")
        document = json.loads(payload.decode("utf-8", errors="strict"))
        if not isinstance(document, dict) or set(document) != {"schemaVersion", "roles"}:
            raise ValueError("taxonomy shape")
        if document["schemaVersion"] != 1 or not isinstance(document["roles"], dict):
            raise ValueError("taxonomy version")
        mapping = document["roles"]
        if len(mapping) != 34 or any(
            not isinstance(role, str)
            or not role
            or lane not in {"consultant", "external-worker", "external-reviewer", "none"}
            for role, lane in mapping.items()
        ):
            raise ValueError("taxonomy membership")
        roles = set(mapping)
        reviewers = {role for role, lane in mapping.items() if lane == "external-reviewer"}
        workers = {role for role, lane in mapping.items() if lane == "external-worker"}
        unsupported = {role for role, lane in mapping.items() if lane == "none"}
        if {role for role, lane in mapping.items() if lane == "consultant"} != {"consultant"}:
            raise ValueError("taxonomy consultant lane")
    except RuntimeError as exc:
        if str(exc) == "E_EXTERNAL_PROVENANCE_ROLE_TAXONOMY_INTEGRITY":
            raise ValueError(str(exc)) from exc
        raise
    except (
        AttributeError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ValueError("E_EXTERNAL_PROVENANCE_ROLE_INVALID: role taxonomy") from exc
    return roles, reviewers, workers, unsupported


def external_role_provenance(control: Control, provider: str) -> ExternalRoleProvenance:
    """Freeze S3 role provenance before external side effects begin."""

    roles, reviewers, workers, unsupported = _external_role_taxonomy()
    if provider in {"codex", "claude"} and not control.ledger_role_explicit:
        return ExternalRoleProvenance("none", "none")
    assigned = control.ledger_role if control.ledger_role_explicit else "none"
    if assigned not in roles:
        raise ValueError("E_EXTERNAL_PROVENANCE_ROLE_INVALID: assigned role")
    if assigned in unsupported:
        raise ValueError("E_EXTERNAL_PROVENANCE_ROLE_UNSUPPORTED: assigned role")
    if assigned == "consultant":
        execution = "consultant"
    elif assigned in reviewers:
        execution = "external-reviewer"
    elif assigned in workers:
        execution = "external-worker"
    else:
        execution = "none"
    return ExternalRoleProvenance(assigned, execution)


def _load_external_dispatch_resolver() -> object:
    """Load only the ordinary resolver sibling paired with this wrapper."""

    resolver_path = Path(__file__).resolve().with_name("resolve-agents-mode.py")
    try:
        validate_no_reparse_components(resolver_path)
        metadata = resolver_path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or _metadata_is_reparse(metadata)
        ):
            raise ValueError("resolver is not ordinary")
        spec = importlib.util.spec_from_file_location(
            "_orchestrarium_external_dispatch_resolver", resolver_path
        )
        if spec is None or spec.loader is None:
            raise ValueError("resolver cannot load")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop(spec.name, None)
        if not callable(getattr(module, "resolve_external_dispatch", None)):
            raise ValueError("resolver API")
        return module
    except Exception:
        raise ValueError("E_EXTERNAL_DISPATCH_POLICY_DENIED") from None


def _policy_bound_external_control(
    provider: str, control: Control
) -> tuple[Control, dict[str, object]]:
    """Authorize one Kimi/Grok invocation from the shared policy owner only."""

    if not control.task_class or not control.role:
        raise ValueError("E_EXTERNAL_DISPATCH_POLICY_DENIED")
    if control.ledger_role_explicit and control.ledger_role != control.role:
        raise ValueError("E_EXTERNAL_DISPATCH_POLICY_DENIED")
    try:
        resolver = _load_external_dispatch_resolver()
        decision = resolver.resolve_external_dispatch(
            provider, control.task_class, control.role
        )
    except Exception:
        raise ValueError("E_EXTERNAL_DISPATCH_POLICY_DENIED") from None
    if (
        not isinstance(decision, dict)
        or set(decision) != _EXTERNAL_DISPATCH_DECISION_FIELDS
        or decision.get("schemaVersion") != 1
        or decision.get("provider") != provider
        or decision.get("taskClass") != control.task_class
        or decision.get("role") != control.role
        or decision.get("status") != "external-authorized"
        or decision.get("executionAuthorized") is not True
        or decision.get("mutationClass") != "read-only"
        or decision.get("finalAuthorizingRole") is not False
        or decision.get("independentVerification") is not True
        or decision.get("fallback") != "none"
        or decision.get("stableId") is not None
    ):
        raise ValueError("E_EXTERNAL_DISPATCH_POLICY_DENIED")
    return replace(control, ledger_role=control.role, ledger_role_explicit=True), decision


def external_execution_provenance(
    control: Control,
    *,
    topic: str,
    provider: str,
    model: str,
    effort: str,
    launch_flags: tuple[str, ...],
    role_provenance: ExternalRoleProvenance,
    dispatch_decision: dict[str, object],
) -> ExecutionProvenance:
    """Freeze every external provenance field before prompt/capture side effects."""

    mapping_loss = dispatch_decision.get("effortMappingLoss")
    if not isinstance(mapping_loss, str) or not mapping_loss:
        raise ValueError("E_EXTERNAL_PROVENANCE_INVALID")
    dispatch_id = f"dispatch-{secrets.token_hex(16)}"
    evidence_id = f"evidence-{secrets.token_hex(16)}"
    return ExecutionProvenance(
        work_item=(Path(control.ledger).name if control.ledger else f"untracked:{topic}"),
        assigned_internal_role=role_provenance.assigned_role,
        provider=provider,
        model=model,
        effort=effort,
        launch_flags=launch_flags,
        artifact_identity=control.ledger_artifact or f"topic:{topic}",
        external_dispatch_id=dispatch_id,
        external_evidence_run_id=evidence_id,
        effort_mapping_loss=mapping_loss,
    )


def require_exact_execution_provenance(
    expected: ExecutionProvenance, supplied: ExecutionProvenance
) -> ExecutionProvenance:
    """Reject any full-field provenance drift before an external terminal sink."""

    if expected.payload() != supplied.payload():
        raise ValueError("E_EXTERNAL_PROVENANCE_MISMATCH")
    return expected


def _prevalidate_policy_bound_external_launch(
    provider: str, argv: list[str]
) -> PolicyBoundLaunch:
    control = parse_control(argv, external=True)
    topic = validate_topic(control.topic)
    if control.ledger_closes:
        raise ValueError(
            "E_EXTERNAL_CLOSES_FORBIDDEN: external provider results cannot close ledger runs"
        )
    control, decision = _policy_bound_external_control(provider, control)
    flags, model, effort = resolved_profile(provider, control.provider_flags)
    role_provenance = external_role_provenance(control, provider)
    return PolicyBoundLaunch(
        control,
        topic,
        tuple(flags),
        model,
        effort,
        role_provenance,
        external_execution_provenance(
            control,
            topic=topic,
            provider=provider,
            model=model,
            effort=effort,
            launch_flags=tuple(flags),
            role_provenance=role_provenance,
            dispatch_decision=decision,
        ),
    )


def require_transport_projection_parity() -> None:
    validator_path = Path(__file__).resolve().with_name(
        "validate-provider-prompt-projections.py"
    )
    if not validator_path.is_file():
        raise ValueError(
            "E_TRANSPORT_PROJECTION_PARITY: projection validator is missing"
        )
    spec = importlib.util.spec_from_file_location(
        "_orchestrarium_transport_projection_validator", validator_path
    )
    if spec is None or spec.loader is None:
        raise ValueError(
            "E_TRANSPORT_PROJECTION_PARITY: projection validator cannot load"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        # This runtime helper validates only the local packed source set.  It
        # must not infer a project/global installation or cross into HOME.
        source_root = validator_path.parent.parent
        module.validate_source_manifest(
            source_root / "shared" / "provider-prompt-projections.v1.json",
            source_root,
        )
    except Exception as exc:
        detail = str(exc)
        if not detail.startswith("E_TRANSPORT_PROJECTION_PARITY:"):
            detail = f"E_TRANSPORT_PROJECTION_PARITY: {detail}"
        raise ValueError(detail) from exc


def _command_from_path(path: str, provenance: str) -> ResolvedProviderCommand | None:
    candidate = Path(path).expanduser()
    discovered = candidate if provenance == "explicit-absolute-binding" else shutil.which(path)
    if not discovered:
        return None
    try:
        target = Path(discovered).resolve(strict=True)
    except OSError:
        return None
    if not target.is_file():
        return None
    suffix = target.suffix.lower()
    if suffix == ".py":
        try:
            interpreter = Path(sys.executable).expanduser().resolve(strict=True)
        except OSError:
            return None
        command = (str(interpreter), str(target))
    elif suffix in {".ps1", ".cmd", ".bat", ".sh"}:
        return None
    else:
        command = (str(target),)
    return ResolvedProviderCommand(command, target, provenance)


def resolve_provider_command(provider: str) -> ResolvedProviderCommand | None:
    # Kimi is bound only by an explicit installer enrollment receipt.  It must
    # never inherit a caller's PATH or KIMI_BIN selection.
    if provider == "kimi":
        return None
    environment_key = {
        "codex": "CODEX_BIN",
        "claude": "CLAUDE_BIN",
    }.get(provider)
    if environment_key is None:
        return None
    requested = os.environ.get(environment_key)
    names = [requested] if requested else [provider, f"{provider}.exe", f"{provider}.cmd"]
    for name in names:
        if name:
            requested_path = Path(name).expanduser()
            provenance = (
                "explicit-absolute-binding"
                if requested is not None and requested_path.is_absolute()
                else "path-discovery"
            )
            command = _command_from_path(name, provenance)
            if command:
                return command
    return None


def _physical_repository_root(query_cwd: Path) -> Path | None:
    physical_cwd = query_cwd.resolve(strict=True)
    for candidate in (physical_cwd, *physical_cwd.parents):
        if os.path.lexists(candidate / ".git"):
            return candidate
    return None


def _reject_repository_path_discovery(
    resolution: ResolvedProviderCommand, query_cwd: Path
) -> None:
    repository_root = _physical_repository_root(query_cwd)
    if repository_root is None:
        return
    if len(resolution.command) > 1:
        interpreter = Path(resolution.command[0])
        try:
            interpreter.relative_to(repository_root)
        except ValueError:
            pass
        else:
            raise ValueError(
                f"{E_EXTERNAL_PROVIDER_REPOSITORY_EXECUTABLE}: "
                "provider interpreter is inside the active repository"
            )
    if resolution.provenance != "path-discovery":
        return
    try:
        resolution.target.relative_to(repository_root)
    except ValueError:
        return
    raise ValueError(
        f"{E_EXTERNAL_PROVIDER_REPOSITORY_EXECUTABLE}: "
        "PATH-discovered provider executable is inside the active repository"
    )


def _kimi_binding_v2_path(runtime_root: Path) -> Path:
    return runtime_root / KIMI_EXECUTABLE_BINDING_FILENAME_V2


def _ensure_kimi_private_root_v2(runtime_root: Path, *, create: bool) -> None:
    try:
        if os.name == "nt":
            if runtime_root.exists():
                WindowsPrivateObjectOwnerV1.verify_existing(
                    runtime_root, directory=True
                )
            elif create:
                WindowsPrivateObjectOwnerV1.ensure_directory(runtime_root)
            return
        if runtime_root.exists():
            validate_no_reparse_components(runtime_root)
            metadata = runtime_root.lstat()
            if not stat.S_ISDIR(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o700:
                raise OSError("Kimi runtime root permissions")
        elif create:
            runtime_root.mkdir(mode=0o700, parents=True)
    except (OSError, ValueError) as exc:
        raise ValueError("E_KIMI_PRIVATE_STATE_INVALID") from exc


def _kimi_version_tuple_v2(value: str) -> tuple[int, int, int]:
    match = KIMI_VERSION_PATTERN_V2.fullmatch(value)
    if match is None:
        raise ValueError("E_KIMI_MANIFEST_INVALID")
    return tuple(int(part) for part in match.groups())  # type: ignore[return-value]


def _kimi_json_no_duplicates_v2(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("E_KIMI_MANIFEST_INVALID")
        result[key] = value
    return result


class _KimiNoRedirectV2(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


def _fetch_kimi_https_once_v2(url: str) -> KimiHttpResponseV2:
    """Fetch one bounded response with system TLS and no proxy or redirect policy."""

    maximum = KIMI_MANIFEST_MAX_BYTES_V2
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}), _KimiNoRedirectV2()
    )
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json, application/octet-stream"},
        method="GET",
    )
    try:
        try:
            response = opener.open(request, timeout=10.0)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            body = response.read(maximum + 1)
            if len(body) > maximum:
                raise ValueError("E_KIMI_OFFICIAL_CHANNEL_INVALID")
            location_values = response.headers.get_all("Location") or []
            if len(location_values) > 1:
                raise ValueError("E_KIMI_OFFICIAL_CHANNEL_INVALID")
            headers = {
                "location": location_values[0]
            } if location_values else {}
            return KimiHttpResponseV2(int(response.status), headers, body)
    except ValueError:
        raise
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        raise KimiOfficialChannelUnavailableV2() from exc


def _kimi_redirected_body_v2(
    fetcher,
    origin_url: str,
    cdn_url: str,
    maximum: int,
) -> bytes:
    try:
        origin = fetcher(origin_url)
        if type(origin) is not KimiHttpResponseV2 or origin.status != 302:
            raise ValueError("E_KIMI_OFFICIAL_CHANNEL_INVALID")
        normalized_headers = {
            str(key).lower(): str(value) for key, value in origin.headers.items()
        }
        if normalized_headers != {"location": cdn_url}:
            raise ValueError("E_KIMI_OFFICIAL_CHANNEL_INVALID")
        parsed = urllib.parse.urlsplit(cdn_url)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "cdn.kimi.com"
            or parsed.port is not None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
            or urllib.parse.urlunsplit(parsed) != cdn_url
        ):
            raise ValueError("E_KIMI_OFFICIAL_CHANNEL_INVALID")
        terminal = fetcher(cdn_url)
        if (
            type(terminal) is not KimiHttpResponseV2
            or terminal.status != 200
            or terminal.headers.get("location") is not None
            or len(terminal.body) > maximum
        ):
            raise ValueError("E_KIMI_OFFICIAL_CHANNEL_INVALID")
        return bytes(terminal.body)
    except KimiOfficialChannelUnavailableV2:
        raise
    except (KeyError, TypeError, UnicodeError, ValueError) as exc:
        if str(exc) == "E_KIMI_OFFICIAL_CHANNEL_INVALID":
            raise
        raise ValueError("E_KIMI_OFFICIAL_CHANNEL_INVALID") from exc


def _live_kimi_manifest_v2(fetcher) -> tuple[str, str, str, str]:
    latest_bytes = _kimi_redirected_body_v2(
        fetcher,
        KIMI_LATEST_URL_V2,
        KIMI_CDN_LATEST_URL_V2,
        KIMI_LATEST_MAX_BYTES_V2,
    )
    try:
        latest_text = latest_bytes.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise ValueError("E_KIMI_MANIFEST_INVALID") from exc
    version = latest_text[:-1] if latest_text.endswith("\n") else latest_text
    _kimi_version_tuple_v2(version)
    manifest_code = (
        f"https://code.kimi.com/kimi-code/binaries/{version}/manifest.json"
    )
    manifest_cdn = (
        f"https://cdn.kimi.com/kimi-code/binaries/{version}/manifest.json"
    )
    manifest_bytes = _kimi_redirected_body_v2(
        fetcher, manifest_code, manifest_cdn, KIMI_MANIFEST_MAX_BYTES_V2
    )
    try:
        manifest = json.loads(
            manifest_bytes.decode("utf-8", errors="strict"),
            object_pairs_hook=_kimi_json_no_duplicates_v2,
        )
        if type(manifest) is not dict or set(manifest) != {"version", "tag", "platforms"}:
            raise ValueError("E_KIMI_MANIFEST_INVALID")
        if manifest["version"] != version or manifest["tag"] != (
            f"@moonshot-ai/kimi-code@{version}"
        ):
            raise ValueError("E_KIMI_MANIFEST_INVALID")
        platforms = manifest["platforms"]
        if type(platforms) is not dict or not 1 <= len(platforms) <= 16:
            raise ValueError("E_KIMI_MANIFEST_INVALID")
        for name, entry in platforms.items():
            if (
                not isinstance(name, str)
                or not re.fullmatch(r"[a-z0-9]+-[a-z0-9]+", name, re.ASCII)
                or type(entry) is not dict
                or set(entry) != {"filename", "checksum"}
                or not isinstance(entry["filename"], str)
                or not isinstance(entry["checksum"], str)
                or re.fullmatch(r"[a-f0-9]{64}", entry["checksum"], re.ASCII) is None
            ):
                raise ValueError("E_KIMI_MANIFEST_INVALID")
        selected = platforms.get("win32-x64")
        if (
            type(selected) is not dict
            or selected["filename"] != "kimi-code-win32-x64.exe"
        ):
            raise ValueError("E_KIMI_MANIFEST_INVALID")
        return (
            version,
            str(selected["filename"]),
            str(selected["checksum"]),
            hashlib.sha256(manifest_bytes).hexdigest(),
        )
    except (KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("E_KIMI_MANIFEST_INVALID") from exc


def _observe_kimi_executable_v2(path: Path) -> ExecutableBindingV1:
    try:
        validate_no_reparse_components(path)
        before = path.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or _metadata_is_reparse(before)
            or not 0 < before.st_size <= KIMI_EXECUTABLE_MAX_BYTES_V2
        ):
            raise OSError("Kimi executable metadata")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        digest = hashlib.sha256()
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino, opened.st_size) != (
                before.st_dev,
                before.st_ino,
                before.st_size,
            ):
                raise OSError("Kimi executable identity")
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        after = path.lstat()
        if (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise OSError("Kimi executable drift")
        return ExecutableBindingV1(
            str(path),
            before.st_size,
            digest.hexdigest(),
            before.st_dev,
            before.st_ino,
            before.st_mode,
            before.st_mtime_ns,
        )
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValueError("E_KIMI_EXECUTABLE_IDENTITY_INVALID") from exc


def _default_kimi_probe_runner_v2(
    executable: Path,
    argv: tuple[str, ...],
    environment: dict[str, str],
    cwd: Path,
    binding: ExecutableBindingV1,
) -> bytes:
    runner = ProcessRunnerV1()
    try:
        sink = runner.mint_memory_capture_sink()
        request = ProcessRequestV1(
            schema_version=1,
            argv=(str(executable), *argv),
            resolved_executable=executable,
            cwd=str(cwd),
            environment=tuple(
                EnvironmentRowV1(name, value) for name, value in environment.items()
            ),
            stdin_bytes=None,
            deadline_monotonic=time.monotonic() + 10.0,
            capture_policy=CapturePolicyV1(
                "kimi-metadata-probe-v2", KIMI_PROBE_MAX_BYTES_V2, 0, 0, 4096
            ),
            capture_sink_binding=sink,
            settle_policy=SettlePolicyV1(5.0),
            windows_argv_profile_id=KIMI_WINDOWS_PROFILE_V1.probe_profile_id,
            expected_executable_binding=binding,
        )
        result = runner.run(request)
        stdout = sink.bytes_for("stdout")
        stderr = sink.bytes_for("stderr")
        if (
            result.outcome != "success"
            or result.target_exit_code != 0
            or stderr
            or len(stdout) > KIMI_PROBE_MAX_BYTES_V2
        ):
            raise ValueError("E_KIMI_PROBE_INVALID")
        return stdout
    except (OSError, ProcessSupervisionError, ValueError) as exc:
        if str(exc) == "E_KIMI_PROBE_INVALID":
            raise
        raise ValueError("E_KIMI_PROBE_INVALID") from exc
    finally:
        runner.close()


def _probe_kimi_executable_v2(
    executable: Path,
    runtime_root: Path | None,
    binding: ExecutableBindingV1,
    version: str,
    probe_runner,
) -> tuple[str, str]:
    try:
        if runtime_root is not None:
            _ensure_kimi_private_root_v2(runtime_root, create=True)
        with tempfile.TemporaryDirectory(
            prefix="orchestrarium-kimi-probe-",
            dir=runtime_root,
        ) as temporary:
            private_home = Path(temporary)
            if os.name == "nt":
                WindowsPrivateObjectOwnerV1.protect_and_verify(
                    private_home, directory=True
                )
            else:
                os.chmod(private_home, 0o700)
            environment = {
                "KIMI_CODE_HOME": str(private_home),
                "KIMI_CODE_NO_AUTO_UPDATE": "1",
            }
            system_root = os.environ.get("SYSTEMROOT")
            if os.name == "nt":
                if not system_root:
                    raise ValueError("E_KIMI_PROBE_INVALID")
                environment["SYSTEMROOT"] = system_root
            version_output = probe_runner(
                executable, ("--version",), environment, private_home, binding
            )
            help_output = probe_runner(
                executable, ("--help",), environment, private_home, binding
            )
        if (
            not isinstance(version_output, bytes)
            or not isinstance(help_output, bytes)
            or len(version_output) > KIMI_PROBE_MAX_BYTES_V2
            or len(help_output) > KIMI_PROBE_MAX_BYTES_V2
            or version_output.decode("utf-8", errors="strict").strip() != version
        ):
            raise ValueError("E_KIMI_PROBE_INVALID")
        help_text = help_output.decode("utf-8", errors="strict")
        required = ("--agent-file", "--skills-dir", "--model", "--output-format", "--prompt")
        if any(flag not in help_text for flag in required):
            raise ValueError("E_KIMI_PROBE_INVALID")
        return (
            hashlib.sha256(version_output).hexdigest(),
            hashlib.sha256(help_output).hexdigest(),
        )
    except (OSError, UnicodeError, ValueError) as exc:
        if str(exc) == "E_KIMI_PROBE_INVALID":
            raise
        raise ValueError("E_KIMI_PROBE_INVALID") from exc


def _classify_kimi_v1_state_v2(
    runtime_root: Path, executable: Path
) -> KimiV1SnapshotV2 | None:
    path = runtime_root / "executable-binding-v1.json"
    if not os.path.lexists(path):
        return None
    try:
        validate_no_reparse_components(path)
        before = path.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or _metadata_is_reparse(before)
            or before.st_size > 4096
        ):
            raise OSError("V1 type")
        descriptor = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_BINARY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino, opened.st_size) != (
                before.st_dev,
                before.st_ino,
                before.st_size,
            ):
                raise OSError("V1 identity")
            payload = stream.read(4097)
        after = path.lstat()
        identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        if identity != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise OSError("V1 drift")
        data = json.loads(
            payload.decode("utf-8", errors="strict"),
            object_pairs_hook=_kimi_json_no_duplicates_v2,
        )
        if type(data) is not dict or set(data) != {"path", "schema", "sha256", "size"}:
            raise ValueError("customized")
        expected = {
            "path": str(executable),
            "schema": "orchestrarium.kimi-executable-binding.v1",
            "sha256": data["sha256"],
            "size": data["size"],
        }
        canonical = json.dumps(
            expected, sort_keys=True, separators=(",", ":")
        ).encode("utf-8") + b"\n"
        if (
            data != expected
            or payload != canonical
            or not isinstance(data["size"], int)
            or not 0 < data["size"] <= KIMI_EXECUTABLE_MAX_BYTES_V2
            or not isinstance(data["sha256"], str)
            or re.fullmatch(r"[a-f0-9]{64}", data["sha256"], re.ASCII) is None
        ):
            raise ValueError("customized")
        return KimiV1SnapshotV2(path, payload, identity)
    except (OSError, TypeError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("E_KIMI_V1_STATE_CUSTOMIZED") from exc


def _reclaim_kimi_v1_after_v2_v2(
    snapshot: KimiV1SnapshotV2,
    runtime_root: Path,
    expected_binding: ExecutableBindingV1,
    reclaim_hook=None,
) -> None:
    receipt = _read_kimi_v2_receipt(runtime_root)
    if (
        receipt is None
        or receipt["path"] != expected_binding.path
        or receipt["size"] != expected_binding.size
        or not secrets.compare_digest(
            str(receipt["sha256"]), expected_binding.sha256
        )
    ):
        raise ValueError("E_KIMI_V2_RECLAIM_PENDING")
    try:
        current_binding = _observe_kimi_executable_v2(Path(expected_binding.path))
        if current_binding != expected_binding:
            raise OSError("current executable changed before V1 reclaim")
        current = snapshot.path.lstat()
        identity = (
            current.st_dev,
            current.st_ino,
            current.st_size,
            current.st_mtime_ns,
        )
        if identity != snapshot.identity or snapshot.path.read_bytes() != snapshot.payload:
            raise OSError("V1 changed before reclaim")
        if reclaim_hook is not None:
            reclaim_hook()
        snapshot.path.unlink()
        if os.path.lexists(snapshot.path):
            raise OSError("V1 remains after reclaim")
    except OSError as exc:
        raise ValueError("E_KIMI_V2_RECLAIM_PENDING") from exc


class KimiAdmissionStateOwnerV2:
    """Classify and harden only the fixed legacy corridor before admission."""

    def __init__(
        self,
        runtime_root: Path,
        executable: Path,
        admission_lock: KimiAdmissionLockV2,
        hook=None,
    ) -> None:
        self.root = runtime_root
        self.executable = executable
        self.admission_lock = admission_lock
        self.lock_path = admission_lock.path
        self.hook = hook or (lambda _event: None)
        self.held_parent: HeldWindowsObjectV2 | None = None
        self.held_root: HeldWindowsObjectV2 | None = None
        self.held_v1: HeldWindowsObjectV2 | None = None
        self.held_runs: HeldWindowsObjectV2 | None = None
        self.v1_snapshot: KimiV1SnapshotV2 | None = None

    def _ordinary_directory(self, path: Path) -> None:
        validate_no_reparse_components(path)
        metadata = path.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or _metadata_is_reparse(metadata):
            raise ValueError("E_KIMI_PRIVATE_STATE_INVALID")
        if os.name == "nt":
            WindowsPrivateObjectOwnerV1.reject_named_streams(path)

    def prepare_write(self) -> KimiV1SnapshotV2 | None:
        if not self.root.exists():
            raise ValueError("E_KIMI_PRIVATE_STATE_INVALID")
        self._ordinary_directory(self.root)
        if os.name == "nt":
            self.held_parent = WindowsHeldObjectApiV2.open_parent_chain_no_follow(
                self.root
            )
            self.held_root = WindowsHeldObjectApiV2.open_relative(
                self.held_parent,
                self.root.name,
                "directory",
                write_dac=True,
            )
            names = set(WindowsHeldObjectApiV2.enumerate_directory(self.held_root))
        else:
            names = {path.name for path in self.root.iterdir()}
        if self.lock_path.name not in names or not self.lock_path.is_file():
            raise ValueError("E_KIMI_ADMISSION_BUSY")
        if WindowsHeldObjectApiV2.identity(
            self.admission_lock.handle, "file"
        ) != self.admission_lock.identity:
            raise ValueError("E_KIMI_PRIVATE_STATE_INVALID")
        transaction_names = {
            KIMI_V2_TRANSACTION_FILENAME,
            KIMI_V2_CANDIDATE_FILENAME,
            KIMI_V2_ROLLBACK_FILENAME,
            KIMI_V2_UPDATE_FILENAME,
        }
        target = _kimi_binding_v2_path(self.root)
        v1_path = self.root / "executable-binding-v1.json"
        runs = self.root / "runs"
        if names & transaction_names:
            _ensure_kimi_private_root_v2(self.root, create=False)
            KimiReceiptTransactionV2(self.root).recover_if_needed()
            names = {path.name for path in self.root.iterdir()}
        if target.exists():
            allowed = {target.name, v1_path.name, runs.name, self.lock_path.name}
            if not names <= allowed:
                raise ValueError("E_KIMI_PRIVATE_STATE_INVALID")
            if runs.exists():
                self._ordinary_directory(runs)
                if any(runs.iterdir()):
                    raise ValueError("E_KIMI_V1_MIGRATION_BUSY")
            _ensure_kimi_private_root_v2(self.root, create=False)
            if os.name == "nt":
                if runs.exists():
                    WindowsPrivateObjectOwnerV1.verify_existing(
                        runs, directory=True
                    )
                WindowsPrivateObjectOwnerV1.reject_named_streams(target)
                WindowsPrivateObjectOwnerV1.verify_existing(target, directory=False)
            snapshot = _classify_kimi_v1_state_v2(self.root, self.executable)
            if snapshot is not None and os.name == "nt":
                self.held_v1 = WindowsHeldObjectApiV2.open_relative(
                    self.held_root, v1_path.name, "file", write_dac=True
                )
                if WindowsHeldObjectApiV2.read_exact(self.held_v1, 4096) != snapshot.payload:
                    raise ValueError("E_KIMI_V1_STATE_CUSTOMIZED")
            if runs.exists() and os.name == "nt":
                self.held_runs = WindowsHeldObjectApiV2.open_relative(
                    self.held_root, runs.name, "directory", write_dac=True
                )
            self.v1_snapshot = snapshot
            return snapshot
        if names == {self.lock_path.name}:
            _ensure_kimi_private_root_v2(self.root, create=False)
            return None
        if not v1_path.exists():
            raise ValueError("E_KIMI_PRIVATE_STATE_INVALID")
        if not names <= {v1_path.name, runs.name, self.lock_path.name}:
            raise ValueError("E_KIMI_PRIVATE_STATE_INVALID")
        if os.name == "nt":
            WindowsPrivateObjectOwnerV1.reject_named_streams(v1_path)
        if runs.exists():
            self._ordinary_directory(runs)
            if any(runs.iterdir()):
                raise ValueError("E_KIMI_V1_MIGRATION_BUSY")
        snapshot = _classify_kimi_v1_state_v2(self.root, self.executable)
        if snapshot is None:
            raise ValueError("E_KIMI_V1_STATE_CUSTOMIZED")
        self.v1_snapshot = snapshot
        try:
            if os.name == "nt":
                self.held_v1 = WindowsHeldObjectApiV2.open_relative(
                    self.held_root, v1_path.name, "file", write_dac=True
                )
                if WindowsHeldObjectApiV2.read_exact(self.held_v1, 4096) != snapshot.payload:
                    raise OSError("held V1 mismatch")
                if runs.exists():
                    self.held_runs = WindowsHeldObjectApiV2.open_relative(
                        self.held_root, runs.name, "directory", write_dac=True
                    )
                self.checkpoint(expect_v1=True)
                WindowsPrivateObjectOwnerV1.protect_handle_and_verify(
                    self.held_root.handle
                )
            else:
                os.chmod(self.root, 0o700)
            self.hook("after-root-hardening")
            if os.name == "nt":
                WindowsPrivateObjectOwnerV1.protect_handle_and_verify(
                    self.held_v1.handle
                )
            else:
                os.chmod(v1_path, 0o600)
            self.hook("after-v1-hardening")
            if runs.exists():
                if os.name == "nt":
                    WindowsPrivateObjectOwnerV1.protect_handle_and_verify(
                        self.held_runs.handle
                    )
                else:
                    os.chmod(runs, 0o700)
                self.hook("after-runs-hardening")
            if os.name == "nt" and WindowsHeldObjectApiV2.read_exact(
                self.held_v1, 4096
            ) != snapshot.payload:
                raise OSError("legacy held bytes changed during hardening")
            current = v1_path.lstat()
            if (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns) != snapshot.identity:
                raise OSError("legacy state changed during hardening")
            self.checkpoint(expect_v1=True)
        except Exception as exc:
            raise ValueError("E_KIMI_PRIVATE_STATE_INVALID") from exc
        self.v1_snapshot = snapshot
        return snapshot

    def checkpoint(self, *, expect_v1: bool) -> None:
        if os.name != "nt" or self.held_root is None:
            return
        WindowsHeldObjectApiV2.reopen_relative_and_match(
            self.held_root, self.held_parent, self.root.name
        )
        names = set(WindowsHeldObjectApiV2.enumerate_directory(self.held_root))
        allowed = {
            KIMI_EXECUTABLE_ADMISSION_LOCK_FILENAME_V2,
            KIMI_EXECUTABLE_BINDING_FILENAME_V2,
            "runs",
        }
        if expect_v1:
            allowed.add("executable-binding-v1.json")
        if names - allowed or (expect_v1 and "executable-binding-v1.json" not in names):
            raise ValueError("E_KIMI_PRIVATE_STATE_INVALID")
        if self.held_v1 is not None and expect_v1:
            WindowsHeldObjectApiV2.reopen_relative_and_match(
                self.held_v1, self.held_root, "executable-binding-v1.json"
            )
            if WindowsHeldObjectApiV2.read_exact(self.held_v1, 4096) != self.v1_snapshot.payload:
                raise ValueError("E_KIMI_V1_STATE_CUSTOMIZED")
        if self.held_runs is not None:
            WindowsHeldObjectApiV2.reopen_relative_and_match(
                self.held_runs, self.held_root, "runs"
            )
            if WindowsHeldObjectApiV2.enumerate_directory(self.held_runs):
                raise ValueError("E_KIMI_V1_MIGRATION_BUSY")

    def release_v1_for_reclaim(self) -> None:
        WindowsHeldObjectApiV2.close(self.held_v1)
        self.held_v1 = None

    def close(self) -> None:
        WindowsHeldObjectApiV2.close(self.held_v1)
        WindowsHeldObjectApiV2.close(self.held_runs)
        WindowsHeldObjectApiV2.close(self.held_root)
        WindowsHeldObjectApiV2.close(self.held_parent)


def _read_kimi_v2_receipt(runtime_root: Path) -> dict[str, object] | None:
    if any(
        os.path.lexists(runtime_root / name)
        for name in (
            KIMI_V2_TRANSACTION_FILENAME,
            KIMI_V2_CANDIDATE_FILENAME,
            KIMI_V2_ROLLBACK_FILENAME,
            KIMI_V2_UPDATE_FILENAME,
        )
    ):
        raise ValueError("E_KIMI_V2_RECEIPT_STATE_INDETERMINATE")
    path = _kimi_binding_v2_path(runtime_root)
    if not os.path.lexists(path):
        return None
    try:
        validate_no_reparse_components(path)
        metadata = path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or _metadata_is_reparse(metadata)
            or metadata.st_size > 8192
        ):
            raise OSError("Kimi V2 receipt metadata")
        if os.name == "nt":
            WindowsPrivateObjectOwnerV1.verify_existing(path, directory=False)
        payload = path.read_bytes()
        data = json.loads(
            payload.decode("utf-8", errors="strict"),
            object_pairs_hook=_kimi_json_no_duplicates_v2,
        )
        required = {
            "schema", "version", "filename", "path", "size", "sha256",
            "manifestSha256", "versionProbeSha256", "helpProbeSha256",
            "admittedAt", "maxObservedUtc", "offlinePolicy",
        }
        if type(data) is not dict or set(data) != required:
            raise ValueError("receipt shape")
        _kimi_version_tuple_v2(str(data["version"]))
        if (
            data["schema"] != KIMI_EXECUTABLE_BINDING_SCHEMA_V2
            or data["filename"] != "kimi-code-win32-x64.exe"
            or data["offlinePolicy"] not in KIMI_OFFLINE_DURATIONS_V2
            or not isinstance(data["size"], int)
            or not 0 < data["size"] <= KIMI_EXECUTABLE_MAX_BYTES_V2
            or any(
                re.fullmatch(r"[a-f0-9]{64}", str(data[key]), re.ASCII) is None
                for key in (
                    "sha256", "manifestSha256", "versionProbeSha256", "helpProbeSha256"
                )
            )
        ):
            raise ValueError("receipt values")
        admitted = datetime.fromisoformat(str(data["admittedAt"]).replace("Z", "+00:00"))
        maximum = datetime.fromisoformat(
            str(data["maxObservedUtc"]).replace("Z", "+00:00")
        )
        if admitted.tzinfo != timezone.utc or maximum.tzinfo != timezone.utc or maximum < admitted:
            raise ValueError("receipt time")
        return data
    except (OSError, TypeError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("E_KIMI_V2_RECEIPT_INVALID") from exc


class KimiReceiptTransactionV2:
    """Rollback-only fixed-path transaction for one private V2 receipt."""

    def __init__(self, runtime_root: Path, hook=None) -> None:
        self.root = runtime_root
        self.target = _kimi_binding_v2_path(runtime_root)
        self.record = runtime_root / KIMI_V2_TRANSACTION_FILENAME
        self.candidate = runtime_root / KIMI_V2_CANDIDATE_FILENAME
        self.rollback = runtime_root / KIMI_V2_ROLLBACK_FILENAME
        self.update = runtime_root / KIMI_V2_UPDATE_FILENAME
        self.hook = hook or (lambda _event: None)

    def _emit(self, event: str) -> None:
        self.hook(event)

    def _write_private(self, path: Path, payload: bytes) -> None:
        descriptor = os.open(
            path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
            0o600,
        )
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name == "nt":
            WindowsPrivateObjectOwnerV1.protect_and_verify(path, directory=False)

    def _record_payload(
        self, phase: str, prior: bytes | None, candidate: bytes
    ) -> bytes:
        target_identity = None
        if self.target.exists():
            stat_row = self.target.stat()
            target_identity = [stat_row.st_dev, stat_row.st_ino, stat_row.st_size, stat_row.st_mtime_ns]
        data = {
            "schema": "orchestrarium.kimi-receipt-transaction.v2",
            "version": 2,
            "priorPresent": prior is not None,
            "priorSize": len(prior) if prior is not None else 0,
            "priorSha256": hashlib.sha256(prior or b"").hexdigest(),
            "candidateSize": len(candidate),
            "candidateSha256": hashlib.sha256(candidate).hexdigest(),
            "capturedIdentity": target_identity,
            "phase": phase,
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode() + b"\n"

    def _cleanup(self, *, keep_record: bool = False) -> None:
        paths = (self.candidate, self.rollback, self.update) if keep_record else (
            self.candidate, self.rollback, self.update, self.record
        )
        for path in paths:
            path.unlink(missing_ok=True)

    def _prove_prior(self, prior: bytes | None) -> None:
        if prior is None:
            if os.path.lexists(self.target):
                raise OSError("target remains")
        elif not self.target.is_file() or self.target.read_bytes() != prior:
            raise OSError("prior receipt mismatch")

    def _rollback(self, prior: bytes | None) -> None:
        self._emit("rollback-start")
        if prior is None:
            self.target.unlink(missing_ok=True)
        else:
            if not self.rollback.is_file() or self.rollback.read_bytes() != prior:
                raise OSError("rollback anchor mismatch")
            os.replace(self.rollback, self.target)
            if os.name == "nt":
                WindowsPrivateObjectOwnerV1.verify_existing(self.target, directory=False)
        self._prove_prior(prior)
        self._cleanup()

    def _update_phase(self, phase: str, prior: bytes | None, candidate: bytes) -> None:
        if self.update.exists():
            old = json.loads(self.record.read_text(encoding="utf-8"))
            self._discard_valid_update(old)
        self._write_private(
            self.update, self._record_payload(phase, prior, candidate)
        )
        self._emit("after-phase-update-temp-" + phase)
        os.replace(self.update, self.record)
        if os.name == "nt":
            WindowsPrivateObjectOwnerV1.verify_existing(self.record, directory=False)

    def _discard_valid_update(self, durable: dict[str, object]) -> None:
        try:
            if os.name == "nt":
                WindowsPrivateObjectOwnerV1.verify_existing(
                    self.update, directory=False
                )
            payload = self.update.read_bytes()
            if len(payload) > 4096:
                raise OSError("update record too large")
            update = json.loads(payload.decode("utf-8"))
            canonical = json.dumps(
                update, sort_keys=True, separators=(",", ":")
            ).encode() + b"\n"
            transitions = {
                "PREPARED_ROLLBACK": "COMMIT_DECIDED",
                "COMMIT_DECIDED": "SETTLED_COMMITTED",
            }
            if (
                type(update) is not dict
                or payload != canonical
                or transitions.get(str(durable.get("phase"))) != update.get("phase")
                or any(
                    update.get(key) != value
                    for key, value in durable.items()
                    if key not in {"phase", "capturedIdentity"}
                )
                or set(update) != set(durable)
            ):
                raise OSError("update record inconsistent")
            current = self.target.stat()
            if update.get("capturedIdentity") != [
                current.st_dev,
                current.st_ino,
                current.st_size,
                current.st_mtime_ns,
            ]:
                raise OSError("update target identity inconsistent")
            self.update.unlink()
            if os.path.lexists(self.update):
                raise OSError("update record remains")
        except Exception as exc:
            raise ValueError("E_KIMI_V2_RECEIPT_STATE_INDETERMINATE") from exc

    def _validate_candidate_target(self, data: dict[str, object]) -> None:
        if (
            not self.target.is_file()
            or self.target.stat().st_size != data["candidateSize"]
            or hashlib.sha256(self.target.read_bytes()).hexdigest()
            != data["candidateSha256"]
        ):
            raise OSError("candidate target mismatch")
        if os.name == "nt":
            WindowsPrivateObjectOwnerV1.verify_existing(self.target, directory=False)

    def _forward_settle(
        self, data: dict[str, object], prior: bytes | None, candidate: bytes
    ) -> None:
        self._validate_candidate_target(data)
        self.rollback.unlink(missing_ok=True)
        if os.path.lexists(self.rollback):
            raise OSError("rollback anchor remains")
        self._update_phase("SETTLED_COMMITTED", prior, candidate)
        self.candidate.unlink(missing_ok=True)
        self.record.unlink()
        if any(
            os.path.lexists(path)
            for path in (self.candidate, self.rollback, self.update, self.record)
        ):
            raise OSError("transaction residue")

    def recover_if_needed(self) -> None:
        artifacts = tuple(
            path
            for path in (self.record, self.candidate, self.rollback, self.update)
            if os.path.lexists(path)
        )
        if not artifacts:
            return
        try:
            if not self.record.is_file():
                raise OSError("transaction record missing")
            data = json.loads(self.record.read_text(encoding="utf-8"))
            required = {
                "schema", "version", "priorPresent", "priorSize", "priorSha256",
                "candidateSize", "candidateSha256", "capturedIdentity", "phase",
            }
            if (
                type(data) is not dict
                or set(data) != required
                or data.get("schema") != "orchestrarium.kimi-receipt-transaction.v2"
                or data.get("version") != 2
                or data.get("phase") not in {
                    "PREPARED_ROLLBACK", "COMMIT_DECIDED", "SETTLED_COMMITTED"
                }
                or not isinstance(data.get("priorPresent"), bool)
                or not isinstance(data.get("priorSize"), int)
                or not isinstance(data.get("candidateSize"), int)
            ):
                raise OSError("transaction record invalid")
            if self.update.exists():
                self._discard_valid_update(data)
            prior = self.rollback.read_bytes() if self.rollback.is_file() else None
            if prior is not None and (
                len(prior) != data["priorSize"]
                or hashlib.sha256(prior).hexdigest() != data["priorSha256"]
            ):
                raise OSError("rollback anchor invalid")
            phase = data["phase"]
            if phase == "PREPARED_ROLLBACK":
                target_bytes = self.target.read_bytes() if self.target.is_file() else None
                target_is_candidate = (
                    target_bytes is not None
                    and len(target_bytes) == data["candidateSize"]
                    and hashlib.sha256(target_bytes).hexdigest()
                    == data["candidateSha256"]
                )
                target_is_prior = (
                    data["priorPresent"]
                    and target_bytes is not None
                    and len(target_bytes) == data["priorSize"]
                    and hashlib.sha256(target_bytes).hexdigest() == data["priorSha256"]
                )
                if target_is_candidate:
                    if data["priorPresent"] and prior is None:
                        raise OSError("rollback anchor missing")
                    self._rollback(prior)
                elif target_is_prior or (
                    not data["priorPresent"] and target_bytes is None
                ):
                    self._cleanup()
                else:
                    raise OSError("prepared transaction target mismatch")
            elif phase == "COMMIT_DECIDED":
                candidate = self.target.read_bytes()
                self._forward_settle(data, prior, candidate)
            else:
                self._validate_candidate_target(data)
                self._cleanup()
        except Exception as exc:
            raise ValueError("E_KIMI_V2_RECEIPT_STATE_INDETERMINATE") from exc

    def commit(self, payload: bytes) -> None:
        self.recover_if_needed()
        prior = self.target.read_bytes() if self.target.exists() else None
        switched = False
        decided = False
        try:
            self._write_private(
                self.record,
                self._record_payload("PREPARED_ROLLBACK", prior, payload),
            )
            self._emit("after-op-2")
            if prior is not None:
                self._write_private(self.rollback, prior)
            self._emit("after-op-3")
            self._write_private(self.candidate, payload)
            self._emit("after-op-4")
            if self.candidate.read_bytes() != payload:
                raise OSError("candidate validation")
            self._emit("after-op-5")
            os.replace(self.candidate, self.target)
            switched = True
            self._emit("after-op-6")
            self._emit("after-switch")
            if os.name == "nt":
                WindowsPrivateObjectOwnerV1.protect_and_verify(self.target, directory=False)
            self._emit("after-target-protect")
            if self.target.read_bytes() != payload:
                raise OSError("candidate readback mismatch")
            self._emit("after-target-readback")
            self._emit("after-op-7")
            self._update_phase("COMMIT_DECIDED", prior, payload)
            decided = True
            self._emit("after-op-8")
            self._emit("before-cleanup")
            self.rollback.unlink(missing_ok=True)
            self._emit("after-op-9")
            self._update_phase("SETTLED_COMMITTED", prior, payload)
            self._emit("after-op-10")
            self.candidate.unlink(missing_ok=True)
            self.record.unlink()
            self._emit("after-op-11")
            if any(
                os.path.lexists(path)
                for path in (self.candidate, self.rollback, self.update, self.record)
            ):
                raise OSError("transaction residue")
            self._emit("after-op-12")
        except Exception as exc:
            try:
                if decided:
                    data = json.loads(self.record.read_text(encoding="utf-8"))
                    self._forward_settle(data, prior, payload)
                    return
                elif switched:
                    self._rollback(prior)
                else:
                    self._cleanup()
                    self._prove_prior(prior)
            except Exception as rollback_exc:
                raise ValueError("E_KIMI_V2_RECEIPT_STATE_INDETERMINATE") from rollback_exc
            raise ValueError("E_KIMI_V2_RECEIPT_WRITE_FAILED") from exc


def _write_kimi_v2_receipt(
    runtime_root: Path, data: dict[str, object], *, transaction_hook=None
) -> None:
    _ensure_kimi_private_root_v2(runtime_root, create=True)
    payload = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    KimiReceiptTransactionV2(runtime_root, transaction_hook).commit(payload)


def _admit_kimi_executable_v2_locked(
    home: Path,
    runtime_root: Path,
    *,
    fetcher=None,
    probe_runner=None,
    now_utc: datetime | None = None,
    offline_policy: str | None = None,
    dry_run: bool,
    transaction_hook=None,
    checkpoint_before_publish=None,
    checkpoint_after_publish=None,
) -> ExecutableBindingV1:
    """Admit the fixed installed Kimi object from live Moonshot evidence or V2 cache."""

    fetcher = fetcher or _fetch_kimi_https_once_v2
    probe_runner = probe_runner or _default_kimi_probe_runner_v2
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo != timezone.utc:
        raise ValueError("E_KIMI_CLOCK_INVALID")
    executable = _fixed_kimi_executable(home)
    previous = _read_kimi_v2_receipt(runtime_root)
    if previous is not None:
        previous_admitted = datetime.fromisoformat(
            str(previous["admittedAt"]).replace("Z", "+00:00")
        )
        previous_maximum = datetime.fromisoformat(
            str(previous["maxObservedUtc"]).replace("Z", "+00:00")
        )
        if now < previous_maximum:
            raise ValueError("E_KIMI_CLOCK_ROLLBACK")
    try:
        version, filename, checksum, manifest_hash = _live_kimi_manifest_v2(fetcher)
        online = True
    except KimiOfficialChannelUnavailableV2:
        online = False
    if not online:
        if previous is None:
            raise ValueError("E_KIMI_LIVE_EVIDENCE_REQUIRED")
        policy = str(previous["offlinePolicy"])
        if offline_policy is not None and offline_policy != policy:
            raise ValueError("E_KIMI_OFFLINE_POLICY_INVALID")
        if policy == "disabled":
            raise ValueError("E_KIMI_LIVE_EVIDENCE_REQUIRED")
        admitted = previous_admitted
        if now - admitted > KIMI_OFFLINE_DURATIONS_V2[policy]:
            raise ValueError("E_KIMI_OFFLINE_EXPIRED")
        binding = _observe_kimi_executable_v2(executable)
        if (
            previous["path"] != binding.path
            or previous["size"] != binding.size
            or not secrets.compare_digest(str(previous["sha256"]), binding.sha256)
        ):
            raise ValueError("E_KIMI_EXECUTABLE_IDENTITY_INVALID")
        version_probe, help_probe = _probe_kimi_executable_v2(
            executable,
            None if dry_run else runtime_root,
            binding,
            str(previous["version"]),
            probe_runner,
        )
        if (
            not secrets.compare_digest(
                str(previous["versionProbeSha256"]), version_probe
            )
            or not secrets.compare_digest(str(previous["helpProbeSha256"]), help_probe)
        ):
            raise ValueError("E_KIMI_PROBE_INVALID")
        if not dry_run:
            advanced = dict(previous)
            advanced["maxObservedUtc"] = now.isoformat(timespec="seconds").replace(
                "+00:00", "Z"
            )
            if checkpoint_before_publish is not None:
                checkpoint_before_publish()
            _write_kimi_v2_receipt(
                runtime_root, advanced, transaction_hook=transaction_hook
            )
            if checkpoint_after_publish is not None:
                checkpoint_after_publish()
        return binding

    assert online
    selected_policy = offline_policy or (
        str(previous["offlinePolicy"]) if previous is not None else "disabled"
    )
    if selected_policy not in KIMI_OFFLINE_DURATIONS_V2:
        raise ValueError("E_KIMI_OFFLINE_POLICY_INVALID")
    if previous is not None:
        previous_version = _kimi_version_tuple_v2(str(previous["version"]))
        candidate_version = _kimi_version_tuple_v2(version)
        if candidate_version < previous_version:
            raise ValueError("E_KIMI_ADMISSION_DOWNGRADE")
    binding = _observe_kimi_executable_v2(executable)
    if not secrets.compare_digest(binding.sha256, checksum):
        raise ValueError("E_KIMI_EXECUTABLE_IDENTITY_INVALID")
    version_probe, help_probe = _probe_kimi_executable_v2(
        executable,
        None if dry_run else runtime_root,
        binding,
        version,
        probe_runner,
    )
    receipt: dict[str, object] = {
        "schema": KIMI_EXECUTABLE_BINDING_SCHEMA_V2,
        "version": version,
        "filename": filename,
        "path": binding.path,
        "size": binding.size,
        "sha256": binding.sha256,
        "manifestSha256": manifest_hash,
        "versionProbeSha256": version_probe,
        "helpProbeSha256": help_probe,
        "admittedAt": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "maxObservedUtc": now.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "offlinePolicy": selected_policy,
    }
    if previous is not None and _kimi_version_tuple_v2(version) == _kimi_version_tuple_v2(
        str(previous["version"])
    ):
        identity_keys = (
            "version", "filename", "path", "size", "sha256", "manifestSha256",
            "versionProbeSha256", "helpProbeSha256",
        )
        if any(previous[key] != receipt[key] for key in identity_keys):
            raise ValueError("E_KIMI_ADMISSION_EQUIVOCATION")
    if not dry_run:
        if checkpoint_before_publish is not None:
            checkpoint_before_publish()
        _write_kimi_v2_receipt(
            runtime_root, receipt, transaction_hook=transaction_hook
        )
        if checkpoint_after_publish is not None:
            checkpoint_after_publish()
    return binding


def admit_kimi_executable_v2(
    home: Path,
    runtime_root: Path,
    *,
    fetcher=None,
    probe_runner=None,
    now_utc: datetime | None = None,
    offline_policy: str | None = None,
    dry_run: bool,
    _transaction_hook=None,
    _hardening_hook=None,
    _reclaim_hook=None,
) -> ExecutableBindingV1:
    """Serialize V2 high-water decisions and remove only the lock this call owns."""

    if os.name != "nt":
        raise ValueError("E_KIMI_WINDOWS_ONLY")
    executable = _fixed_kimi_executable(home)
    if dry_run:
        if runtime_root.exists():
            _ensure_kimi_private_root_v2(runtime_root, create=False)
        v1_snapshot = _classify_kimi_v1_state_v2(runtime_root, executable)
        return _admit_kimi_executable_v2_locked(
            home,
            runtime_root,
            fetcher=fetcher,
            probe_runner=probe_runner,
            now_utc=now_utc,
            offline_policy=offline_policy,
            dry_run=True,
            transaction_hook=_transaction_hook,
        )
    if runtime_root.exists():
        validate_no_reparse_components(runtime_root)
        root_metadata = runtime_root.lstat()
        if not stat.S_ISDIR(root_metadata.st_mode) or _metadata_is_reparse(root_metadata):
            raise ValueError("E_KIMI_PRIVATE_STATE_INVALID")
    else:
        _ensure_kimi_private_root_v2(runtime_root, create=True)
    lock = runtime_root / KIMI_EXECUTABLE_ADMISSION_LOCK_FILENAME_V2
    admission_lock: KimiAdmissionLockV2 | None = None
    state_owner: KimiAdmissionStateOwnerV2 | None = None
    try:
        admission_lock = KimiAdmissionLockV2.acquire(runtime_root, create=True)
        if admission_lock is None:
            raise ValueError("E_KIMI_PRIVATE_STATE_INVALID")
        state_owner = KimiAdmissionStateOwnerV2(
            runtime_root, executable, admission_lock, _hardening_hook
        )
        v1_snapshot = state_owner.prepare_write()
        state_owner.checkpoint(expect_v1=v1_snapshot is not None)
        result = _admit_kimi_executable_v2_locked(
            home,
            runtime_root,
            fetcher=fetcher,
            probe_runner=probe_runner,
            now_utc=now_utc,
            offline_policy=offline_policy,
            dry_run=False,
            transaction_hook=_transaction_hook,
            checkpoint_before_publish=lambda: state_owner.checkpoint(
                expect_v1=v1_snapshot is not None
            ),
            checkpoint_after_publish=lambda: state_owner.checkpoint(
                expect_v1=v1_snapshot is not None
            ),
        )
        if v1_snapshot is not None:
            state_owner.release_v1_for_reclaim()
            _reclaim_kimi_v1_after_v2_v2(
                v1_snapshot,
                runtime_root,
                result,
                reclaim_hook=_reclaim_hook,
            )
        state_owner.checkpoint(expect_v1=False)
        return result
    finally:
        if state_owner is not None:
            state_owner.close()
        if admission_lock is not None:
            admission_lock.close()


def _kimi_runtime_root() -> Path:
    """Return the fixed global Codex state owner; never use ambient temp."""

    home = Path(os.environ.get("USERPROFILE") or Path.home())
    if not home.is_absolute():
        raise ValueError("E_KIMI_RUNTIME_STATE_INVALID")
    root = Path(os.path.abspath(home / ".codex" / "orchestrarium-runtime" / "kimi"))
    validate_no_reparse_components(root)
    return root


def _kimi_user_home() -> Path:
    home = Path(os.environ.get("USERPROFILE") or Path.home())
    if not home.is_absolute():
        raise ValueError("E_KIMI_RUNTIME_STATE_INVALID")
    return Path(os.path.abspath(home))


def _kimi_enrollment_command() -> str:
    wrapper = Path(__file__).with_name("invoke-kimi-prompt.py").resolve()
    return subprocess.list2cmdline(
        [sys.executable, str(wrapper), "--enroll-executable"]
    )


def _fixed_kimi_executable(home: Path) -> Path:
    absolute_home = Path(os.path.abspath(home))
    if not home.is_absolute() or absolute_home != home:
        raise ValueError("E_KIMI_ENROLLMENT_INVALID: fixed executable path")
    return absolute_home / ".kimi-code" / "bin" / "kimi.exe"


def enroll_kimi_executable(
    home: Path,
    runtime_root: Path,
    *,
    dry_run: bool,
    offline_policy: str | None = None,
) -> None:
    """Create or refresh the update-resilient V2 admission from live evidence."""

    admit_kimi_executable_v2(
        home,
        runtime_root,
        offline_policy=offline_policy,
        dry_run=dry_run,
    )


def replace_kimi_enrollment(
    home: Path,
    runtime_root: Path,
    *,
    dry_run: bool,
    offline_policy: str | None = None,
) -> None:
    """Compatibility alias for a live V2 refresh; no release pin rotation exists."""

    enroll_kimi_executable(
        home,
        runtime_root,
        dry_run=dry_run,
        offline_policy=offline_policy,
    )


def _resolve_enrolled_kimi_launch() -> tuple[list[str], ExecutableBindingV1]:
    try:
        fixed_path = _fixed_kimi_executable(_kimi_user_home())
        binding = admit_kimi_executable_v2(
            _kimi_user_home(),
            _kimi_runtime_root(),
            dry_run=False,
        )
        return [str(fixed_path)], binding
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise ValueError(
            "E_KIMI_EXECUTABLE_BINDING_INVALID: run " + _kimi_enrollment_command()
        ) from exc


def resolve_enrolled_kimi_command() -> list[str]:
    command, _binding = _resolve_enrolled_kimi_launch()
    return command


def _verify_kimi_executable_v2_under_lock(
    home: Path,
    runtime_root: Path,
    *,
    probe_runner=None,
) -> ExecutableBindingV1:
    """Verify one existing V2 receipt without network, persistence, or high-water advance."""

    probe_runner = probe_runner or _default_kimi_probe_runner_v2
    if any(
        os.path.lexists(runtime_root / name)
        for name in (
            KIMI_V2_TRANSACTION_FILENAME,
            KIMI_V2_CANDIDATE_FILENAME,
            KIMI_V2_ROLLBACK_FILENAME,
            KIMI_V2_UPDATE_FILENAME,
        )
    ):
        raise ValueError("E_KIMI_V2_RECEIPT_STATE_INDETERMINATE")
    if not _kimi_binding_v2_path(runtime_root).is_file():
        raise ValueError("E_KIMI_V2_RECEIPT_INVALID")
    _ensure_kimi_private_root_v2(runtime_root, create=False)
    receipt = _read_kimi_v2_receipt(runtime_root)
    if receipt is None:
        raise ValueError("E_KIMI_V2_RECEIPT_INVALID")
    executable = _fixed_kimi_executable(home)
    binding = _observe_kimi_executable_v2(executable)
    if (
        receipt["path"] != binding.path
        or receipt["size"] != binding.size
        or not secrets.compare_digest(str(receipt["sha256"]), binding.sha256)
    ):
        raise ValueError("E_KIMI_EXECUTABLE_IDENTITY_INVALID")
    version_probe, help_probe = _probe_kimi_executable_v2(
        executable,
        None,
        binding,
        str(receipt["version"]),
        probe_runner,
    )
    if (
        not secrets.compare_digest(
            str(receipt["versionProbeSha256"]), version_probe
        )
        or not secrets.compare_digest(str(receipt["helpProbeSha256"]), help_probe)
    ):
        raise ValueError("E_KIMI_PROBE_INVALID")
    return binding


def verify_kimi_executable_v2(
    home: Path,
    runtime_root: Path,
    *,
    probe_runner=None,
) -> ExecutableBindingV1:
    if os.name != "nt":
        raise ValueError("E_KIMI_WINDOWS_ONLY")
    if not _kimi_binding_v2_path(runtime_root).is_file():
        raise ValueError("E_KIMI_V2_RECEIPT_INVALID")
    admission_lock = KimiAdmissionLockV2.acquire(runtime_root, create=False)
    if admission_lock is None:
        raise ValueError("E_KIMI_ADMISSION_LOCK_MISSING")
    try:
        return _verify_kimi_executable_v2_under_lock(
            home, runtime_root, probe_runner=probe_runner
        )
    finally:
        admission_lock.close()


def verify_kimi_enrollment() -> list[str]:
    home = _kimi_user_home()
    fixed_path = _fixed_kimi_executable(home)
    verify_kimi_executable_v2(
        home,
        _kimi_runtime_root(),
    )
    return [str(fixed_path)]



def _truthy(value: str | None) -> bool:
    return bool(value and value.lower() in {"1", "true", "yes"})


def _read_settings_object(path: Path, label: str) -> dict[str, object]:
    """Read one bounded ordinary settings file through an identity-bound handle."""

    try:
        candidate = Path(os.path.abspath(path))
        validate_no_reparse_components(candidate)
        before = candidate.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or _metadata_is_reparse(before)
        ):
            raise ValueError("settings file type")
        descriptor = os.open(
            candidate,
            os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino, opened.st_mode) != (
                before.st_dev,
                before.st_ino,
                before.st_mode,
            ):
                raise ValueError("settings identity changed")
            raw = stream.read(SETTINGS_SNAPSHOT_MAX_BYTES + 1)
    except (OSError, ValueError) as exc:
        raise ValueError(
            f"E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE: {label}"
        ) from exc
    if len(raw) > SETTINGS_SNAPSHOT_MAX_BYTES:
        raise ValueError(
            f"E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE: {label}"
        )
    try:
        parsed = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE: {label}"
        ) from exc
    if not isinstance(parsed, dict):
        raise ValueError(
            f"E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE: {label}"
        )
    return parsed


def _claude_user_settings_surface(
    environment: dict[str, str],
) -> ClaudeUserSettingsSurface:
    configured = environment.get("CLAUDE_CONFIG_DIR")
    if configured:
        user_root = Path(configured)
        forwarded = configured
    else:
        home_key = "USERPROFILE" if _claude_settings_os_name() == "nt" else "HOME"
        home = environment.get(home_key)
        user_root = Path(home) if home else Path("")
        forwarded = None
    try:
        if not user_root.is_absolute():
            raise ValueError("relative")
        validate_no_reparse_components(user_root)
        metadata = user_root.lstat()
        if not stat.S_ISDIR(metadata.st_mode) or _metadata_is_reparse(metadata):
            raise ValueError("type")
    except (OSError, ValueError) as exc:
        raise ValueError(
            "E_EXTERNAL_PROVIDER_CLAUDE_SETTINGS_SURFACE_UNAVAILABLE"
        ) from exc
    settings_root = user_root if configured else user_root / ".claude"
    if os.path.lexists(settings_root):
        try:
            validate_no_reparse_components(settings_root)
            settings_metadata = settings_root.lstat()
            if not stat.S_ISDIR(settings_metadata.st_mode) or _metadata_is_reparse(
                settings_metadata
            ):
                raise ValueError("settings root type")
        except (OSError, ValueError) as exc:
            raise ValueError(
                "E_EXTERNAL_PROVIDER_CLAUDE_SETTINGS_SURFACE_UNAVAILABLE"
            ) from exc
    return ClaudeUserSettingsSurface(
        user_root, settings_root / "settings.json", forwarded
    )


def _claude_settings_os_name() -> str:
    return os.name


def _refuse_api_key_helper(surface: ClaudeUserSettingsSurface) -> None:
    """Reject the selected user helper without executing or interpreting it."""

    if not os.path.lexists(surface.settings_path):
        return
    settings = _read_settings_object(surface.settings_path, "user settings")
    if "apiKeyHelper" not in settings:
        return
    raise ValueError("E_EXTERNAL_PROVIDER_API_KEY_HELPER_UNSUPPORTED")


def _child_environment_baseline(environment: dict[str, str]) -> dict[str, str]:
    return {
        name: value
        for name in _NONSECRET_CHILD_ENV_NAMES
        if (value := environment.get(name))
    }


def _copy_provider_path_control(
    child: dict[str, str], source: dict[str, str], name: str, expected: str
) -> None:
    value = source.get(name)
    if not value:
        return
    path = Path(value)
    try:
        if not path.is_absolute():
            raise ValueError("relative")
        validate_no_reparse_components(path)
        metadata = path.lstat()
        expected_type = stat.S_ISREG if expected == "file" else stat.S_ISDIR
        if not expected_type(metadata.st_mode) or _metadata_is_reparse(metadata):
            raise ValueError("type")
        if expected == "file":
            descriptor = os.open(
                path,
                os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0),
            )
            try:
                opened = os.fstat(descriptor)
                if (opened.st_dev, opened.st_ino, opened.st_mode) != (
                    metadata.st_dev,
                    metadata.st_ino,
                    metadata.st_mode,
                ):
                    raise ValueError("identity")
            finally:
                os.close(descriptor)
    except (OSError, ValueError) as exc:
        raise ValueError(
            "E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE: path control"
        ) from exc
    child[name] = value


def resolve_provider_auth_configuration(
    provider: str, environment: dict[str, str] | None = None
) -> ProviderAuthConfiguration:
    """Build the complete child auth surface and its exact raw-byte detector."""

    source = dict(os.environ if environment is None else environment)
    child = _child_environment_baseline(source)
    if provider == "codex":
        if source.get("OPENAI_API_KEY"):
            configured_home = source.get("CODEX_HOME")
            codex_home: Path | None = None
            if configured_home:
                codex_home = Path(configured_home).expanduser()
            elif environment is None:
                codex_home = Path.home() / ".codex"
            if codex_home is not None and os.path.lexists(codex_home / "auth.json"):
                raise ValueError(
                    "E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE: mixed Codex API-key and auth-file credentials"
                )
        mode = "codex-api-key" if source.get("OPENAI_API_KEY") else "codex-auth-file"
    elif provider == "claude":
        selected = []
        if _truthy(source.get("CLAUDE_CODE_USE_BEDROCK")):
            selected.append("claude-bedrock")
        if _truthy(source.get("CLAUDE_CODE_USE_VERTEX")):
            selected.append("claude-vertex")
        if source.get("ANTHROPIC_API_KEY") or source.get("ANTHROPIC_AUTH_TOKEN"):
            selected.append("claude-direct")
        if source.get("ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE") == "1":
            selected.append("claude-subscription-override")
        if not selected:
            user_settings_surface = _claude_user_settings_surface(source)
            _refuse_api_key_helper(user_settings_surface)
            raise ClaudeSubscriptionRefusal("subscription-only Claude authentication")
        if len(selected) != 1:
            raise ValueError("E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE: auth mode")
        mode = selected[0]
        user_settings_surface = (
            _claude_user_settings_surface(source)
            if source.get("CLAUDE_CONFIG_DIR")
            else None
        )
        controls = PROVIDER_AUTH_CONTROL_ENV_KEYS_V1[mode]
        selector = controls["selector"]
        if selector is not None:
            child[selector] = "true"
        for name in controls["scalar"]:
            if (value := source.get(name)):
                child[name] = value
        for name in controls["file"]:
            _copy_provider_path_control(child, source, name, "file")
        for name in controls["directory"]:
            _copy_provider_path_control(child, source, name, "directory")
        if (
            user_settings_surface is not None
            and user_settings_surface.forwarded_config_dir is not None
        ):
            child["CLAUDE_CONFIG_DIR"] = user_settings_surface.forwarded_config_dir
    elif provider == "kimi":
        child.update(
            {
                "KIMI_CODE_EXPERIMENTAL_FLAG": "1",
                "KIMI_CODE_NO_AUTO_UPDATE": "1",
                "DO_NOT_TRACK": "1",
            }
        )
        return ProviderAuthConfiguration(
            "kimi-user-session",
            child,
            (),
            AUTH_OUTPUT_SCAN_OPAQUE_PROVIDER_SESSION,
        )
    else:
        raise ValueError("E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE: provider")

    credential_keys = PROVIDER_AUTH_SECRET_ENV_KEYS_V1.get(mode)
    if credential_keys is None:
        raise ValueError("E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE: registry")
    needles: list[bytes] = []
    for key in credential_keys:
        value = source.get(key, "")
        if not value:
            continue
        try:
            needle = value.encode("ascii", errors="strict")
        except UnicodeEncodeError as exc:
            raise ValueError(
                "E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE: non-ASCII credential"
            ) from exc
        if b"\x00" in needle:
            raise ValueError(
                "E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE: NUL credential"
            )
        child[key] = value
        if needle not in needles:
            needles.append(needle)
    if {key for key in credential_keys if source.get(key)} != {
        key for key in credential_keys if key in child
    }:
        raise ValueError("E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE: child environment")
    disposition = (
        AUTH_OUTPUT_SCAN_CREDENTIAL_FILE_UNSCANNABLE
        if mode == "codex-auth-file"
        or mode in {"claude-bedrock", "claude-vertex"}
        or not needles
        else AUTH_OUTPUT_SCAN_ENVIRONMENT_EXACT
    )
    return ProviderAuthConfiguration(mode, child, tuple(needles), disposition)


def claude_commercial_auth_present() -> bool:
    try:
        resolve_provider_auth_configuration("claude")
    except ClaudeSubscriptionRefusal:
        return False
    return True


def _metadata_is_reparse(metadata: os.stat_result) -> bool:
    attributes = getattr(metadata, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def reject_link(path: Path) -> None:
    metadata = path.lstat()
    if (
        stat.S_ISLNK(metadata.st_mode)
        or _metadata_is_reparse(metadata)
        or (hasattr(os.path, "isjunction") and os.path.isjunction(path))
    ):
        raise ValueError(f"'{path}' is a symlink/junction/reparse point; refusing to follow")


def validate_no_reparse_components(path: Path) -> None:
    if not path.is_absolute():
        raise ValueError(f"capture root '{path}' must be absolute")
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        current /= part
        if os.path.lexists(current):
            reject_link(current)


def secure_output_dir(provider: str) -> Path:
    if provider == "kimi":
        root = _kimi_runtime_root() / "runs"
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        validate_no_reparse_components(root)
        if not root.is_dir():
            raise ValueError("E_KIMI_RUNTIME_STATE_INVALID")
        return root
    env_key = {
        "codex": "CODEX_PROMPTS_DIR",
        "claude": "CLAUDE_PROMPTS_DIR",
    }.get(provider, "PROVIDER_PROMPTS_DIR")
    configured = os.environ.get(env_key)
    if configured:
        output = Path(configured).expanduser()
        if not output.is_absolute():
            raise ValueError(f"{env_key} must name an absolute owner-controlled directory")
    else:
        output = Path.cwd() / ".scratch" / f"{provider}-prompts"
    output = Path(os.path.abspath(output))
    validate_no_reparse_components(output)
    output.mkdir(mode=0o700, parents=True, exist_ok=True)
    validate_no_reparse_components(output)
    if not output.is_dir():
        raise ValueError(f"capture root '{output}' is not a directory")
    if configured and sys.platform != "win32":
        metadata = output.lstat()
        if (
            metadata.st_uid != os.geteuid()
            or stat.S_IMODE(metadata.st_mode) & (stat.S_IWGRP | stat.S_IWOTH)
        ):
            raise ValueError(
                f"{env_key} configured capture root must be owner-controlled"
            )
    return output


KIMI_AGENT_BUNDLE_PREAMBLE = (
    b"The sealed bundle below contains the exact task.\n\nBEGIN SEALED BUNDLE\n"
)
KIMI_AGENT_BUNDLE_EPILOGUE = b"\nEND SEALED BUNDLE\n"


def prepare_kimi_agent_payload(body: bytes) -> bytes:
    """Validate and compose the complete Kimi agent before any launch side effect."""
    if b"${" in body:
        raise ValueError("E_KIMI_BUNDLE_TEMPLATE_INVALID")
    task = _bounded_strict_utf8_snapshot(body, "Kimi bundle")
    return (
        KimiWindowsProfileV1.agent_frontmatter
        + KIMI_AGENT_BUNDLE_PREAMBLE
        + task
        + KIMI_AGENT_BUNDLE_EPILOGUE
        + KIMI_AGENT_TERMINAL_INSTRUCTION
    )


def materialize_kimi_agent_payload(payload: bytes, run_dir: Path) -> tuple[Path, Path]:
    """Materialize one already-validated no-tools, no-subagent Kimi agent."""
    agent = run_dir / "kimi-agent.md"
    skills = run_dir / "kimi-empty-skills"
    skills.mkdir(mode=0o700)
    agent.write_bytes(payload)
    return agent, skills


def _bounded_strict_utf8_snapshot(data: bytes, label: str) -> bytes:
    if len(data) > PROMPT_SNAPSHOT_MAX_BYTES:
        raise ValueError(f"E_EXTERNAL_PROMPT_INVALID: {label} exceeds the byte limit")
    try:
        data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError(f"E_EXTERNAL_PROMPT_INVALID: {label} is not UTF-8") from exc
    return data


def _external_prompt_file_snapshot(path: Path) -> bytes:
    candidate = Path(os.path.abspath(path))
    try:
        validate_no_reparse_components(candidate)
        before = candidate.lstat()
    except OSError as exc:
        raise ValueError("E_EXTERNAL_PROMPT_INVALID: prompt file is unavailable") from exc
    if not stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode) or _metadata_is_reparse(before):
        raise ValueError("E_EXTERNAL_PROMPT_INVALID: prompt file type")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(candidate, flags)
        with os.fdopen(descriptor, "rb") as stream:
            pre_read = os.fstat(stream.fileno())
            if (pre_read.st_dev, pre_read.st_ino) != (before.st_dev, before.st_ino):
                raise ValueError("E_EXTERNAL_PROMPT_INVALID: prompt identity changed")
            data = stream.read(PROMPT_SNAPSHOT_MAX_BYTES + 1)
            post_read = os.fstat(stream.fileno())
            post_path = candidate.lstat()
            stable_fields = (
                "st_dev",
                "st_ino",
                "st_size",
                "st_mtime_ns",
                "st_ctime_ns",
            )
            if tuple(getattr(pre_read, name) for name in stable_fields) != tuple(
                getattr(post_read, name) for name in stable_fields
            ) or tuple(getattr(before, name) for name in stable_fields) != tuple(
                getattr(post_path, name) for name in stable_fields
            ):
                raise ValueError("E_EXTERNAL_PROMPT_INVALID: prompt metadata changed")
    except OSError as exc:
        raise ValueError("E_EXTERNAL_PROMPT_INVALID: prompt read") from exc
    if len(data) > PROMPT_SNAPSHOT_MAX_BYTES:
        raise ValueError("E_EXTERNAL_PROMPT_INVALID: prompt file exceeds the byte limit")
    return _bounded_strict_utf8_snapshot(data, "prompt file")


def external_governance_capsule_path() -> Path:
    """Resolve the manifest-authorized authored or packed capsule view."""

    script = Path(__file__).resolve()
    source_root = script.parent.parent
    source_view = (
        script == source_root / "scripts" / "provider_prompt.py"
        and (source_root / "AGENTS.md").is_file()
        and (source_root / "shared" / "AGENTS.shared.md").is_file()
    )
    if source_view:
        root = source_root
    else:
        candidates = tuple(
            root
            for root in (script.parent.parent, script.parent.parent.parent)
            if (root / "shared" / "provider-prompt-projections.v1.json").is_file()
        )
        if len(candidates) != 1:
            raise ValueError("E_EXTERNAL_PROMPT_GOVERNANCE_MISSING")
        root = candidates[0]
    manifest_path = root / "shared" / "provider-prompt-projections.v1.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        record = manifest["files"][EXTERNAL_GOVERNANCE_CAPSULE_NAME]
        source = Path(str(record["source"]))
        destination = Path(str(record["destination"]))
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("E_EXTERNAL_PROMPT_GOVERNANCE_MISSING") from exc
    if source != Path("shared") / EXTERNAL_GOVERNANCE_CAPSULE_NAME or destination != Path(
        "scripts"
    ) / EXTERNAL_GOVERNANCE_CAPSULE_NAME:
        raise ValueError("E_EXTERNAL_PROMPT_GOVERNANCE_MISSING")
    if source_view:
        authored = root / source
        if authored.is_file():
            return authored
        raise ValueError("E_EXTERNAL_PROMPT_GOVERNANCE_MISSING")
    packed = script.parent / destination.name
    if packed.is_file():
        return packed
    raise ValueError("E_EXTERNAL_PROMPT_GOVERNANCE_MISSING")


def external_governance_capsule_snapshot(path: Path | None = None) -> bytes:
    """Read exactly the generated capsule, failing closed on every trust-boundary error."""

    candidate = Path(os.path.abspath(path or external_governance_capsule_path()))
    try:
        validate_no_reparse_components(candidate)
        before = candidate.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or _metadata_is_reparse(before)
        ):
            raise OSError("capsule is not an ordinary file")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(candidate, flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise OSError("capsule identity changed")
            data = stream.read(PROMPT_SNAPSHOT_MAX_BYTES + 1)
    except (OSError, ValueError) as exc:
        raise ValueError("E_EXTERNAL_PROMPT_GOVERNANCE_MISSING") from exc
    if len(data) > PROMPT_SNAPSHOT_MAX_BYTES:
        raise ValueError("E_EXTERNAL_PROMPT_GOVERNANCE_MISSING")
    try:
        data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("E_EXTERNAL_PROMPT_GOVERNANCE_MISSING") from exc
    if hashlib.sha256(data).hexdigest() != EXTERNAL_GOVERNANCE_CAPSULE_SHA256:
        raise ValueError("E_EXTERNAL_PROMPT_GOVERNANCE_MISSING")
    return data


def assemble_external_prompt(task_bytes: bytes) -> bytes:
    """Prefix every task; task bytes are data and cannot suppress the trusted frame."""

    capsule_bytes = external_governance_capsule_snapshot()
    total = len(EXTERNAL_GOVERNANCE_BEGIN) + len(capsule_bytes) + len(EXTERNAL_GOVERNANCE_END) + len(task_bytes)
    if total > PROMPT_SNAPSHOT_MAX_BYTES:
        raise ValueError("E_EXTERNAL_PROMPT_INVALID: composed prompt exceeds the byte limit")
    return EXTERNAL_GOVERNANCE_BEGIN + capsule_bytes + EXTERNAL_GOVERNANCE_END + task_bytes


def prompt_bytes(control: Control, *, external: bool = False) -> bytes:
    if control.prompt_file is not None:
        if external:
            return _external_prompt_file_snapshot(control.prompt_file)
        if not control.prompt_file.is_file():
            raise ValueError(f"--prompt-file '{control.prompt_file}' does not exist")
        reject_link(control.prompt_file)
        return control.prompt_file.read_bytes()
    if sys.stdin.isatty():
        raise ValueError("no prompt provided (neither --prompt-file nor piped stdin)")
    data = sys.stdin.buffer.read(
        PROMPT_SNAPSHOT_MAX_BYTES + 1 if external else -1
    )
    return _bounded_strict_utf8_snapshot(data, "stdin") if external else data


@dataclass
class RunCaptureLifecycle:
    root: Path
    run_dir: Path
    device: int
    inode: int
    prompt_path: Path

    @staticmethod
    def release_provisional(run_dir: Path) -> CleanupResult:
        """Release only an empty not-yet-owned directory; never recurse here."""
        try:
            os.rmdir(run_dir)
            return CleanupResult(())
        except FileNotFoundError:
            return CleanupResult(())
        except OSError as exc:
            return CleanupResult((str(exc),), recovery_retained=True)

    @classmethod
    def create(cls, provider: str, slug: str) -> "RunCaptureLifecycle":
        root = secure_output_dir(provider)
        configured_root = provider != "kimi" and bool(
            os.environ.get(
                {"codex": "CODEX_PROMPTS_DIR", "claude": "CLAUDE_PROMPTS_DIR"}.get(
                    provider, "PROVIDER_PROMPTS_DIR"
                )
            )
        )
        root_before = root.lstat() if configured_root else None
        run_dir = Path(tempfile.mkdtemp(prefix=f"{slug}-", dir=root))
        try:
            if configured_root:
                root_after = root.lstat()
                if (root_after.st_dev, root_after.st_ino) != (
                    root_before.st_dev,
                    root_before.st_ino,
                ):
                    raise OSError("configured capture root identity changed")
            metadata = run_dir.lstat()
            if not stat.S_ISDIR(metadata.st_mode) or run_dir.parent != root:
                raise OSError("private capture directory creation escaped the configured root")
            run_dir.chmod(0o700)
            lifecycle = cls(
                root=root,
                run_dir=run_dir,
                device=metadata.st_dev,
                inode=metadata.st_ino,
                prompt_path=run_dir / "prompt.md",
            )
            lifecycle._validate_identity()
        except (OSError, ValueError) as exc:
            cleanup = cls.release_provisional(run_dir)
            recovery = "; secure recovery evidence retained" if not cleanup.clean else ""
            raise OSError(f"private capture directory hardening failed: {exc}{recovery}") from exc
        return lifecycle

    def _validate_child(self, path: Path) -> None:
        if path.parent != self.run_dir or path != self.prompt_path:
            raise ValueError("capture path is outside the fixed private run directory")

    def _validate_identity(self) -> None:
        validate_no_reparse_components(self.root)
        if self.run_dir.parent != self.root:
            raise OSError("capture directory parent changed")
        reject_link(self.run_dir)
        metadata = self.run_dir.lstat()
        if (
            not stat.S_ISDIR(metadata.st_mode)
            or metadata.st_dev != self.device
            or metadata.st_ino != self.inode
        ):
            raise OSError("capture directory ownership changed")

    def write_new(self, path: Path, data: bytes) -> None:
        self._validate_identity()
        self._validate_child(path)
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())

    def initialize(self, prompt: bytes) -> None:
        self.write_new(self.prompt_path, prompt)

    @staticmethod
    def _scan_no_reparse(root: Path) -> None:
        pending = [root]
        while pending:
            current = pending.pop()
            with os.scandir(current) as entries:
                for entry in entries:
                    metadata = entry.stat(follow_symlinks=False)
                    entry_path = Path(entry.path)
                    if (
                        stat.S_ISLNK(metadata.st_mode)
                        or _metadata_is_reparse(metadata)
                        or (hasattr(os.path, "isjunction") and os.path.isjunction(entry_path))
                    ):
                        raise OSError("capture tombstone contains a link/junction/reparse point")
                    if stat.S_ISDIR(metadata.st_mode):
                        pending.append(entry_path)

    @classmethod
    def _purge_tombstone(cls, root: Path) -> None:
        """Delete capture content without following a reparse point."""

        for entry in list(os.scandir(root)):
            path = Path(entry.path)
            metadata = entry.stat(follow_symlinks=False)
            if stat.S_ISLNK(metadata.st_mode) or _metadata_is_reparse(metadata):
                os.unlink(path)
            elif stat.S_ISDIR(metadata.st_mode):
                cls._purge_tombstone(path)
            else:
                os.unlink(path)
        os.rmdir(root)

    @staticmethod
    def _scrub_regular_payload(path: Path, expected: os.stat_result) -> None:
        """Overwrite then truncate one owned regular file without following links."""

        flags = os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino):
                raise OSError("capture payload identity changed")
            remaining = opened.st_size
            zeros = b"\0" * min(65536, max(1, remaining))
            os.lseek(descriptor, 0, os.SEEK_SET)
            while remaining:
                written = os.write(descriptor, zeros[: min(len(zeros), remaining)])
                if written <= 0:
                    raise OSError("capture payload overwrite failed")
                remaining -= written
            os.ftruncate(descriptor, 0)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @classmethod
    def _scrub_tombstone(cls, root: Path) -> tuple[str, ...]:
        """Best-effort all-file scrub; continue after every per-file failure."""

        issues: list[str] = []
        for entry in list(os.scandir(root)):
            path = Path(entry.path)
            try:
                metadata = entry.stat(follow_symlinks=False)
                if stat.S_ISLNK(metadata.st_mode) or _metadata_is_reparse(metadata):
                    raise OSError("capture scrub encountered link")
                if stat.S_ISDIR(metadata.st_mode):
                    issues.extend(cls._scrub_tombstone(path))
                elif stat.S_ISREG(metadata.st_mode):
                    cls._scrub_regular_payload(path, metadata)
                else:
                    raise OSError("capture scrub encountered non-regular entry")
            except OSError as exc:
                issues.append(type(exc).__name__)
        return tuple(issues)

    @staticmethod
    def _unlink_regular_payload(path: Path, expected: os.stat_result) -> None:
        """Unlink one owned payload only after a no-follow handle identity check."""

        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino) != (expected.st_dev, expected.st_ino):
                raise OSError("capture payload identity changed")
        finally:
            os.close(descriptor)
        os.unlink(path)

    @classmethod
    def _unlink_owned_payloads(cls, root: Path) -> tuple[str, ...]:
        """Attempt every owned payload unlink even when a sibling operation fails."""

        issues: list[str] = []
        for entry in list(os.scandir(root)):
            path = Path(entry.path)
            try:
                metadata = entry.stat(follow_symlinks=False)
                if stat.S_ISLNK(metadata.st_mode) or _metadata_is_reparse(metadata):
                    os.unlink(path)
                elif stat.S_ISDIR(metadata.st_mode):
                    issues.extend(cls._unlink_owned_payloads(path))
                    try:
                        os.rmdir(path)
                    except OSError:
                        issues.append("rmdir")
                elif stat.S_ISREG(metadata.st_mode):
                    cls._unlink_regular_payload(path, metadata)
                else:
                    issues.append("non-regular")
            except OSError:
                issues.append("unlink")
        return tuple(issues)

    def _write_redacted_recovery(self, issue: str) -> None:
        recovery = self.root / f".capture-recovery-{secrets.token_hex(16)}"
        os.mkdir(recovery, 0o700)
        record = json.dumps(
            {"schemaVersion": 1, "state": "cleanup-incomplete", "issue": issue[:64]},
            separators=(",", ":"),
        ).encode("utf-8")
        descriptor = os.open(recovery / "recovery.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(record)
            stream.flush()
            os.fsync(stream.fileno())

    def cleanup(self) -> CleanupResult:
        tombstone: Path | None = None
        primary_issue = "cleanup-failed"
        try:
            self._validate_identity()
            tombstone = self.root / f".capture-tombstone-{secrets.token_hex(16)}"
            if os.path.lexists(tombstone):
                raise OSError("random capture tombstone collision")
            os.replace(self.run_dir, tombstone)
            self._scan_no_reparse(tombstone)
            if os.name != "nt" and not shutil.rmtree.avoids_symlink_attacks:
                raise OSError("symlink-safe shutil.rmtree is unavailable")
            shutil.rmtree(tombstone)
            return CleanupResult(())
        except (OSError, ValueError) as exc:
            primary_issue = type(exc).__name__
            if tombstone is not None and os.path.lexists(tombstone):
                try:
                    scrub_issues = self._scrub_tombstone(tombstone)
                except (OSError, ValueError):
                    scrub_issues = ("scrub-enumeration-failed",)
                try:
                    self._purge_tombstone(tombstone)
                    try:
                        self._write_redacted_recovery(primary_issue)
                    except (OSError, ValueError):
                        return _bounded_cleanup_result(
                            (primary_issue, *scrub_issues, "recovery-record-write-failed"),
                            recovery_retained=False,
                        )
                    return _bounded_cleanup_result(
                        (primary_issue, *scrub_issues), recovery_retained=True
                    )
                except (OSError, ValueError):
                    if not os.path.lexists(tombstone):
                        return _bounded_cleanup_result(
                            (primary_issue, *scrub_issues, "recovery-record-write-failed"),
                            recovery_retained=False,
                        )
                    try:
                        unlink_issues = self._unlink_owned_payloads(tombstone)
                    except (OSError, ValueError):
                        unlink_issues = ("unlink-enumeration-failed",)
                    try:
                        self._purge_tombstone(tombstone)
                        try:
                            self._write_redacted_recovery(primary_issue)
                        except (OSError, ValueError):
                            return _bounded_cleanup_result(
                                (
                                    primary_issue,
                                    *scrub_issues,
                                    *unlink_issues,
                                    "recovery-record-write-failed",
                                ),
                                recovery_retained=False,
                            )
                        return _bounded_cleanup_result(
                            (primary_issue, *scrub_issues, *unlink_issues),
                            recovery_retained=True,
                        )
                    except (OSError, ValueError):
                        return _bounded_cleanup_result(
                            (
                                primary_issue,
                                *scrub_issues,
                                *unlink_issues,
                                "scrub-unlink-failed",
                            ),
                            recovery_retained=os.path.lexists(tombstone),
                        )
            # A failed purge leaves the tombstone quarantined and is never a
            # clean outcome. Its raw contents are never serialized as recovery.
            return _bounded_cleanup_result(
                (primary_issue,),
                recovery_retained=bool(tombstone and os.path.lexists(tombstone)),
            )


@dataclass
class ReservedExternalRunV1:
    """Own one reserved receipt and the exact capture lifecycle until finalization."""

    receipt: TerminalReceiptV1
    lifecycle: RunCaptureLifecycle | None = None
    state: str = "absent"
    finalized: bool = False
    _cleanup_result: CleanupResult | None = None

    def adopt_lifecycle(self, lifecycle: RunCaptureLifecycle) -> None:
        if self.state != "absent" or self.lifecycle is not None:
            raise ValueError("E_EXTERNAL_RESERVED_RUN_LIFECYCLE_ALREADY_OWNED")
        self.lifecycle = lifecycle
        self.state = "provisional"

    def mark_initialized(self, lifecycle: RunCaptureLifecycle) -> None:
        if self.state != "provisional" or self.lifecycle is not lifecycle:
            raise ValueError("E_EXTERNAL_RESERVED_RUN_LIFECYCLE_MISMATCH")
        self.state = "initialized"

    def cleanup_once(self) -> CleanupResult:
        if self._cleanup_result is not None:
            return self._cleanup_result
        try:
            if self.state == "absent":
                result = CleanupResult(())
            elif self.state == "provisional" and self.lifecycle is not None:
                result = RunCaptureLifecycle.release_provisional(
                    self.lifecycle.run_dir
                )
            elif self.state == "initialized" and self.lifecycle is not None:
                result = self.lifecycle.cleanup()
            else:
                result = _bounded_cleanup_result(
                    ("cleanup-state-invalid", "cleanup-retention-unknown"),
                    recovery_retained=False,
                )
        except Exception:
            result = _bounded_cleanup_result(
                ("cleanup-owner-failed", "cleanup-retention-unknown"),
                recovery_retained=False,
            )
        self._cleanup_result = result
        self.state = "cleaned"
        return result

    def mark_finalized(self) -> None:
        if self.finalized:
            raise ValueError("reserved external run is already finalized")
        if self.state != "cleaned":
            raise ValueError("E_EXTERNAL_RESERVED_RUN_CLEANUP_REQUIRED")
        self.finalized = True

    def __enter__(self) -> "ReservedExternalRunV1":
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        if not self.finalized:
            self.cleanup_once()
        self.receipt.close()


def _bounded_cleanup_result(
    issues: tuple[str, ...], *, recovery_retained: bool
) -> CleanupResult:
    bounded: list[str] = []
    for issue in issues:
        token = re.sub(r"[^A-Za-z0-9_.:-]+", "-", str(issue))[
            :CLEANUP_ISSUE_TOKEN_MAX
        ]
        bounded.append(token or "cleanup-issue")
        if len(bounded) == CLEANUP_ISSUE_LIMIT:
            break
    return CleanupResult(tuple(bounded), recovery_retained=recovery_retained)


def ledger_helper() -> Path | None:
    script_dir = Path(__file__).resolve().parent
    candidates = (
        script_dir / "agent-run-ledger.py",
        Path("scripts/agent-run-ledger.py"),
        script_dir.parents[2] / "scripts" / "agent-run-ledger.py",
    )
    return next((path for path in candidates if path.is_file()), None)


def _runner_support_environment(source: dict[str, str]) -> dict[str, str]:
    allowed = {
        "COMSPEC", "LANG", "LC_ALL", "PATH", "PATHEXT", "SYSTEMROOT",
        "TEMP", "TMP", "TMPDIR", "WINDIR", "PYTHONIOENCODING",
    }
    return {key: value for key, value in source.items() if key.upper() in allowed}


def run_support_command(
    runner: ProcessRunnerV1,
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    timeout_secs: float,
) -> tuple[ProcessResultV1, bytes, bytes]:
    executable = Path(command[0]).resolve(strict=True)
    argv = (str(executable), *command[1:])
    sink = runner.mint_memory_capture_sink()
    request = ProcessRequestV1(
        schema_version=1,
        argv=argv,
        resolved_executable=executable,
        cwd=str(cwd),
        environment=tuple(
            EnvironmentRowV1(name, value) for name, value in environment.items()
        ),
        stdin_bytes=None,
        deadline_monotonic=time.monotonic() + timeout_secs,
        capture_policy=CapturePolicyV1("provider-support-v1", 1024 * 1024, 0, 0, 64 * 1024),
        capture_sink_binding=sink,
        settle_policy=SettlePolicyV1(5.0),
        windows_argv_profile_id=provider_windows_argv_profile_id(
            "python-support", executable
        ),
    )
    result = runner.run(request)
    return result, sink.bytes_for("stdout"), sink.bytes_for("stderr")


def run_ledger(runner: ProcessRunnerV1, args: list[str]) -> bool:
    helper = ledger_helper()
    if helper is None:
        return False
    try:
        result, _stdout, _stderr = run_support_command(
            runner,
            [sys.executable, str(helper), *args],
            cwd=Path.cwd().resolve(),
            environment=_runner_support_environment(dict(os.environ)),
            timeout_secs=30,
        )
    except (OSError, ValueError):
        return False
    return result.outcome == "success" and result.target_exit_code == 0


def codex_hook_health_helper(codex_home: Path) -> Path | None:
    adjacent_helper = Path(__file__).resolve().with_name("check-hook-health.py")
    if adjacent_helper.is_file():
        return adjacent_helper
    installed_helper = codex_home / "skills" / "lead" / "scripts" / "check-hook-health.py"
    if installed_helper.is_file():
        return installed_helper

    script_dir = Path(__file__).resolve().parent
    for repo_root in (script_dir.parent, script_dir.parents[2]):
        source_helper = repo_root / "scripts" / "check-hook-health.py"
        if (repo_root / "shared" / "AGENTS.shared.md").is_file() and source_helper.is_file():
            return source_helper
    return None


def _trust_probe_env(codex_home: Path) -> dict[str, str]:
    allowed = {
        "COMSPEC",
        "LANG",
        "LC_ALL",
        "PATH",
        "PATHEXT",
        "SYSTEMROOT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "WINDIR",
    }
    child = {key: value for key, value in os.environ.items() if key.upper() in allowed}
    child["CODEX_HOME"] = str(codex_home)
    return child


def require_codex_hook_trust(
    runner: ProcessRunnerV1,
    command: list[str],
    codex_home: Path,
    query_cwd: Path,
) -> int:
    helper = codex_hook_health_helper(codex_home)
    if helper is None:
        return fail("Codex hook trust helper was not found")
    host_os = "windows" if os.name == "nt" else "posix"
    target = (codex_home / "hooks.json").resolve(strict=False)
    try:
        result, stdout, stderr = run_support_command(
            runner,
            [
                sys.executable,
                str(helper),
                "--target",
                str(target),
                "--platform",
                "codex",
                "--host-os",
                host_os,
                "--codex-trust-mode",
                "require",
                "--codex-command-json",
                json.dumps(command),
                "--codex-home",
                str(codex_home),
                "--query-cwd",
                str(query_cwd),
            ],
            cwd=query_cwd,
            environment=_trust_probe_env(codex_home),
            timeout_secs=30,
        )
    except (OSError, ValueError):
        return fail("Codex hook trust inventory query failed")
    if result.outcome != "success" or result.target_exit_code != 0:
        raw = stderr or stdout
        detail = " ".join(raw.decode("utf-8", errors="replace").split())[:512]
        return fail(detail or "Codex hook trust requirement failed")
    return 0


def ledger_common(
    control: Control,
    provider: str,
    model: str,
    effort: str,
    slug: str,
    *,
    role_provenance: ExternalRoleProvenance | None = None,
    provenance: ExecutionProvenance | None = None,
    launch_flags: tuple[str, ...] | list[str] | None = None,
) -> list[str]:
    external = provider in EXTERNAL_PROVIDER_NAMES
    frozen_role = role_provenance or (
        external_role_provenance(control, provider) if external else None
    )
    if provenance is not None:
        if launch_flags is None:
            launch_flags = provenance.launch_flags
        if (
            provider != provenance.provider
            or model != provenance.model
            or effort != provenance.effort
            or frozen_role is None
            or frozen_role.assigned_role != provenance.assigned_internal_role
            or normalize_launch_flags(provider, launch_flags) != provenance.launch_flags
        ):
            raise ValueError("E_EXTERNAL_PROVENANCE_MISMATCH")
    execution_role = frozen_role.execution_role if frozen_role is not None else "external-reviewer"
    values = [
        "--role",
        execution_role if external else (control.ledger_role or "none"),
        "--execution-role",
        execution_role,
        "--provider",
        provider,
        "--scope",
        f"external run: {slug}",
        "--model",
        model,
        "--effort",
        effort,
    ]
    if control.ledger_lane:
        values += ["--lane", control.ledger_lane]
    if control.ledger_artifact:
        values += ["--artifact", control.ledger_artifact]
    if external:
        values += ["--assigned-role", frozen_role.assigned_role]
        if launch_flags is not None:
            values += [
                "--launch-flags-json",
                json.dumps(
                    list(normalize_launch_flags(provider, launch_flags)),
                    ensure_ascii=True,
                    separators=(",", ":"),
                ),
            ]
    return values


def external_terminal_ledger_args(
    control: Control,
    provider: str,
    model: str,
    effort: str,
    slug: str,
    realization: dict[str, object] | None,
    *,
    provenance: ExecutionProvenance | None = None,
    expected_provenance: ExecutionProvenance | None = None,
) -> list[str]:
    common = [
        "--terminal-class", "external-nonauthorizing",
        "--authorizing", "false",
        "--actual-execution-path", "direct-external-cli",
    ]
    if realization is not None:
        raise ValueError("E_EXTERNAL_LEDGER_UNVERIFIED: unexpected provider realization")
    if provenance is None:
        values = list(common)
        if control.ledger_artifact:
            values += ["--artifact-identity", control.ledger_artifact]
        return values
    provenance = require_exact_execution_provenance(
        expected_provenance or provenance, provenance
    )
    return [
        *common,
        "--artifact-identity", provenance.artifact_identity,
        "--external-dispatch-id", provenance.external_dispatch_id,
        "--external-evidence-run-id", provenance.external_evidence_run_id,
        "--effort-mapping-loss", provenance.effort_mapping_loss,
    ]


def _final_nonblank_line(text: str) -> str:
    lines = [line.rstrip("\r") for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


def _kimi_gate_like(line: str) -> bool:
    """Classify only a bounded renderer-decorated leading gate attempt."""

    if line.startswith("\u2022 "):
        line = line.removeprefix("\u2022 ")
    elif line.startswith("  "):
        line = line.removeprefix("  ")
    return KIMI_GATE_LIKE.match(line) is not None


def _kimi_final_gate(text: str) -> str | None:
    """Accept only Kimi's known final-line decoration and one consistent verdict."""

    lines = [line.rstrip("\r") for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    final = KIMI_RENDERED_GATE.fullmatch(lines[-1])
    if final is None:
        return None
    gate = final.group(1)
    gate_like = [line for line in lines if _kimi_gate_like(line)]
    return gate if gate_like == [lines[-1]] else None


def parse_codex_jsonl_result(data: bytes, result_max_bytes: int) -> bytes:
    if not data or not data.endswith(b"\n"):
        raise ResultMaterializationError("Codex JSONL is empty or truncated")
    selected: bytes | None = None
    for encoded_line in data[:-1].split(b"\n"):
        if not encoded_line:
            raise ResultMaterializationError("Codex JSONL contains an empty record")
        try:
            line = encoded_line.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise ResultMaterializationError("Codex JSONL is not valid UTF-8") from exc
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ResultMaterializationError("Codex JSONL contains a malformed record") from exc
        if not isinstance(record, dict):
            raise ResultMaterializationError("Codex JSONL record is not an object")
        item = record.get("item")
        if (
            record.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "agent_message"
            and isinstance(item.get("text"), str)
        ):
            candidate = item["text"].encode("utf-8")
            selected = candidate
    if selected is None:
        raise ResultMaterializationError(
            "Codex JSONL contains no completed agent_message item"
        )
    if len(selected) > result_max_bytes:
        raise ResultMaterializationError(
            f"provider result exceeds configured maximum of {result_max_bytes} bytes"
        )
    return selected


def provider_capture_policy(capture_max_bytes: int) -> CapturePolicyV1:
    """Keep the provider's injected capture bound at its existing policy owner."""

    return CapturePolicyV1(
        "provider-capture-v1", capture_max_bytes, 0, 0, 64 * 1024
    )


def provider_windows_argv_profile_id(
    provider: str, executable: Path
) -> str | None:
    """Select one sealed runner profile without constructing observed evidence."""
    if os.name != "nt":
        return None
    if os.path.normcase(os.path.abspath(executable)) == os.path.normcase(
        os.path.abspath(sys.executable)
    ):
        return "python-validator-json-echo-v1"
    if provider == "kimi" and executable.name.casefold() == "kimi.exe":
        return KIMI_WINDOWS_PROFILE_V1.profile_id
    return None


def kimi_provider_args(agent_file: Path, skills_dir: Path) -> list[str]:
    """Delegate the exact sealed Kimi argv to the runner-owned profile."""

    return KIMI_WINDOWS_PROFILE_V1.build_args(agent_file, skills_dir)


def run_provider_process(
    runner: ProcessRunnerV1,
    command: list[str],
    provider_args: list[str],
    child_environment: dict[str, str],
    query_cwd: Path,
    body: bytes | None,
    control: Control,
    provider: str | None = None,
    *,
    expected_executable_binding: ExecutableBindingV1 | None = None,
) -> tuple[ProcessResultV1, bytes, bytes]:
    """Run one provider through the sole process/tree/I-O lifecycle owner."""

    executable = Path(os.path.abspath(command[0]))
    argv = (str(executable), *command[1:], *provider_args)
    sink = runner.mint_memory_capture_sink()
    request = ProcessRequestV1(
        schema_version=1,
        argv=argv,
        resolved_executable=executable,
        cwd=str(query_cwd),
        environment=tuple(
            EnvironmentRowV1(name, value) for name, value in child_environment.items()
        ),
        stdin_bytes=body,
        deadline_monotonic=time.monotonic() + control.timeout_secs,
        capture_policy=provider_capture_policy(control.capture_max_bytes),
        capture_sink_binding=sink,
        settle_policy=SettlePolicyV1(5.0),
        windows_argv_profile_id=provider_windows_argv_profile_id(
            provider or "python-support", executable
        ),
        expected_executable_binding=expected_executable_binding,
    )
    result = runner.run(request)
    return result, sink.bytes_for("stdout"), sink.bytes_for("stderr")


def provider_stream_result(
    result: ProcessResultV1, *, include_stderr: bool = True
) -> StreamCaptureResult:
    stdout, stderr = result.stdout, result.stderr
    stderr_digest = stderr.digest if include_stderr else hashlib.sha256(b"").hexdigest()
    digest = hashlib.sha256(
        b"provider-capture-v1\x00" + stdout.digest.encode("ascii")
        + b"\x00" + stderr_digest.encode("ascii")
    ).hexdigest()
    issues = list(result.cleanup_issues)
    if result.failure_id is not None:
        issues.append(result.failure_id)
    if not result.resources_closed or not result.tree.tree_empty:
        issues.append("process-unsettled")
    return StreamCaptureResult(
        overflow=stdout.truncated or (include_stderr and stderr.truncated),
        observed_bytes=stdout.observed_bytes + (
            stderr.observed_bytes if include_stderr else 0
        ),
        persisted_bytes=stdout.persisted_bytes + (
            stderr.persisted_bytes if include_stderr else 0
        ),
        digest=digest,
        issues=tuple(dict.fromkeys(issues)),
    )


def empty_provider_stream_result() -> StreamCaptureResult:
    """Return the fixed public capture projection for rejected Kimi output."""

    empty_digest = hashlib.sha256(b"").hexdigest()
    digest = hashlib.sha256(
        b"provider-capture-v1\x00"
        + empty_digest.encode("ascii")
        + b"\x00"
        + empty_digest.encode("ascii")
    ).hexdigest()
    return StreamCaptureResult(False, 0, 0, digest, ())


def _sanitized_diagnostic(
    message: str, lifecycle: RunCaptureLifecycle | None
) -> str:
    sanitized = message
    if lifecycle is not None:
        for path in (lifecycle.run_dir, lifecycle.root):
            sanitized = sanitized.replace(str(path), "<capture>")
    sanitized = re.sub(
        r"(?i)\b(?:api[_-]?key|token|secret|password)\s*=\s*[^\s;]+",
        "<redacted>",
        sanitized,
    )
    return " ".join(sanitized.split())[:512]


def credential_scan_terminal(
    needles: tuple[bytes, ...],
    *,
    stdout: bytes,
    stderr: bytes,
) -> str | None:
    """Return the stable scanner outcome after both child streams are settled."""

    if any(needle in stdout or needle in stderr for needle in needles):
        return "E_EXTERNAL_PROVIDER_CREDENTIAL_ECHO"
    return None


def provider_output_safety_scan_terminal(
    provider: str,
    needles: tuple[bytes, ...],
    *,
    stdout: bytes,
    stderr: bytes,
    serialized_line: bool = False,
) -> str | None:
    """Reuse the sole credential/path detectors for every public terminal line."""

    credential = credential_scan_terminal(needles, stdout=stdout, stderr=stderr)
    if credential is not None:
        return credential
    if provider != "kimi" and not serialized_line:
        return None
    try:
        script_dir = Path(__file__).resolve().parent
        candidates = (
            script_dir.parent / "hooks" / "check-machine-local-path.py",
            script_dir / "universal-hooks" / "hooks" / "check-machine-local-path.py",
        )
        classifier = next(path for path in candidates if path.is_file())
        spec = importlib.util.spec_from_file_location("_kimi_machine_path_classifier", classifier)
        if spec is None or spec.loader is None:
            raise ValueError("classifier")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        finder = getattr(module, "find_machine_paths")
        if finder(stdout.decode("utf-8", errors="replace")):
            return "E_EXTERNAL_PROVIDER_MACHINE_PATH_ECHO"
    except (OSError, ValueError, StopIteration, AttributeError, ImportError):
        return "E_EXTERNAL_PROVIDER_OUTPUT_SCAN_UNAVAILABLE"
    return None


def classify_kimi_child_nonzero(stderr: bytes) -> str:
    """Map one settled Kimi child refusal to its closed public category."""

    try:
        text = stderr.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return "unknown"
    if "\x00" in text:
        return "unknown"
    categories: set[str] = set()
    structured_codes = {
        "provider.rate_limit": "rate_limit",
        "auth.login_required": "auth",
        "provider.auth_error": "auth",
        "provider.overloaded": "vendor",
        "provider.connection_error": "vendor",
    }
    for line in text.splitlines():
        normalized = line.strip()
        category = structured_codes.get(normalized)
        if category is not None:
            categories.add(category)
        if re.fullmatch(r"error: unknown (?:command|option)(?: [^\r\n]*)?", normalized):
            categories.add("invocation")
    return next(iter(categories)) if len(categories) == 1 else "unknown"


def output_safety_scan_failure_terminal(
    lifecycle: RunCaptureLifecycle, stable_id: str
) -> TerminalResult:
    return TerminalResult(
        lifecycle.prompt_path,
        "blocked",
        "none",
        stable_id,
        f"UNVERIFIED:{stable_id}",
        0,
    )


def materialize_terminal(
    lifecycle: RunCaptureLifecycle,
    provider: str,
    exit_code: int,
    result_max_bytes: int,
    *,
    stdout: bytes | None = None,
    stderr: bytes | None = None,
) -> tuple[TerminalResult, str]:
    evidence_path = lifecycle.prompt_path
    captured_stdout = (
        stdout if stdout is not None else getattr(lifecycle, "_test_stdout", b"")
    )
    if provider == "codex":
        result_bytes = parse_codex_jsonl_result(captured_stdout, result_max_bytes)
    else:
        if len(captured_stdout) > result_max_bytes:
            raise ResultMaterializationError(
                f"provider result exceeds configured maximum of {result_max_bytes} bytes"
            )
        result_bytes = captured_stdout
    stderr_bytes = stderr if stderr is not None else getattr(lifecycle, "_test_stderr", b"")
    result_text = result_bytes.decode("utf-8", errors="replace")
    stderr_text = stderr_bytes.decode("utf-8", errors="replace")
    marker_count = sum(
        1 for line in stderr_text.splitlines() if ERROR_MARKER.match(line)
    )
    final_line = _final_nonblank_line(result_text)
    status, gate = "blocked", "none"
    if exit_code != 0:
        note = f"oracle: nonzero exit ({exit_code})"
        token = "FAILED:nonzero-exit"
    elif not result_bytes:
        note = "oracle: empty provider result"
        token = "UNVERIFIED:empty"
    elif marker_count:
        note = f"oracle: err markers present ({marker_count})"
        token = "UNVERIFIED:err-markers"
    elif provider == "kimi":
        kimi_gate = _kimi_final_gate(result_text)
        if kimi_gate == "PASS":
            status, gate, note = "completed", "PASS", "oracle: final-line Kimi GATE: PASS"
            token = "COMPLETE:PASS"
        elif kimi_gate == "REVISE":
            status, gate, note = "revise", "REVISE", "oracle: final-line Kimi GATE: REVISE"
            token = "COMPLETE:REVISE"
        elif kimi_gate == "BLOCKED":
            status, gate, note = "blocked", "BLOCKED", "oracle: final-line Kimi GATE: BLOCKED"
            token = "COMPLETE:BLOCKED"
        else:
            note = "oracle: final line is not an anchored GATE verdict"
            token = "UNVERIFIED:no-gate-line"
    elif final_line == "GATE: PASS":
        status, gate, note = "completed", "PASS", "oracle: final-line GATE: PASS"
        token = "COMPLETE:PASS"
    elif final_line == "GATE: REVISE":
        status, gate, note = "revise", "REVISE", "oracle: final-line GATE: REVISE"
        token = "COMPLETE:REVISE"
    else:
        note = "oracle: final line is not an anchored GATE verdict"
        token = "UNVERIFIED:no-gate-line"
    return (
        TerminalResult(evidence_path, status, gate, note, token, marker_count),
        result_text,
    )


def combine_terminal_outcomes(
    exit_code: int,
    terminal: TerminalResult,
    cleanup: CleanupResult,
    lifecycle: RunCaptureLifecycle | None,
    *,
    external: bool = False,
    primary_terminal: TerminalResult | None = None,
) -> FinalOutcome:
    primary = primary_terminal or terminal
    cleanup_status = "complete" if cleanup.clean else "incomplete"
    cleanup_diagnostic = _sanitized_diagnostic("; ".join(cleanup.issues), lifecycle)
    if cleanup.clean:
        combined_exit = exit_code
        token, status, gate, note = (
            terminal.token,
            terminal.status,
            terminal.gate,
            terminal.note,
        )
    else:
        combined_exit = exit_code if exit_code != 0 else 1
        token = (
            "UNVERIFIED:E_EXTERNAL_CAPTURE_CLEANUP"
            if external
            else "FAILED:cleanup-incomplete"
        )
        status, gate = "blocked", "none"
        note = (
            f"cleanup: incomplete ({len(cleanup.issues)}); "
            f"primary={primary.token}"
        )
    return FinalOutcome(
        combined_exit,
        token,
        status,
        gate,
        note,
        exit_code,
        primary.token,
        primary.status,
        primary.gate,
        primary.note,
        cleanup_status,
        len(cleanup.issues),
        cleanup_diagnostic,
        cleanup.recovery_retained,
        terminal.stderr_marker_count,
    )


def settle_once(
    exit_code: int,
    terminal: TerminalResult,
    lifecycle: RunCaptureLifecycle,
    *,
    external: bool,
    primary_terminal: TerminalResult | None = None,
) -> FinalOutcome:
    """Complete cleanup/recovery before the caller emits the sole durable terminal."""

    try:
        cleanup = lifecycle.cleanup()
    except Exception:
        cleanup = _bounded_cleanup_result(
            ("cleanup-owner-failed",), recovery_retained=True
        )
    return combine_terminal_outcomes(
        exit_code,
        terminal,
        cleanup,
        lifecycle,
        external=external,
        primary_terminal=primary_terminal,
    )


def capture_overflow_terminal(stream: StreamCaptureResult) -> TerminalResult:
    return TerminalResult(
        Path("<stream-capture>"),
        "blocked",
        "none",
        (
            "stream: combined stdout/stderr capture exceeded configured maximum; "
            f"observedBytes={stream.observed_bytes}"
        ),
        "FAILED:capture-overflow",
        0,
    )


def serialized_safety_failure_outcome(
    outcome: FinalOutcome, stable_id: str
) -> FinalOutcome:
    """Return a path/detail-free blocked result after the public line fails scanning."""

    return FinalOutcome(
        1,
        f"UNVERIFIED:{stable_id}",
        "blocked",
        "none",
        stable_id,
        1,
        f"UNVERIFIED:{stable_id}",
        "blocked",
        "none",
        stable_id,
        outcome.cleanup_status,
        outcome.cleanup_issue_count,
        "",
        outcome.recovery_retained,
        0,
    )


def build_provider_result_line(
    provider: str,
    model: str,
    effort: str,
    result_text: str,
    outcome: FinalOutcome,
    stream: StreamCaptureResult | None = None,
    *,
    cancelled: bool,
    timed_out: bool,
    realization: dict[str, str] | None = None,
    role_provenance: ExternalRoleProvenance | None = None,
    provenance: ExecutionProvenance | None = None,
    expected_provenance: ExecutionProvenance | None = None,
    child_nonzero_category: str | None = None,
    launch_flags: tuple[str, ...] | list[str] | None = None,
) -> str:
    if provenance is not None:
        provenance = require_exact_execution_provenance(
            expected_provenance or provenance, provenance
        )
    frozen_role = role_provenance or ExternalRoleProvenance("none", "none")
    frozen_launch_flags = (
        normalize_launch_flags(provider, launch_flags)
        if launch_flags is not None
        else provenance.launch_flags
        if provenance is not None
        else None
    )
    if provenance is not None and frozen_launch_flags != provenance.launch_flags:
        raise ValueError("E_EXTERNAL_PROVENANCE_MISMATCH")
    payload = {
        "schema": "orchestrarium.provider-result.v2",
        "provider": provider,
        "model": model,
        "effort": effort,
        "resultText": result_text,
        "exitCode": outcome.exit_code,
        "token": outcome.token,
        "status": outcome.status,
        "gate": outcome.gate,
        "note": outcome.note[:512],
        "cancelled": cancelled,
        "timedOut": timed_out,
        "stderrMarkerCount": outcome.stderr_marker_count,
        "cleanupStatus": outcome.cleanup_status,
        "cleanupIssueCount": outcome.cleanup_issue_count,
        "captureRecoveryRetained": outcome.recovery_retained,
        "primaryOutcome": {
            "exitCode": outcome.primary_exit_code,
            "token": outcome.primary_token,
            "status": outcome.primary_status,
            "gate": outcome.primary_gate,
            "note": outcome.primary_note[:512],
        },
        "authorizing": False,
        "closesRunIds": [],
        "independentVerificationRequired": True,
        "terminalClass": "external-nonauthorizing",
        "actualExecutionPath": (
            provenance.actual_execution_path
            if provenance is not None
            else "direct-external-cli"
        ),
        "assignedRole": frozen_role.assigned_role,
        "executionRole": frozen_role.execution_role,
    }
    if provenance is not None:
        payload.update(provenance.payload())
    elif frozen_launch_flags is not None:
        payload["launchFlags"] = list(frozen_launch_flags)
    if outcome.cleanup_diagnostic:
        payload["cleanupDiagnostic"] = outcome.cleanup_diagnostic
    if child_nonzero_category is not None:
        if child_nonzero_category not in KIMI_CHILD_NONZERO_CATEGORIES:
            raise ValueError("invalid Kimi child nonzero category")
        payload["childNonzeroCategory"] = child_nonzero_category
        payload["primaryOutcome"]["childNonzeroCategory"] = child_nonzero_category
    if stream is not None:
        payload.update(
            {
                "captureOverflow": stream.overflow,
                "captureObservedBytes": stream.observed_bytes,
                "capturePersistedBytes": stream.persisted_bytes,
                "captureDigest": stream.digest,
                "captureIssueCount": len(stream.issues),
            }
        )
    if realization is not None:
        raise ValueError("provider result realization is unsupported")
    line = RESULT_PREFIX + json.dumps(
        payload, ensure_ascii=True, separators=(",", ":")
    )
    return line + "\n"


def build_minimal_provider_failure_line(
    provider: str,
    model: str,
    effort: str,
    *,
    stable_id: str,
    cancelled: bool,
    timed_out: bool,
    exit_code: int = 1,
    cleanup_status: str = "complete",
    cleanup_issue_count: int = 0,
    recovery_retained: bool = False,
) -> str:
    """Build one detail-free V2 failure without depending on the full builder."""

    safe_provider = provider if provider in EXTERNAL_PROVIDER_NAMES else "unknown"
    safe_model = model if isinstance(model, str) and _MODEL_TOKEN.fullmatch(model) else "unavailable"
    safe_effort = effort if effort in EFFORTS or effort == "unsupported" else "unspecified"
    safe_id = (
        stable_id
        if isinstance(stable_id, str)
        and re.fullmatch(r"E_[A-Z0-9_]{1,127}", stable_id, re.ASCII)
        else "E_EXTERNAL_PROVIDER_TERMINAL_BUILD_FAILED"
    )
    safe_cleanup = cleanup_status if cleanup_status in {"complete", "incomplete"} else "incomplete"
    safe_count = cleanup_issue_count if isinstance(cleanup_issue_count, int) and 0 <= cleanup_issue_count <= CLEANUP_ISSUE_LIMIT else CLEANUP_ISSUE_LIMIT
    safe_exit_code = (
        130
        if cancelled
        else 124
        if timed_out
        else exit_code
        if isinstance(exit_code, int) and 0 < exit_code <= 255
        else 1
    )
    token = f"UNVERIFIED:{safe_id}"
    payload = {
        "schema": "orchestrarium.provider-result.v2",
        "provider": safe_provider,
        "model": safe_model,
        "effort": safe_effort,
        "resultText": "",
        "exitCode": safe_exit_code,
        "token": token,
        "status": "blocked",
        "gate": "none",
        "note": safe_id,
        "cancelled": bool(cancelled),
        "timedOut": bool(timed_out),
        "stderrMarkerCount": 0,
        "cleanupStatus": safe_cleanup,
        "cleanupIssueCount": safe_count,
        "captureRecoveryRetained": bool(recovery_retained),
        "primaryOutcome": {
            "exitCode": safe_exit_code,
            "token": token,
            "status": "blocked",
            "gate": "none",
            "note": safe_id,
        },
        "authorizing": False,
        "closesRunIds": [],
        "independentVerificationRequired": True,
        "terminalClass": "external-nonauthorizing",
        "actualExecutionPath": "direct-external-cli",
        "assignedRole": "none",
        "executionRole": "none",
    }
    return RESULT_PREFIX + json.dumps(
        payload, ensure_ascii=True, separators=(",", ":")
    ) + "\n"


def parse_provider_result(output: str) -> dict[str, object]:
    if "\r" in output:
        raise ValueError("provider result must use one newline-terminated record")
    if not output.endswith("\n") or output.count("\n") != 1:
        raise ValueError("provider result must contain exactly one line")
    line = output[:-1]
    if not line.startswith(RESULT_PREFIX):
        raise ValueError("provider result prefix mismatch")
    encoded = line[len(RESULT_PREFIX) :]
    decoder = json.JSONDecoder()
    payload, end = decoder.raw_decode(encoded)
    if end != len(encoded) or not isinstance(payload, dict):
        raise ValueError("provider result must contain exactly one JSON object")
    if payload.get("schema") != "orchestrarium.provider-result.v2":
        raise ValueError("provider result schema mismatch")
    if not isinstance(payload.get("resultText"), str):
        raise ValueError("provider result resultText must be a string")
    if (
        not isinstance(payload.get("assignedRole"), str)
        or not isinstance(payload.get("executionRole"), str)
    ):
        raise ValueError("provider result role provenance mismatch")
    if (
        payload.get("authorizing") is not False
        or payload.get("closesRunIds") != []
        or payload.get("independentVerificationRequired") is not True
        or payload.get("terminalClass") != "external-nonauthorizing"
        or payload.get("actualExecutionPath") != "direct-external-cli"
    ):
        raise ValueError("provider result nonauthorizing tuple mismatch")
    if "launchFlags" in payload:
        try:
            frozen, derived_model, derived_effort = normalize_launch_profile(
                str(payload.get("provider", "")), payload["launchFlags"]
            )
        except ValueError as exc:
            raise ValueError("provider result launchFlags mismatch") from exc
        if (
            payload["launchFlags"] != list(frozen)
            or payload.get("model") != derived_model
            or payload.get("effort") != derived_effort
        ):
            raise ValueError("provider result launchFlags mismatch")
    child_category = payload.get("childNonzeroCategory")
    primary = payload.get("primaryOutcome")
    if child_category is not None:
        if (
            payload.get("provider") != "kimi"
            or child_category not in KIMI_CHILD_NONZERO_CATEGORIES
            or not isinstance(primary, dict)
            or primary.get("childNonzeroCategory") != child_category
        ):
            raise ValueError("provider result Kimi child nonzero category mismatch")
    elif isinstance(primary, dict) and "childNonzeroCategory" in primary:
        raise ValueError("provider result Kimi child nonzero category mismatch")
    return payload


def _agent_run_jsonl_limits() -> tuple[int, int]:
    """Return compiled protocol limits; source tests bind them to the schema owner."""

    return AGENT_RUN_MAX_LINE_CHARS, AGENT_RUN_MAX_EVENTS


def read_back_external_terminal(
    control: Control,
    provider: str,
    launch_run_id: str,
    expected_provenance: ExecutionProvenance | None = None,
) -> dict[str, object] | None:
    """Bind tracked evidence to the durable terminal row, never to a slug-derived id."""

    if not control.ledger or not launch_run_id:
        return None
    terminal: dict[str, object] | None = None
    matches = 0
    events = 0
    invalid = False
    try:
        max_line_chars, max_events = _agent_run_jsonl_limits()
        with (Path(control.ledger) / "agent-runs.jsonl").open(
            "r", encoding="utf-8", newline=""
        ) as stream:
            while True:
                raw = stream.readline(max_line_chars + 2)
                if raw == "":
                    break
                complete_line = raw.endswith("\n")
                line = raw.rstrip("\r\n")
                if len(line) > max_line_chars or (
                    not complete_line and len(raw) > max_line_chars
                ):
                    events += 1
                    if events > max_events:
                        return None
                    invalid = True
                    while raw and not raw.endswith("\n"):
                        raw = stream.readline(max_line_chars + 2)
                    continue
                if not line.strip():
                    continue
                events += 1
                if events > max_events:
                    return None
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    invalid = True
                    continue
                if (
                    isinstance(row, dict)
                    and row.get("eventKind") == "terminal"
                    and row.get("launchRunId") == launch_run_id
                ):
                    matches += 1
                    if matches == 1:
                        terminal = row
    except (OSError, KeyError, TypeError, ValueError):
        return None
    if invalid or matches != 1 or terminal is None:
        return None
    if (
        not isinstance(terminal.get("runId"), str)
        or terminal.get("provider") != provider
        or terminal.get("terminalClass") != "external-nonauthorizing"
        or terminal.get("authorizing") is not False
        or terminal.get("closesRunIds") != []
    ):
        return None
    if expected_provenance is not None:
        expected = expected_provenance.terminal_projection()
        if any(terminal.get(key) != value for key, value in expected.items()):
            return None
        if (
            terminal.get("runId") != expected_provenance.external_evidence_run_id
            or terminal.get("launchRunId") != expected_provenance.external_dispatch_id
        ):
            return None
    return terminal


def record_terminal(
    control: Control,
    provider: str,
    model: str,
    effort: str,
    slug: str,
    launch_run_id: str,
    outcome: FinalOutcome,
    *,
    cancelled: bool,
    timed_out: bool,
    result_delivered: bool,
    realization: dict[str, object] | None = None,
    runner: ProcessRunnerV1,
    role_provenance: ExternalRoleProvenance | None = None,
    provenance: ExecutionProvenance | None = None,
    expected_provenance: ExecutionProvenance | None = None,
    child_nonzero_category: str | None = None,
    launch_flags: tuple[str, ...] | list[str] | None = None,
) -> bool:
    if provenance is not None:
        provenance = require_exact_execution_provenance(
            expected_provenance or provenance, provenance
        )
    category_note = (
        f"; childNonzeroCategory={child_nonzero_category}"
        if child_nonzero_category is not None
        else ""
    )
    notes = (
        f"{outcome.note}; exitCode={outcome.exit_code}; "
        f"primaryExitCode={outcome.primary_exit_code}; "
        f"primaryToken={outcome.primary_token}; "
        f"cleanupStatus={outcome.cleanup_status}; "
        f"cleanupIssueCount={outcome.cleanup_issue_count}; "
        f"cleanupDiagnostic={outcome.cleanup_diagnostic or 'none'}; "
        f"cancelled={str(cancelled).lower()}; "
        f"timedOut={str(timed_out).lower()}; "
        f"resultDelivered={str(result_delivered).lower()}; "
        f"stderrMarkers={outcome.stderr_marker_count}{category_note}"
    )[:1024]
    args = [
        "--work-item",
        control.ledger or "",
        "append",
        *(
            ["--run-id", provenance.external_evidence_run_id]
            if provenance is not None
            else []
        ),
        *(
            ["--work-item-name", provenance.work_item]
            if provenance is not None
            else []
        ),
        "--status",
        outcome.status,
        "--gate",
        outcome.gate,
        "--event-kind",
        "terminal",
        "--launch-run-id",
        launch_run_id or f"setup-{slug}",
        "--evidence",
        (
            "command:provider-result-envelope-flushed"
            if result_delivered
            else "command:provider-result-envelope-not-delivered"
        ),
        "--notes",
        notes,
        *ledger_common(
            control,
            provider,
            model,
            effort,
            slug,
            role_provenance=role_provenance,
            provenance=provenance,
            launch_flags=launch_flags,
        ),
    ]
    args += external_terminal_ledger_args(
        control,
        provider,
        model,
        effort,
        slug,
        realization,
        provenance=provenance,
        expected_provenance=expected_provenance,
    )
    recorded = runner is not None and run_ledger(runner, args)
    if recorded and read_back_external_terminal(
        control, provider, launch_run_id, provenance
    ) is None:
        recorded = False
    if not recorded:
        print(
            f"FAIL: provider result is NOT in the ledger; launch {launch_run_id} "
            "stays unsettled.",
            file=sys.stderr,
        )
    return recorded


def finalize_reserved_run_once(
    control: Control,
    provider: str,
    model: str,
    effort: str,
    slug: str,
    launch_run_id: str,
    reserved_run: ReservedExternalRunV1,
    exit_code: int,
    stream: StreamCaptureResult | None = None,
    *,
    cancelled: bool = False,
    timed_out: bool = False,
    launch_error: str | None = None,
    realization: dict[str, object] | None = None,
    credential_needles: tuple[bytes, ...] = (),
    auth_output_scan_disposition: str | None = None,
    role_provenance: ExternalRoleProvenance | None = None,
    provenance: ExecutionProvenance | None = None,
    raw_stdout: bytes | None = None,
    raw_stderr: bytes | None = None,
    process_result: ProcessResultV1 | None = None,
    runner: ProcessRunnerV1 | None = None,
    launch_flags: tuple[str, ...] | list[str] | None = None,
    stable_failure_id: str | None = None,
) -> int:
    terminal_receipt = reserved_run.receipt
    lifecycle = reserved_run.lifecycle
    if terminal_receipt.committed:
        print("FAIL: terminal receipt was already committed", file=sys.stderr)
        return 1
    if lifecycle is None:
        cleanup = reserved_run.cleanup_once()
        line = build_minimal_provider_failure_line(
            provider,
            model,
            effort,
            stable_id=stable_failure_id or "E_EXTERNAL_PROVIDER_PRELAUNCH_FAILED",
            cancelled=cancelled,
            timed_out=timed_out,
            exit_code=exit_code,
            cleanup_status="complete" if cleanup.clean else "incomplete",
            cleanup_issue_count=len(cleanup.issues),
            recovery_retained=cleanup.recovery_retained,
        )
        try:
            terminal_receipt.commit(line.encode("utf-8", errors="strict"))
        except (OSError, ValueError) as exc:
            print(
                f"FAIL: terminal receipt commit failed: {type(exc).__name__}",
                file=sys.stderr,
            )
            return 1
        reserved_run.mark_finalized()
        try:
            sys.stdout.write(line)
            sys.stdout.flush()
        except Exception:
            print("FAIL: E_EXTERNAL_PROVIDER_RESULT_STDOUT_FAILED", file=sys.stderr)
            return 1
        return 130 if cancelled else 124 if timed_out else exit_code if exit_code != 0 else 1

    if provenance is not None:
        provenance = require_exact_execution_provenance(provenance, provenance)
    frozen_role = role_provenance or external_role_provenance(control, provider)
    raw_streams_settled = (
        process_result is not None
        and process_result.resources_closed
        and process_result.tree.tree_empty
        and process_result.tree.direct_reaped
        and not process_result.stdout.truncated
        and not process_result.stderr.truncated
        and raw_stdout is not None
        and raw_stderr is not None
    )
    scan_outcome: str | None = None
    credential_coverage_unavailable = (
        provider != "kimi"
        and process_result is not None
        and (
            auth_output_scan_disposition != AUTH_OUTPUT_SCAN_ENVIRONMENT_EXACT
            or not credential_needles
        )
    )
    scan_required = (
        provider == "kimi" or credential_coverage_unavailable or bool(credential_needles)
    )
    scan_unavailable = (
        "E_EXTERNAL_PROVIDER_OUTPUT_SCAN_UNAVAILABLE"
        if provider == "kimi"
        else "E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE"
    )
    if credential_coverage_unavailable:
        scan_outcome = "E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE"
    elif scan_required:
        try:
            scan_outcome = (
                provider_output_safety_scan_terminal(
                    provider, credential_needles, stdout=raw_stdout, stderr=raw_stderr
                )
                if raw_streams_settled
                else scan_unavailable
            )
        except Exception:
            scan_outcome = scan_unavailable
    if scan_required and stream is not None and stream.overflow:
        scan_outcome = scan_unavailable
    child_nonzero_category = None
    if (
        provider == "kimi"
        and scan_outcome is None
        and process_result is not None
        and process_result.target_exit_code not in (None, 0)
        and process_result.failure_id is None
        and not cancelled
        and not timed_out
        and launch_error is None
        and (stream is None or not stream.issues)
    ):
        child_nonzero_category = classify_kimi_child_nonzero(raw_stderr)
    public_stream = stream
    if provider == "kimi":
        public_stream = (
            empty_provider_stream_result()
            if scan_outcome is not None
            else provider_stream_result(process_result, include_stderr=False)
        )
    primary_terminal: TerminalResult | None = None
    combined_exit = exit_code
    if scan_outcome is not None:
        result_text = ""
        terminal = output_safety_scan_failure_terminal(lifecycle, scan_outcome)
        combined_exit = exit_code if exit_code != 0 else 1
    elif stream is not None and stream.overflow:
        result_text = ""
        terminal = capture_overflow_terminal(stream)
        combined_exit = exit_code if exit_code != 0 else 1
    else:
        try:
            terminal, result_text = materialize_terminal(
                lifecycle,
                provider,
                exit_code,
                control.result_max_bytes,
                stdout=raw_stdout,
                stderr=raw_stderr,
            )
        except (OSError, ValueError, ResultMaterializationError) as exc:
            result_text = ""
            terminal = TerminalResult(
                lifecycle.prompt_path,
                "blocked",
                "none",
                "result materialization failed",
                "UNVERIFIED:result-materialization",
                0,
            )
            combined_exit = exit_code if exit_code != 0 else 1
            print("FAIL: result materialization failed", file=sys.stderr)
        else:
            primary_terminal = terminal
            if terminal.token.startswith("COMPLETE:"):
                terminal = TerminalResult(
                    terminal.evidence_path,
                    terminal.status,
                    terminal.gate,
                    terminal.note,
                    "COMPLETE:EXTERNAL_NONAUTHORIZING",
                    terminal.stderr_marker_count,
                )
    cleanup = reserved_run.cleanup_once()
    outcome = combine_terminal_outcomes(
        combined_exit,
        terminal,
        cleanup,
        lifecycle,
        external=True,
        primary_terminal=primary_terminal,
    )
    if outcome.cleanup_status != "complete":
        print(
            "FAIL: secure capture cleanup did not complete",
            file=sys.stderr,
        )

    if launch_error:
        print(f"FAIL: {launch_error}", file=sys.stderr)

    terminal_outcome = outcome
    try:
        line = build_provider_result_line(
            provider,
            model,
            effort,
            result_text,
            outcome,
            public_stream,
            cancelled=cancelled,
            timed_out=timed_out,
            realization=realization,
            role_provenance=frozen_role,
            provenance=provenance,
            expected_provenance=provenance,
            child_nonzero_category=child_nonzero_category,
            launch_flags=launch_flags,
        )
    except Exception:
        terminal_outcome = serialized_safety_failure_outcome(
            outcome, "E_EXTERNAL_PROVIDER_TERMINAL_BUILD_FAILED"
        )
        line = build_minimal_provider_failure_line(
            provider,
            model,
            effort,
            stable_id="E_EXTERNAL_PROVIDER_TERMINAL_BUILD_FAILED",
            cancelled=cancelled,
            timed_out=timed_out,
            cleanup_status=outcome.cleanup_status,
            cleanup_issue_count=outcome.cleanup_issue_count,
            recovery_retained=outcome.recovery_retained,
        )

    try:
        serialized_scan = provider_output_safety_scan_terminal(
            provider,
            credential_needles,
            stdout=line.encode("utf-8", errors="strict"),
            stderr=b"",
            serialized_line=True,
        )
    except Exception:
        serialized_scan = "E_EXTERNAL_PROVIDER_OUTPUT_SCAN_UNAVAILABLE"
    if serialized_scan is not None:
        result_text = ""
        public_stream = None
        terminal_outcome = serialized_safety_failure_outcome(outcome, serialized_scan)
        line = build_minimal_provider_failure_line(
            provider,
            model,
            effort,
            stable_id=serialized_scan,
            cancelled=cancelled,
            timed_out=timed_out,
            cleanup_status=outcome.cleanup_status,
            cleanup_issue_count=outcome.cleanup_issue_count,
            recovery_retained=outcome.recovery_retained,
        )

    try:
        terminal_receipt.commit(line.encode("utf-8", errors="strict"))
    except (OSError, ValueError) as exc:
        print(
            f"FAIL: terminal receipt commit failed: {type(exc).__name__}",
            file=sys.stderr,
        )
        return terminal_outcome.exit_code if terminal_outcome.exit_code != 0 else 1
    reserved_run.mark_finalized()

    try:
        sys.stdout.write(line)
        sys.stdout.flush()
    except Exception:
        print("FAIL: E_EXTERNAL_PROVIDER_RESULT_STDOUT_FAILED", file=sys.stderr)
        return terminal_outcome.exit_code if terminal_outcome.exit_code != 0 else 1

    if control.ledger:
        try:
            recorded = record_terminal(
                control,
                provider,
                model,
                effort,
                slug,
                launch_run_id,
                terminal_outcome,
                cancelled=cancelled,
                timed_out=timed_out,
                result_delivered=True,
                realization=realization,
                runner=runner,
                role_provenance=frozen_role,
                provenance=provenance,
                expected_provenance=provenance,
                child_nonzero_category=child_nonzero_category,
                launch_flags=launch_flags,
            )
        except Exception:
            recorded = False
        if not recorded:
            print("FAIL: E_EXTERNAL_TERMINAL_LEDGER_APPEND_FAILED", file=sys.stderr)
            return terminal_outcome.exit_code if terminal_outcome.exit_code != 0 else 1
    return terminal_outcome.exit_code


def launch(provider: str, argv: list[str]) -> int:
    """Provider-launch composition root and sole owner of the injected runner."""

    try:
        if provider in POLICY_BOUND_EXTERNAL_PROVIDERS:
            prevalidated = _prevalidate_policy_bound_external_launch(provider, argv)
        else:
            unavailable = EXTERNAL_UNAVAILABLE_IDS.get(provider)
            if unavailable is not None:
                return fail(f"{unavailable}: provider execution is unavailable")
            control = parse_control(argv)
            topic = validate_topic(control.topic)
            flags, model, effort = resolved_profile(provider, control.provider_flags)
            if control.ledger_closes:
                return fail(
                    "E_EXTERNAL_CLOSES_FORBIDDEN: external provider results cannot close ledger runs"
                )
            role_provenance = external_role_provenance(control, provider)
            prevalidated = PolicyBoundLaunch(
                control,
                topic,
                tuple(flags),
                model,
                effort,
                role_provenance,
                None,
            )
        if provider == "kimi" and os.name != "nt":
            return fail("E_KIMI_WINDOWS_ONLY: Kimi bundle review is Windows-only")
        if prevalidated.control.terminal_receipt is None:
            return fail("--terminal-receipt is required for external launches")
        receipt = TerminalReceiptV1.reserve(prevalidated.control.terminal_receipt)
    except ValueError as exc:
        return fail(str(exc))

    with ReservedExternalRunV1(receipt) as reserved_run:
        try:
            with ProcessRunnerV1() as runner:
                return _launch_with_runner(
                    provider,
                    argv,
                    runner,
                    prevalidated=prevalidated,
                    reserved_run=reserved_run,
                )
        except KeyboardInterrupt:
            if receipt.committed:
                return 130
            return finalize_reserved_run_once(
                replace(prevalidated.control, ledger=None),
                provider,
                prevalidated.model,
                prevalidated.effort,
                prevalidated.topic,
                "",
                reserved_run,
                130,
                cancelled=True,
                role_provenance=prevalidated.role_provenance,
                provenance=prevalidated.provenance,
                launch_flags=(
                    prevalidated.provenance.launch_flags
                    if prevalidated.provenance is not None
                    else prevalidated.flags
                ),
                stable_failure_id="E_EXTERNAL_PROVIDER_CANCELLED",
            )
        except Exception:
            if receipt.committed:
                return 1
            return finalize_reserved_run_once(
                replace(prevalidated.control, ledger=None),
                provider,
                prevalidated.model,
                prevalidated.effort,
                prevalidated.topic,
                "",
                reserved_run,
                1,
                role_provenance=prevalidated.role_provenance,
                provenance=prevalidated.provenance,
                launch_flags=(
                    prevalidated.provenance.launch_flags
                    if prevalidated.provenance is not None
                    else prevalidated.flags
                ),
                stable_failure_id="E_EXTERNAL_PROCESS_RUNNER_UNAVAILABLE",
            )


def kimi_main(argv: list[str]) -> int:
    """Route Kimi maintenance modes locally; all other arguments remain launches."""

    maintenance_flags = {
        "--enroll-executable",
        "--replace-kimi-enrollment",
        "--verify-enrollment",
    }
    selected = maintenance_flags.intersection(argv)
    if not selected:
        return launch("kimi", argv)
    if argv == ["--enroll-executable"]:
        try:
            home = _kimi_user_home()
            enroll_kimi_executable(home, _kimi_runtime_root(), dry_run=False)
        except ValueError as exc:
            return fail(str(exc))
        print("KIMI-EXECUTABLE-ENROLLMENT: PASS")
        return 0
    if argv == ["--replace-kimi-enrollment"]:
        try:
            home = _kimi_user_home()
            replace_kimi_enrollment(home, _kimi_runtime_root(), dry_run=False)
        except ValueError as exc:
            return fail(str(exc))
        print("KIMI-EXECUTABLE-REPLACEMENT: PASS")
        return 0
    if argv == ["--verify-enrollment"]:
        try:
            command = verify_kimi_enrollment()
        except ValueError as exc:
            return fail(str(exc))
        print(f"KIMI-EXECUTABLE-ENROLLMENT: PASS path={command[0]}")
        return 0
    return fail("E_KIMI_MAINTENANCE_ARGUMENTS_INVALID")


def _requires_early_native_windows_refusal(provider: str) -> bool:
    return os.name == "nt" and provider in {"codex", "claude"}


def _resolve_launch_provider_command(
    provider: str, query_cwd: Path
) -> tuple[list[str], ExecutableBindingV1 | None]:
    if provider == "kimi":
        return _resolve_enrolled_kimi_launch()
    resolution = resolve_provider_command(provider)
    if resolution is not None:
        _reject_repository_path_discovery(resolution, query_cwd)
        return list(resolution.command), None
    key = {"codex": "CODEX_BIN", "claude": "CLAUDE_BIN"}.get(
        provider, "PROVIDER_BIN"
    )
    raise ValueError(
        f"{provider} binary '{os.environ.get(key) or provider}' not found on PATH. "
        f"Set {key} if installed elsewhere."
    )


def _launch_with_runner(
    provider: str,
    argv: list[str],
    runner: ProcessRunnerV1,
    *,
    prevalidated: PolicyBoundLaunch,
    reserved_run: ReservedExternalRunV1,
) -> int:
    control = prevalidated.control
    topic = prevalidated.topic
    flags = list(prevalidated.flags)
    model = prevalidated.model
    effort = prevalidated.effort
    role_provenance = prevalidated.role_provenance
    provenance = prevalidated.provenance
    launch_flags = provenance.launch_flags if provenance is not None else tuple(flags)

    def reserved_failure(stable_id: str, *, code: int = 1) -> int:
        print(f"FAIL: {stable_id}", file=sys.stderr)
        return finalize_reserved_run_once(
            replace(control, ledger=None),
            provider,
            model,
            effort,
            topic,
            "",
            reserved_run,
            code,
            stable_failure_id=stable_id,
        )

    try:
        query_cwd = Path.cwd().resolve(strict=True)
        command, expected_executable_binding = _resolve_launch_provider_command(
            provider, query_cwd
        )
    except Exception as exc:
        return reserved_failure(
            stable_failure_id_from_exception(
                exc, "E_EXTERNAL_PROVIDER_COMMAND_UNAVAILABLE"
            )
        )

    if _requires_early_native_windows_refusal(provider):
        executable = Path(command[0])
        try:
            identity_available = (
                executable.is_absolute()
                and executable.is_file()
                and bool(resolve_executable_identity(executable))
            )
        except Exception:
            identity_available = False
        if identity_available and len(command) == 1:
            return reserved_failure(E_EXTERNAL_PROVIDER_WINDOWS_NATIVE_ARGV_UNAVAILABLE)

    try:
        auth_configuration = resolve_provider_auth_configuration(provider)
    except ClaudeSubscriptionRefusal:
        print(
            "WARNING: Refusing automated Claude launch.\n"
            "Automated `claude -p` under a subscription is not permitted.\n"
            "Anthropic policy: https://code.claude.com/docs/en/legal-and-compliance\n\n"
            "Use commercial authentication with ANTHROPIC_API_KEY or "
            "ANTHROPIC_AUTH_TOKEN.",
            file=sys.stderr,
        )
        return reserved_failure("E_EXTERNAL_PROVIDER_AUTH_REFUSED", code=3)
    except Exception as exc:
        return reserved_failure(
            stable_failure_id_from_exception(
                exc, "E_EXTERNAL_PROVIDER_AUTH_UNAVAILABLE"
            )
        )
    if (
        provider != "kimi"
        and (
            auth_configuration.output_scan_disposition
            != AUTH_OUTPUT_SCAN_ENVIRONMENT_EXACT
            or not auth_configuration.needles
        )
    ):
        return reserved_failure("E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE")

    try:
        body = assemble_external_prompt(prompt_bytes(control, external=True))
    except Exception as exc:
        return reserved_failure(
            stable_failure_id_from_exception(exc, "E_EXTERNAL_PROMPT_INVALID")
        )

    kimi_agent_payload: bytes | None = None
    if provider == "kimi":
        try:
            kimi_agent_payload = prepare_kimi_agent_payload(body)
        except Exception as exc:
            return reserved_failure(
                stable_failure_id_from_exception(exc, "E_KIMI_BUNDLE_INVALID")
            )

    if provider == "codex":
        if not Path(command[0]).is_absolute() or not Path(command[0]).is_file():
            return reserved_failure("E_EXTERNAL_PROVIDER_EXECUTABLE_INVALID")
        codex_home = Path(
            os.environ.get("CODEX_HOME") or Path.home() / ".codex"
        ).expanduser().resolve(strict=False)
        try:
            trust_result = require_codex_hook_trust(
                runner, command, codex_home, query_cwd
            )
        except Exception:
            return reserved_failure("E_EXTERNAL_PROVIDER_HOOK_TRUST")
        if trust_result:
            return reserved_failure("E_EXTERNAL_PROVIDER_HOOK_TRUST", code=trust_result)

    lifecycle: RunCaptureLifecycle | None = None
    lifecycle_initialized = False
    realization: dict[str, str] | None = None
    try:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = f"{topic}-{timestamp}-{secrets.token_hex(4)}"
        lifecycle = RunCaptureLifecycle.create(provider, slug)
        reserved_run.adopt_lifecycle(lifecycle)
        lifecycle.initialize(body)
        reserved_run.mark_initialized(lifecycle)
        lifecycle_initialized = True
    except Exception:
        if lifecycle is None:
            return reserved_failure("E_EXTERNAL_CAPTURE_SETUP")
        return finalize_reserved_run_once(
            replace(control, ledger=None),
            provider,
            model,
            effort,
            topic,
            "",
            reserved_run,
            1,
            launch_error="E_EXTERNAL_CAPTURE_SETUP",
            credential_needles=auth_configuration.needles,
            auth_output_scan_disposition=auth_configuration.output_scan_disposition,
            runner=runner,
            role_provenance=role_provenance,
            provenance=provenance,
            launch_flags=launch_flags,
        )

    assert lifecycle is not None

    launch_run_id = ""
    if control.ledger:
        try:
            helper_available = ledger_helper() is not None
        except Exception:
            helper_available = False
        if not helper_available:
            return finalize_reserved_run_once(
                replace(control, ledger=None), provider, model, effort, slug, "", reserved_run, 1,
                launch_error="E_EXTERNAL_LEDGER_HELPER_UNAVAILABLE", realization=realization, runner=runner,
                role_provenance=role_provenance, provenance=provenance,
                launch_flags=launch_flags,
            )
        launch_run_id = (
            provenance.external_dispatch_id
            if provenance is not None
            else datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + f"-launch-{slug}"
        )
        launch_args = [
            "--work-item",
            control.ledger,
            "append",
            "--run-id",
            launch_run_id,
            *(
                ["--work-item-name", provenance.work_item]
                if provenance is not None
                else []
            ),
            "--status",
            "running",
            "--gate",
            "none",
            "--event-kind",
            "launch",
            "--notes",
            "wrapper-dispatched; terminal result is returned by the provider envelope",
            *ledger_common(
                control,
                provider,
                model,
                effort,
                slug,
                role_provenance=role_provenance,
                provenance=provenance,
                launch_flags=launch_flags,
            ),
        ]
        try:
            launch_recorded = run_ledger(runner, launch_args)
        except Exception:
            launch_recorded = False
        if not launch_recorded:
            return finalize_reserved_run_once(
                replace(control, ledger=None), provider, model, effort, slug, "", reserved_run, 1,
                launch_error="E_EXTERNAL_LAUNCH_LEDGER_FAILED", realization=realization, runner=runner,
                role_provenance=role_provenance, provenance=provenance,
                launch_flags=launch_flags,
            )

    kimi_agent: Path | None = None
    kimi_skills: Path | None = None
    if provider == "kimi":
        try:
            assert kimi_agent_payload is not None
            kimi_agent, kimi_skills = materialize_kimi_agent_payload(
                kimi_agent_payload, lifecycle.run_dir
            )
        except Exception:
            return finalize_reserved_run_once(
                control, provider, model, effort, slug, launch_run_id, reserved_run, 1,
                launch_error="E_KIMI_BUNDLE_MATERIALIZATION", realization=realization, runner=runner,
                role_provenance=role_provenance, provenance=provenance,
                launch_flags=launch_flags,
            )
    provider_args = (
        [
            "exec",
            "--skip-git-repo-check",
            "--json",
            *flags,
        ]
        if provider == "codex"
        else kimi_provider_args(kimi_agent, kimi_skills)
        if provider == "kimi"
        else flags
    )
    child_environment = dict(auth_configuration.child_environment)
    if provider == "claude":
        child_environment["ORCHESTRARIUM_DISPATCHED_REVIEW"] = "1"
    elif provider == "codex":
        child_environment["CODEX_HOME"] = str(codex_home)

    exit_code = 1
    launch_error: str | None = None
    interrupted = False
    timed_out = False
    stream_result: StreamCaptureResult | None = None
    raw_stdout: bytes | None = None
    raw_stderr: bytes | None = None
    process_result: ProcessResultV1 | None = None
    try:
        process_result, raw_stdout, raw_stderr = run_provider_process(
            runner,
            command,
            provider_args,
            child_environment,
            lifecycle.run_dir if provider == "kimi" else query_cwd,
            None if provider == "kimi" else body,
            control,
            provider,
            expected_executable_binding=expected_executable_binding,
        )
        stream_result = provider_stream_result(process_result)
        if process_result.target_exit_code is not None:
            exit_code = process_result.target_exit_code
        interrupted = process_result.cancelled
        timed_out = process_result.timed_out
        if process_result.failure_id is not None:
            launch_error = (
                f"{provider} process supervision failed: {process_result.failure_id}"
            )
            if exit_code == 0:
                exit_code = 1
    except KeyboardInterrupt:
        interrupted = True
        launch_error = f"{provider} process supervision cancelled"
        exit_code = 130
    except Exception as exc:
        launch_error = f"{provider} launch failed: {type(exc).__name__}"
        exit_code = 1
    if stream_result is not None and stream_result.issues:
        detail = "; ".join(stream_result.issues)[:512]
        launch_error = f"{launch_error + '; ' if launch_error else ''}stream capture incomplete: {detail}"
        if exit_code == 0:
            exit_code = 1
    return finalize_reserved_run_once(
        control,
        provider,
        model,
        effort,
        slug,
        launch_run_id,
        reserved_run,
        exit_code,
        stream_result,
        cancelled=interrupted,
        timed_out=timed_out,
        launch_error=launch_error,
        realization=realization,
        credential_needles=auth_configuration.needles,
        auth_output_scan_disposition=auth_configuration.output_scan_disposition,
        role_provenance=role_provenance,
        provenance=provenance,
        raw_stdout=raw_stdout,
        raw_stderr=raw_stderr,
        process_result=process_result,
        runner=runner,
        launch_flags=launch_flags,
    )
