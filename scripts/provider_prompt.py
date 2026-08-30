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
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
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
        SettlePolicyV1,
        kimi_release_bindings,
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
        SettlePolicyV1,
        kimi_release_bindings,
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
KIMI_EXECUTABLE_BINDING_SCHEMA_V1 = "orchestrarium.kimi-executable-binding.v1"
KIMI_EXECUTABLE_BINDING_FILENAME_V1 = "executable-binding-v1.json"
KIMI_EXECUTABLE_REPLACEMENT_LOCK_FILENAME_V1 = ".kimi-binding.replace.lock"
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

    @staticmethod
    def _windows_current_user_security_descriptor():
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
        kernel32.CloseHandle.restype = wintypes.BOOL
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
        advapi32.OpenProcessToken.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.HANDLE),
        ]
        advapi32.OpenProcessToken.restype = wintypes.BOOL
        advapi32.GetTokenInformation.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        advapi32.GetTokenInformation.restype = wintypes.BOOL
        advapi32.ConvertSidToStringSidW.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.LPWSTR),
        ]
        advapi32.ConvertSidToStringSidW.restype = wintypes.BOOL
        advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.POINTER(ctypes.c_void_p),
            ctypes.POINTER(wintypes.DWORD),
        ]
        advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = wintypes.BOOL
        token = wintypes.HANDLE()
        if not advapi32.OpenProcessToken(
            kernel32.GetCurrentProcess(), TOKEN_QUERY, ctypes.byref(token)
        ):
            raise OSError(ctypes.get_last_error(), "OpenProcessToken")
        sid_text = wintypes.LPWSTR()
        try:
            size = wintypes.DWORD()
            advapi32.GetTokenInformation(token, TOKEN_USER_CLASS, None, 0, ctypes.byref(size))
            if not size.value:
                raise OSError(ctypes.get_last_error(), "GetTokenInformation(size)")
            buffer = ctypes.create_string_buffer(size.value)
            if not advapi32.GetTokenInformation(
                token, TOKEN_USER_CLASS, buffer, size, ctypes.byref(size)
            ):
                raise OSError(ctypes.get_last_error(), "GetTokenInformation")
            token_user = ctypes.cast(buffer, ctypes.POINTER(TOKEN_USER)).contents
            if not advapi32.ConvertSidToStringSidW(token_user.User.Sid, ctypes.byref(sid_text)):
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
        return descriptor, sddl

    @staticmethod
    def _windows_verify_dacl(handle: int, expected_sddl: str) -> None:
        import ctypes
        from ctypes import wintypes

        DACL_SECURITY_INFORMATION = 0x00000004
        SE_FILE_OBJECT = 1
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree.restype = ctypes.c_void_p
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
                raise OSError("terminal receipt DACL mismatch")
        finally:
            if rendered:
                kernel32.LocalFree(rendered)
            if descriptor:
                kernel32.LocalFree(descriptor)

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
            descriptor, expected_sddl = cls._windows_current_user_security_descriptor()
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
            cls._windows_verify_dacl(leaf, expected_sddl)
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


def _kimi_binding_path() -> Path:
    return _kimi_runtime_root() / KIMI_EXECUTABLE_BINDING_FILENAME_V1


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


def _observe_kimi_executable(
    path: Path, failure_id: str, *, require_current: bool = False
) -> dict[str, object]:
    try:
        accepted_bindings = kimi_release_bindings(KimiWindowsProfileV1)
        validate_no_reparse_components(path)
        before = path.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or _metadata_is_reparse(before)
            or before.st_size not in {size for size, _digest in accepted_bindings}
        ):
            raise OSError("Kimi executable metadata")
        digest = hashlib.sha256()
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
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
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        ) != (
            before.st_dev,
            before.st_ino,
            before.st_size,
            before.st_mtime_ns,
        ):
            raise OSError("Kimi executable drift")
        observed_sha256 = digest.hexdigest()
        observed_binding = (before.st_size, observed_sha256)
        if not any(
            observed_binding[0] == size
            and secrets.compare_digest(observed_binding[1], accepted)
            for size, accepted in accepted_bindings
        ):
            raise OSError("Kimi executable digest")
        if require_current and not (
            observed_binding[0] == accepted_bindings[0][0]
            and secrets.compare_digest(observed_binding[1], accepted_bindings[0][1])
        ):
            raise OSError("Kimi executable is not the current release")
        return {
            "schema": KIMI_EXECUTABLE_BINDING_SCHEMA_V1,
            "path": str(path),
            "size": before.st_size,
            "sha256": observed_sha256,
        }
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValueError(failure_id) from exc


