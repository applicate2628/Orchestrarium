#!/usr/bin/env python3
"""Install or update Orchestrarium structural hooks idempotently.

This script merges an Orchestrarium structural hook config into a
target settings/hooks JSON file while preserving all other user-owned keys and
other hooks. Running it multiple times produces the same result
(ownership follows the selected managed script target,
so re-runs update only owned handlers rather than appending duplicates).

Supported targets:
  --platform claude   ->  Claude Code settings.json (e.g. ~/.claude/settings.json)
  --platform codex    ->  Codex hooks.json (e.g. ~/.codex/hooks.json)
  --platform generic  ->  Provider-neutral exec-form JSON for compatible runtimes
                         using the provider's hook schema.

Cross-platform behavior:
  Claude/generic use exec form; Codex uses shell form. The default runtime
  profile invokes the installed Python target directly through the absolute
  interpreter path reported by the installer process's sys.executable.
  Registration always invokes the selected Python hook directly.

Removal:
  --remove  Removes owned handlers (handles duplicates from earlier buggy
            versions). Codex group slots are retained. The opt-out env
            var does NOT block --remove, so a standing opt-out can still
            uninstall a previously-installed hook.

Safety hardening:
  - Refuses to write through a symlinked settings.json target (security: avoid
    same-user clobber of /etc/passwd-style symlink attacks).
  - Atomic write via temp file + os.replace to prevent torn writes.
  - Validates that hooks/<event> are correct JSON types before iterating
    (a malformed-but-valid JSON like {"hooks": {"Stop": [{"hooks": 5}]}}
    is rejected with a clear error instead of crashing with TypeError).

Exit codes:
  0 on success (install, update, remove, or no-op).
  1 on JSON parse error, type-validation error, filesystem error, symlink
    target.
  2 on argument error.
"""

from __future__ import annotations

import argparse
import json
import importlib.util
import os
import re
import shlex
import sys
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PureWindowsPath
from typing import Any, ClassVar, Mapping

DEFAULT_SCRIPT_MARKER = "check-bugfix-discipline"

# Matcher regex covers Claude's code-mutating tools + Codex's apply_patch.
# Per Claude Code hooks-reference, `matcher` is a regex on tool name; per
# Codex hooks docs, same. The single regex covers both platforms cleanly.
# This hook fires on every code edit; the script self-filters on bug-context
# detected from the session transcript.
TOOL_MATCHER_REGEX = "Edit|Write|NotebookEdit|apply_patch"

WINDOWS_UNQUOTED_PATH_RE = re.compile(r"^[A-Za-z0-9_:\\./-]+$")


class TestTransactionAbort(RuntimeError):
    """Intentional, scratch-contained installer interruption for regression tests."""


class InstallScope(str, Enum):
    """Resolved installer scope injected into the test-only checkpoint policy."""

    REPO = "repo"
    TARGET = "target"
    GLOBAL = "global"


