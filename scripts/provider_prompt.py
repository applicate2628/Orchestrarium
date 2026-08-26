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
        ProcessRequestV1,
        ProcessResultV1,
        ProcessRunnerV1,
        SettlePolicyV1,
        resolve_executable_identity,
    )
except ModuleNotFoundError:
    from scripts.process_supervision.process_runner import (
        CapturePolicyV1,
        EnvironmentRowV1,
        ProcessRequestV1,
        ProcessResultV1,
        ProcessRunnerV1,
        SettlePolicyV1,
        resolve_executable_identity,
    )

EFFORTS = frozenset({"low", "medium", "high", "xhigh", "max"})
ERROR_MARKER = re.compile(
    r"^([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(\.[0-9]+)?Z? )?(ERROR|FATAL|API Error)"
    r"(: | [A-Za-z0-9_]+(::[A-Za-z0-9_]+)*: )"
)
INVALID_SLUG = re.compile(r'[\\/:\*\?"<>\|\x00]')
RESULT_MAX_BYTES_DEFAULT = 1024 * 1024
RESULT_MAX_BYTES_HARD = 16 * 1024 * 1024
CAPTURE_MAX_BYTES_DEFAULT = 16 * 1024 * 1024
CAPTURE_MAX_BYTES_HARD = 256 * 1024 * 1024
STDERR_SCAN_MAX_BYTES = 64 * 1024
RESULT_PREFIX = "ORCHESTRARIUM_PROVIDER_RESULT_V2="
E_EXTERNAL_PROVIDER_WINDOWS_NATIVE_ARGV_UNAVAILABLE = (
    "E_EXTERNAL_PROVIDER_WINDOWS_NATIVE_ARGV_UNAVAILABLE"
)
EXTERNAL_PROVIDER_NAMES = frozenset({"codex", "claude"})
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
    "kimi": "E_KIMI_READINESS_UNVERIFIED",
    "grok": "E_GROK_CONTAINMENT_UNAVAILABLE",
}
EXTERNAL_ROLE_TAXONOMY_NAME = "external-role-taxonomy.v1.json"
EXTERNAL_ROLE_TAXONOMY_MAX_BYTES = 64 * 1024
EXTERNAL_ROLE_TAXONOMY_SHA256 = "c26585be7117568e2e61c3904ddf7192e81eebdc3ab72b29d9cab17e3a7ab647"


@dataclass
class Control:
    topic: str | None = None
    prompt_file: Path | None = None
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
class ExternalRoleProvenance:
    """The caller assignment and actual external adapter lane are distinct facts."""

    assigned_role: str
    execution_role: str


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


@dataclass(frozen=True)
class ClaudeUserSettingsSurface:
    root: Path
    settings_path: Path
    forwarded_config_dir: str | None


class ResultMaterializationError(RuntimeError):
    pass


class ClaudeSubscriptionRefusal(ValueError):
    pass


def fail(message: str, code: int = 1) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return code


def parse_control(argv: list[str], *, external: bool = False) -> Control:
    result = Control()
    seen_values: dict[str, object] = {}
    value_flags = {
        "-promptfile": "prompt_file",
        "--prompt-file": "prompt_file",
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
            if attr == "prompt_file":
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


def resolved_profile(provider: str, flags: list[str]) -> tuple[list[str], str, str]:
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
    model = ""
    effort = ""
    for index, token in enumerate(flags):
        following = flags[index + 1] if index + 1 < len(flags) else ""
        if token == "--model" and following and not following.startswith("-"):
            model = following
        if provider == "codex" and token == "-c":
            matched = re.fullmatch(
                r'model_reasoning_effort="?(low|medium|high|xhigh|max)"?',
                following,
            )
            if matched:
                effort = matched.group(1)
        elif provider == "claude" and token == "--effort" and following in EFFORTS:
            effort = following
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
    if provider == "claude":
        flags = [*flags, "--setting-sources", "user"]
    return flags, model, effort


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
        if len(mapping) != 33 or any(
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


def _command_from_path(path: str) -> list[str] | None:
    candidate = Path(path).expanduser()
    resolved = str(candidate.resolve()) if candidate.is_file() else shutil.which(path)
    if not resolved:
        return None
    suffix = Path(resolved).suffix.lower()
    if suffix == ".py":
        return [sys.executable, resolved]
    if suffix in {".ps1", ".cmd", ".bat", ".sh"}:
        return None
    return [resolved]


def resolve_provider_command(provider: str) -> list[str] | None:
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
            command = _command_from_path(name)
            if command:
                return command
    return None


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
    return ProviderAuthConfiguration(mode, child, tuple(needles))


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
) -> list[str]:
    external = provider in EXTERNAL_PROVIDER_NAMES
    provenance = external_role_provenance(control, provider) if external else None
    execution_role = provenance.execution_role if provenance is not None else "external-reviewer"
    ledger_effort = "high" if effort == "unsupported" else effort
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
        ledger_effort,
    ]
    if control.ledger_lane:
        values += ["--lane", control.ledger_lane]
    if control.ledger_artifact:
        values += ["--artifact", control.ledger_artifact]
    if external:
        values += ["--assigned-role", provenance.assigned_role]
    return values