def enroll_kimi_executable(
    home: Path, runtime_root: Path, *, dry_run: bool
) -> None:
    """Create the fixed Kimi continuity pin without launching the provider."""

    executable = _fixed_kimi_executable(home)
    observed = _observe_kimi_executable(
        executable, "E_KIMI_ENROLLMENT_INVALID: observed release binding"
    )
    pin = Path(os.path.abspath(runtime_root)) / KIMI_EXECUTABLE_BINDING_FILENAME_V1
    if not runtime_root.is_absolute() or pin.parent != runtime_root:
        raise ValueError("E_KIMI_ENROLLMENT_INVALID: pin root")
    payload = json.dumps(
        observed, sort_keys=True, separators=(",", ":")
    ).encode("utf-8") + b"\n"
    if os.path.lexists(pin):
        try:
            validate_no_reparse_components(pin)
            metadata = pin.lstat()
            if (
                not stat.S_ISREG(metadata.st_mode)
                or stat.S_ISLNK(metadata.st_mode)
                or _metadata_is_reparse(metadata)
            ):
                raise OSError("existing pin")
            existing = pin.read_bytes()
        except (OSError, ValueError) as exc:
            raise ValueError("E_KIMI_ENROLLMENT_INVALID: existing pin") from exc
        if existing == payload:
            print("  Kimi executable enrollment is exact and left byte-exact")
            return
        raise ValueError(
            "E_KIMI_ENROLLMENT_DRIFT: re-enrollment requires explicit replacement workflow"
        )
    if dry_run:
        print("  [dry-run] Kimi executable enrollment would create local continuity pin")
        return
    pin.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        validate_no_reparse_components(pin.parent)
    except (OSError, ValueError) as exc:
        raise ValueError("E_KIMI_ENROLLMENT_INVALID: pin root") from exc
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".kimi-binding.", suffix=".tmp", dir=pin.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, pin)
        except FileExistsError as exc:
            raise ValueError(
                "E_KIMI_ENROLLMENT_DRIFT: re-enrollment requires explicit replacement workflow"
            ) from exc
        except OSError as exc:
            raise ValueError("E_KIMI_ENROLLMENT_INVALID: pin create") from exc
    finally:
        temporary.unlink(missing_ok=True)
    if pin.read_bytes() != payload:
        raise ValueError("E_KIMI_ENROLLMENT_POSTCONDITION")


def _validated_kimi_binding_values(
    data: object, fixed_executable: Path
) -> tuple[int, str]:
    if not isinstance(data, dict):
        raise ValueError("E_KIMI_EXECUTABLE_BINDING_DRIFT")
    path = Path(data["path"])
    size = int(data["size"])
    digest = str(data["sha256"]).lower()
    accepted = kimi_release_bindings(KimiWindowsProfileV1)
    if (
        data.get("schema") != KIMI_EXECUTABLE_BINDING_SCHEMA_V1
        or not path.is_absolute()
        or Path(os.path.abspath(path)) != path
        or path != fixed_executable
        or path.name.casefold() != "kimi.exe"
        or not any(
            size == accepted_size
            and secrets.compare_digest(digest, accepted_digest)
            for accepted_size, accepted_digest in accepted
        )
    ):
        raise ValueError("E_KIMI_EXECUTABLE_BINDING_DRIFT")
    return size, digest


