#!/usr/bin/env python3
"""Shared Python owner for file-based provider prompt transports."""

from __future__ import annotations

import ctypes
import errno
import hashlib
import importlib.util
import json
import math
import os
import re
import secrets
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import types
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

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
EXTERNAL_PROVIDER_NAMES = frozenset({"codex", "claude"})
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
    "claude-api-key-helper": (),
    "claude-subscription-override": (),
}
_NONSECRET_CHILD_ENV_NAMES = (
    "COMSPEC", "SystemRoot", "SYSTEMROOT", "WINDIR", "PATH", "PATHEXT",
    "TEMP", "TMP", "TMPDIR", "USERPROFILE", "LOCALAPPDATA", "APPDATA",
    "HOME", "LANG", "LC_ALL",
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
_ROLE_TAXONOMY_RESOLVER_SHA256 = (
    "bfdbf9695dbdaadb7507681259a02f9202931b1c38f98617f4d91cf6148766ea"
)


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


class ResultMaterializationError(RuntimeError):
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
    return flags, model, effort


def _lexically_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _external_role_taxonomy() -> tuple[set[str], set[str], set[str]]:
    """Read the routing policy's role taxonomy instead of inferring a lane from task class."""

    try:
        resolver_path = Path(__file__).resolve().with_name("resolve-agents-mode.py")
        metadata = resolver_path.lstat()
        if (
            not stat.S_ISREG(metadata.st_mode)
            or stat.S_ISLNK(metadata.st_mode)
            or _metadata_is_reparse(metadata)
        ):
            raise ValueError("resolver sibling is not ordinary")
        descriptor = os.open(
            resolver_path,
            os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            opened = os.fstat(descriptor)
            if (opened.st_dev, opened.st_ino, opened.st_mode) != (
                metadata.st_dev,
                metadata.st_ino,
                metadata.st_mode,
            ):
                raise ValueError("resolver sibling identity changed")
            chunks: list[bytes] = []
            while chunk := os.read(descriptor, 1024 * 1024):
                chunks.append(chunk)
            payload = b"".join(chunks)
        finally:
            os.close(descriptor)
        if hashlib.sha256(payload).hexdigest() != _ROLE_TAXONOMY_RESOLVER_SHA256:
            raise ValueError("resolver sibling digest drift")
        module_name = "_orchestrarium_external_role_taxonomy"
        prior = sys.modules.get(module_name)
        resolver = types.ModuleType(module_name)
        resolver.__file__ = str(resolver_path)
        sys.modules[module_name] = resolver
        try:
            exec(compile(payload, str(resolver_path), "exec"), resolver.__dict__)
            policy, _ = resolver.load_role_policy(resolver_path.parent.parent)
        finally:
            if prior is None:
                sys.modules.pop(module_name, None)
            else:
                sys.modules[module_name] = prior
        roles = set(policy["roles"])
        eligibility = policy["taskRoleEligibility"]
        reviewers = set(eligibility["review"])
        workers = set().union(
            eligibility["exploration"],
            eligibility["planning"],
            eligibility["engineering"],
            eligibility["recovery"],
        )
    except (AttributeError, ImportError, KeyError, OSError, TypeError, ValueError, SyntaxError) as exc:
        raise ValueError("E_EXTERNAL_PROVENANCE_ROLE_INVALID: role taxonomy") from exc
    # These owner/advisory identities are canonical governance roles but deliberately
    # have no native dispatch profile. They remain truthful assignments with no lane.
    roles.update({"consultant", "lead", "product-manager"})
    return roles, reviewers, workers


def external_role_provenance(control: Control, provider: str) -> ExternalRoleProvenance:
    """Freeze S3 role provenance before external side effects begin."""

    if provider in {"codex", "claude"} and not control.ledger_role_explicit:
        return ExternalRoleProvenance("none", "none")
    roles, reviewers, workers = _external_role_taxonomy()
    assigned = control.ledger_role if control.ledger_role_explicit else "none"
    if assigned != "none" and assigned not in roles:
        raise ValueError("E_EXTERNAL_PROVENANCE_ROLE_INVALID: assigned role")
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
    if suffix == ".ps1":
        powershell = (
            shutil.which("pwsh")
            or shutil.which("pwsh.exe")
            or shutil.which("powershell")
            or shutil.which("powershell.exe")
        )
        if not powershell:
            return None
        return [
            powershell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            resolved,
        ]
    if os.name == "nt" and suffix in {".cmd", ".bat"}:
        command_shell = os.environ.get("COMSPEC") or shutil.which("cmd.exe")
        if not command_shell:
            return None
        return [command_shell, "/d", "/s", "/c", resolved]
    if suffix == ".sh" and os.name == "nt":
        bash = shutil.which("bash")
        return [bash, resolved] if bash else None
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


def _api_key_helper_configured() -> bool:
    try:
        settings = [Path.home() / ".claude" / "settings.json", Path.cwd() / ".claude" / "settings.json"]
    except RuntimeError:
        return False
    for path in settings:
        try:
            if '"apiKeyHelper"' in path.read_text(encoding="utf-8"):
                return True
        except OSError:
            continue
    return False


def _child_environment_baseline(environment: dict[str, str]) -> dict[str, str]:
    return {
        name: value
        for name in _NONSECRET_CHILD_ENV_NAMES
        if (value := environment.get(name))
    }


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
        if _api_key_helper_configured():
            selected.append("claude-api-key-helper")
        if source.get("ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE") == "1":
            selected.append("claude-subscription-override")
        if len(selected) != 1:
            raise ValueError("E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE: auth mode")
        mode = selected[0]
        if mode == "claude-bedrock":
            child["CLAUDE_CODE_USE_BEDROCK"] = "true"
        elif mode == "claude-vertex":
            child["CLAUDE_CODE_USE_VERTEX"] = "true"
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
    if (
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or _truthy(os.environ.get("CLAUDE_CODE_USE_BEDROCK"))
        or _truthy(os.environ.get("CLAUDE_CODE_USE_VERTEX"))
        or os.environ.get("ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE") == "1"
    ):
        return True
    return _api_key_helper_configured()


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
    out_path: Path
    err_path: Path
    pid_path: Path

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
                out_path=run_dir / "provider.out",
                err_path=run_dir / "provider.err",
                pid_path=run_dir / "provider.pid",
            )
            lifecycle._validate_identity()
        except (OSError, ValueError) as exc:
            cleanup = cls.release_provisional(run_dir)
            recovery = "; secure recovery evidence retained" if not cleanup.clean else ""
            raise OSError(f"private capture directory hardening failed: {exc}{recovery}") from exc
        return lifecycle

    def _validate_child(self, path: Path) -> None:
        if path.parent != self.run_dir or path not in {
            self.prompt_path,
            self.out_path,
            self.err_path,
            self.pid_path,
        }:
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
        self.write_new(self.out_path, b"")
        self.write_new(self.err_path, b"")
        self.write_new(self.pid_path, b"")

    def open_for_write(self, path: Path):
        self._validate_identity()
        self._validate_child(path)
        reject_link(path)
        flags = os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        os.ftruncate(descriptor, 0)
        return os.fdopen(descriptor, "wb")

    def write_pid(self, data: bytes) -> None:
        with self.open_for_write(self.pid_path) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())

    def read_bounded(self, path: Path, limit: int, label: str) -> bytes:
        self._validate_identity()
        self._validate_child(path)
        reject_link(path)
        with path.open("rb") as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ResultMaterializationError(
                f"{label} exceeds configured maximum of {limit} bytes"
            )
        return data

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
            if tombstone is not None and tombstone.exists():
                scrub_issues = self._scrub_tombstone(tombstone)
                try:
                    self._purge_tombstone(tombstone)
                    self._write_redacted_recovery(type(exc).__name__)
                    return CleanupResult(
                        (type(exc).__name__, *scrub_issues), recovery_retained=True
                    )
                except (OSError, ValueError):
                    unlink_issues = self._unlink_owned_payloads(tombstone)
                    try:
                        self._purge_tombstone(tombstone)
                        self._write_redacted_recovery(type(exc).__name__)
                        return CleanupResult(
                            (type(exc).__name__, *scrub_issues, *unlink_issues),
                            recovery_retained=True,
                        )
                    except (OSError, ValueError):
                        return CleanupResult(
                            (
                                type(exc).__name__,
                                *scrub_issues,
                                *unlink_issues,
                                "scrub-unlink-failed",
                            ),
                            recovery_retained=True,
                        )
            # A failed purge leaves the tombstone quarantined and is never a
            # clean outcome. Its raw contents are never serialized as recovery.
            return CleanupResult((type(exc).__name__,), recovery_retained=True)