@dataclass(frozen=True)
class TestAbortPolicy:
    """Single owner for the test-only installer interruption contract."""

    ABORT_ENV: ClassVar[str] = "ORCHESTRARIUM_TEST_ABORT_HOOK_TRANSACTION_AFTER"
    PROVENANCE_ENV: ClassVar[str] = "PYTEST_CURRENT_TEST"
    STAGES: ClassVar[tuple[str, ...]] = ("sync", "register", "verify", "reclaim")
    MARKER: ClassVar[str] = "TEST-ABORT:"
    EXIT_CODE: ClassVar[int] = 86

    requested_stage: str | None
    target_path: Path | None

    @classmethod
    def resolve_and_preflight(
        cls,
        environ: Mapping[str, str] | None,
        install_scope: InstallScope,
        target_path: Path,
        repo_root: Path,
    ) -> "TestAbortPolicy":
        """Resolve once and reject unsafe requests before installer mutation."""
        source = os.environ if environ is None else environ
        requested = source.get(cls.ABORT_ENV)
        if not requested:
            return cls(requested_stage=None, target_path=None)
        if not isinstance(install_scope, InstallScope):
            raise ValueError("test transaction abort install scope is invalid")
        if install_scope is InstallScope.GLOBAL:
            raise ValueError("test transaction abort is forbidden for global install scope")
        if install_scope not in (InstallScope.REPO, InstallScope.TARGET):
            raise ValueError(
                f"test transaction abort install scope is unsupported: {install_scope.value}"
            )
        if not source.get(cls.PROVENANCE_ENV):
            raise ValueError(
                f"{cls.ABORT_ENV} is test-only and requires pytest provenance"
            )
        if requested not in cls.STAGES:
            raise ValueError(
                f"{cls.ABORT_ENV} must name one of: "
                + ", ".join(sorted(cls.STAGES))
            )

        resolved_repo = repo_root.expanduser().resolve()
        scratch_root = (resolved_repo / ".scratch").resolve()
        resolved_target = target_path.expanduser().resolve(strict=False)
        try:
            relative = resolved_target.relative_to(scratch_root)
        except ValueError as exc:
            raise ValueError(
                "test transaction abort target must remain under repository .scratch: "
                f"{resolved_target}"
            ) from exc
        if not relative.parts:
            raise ValueError("test transaction abort target must be below repository .scratch")
        return cls(requested_stage=requested, target_path=resolved_target)

    def checkpoint(self, stage: str) -> None:
        """Raise only at the armed stage; an absent request is an exact no-op."""
        if self.requested_stage is None:
            return
        if stage not in self.STAGES:
            raise ValueError(
                "test transaction checkpoint stage must name one of: "
                + ", ".join(self.STAGES)
            )
        if self.requested_stage != stage:
            return
        if self.target_path is None:
            raise ValueError("armed test transaction abort has no validated target")
        raise TestTransactionAbort(
            f"intentional test interruption after {stage.upper()} at {self.target_path}"
        )


# Compatibility names remain read-only projections of the single policy owner.
TEST_TRANSACTION_ABORT_ENV = TestAbortPolicy.ABORT_ENV
TEST_TRANSACTION_STAGES = TestAbortPolicy.STAGES
TEST_TRANSACTION_ABORT_EXIT = TestAbortPolicy.EXIT_CODE


@dataclass(frozen=True)
class HookTarget:
    """Runtime-neutral process target serialized into a hook registration."""

    executable: str
    args: tuple[str, ...] = ()


def _absolute_file(path_value: str, label: str) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{label} must be absolute: {path}")
    if not path.is_file():
        raise ValueError(f"{label} does not name an existing file: {path}")
    return path


def _validate_spawnable_executable(path_value: str, host_os: str) -> Path:
    path = _absolute_file(path_value, "hook executable")
    if host_os == "windows":
        if path.suffix.lower() != ".exe":
            raise ValueError(f"Windows hook executable must be a real .exe, not a shim: {path}")
        is_junction = getattr(path, "is_junction", lambda: False)
        if path.is_symlink() or is_junction():
            raise ValueError(f"Windows hook executable must not be a reparse target: {path}")
    elif not os.access(path, os.X_OK):
        raise ValueError(f"hook executable is not executable: {path}")
    return path


def _codex_windows_command_tokens(target: HookTarget) -> HookTarget:
    """Render the operator-verified Codex Windows token spelling.

    The verified unquoted Windows grammar spells absolute paths with forward
    separators. Both cmd.exe and PowerShell resolve either separator for an
    absolute command token, so this is not a correctness fix -- it is a byte
    fidelity one. Codex derives each hook's trust hash from the entry content,
    so emitting exactly the spelling the operator already trusted lets a
    reinstall reproduce the stored `trusted_hash` instead of re-keying all 12
    entries and raising a blocking review modal.

    The direct-Python registration is the only supported hook command shape.
    """
    return HookTarget(
        PureWindowsPath(target.executable).as_posix(),
        tuple(PureWindowsPath(arg).as_posix() for arg in target.args),
    )