def _read_kimi_binding_snapshot(
    pin: Path,
    fixed_executable: Path,
    *,
    validation_failure_id: str = "E_KIMI_ENROLLMENT_INVALID: existing pin",
) -> tuple[bytes, tuple[int, int, int, int], tuple[int, str]]:
    """Read one ordinary pin through an identity-bound handle."""

    try:
        validate_no_reparse_components(pin)
        before = pin.lstat()
        if (
            not stat.S_ISREG(before.st_mode)
            or stat.S_ISLNK(before.st_mode)
            or _metadata_is_reparse(before)
            or before.st_size > 4096
        ):
            raise OSError("Kimi binding metadata")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(pin, flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino, opened.st_size) != (
                before.st_dev,
                before.st_ino,
                before.st_size,
            ):
                raise OSError("Kimi binding identity")
            payload = stream.read(4097)
        after = pin.lstat()
        identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        if identity != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns):
            raise OSError("Kimi binding drift")
        data = json.loads(payload.decode("utf-8"))
    except (OSError, ValueError, KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("E_KIMI_ENROLLMENT_INVALID: existing pin") from exc
    try:
        size, digest = _validated_kimi_binding_values(data, fixed_executable)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(validation_failure_id) from exc
    return payload, identity, (size, digest)


def _write_kimi_binding_temporary(parent: Path, prefix: str, payload: bytes) -> Path:
    descriptor, temporary_name = tempfile.mkstemp(prefix=prefix, suffix=".tmp", dir=parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    return temporary


def replace_kimi_enrollment(
    home: Path, runtime_root: Path, *, dry_run: bool
) -> None:
    """Atomically rotate one accepted rollback pin to the current release."""

    executable = _fixed_kimi_executable(home)
    observed = _observe_kimi_executable(
        executable,
        "E_KIMI_ENROLLMENT_INVALID: current release binding",
        require_current=True,
    )
    root = Path(os.path.abspath(runtime_root))
    pin = root / KIMI_EXECUTABLE_BINDING_FILENAME_V1
    if not runtime_root.is_absolute() or pin.parent != runtime_root:
        raise ValueError("E_KIMI_ENROLLMENT_INVALID: pin root")
    payload = json.dumps(observed, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
    existing, existing_identity, existing_binding = _read_kimi_binding_snapshot(
        pin, executable
    )
    accepted = kimi_release_bindings(KimiWindowsProfileV1)
    if existing == payload:
        print("  Kimi executable enrollment is current and left byte-exact")
        return
    if not any(
        existing_binding[0] == size
        and secrets.compare_digest(existing_binding[1], digest)
        for size, digest in accepted[1:]
    ):
        raise ValueError("E_KIMI_ENROLLMENT_DRIFT: replacement requires accepted rollback pin")
    if dry_run:
        print("  [dry-run] Kimi executable enrollment would rotate rollback pin to current release")
        return

    lock = root / KIMI_EXECUTABLE_REPLACEMENT_LOCK_FILENAME_V1
    lock_descriptor: int | None = None
    lock_identity: tuple[int, int] | None = None
    candidate: Path | None = None
    backup: Path | None = None
    replaced = False
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        try:
            lock_descriptor = os.open(lock, flags, 0o600)
        except FileExistsError as exc:
            raise ValueError("E_KIMI_ENROLLMENT_BUSY") from exc
        with os.fdopen(lock_descriptor, "wb") as stream:
            lock_descriptor = None
            stream.write(b"orchestrarium-kimi-enrollment-replacement-v1\n")
            stream.flush()
            os.fsync(stream.fileno())
            locked = os.fstat(stream.fileno())
            lock_identity = (locked.st_dev, locked.st_ino)

        current, current_identity, current_binding = _read_kimi_binding_snapshot(
            pin, executable
        )
        if (
            current != existing
            or current_identity != existing_identity
            or current_binding != existing_binding
        ):
            raise ValueError("E_KIMI_ENROLLMENT_DRIFT: pin changed during replacement")
        reobserved = _observe_kimi_executable(
            executable,
            "E_KIMI_ENROLLMENT_INVALID: current release changed during replacement",
            require_current=True,
        )
        if reobserved != observed:
            raise ValueError("E_KIMI_ENROLLMENT_DRIFT: executable changed during replacement")
        candidate = _write_kimi_binding_temporary(root, ".kimi-binding.candidate.", payload)
        backup = _write_kimi_binding_temporary(root, ".kimi-binding.rollback.", existing)
        os.replace(candidate, pin)
        candidate = None
        replaced = True
        committed, _identity, committed_binding = _read_kimi_binding_snapshot(pin, executable)
        if committed != payload or committed_binding != accepted[0]:
            raise OSError("Kimi replacement postcondition")
        committed_executable = _observe_kimi_executable(
            executable,
            "E_KIMI_ENROLLMENT_INVALID: current release changed after replacement",
            require_current=True,
        )
        if committed_executable != observed:
            raise OSError("Kimi replacement executable postcondition")
        current_lock = lock.lstat()
        if (current_lock.st_dev, current_lock.st_ino) != lock_identity:
            raise OSError("Kimi replacement lock identity")
        lock.unlink()
        lock_identity = None
    except (OSError, TypeError, UnicodeError, ValueError) as exc:
        if not replaced and isinstance(exc, ValueError):
            raise
        if replaced and backup is not None:
            try:
                os.replace(backup, pin)
                backup = None
                restored, _identity, restored_binding = _read_kimi_binding_snapshot(
                    pin, executable
                )
                if restored != existing or restored_binding != existing_binding:
                    raise OSError("Kimi rollback postcondition")
            except (OSError, ValueError, TypeError, UnicodeError) as rollback_exc:
                raise ValueError("E_KIMI_ENROLLMENT_ROLLBACK_FAILED") from rollback_exc
        raise ValueError("E_KIMI_ENROLLMENT_REPLACE_FAILED") from exc
    finally:
        if lock_descriptor is not None:
            os.close(lock_descriptor)
        if candidate is not None:
            candidate.unlink(missing_ok=True)
        if backup is not None:
            backup.unlink(missing_ok=True)
        if lock_identity is not None:
            try:
                current_lock = lock.lstat()
                if (current_lock.st_dev, current_lock.st_ino) == lock_identity:
                    lock.unlink()
            except OSError:
                pass


def _resolve_enrolled_kimi_launch() -> tuple[list[str], ExecutableBindingV1]:
    try:
        binding_path = _kimi_binding_path()
        fixed_path = _fixed_kimi_executable(_kimi_user_home())
        _payload, _identity, (size, digest) = _read_kimi_binding_snapshot(
            binding_path,
            fixed_path,
            validation_failure_id="E_KIMI_EXECUTABLE_BINDING_DRIFT",
        )
        if fixed_path.stat().st_size != size:
            raise ValueError("E_KIMI_EXECUTABLE_BINDING_DRIFT")
        binding = ExecutableBindingV1(str(fixed_path), size, digest)
        return [str(fixed_path)], binding
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        if str(exc) == "E_KIMI_EXECUTABLE_BINDING_DRIFT":
            raise
        raise ValueError(
            "E_KIMI_EXECUTABLE_BINDING_INVALID: run " + _kimi_enrollment_command()
        ) from exc


def resolve_enrolled_kimi_command() -> list[str]:
    command, _binding = _resolve_enrolled_kimi_launch()
    return command


def verify_kimi_enrollment() -> list[str]:
    command, expected = _resolve_enrolled_kimi_launch()
    observed = _observe_kimi_executable(
        Path(command[0]), "E_KIMI_EXECUTABLE_BINDING_DRIFT"
    )
    if (
        observed["size"] != expected.size
        or not secrets.compare_digest(str(observed["sha256"]), expected.sha256)
    ):
        raise ValueError("E_KIMI_EXECUTABLE_BINDING_DRIFT")
    return command


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
            opened = os.fstat(stream.fileno())
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise ValueError("E_EXTERNAL_PROMPT_INVALID: prompt identity changed")
            data = stream.read(PROMPT_SNAPSHOT_MAX_BYTES + 1)
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
        run_dir = Path(tempfile.mkdtemp(prefix=f"{slug}-", dir=root))
        try:
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
            "Use commercial authentication (ANTHROPIC_API_KEY, "
            "ANTHROPIC_AUTH_TOKEN, Amazon Bedrock, or Google "
            "Vertex AI), or explicitly set ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE=1.",
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