def external_terminal_ledger_args(
    control: Control,
    provider: str,
    model: str,
    effort: str,
    slug: str,
    realization: dict[str, object] | None,
) -> list[str]:
    common = [
        "--terminal-class", "external-nonauthorizing",
        "--authorizing", "false",
        "--actual-execution-path", "direct-external-cli",
    ]
    if realization is not None:
        raise ValueError("E_EXTERNAL_LEDGER_UNVERIFIED: unexpected provider realization")
    values = list(common)
    if control.ledger_artifact:
        values += ["--artifact-identity", control.ledger_artifact]
    return values


def _final_nonblank_line(text: str) -> str:
    lines = [line.rstrip("\r") for line in text.splitlines() if line.strip()]
    return lines[-1] if lines else ""


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
    if executable.resolve() == Path(sys.executable).resolve():
        return "python-validator-json-echo-v1"
    return None


def run_provider_process(
    runner: ProcessRunnerV1,
    command: list[str],
    provider_args: list[str],
    child_environment: dict[str, str],
    query_cwd: Path,
    body: bytes,
    control: Control,
    provider: str | None = None,
) -> tuple[ProcessResultV1, bytes, bytes]:
    """Run one provider through the sole process/tree/I-O lifecycle owner."""

    executable = Path(command[0]).resolve(strict=True)
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
    )
    result = runner.run(request)
    return result, sink.bytes_for("stdout"), sink.bytes_for("stderr")


def provider_stream_result(result: ProcessResultV1) -> StreamCaptureResult:
    stdout, stderr = result.stdout, result.stderr
    digest = hashlib.sha256(
        b"provider-capture-v1\x00" + stdout.digest.encode("ascii")
        + b"\x00" + stderr.digest.encode("ascii")
    ).hexdigest()
    issues = list(result.cleanup_issues)
    if result.failure_id is not None:
        issues.append(result.failure_id)
    if not result.resources_closed or not result.tree.tree_empty:
        issues.append("process-unsettled")
    return StreamCaptureResult(
        overflow=stdout.truncated or stderr.truncated,
        observed_bytes=stdout.observed_bytes + stderr.observed_bytes,
        persisted_bytes=stdout.persisted_bytes + stderr.persisted_bytes,
        digest=digest,
        issues=tuple(dict.fromkeys(issues)),
    )


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


def credential_scan_failure_terminal(
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
    stderr_bytes = (
        stderr if stderr is not None else getattr(lifecycle, "_test_stderr", b"")
    )[:STDERR_SCAN_MAX_BYTES]
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


def with_emit_failure(outcome: FinalOutcome) -> FinalOutcome:
    return FinalOutcome(
        outcome.exit_code if outcome.exit_code != 0 else 1,
        "FAILED:result-emission",
        "blocked",
        "none",
        f"result: envelope emission failed; combined={outcome.token}",
        outcome.primary_exit_code,
        outcome.primary_token,
        outcome.primary_status,
        outcome.primary_gate,
        outcome.primary_note,
        outcome.cleanup_status,
        outcome.cleanup_issue_count,
        outcome.cleanup_diagnostic,
        outcome.recovery_retained,
        outcome.stderr_marker_count,
    )


def emit_provider_result(
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
) -> None:
    frozen_role = role_provenance or ExternalRoleProvenance("none", "none")
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
        "actualExecutionPath": "direct-external-cli",
        "assignedRole": frozen_role.assigned_role,
        "executionRole": frozen_role.execution_role,
    }
    if outcome.cleanup_diagnostic:
        payload["cleanupDiagnostic"] = outcome.cleanup_diagnostic
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
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


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
    return payload