def _validate_windows_unquoted_tokens(target: HookTarget) -> None:
    for token in (target.executable, *target.args):
        if not WINDOWS_UNQUOTED_PATH_RE.fullmatch(token):
            raise ValueError(
                "unsupported Windows hook command token for the verified unquoted "
                f"serialization: {token!r}"
            )


def resolve_hook_target(
    script_path: str,
    host_os: str,
    platform: str,
    *,
    python_executable: str | None = None,
    require_script: bool = True,
) -> HookTarget:
    """Resolve and validate the direct-Python hook process target."""
    requested_script = Path(script_path).expanduser()
    if not requested_script.is_absolute():
        raise ValueError(f"hook script path must be absolute: {requested_script}")

    executable = _validate_spawnable_executable(
        python_executable if python_executable is not None else sys.executable,
        host_os,
    )
    script = (
        _absolute_file(str(requested_script), "hook Python target")
        if require_script
        else requested_script
    )
    if script.suffix.lower() != ".py":
        raise ValueError(f"Python hook target must end in .py: {script}")
    target = HookTarget(str(executable), (str(script),))
    if platform == "codex" and host_os == "windows":
        target = _codex_windows_command_tokens(target)
        _validate_windows_unquoted_tokens(target)
    return target


def _with_event_matcher(
    entry: dict[str, Any], hook_event: str, tool_matcher: str | None = None
) -> dict[str, Any]:
    """Attach matcher only for tool hook events that consume one.

    tool_matcher overrides the default TOOL_MATCHER_REGEX for a hook that must
    fire on a different tool set (e.g. "Bash" for a shell-command guard). When
    None, the shared default applies, so every existing hook entry is unchanged.
    """
    if hook_event in ("PreToolUse", "PostToolUse"):
        return {"matcher": tool_matcher or TOOL_MATCHER_REGEX, **entry}
    return entry


def build_claude_entry(
    target: HookTarget,
    hook_event: str = "PreToolUse",
    tool_matcher: str | None = None,
) -> dict[str, Any]:
    """Build the host-independent Claude exec-form entry for a HookTarget."""
    return _with_event_matcher(
        {
            "hooks": [
                {
                    "type": "command",
                    "command": target.executable,
                    "args": list(target.args),
                }
            ],
        },
        hook_event,
        tool_matcher,
    )


def build_generic_entry(
    target: HookTarget,
    hook_event: str = "PreToolUse",
    tool_matcher: str | None = None,
) -> dict[str, Any]:
    """Build the provider-neutral exec form for a HookTarget."""
    return build_claude_entry(target, hook_event, tool_matcher)


def build_codex_entry(
    target: HookTarget,
    host_os: str,
    hook_event: str = "PreToolUse",
    tool_matcher: str | None = None,
    status_message: str | None = None,
) -> dict[str, Any]:
    """Build the Codex shell-form entry for a resolved HookTarget."""
    tokens = (target.executable, *target.args)
    command_str = (
        " ".join(tokens)
        if host_os == "windows"
        else " ".join(shlex.quote(token) for token in tokens)
    )
    handler = {
        "type": "command",
        "command": command_str,
    }
    if status_message is not None:
        handler["statusMessage"] = status_message
    return _with_event_matcher(
        {
            "hooks": [handler],
        },
        hook_event,
        tool_matcher,
    )


def _hook_health_owner():
    """Load the exact source sibling; health has no dependency on this writer."""
    path = Path(__file__).with_name("check-hook-health.py")
    spec = importlib.util.spec_from_file_location("orchestrarium_registration_health_owner", path)
    if spec is None or spec.loader is None:
        raise ValueError("hook invocation owner could not be loaded")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except (OSError, ImportError) as exc:
        raise ValueError("hook invocation owner could not be loaded") from exc
    if not callable(getattr(module, "classify_hook_invocation", None)):
        raise ValueError("hook invocation owner is incompatible")
    return module