def _posix_start_marker(pid: int) -> str | None:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except OSError:
        return None
    close = raw.rfind(") ")
    fields = raw[close + 2 :].split() if close >= 0 else []
    return fields[19] if len(fields) >= 20 else None


def process_start_marker(pid: int) -> str | None:
    if os.name != "nt":
        return _posix_start_marker(pid)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        creation = ctypes.c_ulonglong()
        exit_time = ctypes.c_ulonglong()
        kernel = ctypes.c_ulonglong()
        user = ctypes.c_ulonglong()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            return None
        return str(creation.value)
    finally:
        kernel32.CloseHandle(handle)


def ledger_helper() -> Path | None:
    script_dir = Path(__file__).resolve().parent
    candidates = (
        script_dir / "agent-run-ledger.py",
        Path("scripts/agent-run-ledger.py"),
        script_dir.parents[2] / "scripts" / "agent-run-ledger.py",
    )
    return next((path for path in candidates if path.is_file()), None)


def run_ledger(args: list[str]) -> bool:
    helper = ledger_helper()
    if helper is None:
        return False
    return (
        subprocess.run(
            [sys.executable, str(helper), *args],
            capture_output=True,
            check=False,
        ).returncode
        == 0
    )


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
        completed = subprocess.run(
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
            capture_output=True,
            text=True,
            check=False,
            cwd=query_cwd,
            env=_trust_probe_env(codex_home),
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        return fail("Codex hook trust inventory query failed")
    if completed.returncode:
        detail = " ".join((completed.stderr or completed.stdout).split())[:512]
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


class SharedCaptureBudget:
    def __init__(self, limit: int, salt: bytes) -> None:
        self.limit = limit
        self.remaining = limit
        self.observed_bytes = 0
        self.persisted_bytes = 0
        self.overflow = threading.Event()
        self.lock = threading.Lock()
        self.digest = hashlib.sha256(salt)

    def reserve(self, stream_name: str, chunk: bytes) -> bytes:
        with self.lock:
            self.observed_bytes = min(
                self.limit + 1, self.observed_bytes + len(chunk)
            )
            self.digest.update(stream_name.encode("ascii") + b"\x00" + chunk)
            if self.overflow.is_set() or len(chunk) > self.remaining:
                self.overflow.set()
                return b""
            self.remaining -= len(chunk)
            self.persisted_bytes += len(chunk)
            return chunk

    def result(self, issues: list[str]) -> StreamCaptureResult:
        return StreamCaptureResult(
            overflow=self.overflow.is_set(),
            observed_bytes=self.observed_bytes,
            persisted_bytes=self.persisted_bytes,
            digest=self.digest.hexdigest(),
            issues=tuple(issues),
        )


def supervise_provider_io(
    process: subprocess.Popen[bytes],
    lifecycle: RunCaptureLifecycle,
    body: bytes,
    capture_max_bytes: int,
    timeout_secs: float,
) -> tuple[int, bool, bool, tuple[str, ...], StreamCaptureResult]:
    budget = SharedCaptureBudget(capture_max_bytes, secrets.token_bytes(32))
    issues: list[str] = []
    issue_lock = threading.Lock()

    def add_issue(message: str) -> None:
        with issue_lock:
            issues.append(message[:256])

    writer_failure: OSError | None = None

    def reader(name: str, source, target: Path) -> None:
        try:
            with lifecycle.open_for_write(target) as destination:
                while True:
                    chunk = source.read(65536)
                    if not chunk:
                        break
                    accepted = budget.reserve(name, chunk)
                    if accepted:
                        destination.write(accepted)
                destination.flush()
                os.fsync(destination.fileno())
        except Exception as exc:
            add_issue(f"{name} reader failed: {type(exc).__name__}")
        finally:
            try:
                source.close()
            except Exception as exc:
                add_issue(f"{name} pipe close failed: {type(exc).__name__}")

    def writer() -> None:
        nonlocal writer_failure
        bytes_written = 0
        try:
            if process.stdin is None:
                raise OSError("stdin pipe unavailable")
            written = process.stdin.write(body)
            bytes_written = len(body) if written is None else int(written)
            process.stdin.flush()
        except OSError as exc:
            writer_failure = exc
        except Exception as exc:
            add_issue(f"stdin writer failed: {type(exc).__name__}")
        finally:
            if process.stdin is not None:
                try:
                    process.stdin.close()
                except Exception as exc:
                    add_issue(f"stdin pipe close failed: {type(exc).__name__}")

    timed_out = False
    cancelled = False
    settle_issues: list[str] = []
    exit_code = 1
    deadline = time.monotonic() + timeout_secs
    threads: list[threading.Thread] = []
    started_threads: list[threading.Thread] = []

    def close_pipes() -> None:
        for name, pipe in (
            ("stdin", process.stdin),
            ("stdout", process.stdout),
            ("stderr", process.stderr),
        ):
            if pipe is None:
                continue
            try:
                pipe.close()
            except Exception as exc:
                add_issue(f"{name} pipe close failed: {type(exc).__name__}")

    try:
        if process.stdin is None or process.stdout is None or process.stderr is None:
            raise OSError("provider streaming pipes are unavailable")
        thread_specs = (
            (writer, (), "provider-stdin"),
            (reader, ("stdout", process.stdout, lifecycle.out_path), "provider-stdout"),
            (reader, ("stderr", process.stderr, lifecycle.err_path), "provider-stderr"),
        )
        for target, args, name in thread_specs:
            threads.append(threading.Thread(target=target, args=args, name=name))
        for thread in threads:
            try:
                thread.start()
            except Exception as exc:
                if thread.is_alive():
                    started_threads.append(thread)
                add_issue(f"{thread.name} start failed: {type(exc).__name__}")
                raise
            else:
                started_threads.append(thread)

        while True:
            if budget.overflow.is_set():
                exit_code = 1
                break
            with issue_lock:
                stream_failed = bool(issues)
            if stream_failed:
                exit_code = 1
                break
            if time.monotonic() >= deadline:
                timed_out = True
                exit_code = 124
                break
            try:
                exit_code = process.wait(timeout=0.05)
                break
            except subprocess.TimeoutExpired:
                continue
    except KeyboardInterrupt:
        cancelled = True
        exit_code = 130
    except Exception as exc:
        add_issue(f"provider supervision failed: {type(exc).__name__}")
        exit_code = 1
    finally:
        try:
            process_live = process.poll() is None
        except Exception as exc:
            add_issue(f"provider poll failed: {type(exc).__name__}")
            process_live = True
        if process_live:
            settle_issues.extend(terminate_and_reap(process))
        for thread in started_threads:
            try:
                thread.join(timeout=5)
            except Exception as exc:
                add_issue(f"{thread.name} join failed: {type(exc).__name__}")
        close_pipes()
        for thread in started_threads:
            if thread.is_alive():
                try:
                    thread.join(timeout=1)
                except Exception as exc:
                    add_issue(f"{thread.name} final join failed: {type(exc).__name__}")
            if thread.is_alive():
                add_issue(f"{thread.name} did not stop")
        if writer_failure is not None:
            known_closed_stdin = (
                writer_failure.errno == errno.EPIPE
                or getattr(writer_failure, "winerror", None) in {6, 109, 232}
            )
            try:
                child_terminated = process.poll() is not None
            except Exception:
                child_terminated = False
            if not (known_closed_stdin and child_terminated):
                add_issue(f"stdin writer failed: {type(writer_failure).__name__}")
    return (
        exit_code,
        cancelled,
        timed_out,
        tuple(settle_issues),
        budget.result(issues),
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


def credential_scan_terminal(lifecycle: RunCaptureLifecycle, needles: tuple[bytes, ...]) -> str | None:
    """Return the stable scanner outcome after both child streams are settled."""

    try:
        stdout = lifecycle.read_bounded(
            lifecycle.out_path, CAPTURE_MAX_BYTES_HARD, "provider stdout capture"
        )
        stderr = lifecycle.read_bounded(
            lifecycle.err_path, CAPTURE_MAX_BYTES_HARD, "provider stderr capture"
        )
    except (OSError, ValueError):
        return "E_EXTERNAL_PROVIDER_CREDENTIAL_SCAN_UNAVAILABLE"
    if any(needle in stdout or needle in stderr for needle in needles):
        return "E_EXTERNAL_PROVIDER_CREDENTIAL_ECHO"
    return None


def credential_scan_failure_terminal(
    lifecycle: RunCaptureLifecycle, stable_id: str
) -> TerminalResult:
    return TerminalResult(
        lifecycle.out_path,
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
) -> tuple[TerminalResult, str]:
    evidence_path = lifecycle.out_path
    captured_stdout = lifecycle.read_bounded(
        lifecycle.out_path, CAPTURE_MAX_BYTES_HARD, "provider stdout capture"
    )
    if provider == "codex":
        result_bytes = parse_codex_jsonl_result(captured_stdout, result_max_bytes)
    else:
        if len(captured_stdout) > result_max_bytes:
            raise ResultMaterializationError(
                f"provider result exceeds configured maximum of {result_max_bytes} bytes"
            )
        result_bytes = captured_stdout
    stderr_bytes = lifecycle.read_bounded(
        lifecycle.err_path, STDERR_SCAN_MAX_BYTES, "provider stderr diagnostic"
    )
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

    return combine_terminal_outcomes(
        exit_code,
        terminal,
        lifecycle.cleanup(),
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


def terminate_and_reap(process: subprocess.Popen[bytes]) -> tuple[str, ...]:
    issues: list[str] = []
    must_kill = False
    try:
        process.terminate()
    except Exception as exc:
        issues.append(f"terminate failed: {type(exc).__name__}")
        must_kill = True
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        must_kill = True
    except Exception as exc:
        issues.append(f"wait after terminate failed: {type(exc).__name__}")
        must_kill = True
    if must_kill:
        try:
            process.kill()
        except Exception as exc:
            issues.append(f"kill failed: {type(exc).__name__}")
        try:
            process.wait()
        except Exception as exc:
            issues.append(f"wait after kill failed: {type(exc).__name__}")
    return tuple(issues)


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
    recorded = run_ledger(args)
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
) -> int:
    frozen_role = role_provenance or external_role_provenance(control, provider)
    scan_outcome = (
        credential_scan_terminal(lifecycle, credential_needles)
        if credential_needles
        else None
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
                lifecycle, provider, exit_code, control.result_max_bytes
            )
        except (OSError, ValueError, ResultMaterializationError) as exc:
            result_text = ""
            terminal = TerminalResult(
                lifecycle.out_path,
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
    )


def launch(provider: str, argv: list[str]) -> int:
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

    if provider == "claude" and not claude_commercial_auth_present():
        print(
            "WARNING: Refusing automated Claude launch.\n"
            "Automated `claude -p` under a subscription is not permitted.\n"
            "Anthropic policy: https://code.claude.com/docs/en/legal-and-compliance\n\n"
            "Use commercial authentication (ANTHROPIC_API_KEY, "
            "ANTHROPIC_AUTH_TOKEN, apiKeyHelper, Amazon Bedrock, or Google "
            "Vertex AI), or explicitly set ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE=1.",
            file=sys.stderr,
        )
        return 3
    try:
        auth_configuration = resolve_provider_auth_configuration(provider)
    except ValueError as exc:
        return fail(str(exc))

    try:
        body = assemble_external_prompt(prompt_bytes(control, external=True))
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
    if provider == "codex":
        if not Path(command[0]).is_absolute() or not Path(command[0]).is_file():
            return fail("resolved Codex executable is not an absolute regular file")
        codex_home = Path(
            os.environ.get("CODEX_HOME") or Path.home() / ".codex"
        ).expanduser().resolve(strict=False)
        trust_result = require_codex_hook_trust(command, codex_home, query_cwd)
        if trust_result:
            return trust_result

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
                RuntimeError("ledger helper unavailable"), realization,
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
        if not run_ledger(launch_args):
            return settle_initialized_setup_failure(
                control, provider, model, effort, slug, lifecycle,
                RuntimeError("launch ledger append failed"), realization,
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
    process: subprocess.Popen[bytes] | None = None
    timed_out = False
    settle_issues: tuple[str, ...] = ()
    stream_result: StreamCaptureResult | None = None
    try:
        process = subprocess.Popen(
            command + provider_args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=child_environment,
            cwd=query_cwd if provider == "codex" else None,
            bufsize=0,
        )
        marker = process_start_marker(process.pid)
        pid_text = f"pid={process.pid}\n"
        if marker:
            pid_text += f"start={marker}\n"
        lifecycle.write_pid(pid_text.encode("utf-8"))
        (
            exit_code,
            interrupted,
            timed_out,
            settle_issues,
            stream_result,
        ) = supervise_provider_io(
            process,
            lifecycle,
            body,
            control.capture_max_bytes,
            control.timeout_secs,
        )
    except OSError as exc:
        if process is not None:
            settle_issues = terminate_and_reap(process)
        launch_error = f"{provider} launch failed: {exc}"
        exit_code = 1
    if settle_issues:
        detail = "; ".join(settle_issues)[:512]
        launch_error = f"{launch_error + '; ' if launch_error else ''}process settle incomplete: {detail}"
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
    )