def read_back_external_terminal(
    control: Control, provider: str, launch_run_id: str
) -> dict[str, object] | None:
    """Bind tracked evidence to the durable terminal row, never to a slug-derived id."""

    if not control.ledger or not launch_run_id:
        return None
    try:
        rows = [
            json.loads(line)
            for line in (Path(control.ledger) / "agent-runs.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        ]
    except (OSError, json.JSONDecodeError):
        return None
    matches = [
        row for row in rows
        if isinstance(row, dict)
        and row.get("eventKind") == "terminal"
        and row.get("launchRunId") == launch_run_id
    ]
    if len(matches) != 1:
        return None
    terminal = matches[0]
    if (
        not isinstance(terminal.get("runId"), str)
        or terminal.get("provider") != provider
        or terminal.get("terminalClass") != "external-nonauthorizing"
        or terminal.get("authorizing") is not False
        or terminal.get("closesRunIds") != []
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
) -> bool:
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
        f"stderrMarkers={outcome.stderr_marker_count}"
    )[:1024]
    args = [
        "--work-item",
        control.ledger or "",
        "append",
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
        *ledger_common(control, provider, model, effort, slug),
    ]
    args += external_terminal_ledger_args(
        control, provider, model, effort, slug, realization
    )
    recorded = runner is not None and run_ledger(runner, args)
    if recorded and read_back_external_terminal(control, provider, launch_run_id) is None:
        recorded = False
    if not recorded:
        print(
            f"FAIL: provider result is NOT in the ledger; launch {launch_run_id} "
            "stays unsettled.",
            file=sys.stderr,
        )
    return recorded


def finalize_run(
    control: Control,
    provider: str,
    model: str,
    effort: str,
    slug: str,
    launch_run_id: str,
    lifecycle: RunCaptureLifecycle,
    exit_code: int,
    stream: StreamCaptureResult | None = None,
    *,
    cancelled: bool = False,
    timed_out: bool = False,
    launch_error: str | None = None,
    realization: dict[str, object] | None = None,
    credential_needles: tuple[bytes, ...] = (),
    role_provenance: ExternalRoleProvenance | None = None,
    raw_stdout: bytes | None = None,
    raw_stderr: bytes | None = None,
    process_result: ProcessResultV1 | None = None,
    runner: ProcessRunnerV1 | None = None,
) -> int:
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
    scan_outcome = None
    if credential_needles:
        scan_outcome = (
            credential_scan_terminal(
                credential_needles, stdout=raw_stdout, stderr=raw_stderr
            )
            if raw_streams_settled or process_result is None
            else "E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE"
        )
    if credential_needles and stream is not None and stream.overflow:
        scan_outcome = "E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE"
    if scan_outcome is not None:
        result_text = ""
        terminal = credential_scan_failure_terminal(lifecycle, scan_outcome)
        outcome = settle_once(
            exit_code if exit_code != 0 else 1,
            terminal,
            lifecycle,
            external=True,
        )
    elif stream is not None and stream.overflow:
        result_text = ""
        outcome = settle_once(
            exit_code if exit_code != 0 else 1,
            capture_overflow_terminal(stream),
            lifecycle,
            external=True,
        )
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
            outcome = settle_once(
                exit_code if exit_code != 0 else 1,
                terminal,
                lifecycle,
                external=True,
            )
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
            outcome = settle_once(
                exit_code,
                terminal,
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

    result_delivered = False
    terminal_outcome = outcome
    try:
        emit_provider_result(
            provider,
            model,
            effort,
            result_text,
            outcome,
            stream,
            cancelled=cancelled,
            timed_out=timed_out,
            realization=realization,
            role_provenance=frozen_role,
        )
        result_delivered = True
    except Exception as exc:
        print(f"FAIL: could not emit provider result: {exc}", file=sys.stderr)
        terminal_outcome = with_emit_failure(outcome)

    ledger_failed = False
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
                result_delivered=result_delivered,
                realization=realization,
                runner=runner,
            )
        except Exception as exc:
            recorded = False
            print(f"FAIL: terminal ledger append raised: {exc}", file=sys.stderr)
        if not recorded:
            ledger_failed = True

    if not result_delivered:
        return terminal_outcome.exit_code if terminal_outcome.exit_code != 0 else 1
    if ledger_failed:
        return outcome.exit_code if outcome.exit_code != 0 else 1
    return outcome.exit_code


def settle_initialized_setup_failure(
    control: Control,
    provider: str,
    model: str,
    effort: str,
    slug: str,
    lifecycle: RunCaptureLifecycle,
    failure: Exception,
    realization: dict[str, object] | None,
    *,
    runner: ProcessRunnerV1 | None = None,
) -> int:
    """Settle an unlaunched run without fabricating a durable ledger relation."""

    return finalize_run(
        replace(control, ledger=None),
        provider,
        model,
        effort,
        slug,
        "",
        lifecycle,
        1,
        launch_error=type(failure).__name__,
        realization=realization,
        runner=runner,
    )


def launch(provider: str, argv: list[str]) -> int:
    """Provider-launch composition root and sole owner of the injected runner."""

    with ProcessRunnerV1() as runner:
        return _launch_with_runner(provider, argv, runner)


def _launch_with_runner(
    provider: str, argv: list[str], runner: ProcessRunnerV1
) -> int:
    unavailable = EXTERNAL_UNAVAILABLE_IDS.get(provider)
    if unavailable is not None:
        return fail(f"{unavailable}: provider execution is unavailable")
    try:
        control = parse_control(argv)
        topic = validate_topic(control.topic)
        flags, model, effort = resolved_profile(provider, control.provider_flags)
    except ValueError as exc:
        return fail(str(exc))

    if control.ledger_closes:
        return fail("E_EXTERNAL_CLOSES_FORBIDDEN: external provider results cannot close ledger runs")
    try:
        role_provenance = external_role_provenance(control, provider)
    except ValueError as exc:
        return fail(str(exc))

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
        return 3
    except ValueError as exc:
        return fail(str(exc))

    query_cwd = Path.cwd().resolve()
    command = resolve_provider_command(provider)
    if command is None:
        key = {"codex": "CODEX_BIN", "claude": "CLAUDE_BIN"}.get(
            provider, "PROVIDER_BIN"
        )
        return fail(
            f"{provider} binary '{os.environ.get(key) or provider}' not found on PATH. "
            f"Set {key} if installed elsewhere."
        )
    if os.name == "nt" and provider in {"codex", "claude"}:
        executable = Path(command[0])
        try:
            identity_available = (
                executable.is_absolute()
                and executable.is_file()
                and bool(resolve_executable_identity(executable))
            )
        except (OSError, ValueError):
            identity_available = False
        if identity_available and len(command) == 1:
            return fail(
                f"{E_EXTERNAL_PROVIDER_WINDOWS_NATIVE_ARGV_UNAVAILABLE}: "
                f"native {provider} argv observation is unavailable on Windows"
            )
    if provider == "codex":
        if not Path(command[0]).is_absolute() or not Path(command[0]).is_file():
            return fail("resolved Codex executable is not an absolute regular file")
        codex_home = Path(
            os.environ.get("CODEX_HOME") or Path.home() / ".codex"
        ).expanduser().resolve(strict=False)
        trust_result = require_codex_hook_trust(
            runner, command, codex_home, query_cwd
        )
        if trust_result:
            return trust_result

    try:
        body = assemble_external_prompt(prompt_bytes(control, external=True))
    except ValueError as exc:
        return fail(str(exc))

    lifecycle: RunCaptureLifecycle | None = None
    lifecycle_initialized = False
    realization: dict[str, str] | None = None
    try:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        slug = f"{topic}-{timestamp}-{secrets.token_hex(4)}"
        lifecycle = RunCaptureLifecycle.create(provider, slug)
        lifecycle.initialize(body)
        lifecycle_initialized = True
    except (OSError, ValueError) as exc:
        if lifecycle is not None:
            cleanup = RunCaptureLifecycle.release_provisional(lifecycle.run_dir)
            for issue in cleanup.issues:
                print(
                    f"FAIL: provisional capture preserved after setup failure: {issue}",
                    file=sys.stderr,
                )
        return fail(str(exc))

    assert lifecycle is not None

    launch_run_id = ""
    if control.ledger:
        if ledger_helper() is None:
            return settle_initialized_setup_failure(
                control, provider, model, effort, slug, lifecycle,
                RuntimeError("ledger helper unavailable"), realization, runner=runner,
            )
        launch_run_id = (
            datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + f"-launch-{slug}"
        )
        launch_args = [
            "--work-item",
            control.ledger,
            "append",
            "--run-id",
            launch_run_id,
            "--status",
            "running",
            "--gate",
            "none",
            "--event-kind",
            "launch",
            "--notes",
            "wrapper-dispatched; terminal result is returned by the provider envelope",
            *ledger_common(control, provider, model, effort, slug),
        ]
        if not run_ledger(runner, launch_args):
            return settle_initialized_setup_failure(
                control, provider, model, effort, slug, lifecycle,
                RuntimeError("launch ledger append failed"), realization, runner=runner,
            )

    provider_args = (
        [
            "exec",
            "--skip-git-repo-check",
            "--json",
            *flags,
        ]
        if provider == "codex"
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
            query_cwd,
            body,
            control,
            provider,
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
    except (OSError, ValueError) as exc:
        launch_error = f"{provider} launch failed: {type(exc).__name__}"
        exit_code = 1
    if stream_result is not None and stream_result.issues:
        detail = "; ".join(stream_result.issues)[:512]
        launch_error = f"{launch_error + '; ' if launch_error else ''}stream capture incomplete: {detail}"
        if exit_code == 0:
            exit_code = 1
    return finalize_run(
        control,
        provider,
        model,
        effort,
        slug,
        launch_run_id,
        lifecycle,
        exit_code,
        stream_result,
        cancelled=interrupted,
        timed_out=timed_out,
        launch_error=launch_error,
        realization=realization,
        credential_needles=auth_configuration.needles,
        role_provenance=role_provenance,
        raw_stdout=raw_stdout,
        raw_stderr=raw_stderr,
        process_result=process_result,
        runner=runner,
    )