def _hook_contains_marker(
    hook: dict[str, Any], script_marker: str,
    platform: str = "codex", host_os: str = "posix", *, owner=None, managed_targets=None,
) -> bool:
    owner = _hook_health_owner() if owner is None else owner
    invocation = owner.classify_hook_invocation(hook, {script_marker}, platform, host_os, managed_targets)
    if invocation.kind == "malformed-owned":
        raise ValueError("owned hook could not be parsed: " + script_marker)
    if invocation.kind == "unproven":
        print(f"  Preserving unproven {script_marker} registration")
    return invocation.kind in {"current-owned", "legacy-owned"}


def find_our_entry_indices(
    hook_event_list: list[Any], script_marker: str,
    platform: str = "codex", host_os: str = "posix", *, owner=None, managed_targets=None,
) -> list[int]:
    """Return group positions containing an actually invoked owned target."""
    owner = _hook_health_owner() if owner is None else owner
    indices: list[int] = []
    for idx, entry in enumerate(hook_event_list):
        if not isinstance(entry, dict):
            continue
        hooks_field = entry.get("hooks")
        if not isinstance(hooks_field, list):
            # Defensive: a non-list `hooks` is malformed for this entry; skip
            # it rather than crashing. Per-entry malformations are not the
            # script's job to repair.
            continue
        for hook in hooks_field:
            if isinstance(hook, dict) and _hook_contains_marker(hook, script_marker, platform, host_os, owner=owner, managed_targets=managed_targets):
                indices.append(idx)
                break
    return indices


def _iter_command_hooks(data: dict[str, Any]) -> list[dict[str, Any]]:
    hooks = data.get("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("'hooks' key is not a JSON object")
    result: list[dict[str, Any]] = []
    for entries in hooks.values():
        if not isinstance(entries, list):
            raise ValueError("hook event value is not a JSON array")
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            commands = entry.get("hooks")
            if not isinstance(commands, list):
                continue
            result.extend(command for command in commands if isinstance(command, dict))
    return result


def load_existing(target: Path) -> dict[str, Any]:
    if not target.exists():
        return {}
    text = target.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"FAIL: {target} is not valid JSON: {exc}\n")
        sys.exit(1)
    if not isinstance(data, dict):
        sys.stderr.write(f"FAIL: {target} top-level must be a JSON object\n")
        sys.exit(1)
    return data


def encode_hook_config(data: dict[str, Any]) -> bytes:
    """Render the existing UTF-8 JSON format, including host-native newlines.

    Planning has no filesystem effect. The standalone writer and an admitted
    parent writer consume these same bytes; neither owns a second serializer.
    """
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    return text.replace("\n", os.linesep).encode("utf-8")


def write_atomic(target: Path, data: dict[str, Any]) -> None:
    """Write target atomically via temp file + os.replace.

    Writes THROUGH a symlink: when target is a symlink, the atomic replace runs
    on the symlink's resolved real path, so the link itself is preserved and its
    target's content is updated. (os.replace on the symlink path would clobber
    the link with a regular file -- the reason this used to refuse symlinks.)
    The temp file is created beside the REAL target so os.replace stays atomic on
    the same filesystem, even when the symlink points across a filesystem
    boundary (e.g. ~/.codex/hooks.json -> a synced shared-env volume).
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    real_target = target.resolve() if target.is_symlink() else target
    real_target.parent.mkdir(parents=True, exist_ok=True)
    content = encode_hook_config(data)
    # tempfile beside the REAL target so os.replace is atomic on the same FS.
    fd, tmp_path_str = tempfile.mkstemp(
        prefix=".install-hypothesis-hook.", suffix=".tmp", dir=str(real_target.parent)
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
            f.flush()
            try:
                os.fsync(f.fileno())
            except (AttributeError, OSError):
                # fsync may not be available on every filesystem (Windows
                # remote shares, some FUSE mounts); best-effort only.
                pass
        os.replace(tmp_path, real_target)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def install(
    data: dict[str, Any],
    new_entry: dict[str, Any],
    hook_event: str,
    script_marker: str,
    *, platform: str = "claude", host_os: str = "posix",
    managed_targets: dict[str, set[str]] | None = None,
) -> bool:
    """Update only owned handlers, preserving foreign content and Codex slots."""
    owner = _hook_health_owner()
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        sys.stderr.write("FAIL: 'hooks' key is not a JSON object\n")
        sys.exit(1)
    hook_entries = hooks.setdefault(hook_event, [])
    if not isinstance(hook_entries, list):
        sys.stderr.write(f"FAIL: 'hooks.{hook_event}' is not a JSON array\n")
        sys.exit(1)
    selected_argv = owner._command_argv(new_entry["hooks"][0], "claude" if platform == "generic" else platform, host_os)
    selected_target, _ = owner._invoked_script(selected_argv)
    if selected_target is None:
        raise ValueError("selected managed hook target is invalid")
    managed_targets = {script_marker: {selected_target} | set((managed_targets or {}).get(script_marker, ()))}

    positions = [
        (group_index, handler_index)
        for group_index, group in enumerate(hook_entries)
        if isinstance(group, dict) and isinstance(group.get("hooks"), list)
        for handler_index, handler in enumerate(group["hooks"])
        if isinstance(handler, dict)
        and _hook_contains_marker(handler, script_marker, platform, host_os, owner=owner, managed_targets=managed_targets)
    ]
    compatible = next((position for position in positions
                       if hook_entries[position[0]].get("matcher") == new_entry.get("matcher")), None)
    retained_metadata = (
        hook_entries[(compatible or positions[0])[0]]["hooks"][(compatible or positions[0])[1]]
        if positions else {}
    )
    managed = {"type", "command", "args", "statusMessage"}
    replacement = {key: value for key, value in retained_metadata.items() if key not in managed}
    replacement.update(new_entry["hooks"][0])
    # Build the complete result before mutating: malformed/ambiguous ownership
    # fails without a partially rewritten registration.
    updated = []
    owned_positions = set(positions)
    for group_index, group in enumerate(hook_entries):
        if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
            updated.append(group)
            continue
        handlers = []
        removed_owned = False
        for handler_index, handler in enumerate(group["hooks"]):
            position = (group_index, handler_index)
            if position == compatible:
                handlers.append(replacement)
            elif position in owned_positions:
                removed_owned = True
            else:
                handlers.append(handler)
        if removed_owned and not handlers and platform != "codex" and set(group) <= {"hooks", "matcher"}:
            continue
        updated.append({**group, "hooks": handlers})
    if compatible is None:
        updated.append({**new_entry, "hooks": [replacement]})
    if updated == hook_entries:
        return False
    hook_entries[:] = updated
    return True


def remove(
    data: dict[str, Any],
    hook_event: str,
    script_marker: str,
    *,
    expected_entry: dict[str, Any] | None = None,
    platform: str = "claude", host_os: str = "posix",
    managed_targets: dict[str, set[str]] | None = None,
) -> bool:
    """Remove owned entries, or exact handlers when a retirement identity is supplied."""
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return False
    hook_entries = hooks.get(hook_event)
    if not isinstance(hook_entries, list):
        return False
    owner = _hook_health_owner()
    if expected_entry is not None:
        selected_argv = owner._command_argv(expected_entry["hooks"][0], "claude" if platform == "generic" else platform, host_os)
        selected_target, _ = owner._invoked_script(selected_argv)
        if selected_target is not None:
            managed_targets = {script_marker: {selected_target}}
    indices = find_our_entry_indices(hook_entries, script_marker, platform, host_os, owner=owner, managed_targets=managed_targets)
    if not indices:
        return False
    changed = False
    expected_handler = expected_entry["hooks"][0] if expected_entry is not None else None
    # Delete from the end so earlier indices stay valid.
    for idx in reversed(indices):
        entry = hook_entries[idx]
        if expected_entry is None:
            retained = [handler for handler in entry["hooks"]
                        if not (isinstance(handler, dict) and _hook_contains_marker(
                            handler, script_marker, platform, host_os, owner=owner, managed_targets=managed_targets))]
        elif entry.get("matcher") != expected_entry.get("matcher"):
            continue
        else:
            retained = [
                handler
                for handler in entry["hooks"]
                if not (
                    isinstance(handler, dict)
                    and all(handler.get(key) == expected_handler.get(key) for key in ("type", "command", "args"))
                    and not set(handler).difference({"type", "command", "args", "statusMessage"})
                )
            ]
        if len(retained) == len(entry["hooks"]):
            continue
        entry["hooks"] = retained
        if expected_entry is None and not retained and platform != "codex" and set(entry) <= {"hooks", "matcher"}:
            del hook_entries[idx]
        changed = True
    # Marker-only removal may empty event containers. Exact removal retains
    # valid empty groups: no runnable handler, but later native group slots stay stable.
    if not hook_entries:
        del hooks[hook_event]
    if not hooks:
        del data["hooks"]
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        required=True,
        help="Path to settings/hooks JSON for the selected platform",
    )
    parser.add_argument(
        "--platform",
        choices=("claude", "codex", "generic"),
        required=True,
        help="Which platform's hook config schema to write",
    )
    parser.add_argument(
        "--script-path",
        help="Absolute installed .py hook target",
    )
    parser.add_argument(
        "--host-os",
        choices=("posix", "windows"),
        default="posix",
        help="Host OS class used for target validation and Codex command serialization",
    )
    parser.add_argument(
        "--hook-event",
        choices=("PreToolUse", "PostToolUse", "Stop", "SessionStart", "UserPromptSubmit"),
        default="PreToolUse",
        help="Hook event to install under (default: PreToolUse)",
    )
    parser.add_argument(
        "--script-marker",
        default=DEFAULT_SCRIPT_MARKER,
        help="Substring identifying this specific hook entry for idempotency",
    )
    parser.add_argument(
        "--tool-matcher",
        default=None,
        help=(
            "Override the tool-event matcher regex (default: "
            "Edit|Write|NotebookEdit|apply_patch). Use for a hook that must fire "
            "on a different tool set, e.g. 'Bash' for a shell-command guard. "
            "Ignored for the Stop event, which takes no matcher."
        ),
    )
    parser.add_argument(
        "--status-message",
        default=None,
        help="Optional Codex command-handler statusMessage shown while the hook runs",
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove our hook entry instead of installing it",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Resolve and validate the selected target without reading or writing registration",
    )
    parser.add_argument(
        "--repo-root",
        help="Repository root required only by transaction-test actions",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without modifying any file",
    )
    parser.add_argument(
        "--test-transaction-preflight",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--test-transaction-checkpoint",
        choices=TEST_TRANSACTION_STAGES,
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--test-install-scope",
        choices=tuple(scope.value for scope in InstallScope),
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()

    # The opt-out env var blocks install but NOT remove — a standing opt-out
    # should still allow uninstall of a previously-installed hook entry.
    if os.environ.get("ORCHESTRARIUM_NO_HYPOTHESIS_HOOK") and not args.remove:
        sys.stderr.write(
            "SKIP: ORCHESTRARIUM_NO_HYPOTHESIS_HOOK set; not installing into "
            f"{args.target}\n"
        )
        return 0

    target = Path(args.target).expanduser()

    try:
        if args.test_transaction_preflight or args.test_transaction_checkpoint:
            if not args.repo_root:
                raise ValueError(
                    "--repo-root is required with a test transaction action"
                )
            if not args.test_install_scope:
                raise ValueError(
                    "--test-install-scope is required with a test transaction action"
                )
            abort_policy = TestAbortPolicy.resolve_and_preflight(
                None,
                InstallScope(args.test_install_scope),
                target,
                Path(args.repo_root),
            )
            if args.test_transaction_checkpoint:
                abort_policy.checkpoint(args.test_transaction_checkpoint)
            return 0

        if args.remove:
            data = load_existing(target)
            expected_entry = None
            if not args.script_path:
                owner = _hook_health_owner()
                package = owner._installed_root_for_target(target, args.platform)
                artifact = (owner._hook_manifest(Path(owner.__file__).parent.parent)
                            .hook_artifact_target(args.platform, package, args.script_marker)
                            if package is not None and args.tool_matcher is None else None)
                if artifact is None:
                    sys.stdout.write(f"  Preserving {args.script_marker} registrations: managed identity is unavailable\n")
                    return 0
                managed_targets = {args.script_marker: {str(artifact)}}
            else:
                hook_target = resolve_hook_target(
                    args.script_path, args.host_os, args.platform, require_script=False
                )
                selected_entry = (
                    build_codex_entry(hook_target, args.host_os, args.hook_event, args.tool_matcher)
                    if args.platform == "codex"
                    else build_generic_entry(hook_target, args.hook_event, args.tool_matcher)
                )
                expected_entry = selected_entry if args.tool_matcher is not None else None
                managed_targets = {args.script_marker: {hook_target.args[0]}}
            changed = remove(
                data, args.hook_event, args.script_marker, expected_entry=expected_entry,
                platform=args.platform, host_os=args.host_os, managed_targets=managed_targets,
            )
            remaining_hooks = data.get("hooks")
            remaining_entries = (
                remaining_hooks.get(args.hook_event) if isinstance(remaining_hooks, dict) else None
            )
            if expected_entry is not None and isinstance(remaining_entries, list) and find_our_entry_indices(
                remaining_entries, args.script_marker, args.platform, args.host_os,
                managed_targets=managed_targets,
            ):
                sys.stdout.write(f"  Preserving unmatched {args.script_marker} registration identities\n")
            action = "removed"
        else:
            if not args.script_path:
                raise ValueError("--script-path is required when installing a hook")
            hook_target = resolve_hook_target(
                args.script_path,
                args.host_os,
                args.platform,
            )
            if args.validate_only:
                sys.stdout.write(
                    f"  validated hook target: {hook_target.executable}"
                    + (
                        " " + " ".join(hook_target.args)
                        if hook_target.args
                        else ""
                    )
                    + "\n"
                )
                return 0
            if args.platform == "claude":
                entry = build_claude_entry(
                    hook_target, args.hook_event, args.tool_matcher
                )
            elif args.platform == "codex":
                entry = build_codex_entry(
                    hook_target,
                    args.host_os,
                    args.hook_event,
                    args.tool_matcher,
                    args.status_message,
                )
            else:
                entry = build_generic_entry(
                    hook_target, args.hook_event, args.tool_matcher
                )
            data = load_existing(target)
            changed = install(data, entry, args.hook_event, args.script_marker,
                              platform=args.platform, host_os=args.host_os)
            action = "installed/updated"
    except TestTransactionAbort as exc:
        sys.stderr.write(f"{TestAbortPolicy.MARKER} {exc}\n")
        return TestAbortPolicy.EXIT_CODE
    except (OSError, ValueError) as exc:
        sys.stderr.write(f"FAIL: {exc}\n")
        return 1

    if not changed:
        sys.stdout.write(
            f"  {args.script_marker} hook already present in {target} (no-op)\n"
        )
        return 0

    if args.dry_run:
        sys.stdout.write(f"  [dry-run] would write {target}\n")
        return 0

    # Special case: file removal when remove cleared everything.
    if args.remove and not data:
        if target.exists():
            if target.is_symlink():
                # Preserve the symlink: write the cleared data THROUGH it to the
                # real target instead of deleting the link itself.
                write_atomic(target, data)
                sys.stdout.write(
                    f"  {args.script_marker} hook {action}; cleared {target} (symlink preserved)\n"
                )
                return 0
            target.unlink()
            sys.stdout.write(
                f"  {args.script_marker} hook {action}; deleted now-empty {target}\n"
            )
        return 0

    write_atomic(target, data)
    sys.stdout.write(f"  {args.script_marker} hook {action} in {target}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
