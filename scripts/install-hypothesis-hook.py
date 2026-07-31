#!/usr/bin/env python3
"""Install or update Orchestrarium structural hooks idempotently.

This script merges an Orchestrarium structural hook config into a
target settings/hooks JSON file while preserving all other user-owned keys and
other hooks. Running it multiple times produces the same result
(our entry is identified by the configured script marker in the command or
args fields, so re-runs update in place rather than appending
duplicates).

Supported targets:
  --platform claude   →  Claude Code settings.json (e.g. ~/.claude/settings.json)
  --platform codex    →  Codex hooks.json (e.g. ~/.codex/hooks.json)
  --platform generic  →  Provider-neutral exec-form JSON for compatible runtimes
                         or approved wrapper-driven hook wiring.

Cross-platform behavior:
  Claude/generic use exec form; Codex uses shell form. The default runtime
  profile invokes the installed Python target directly through the absolute
  interpreter path reported by the installer process's sys.executable.
  The wrapper profile preserves the prior bash/PowerShell entries for rollback.

Removal:
  --remove  Removes ALL of our hook entries (handles duplicates from earlier
            buggy versions). Cleans up empty hooks containers. The opt-out env
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
WRAPPER_EXECUTABLES = frozenset({"bash", "powershell", "powershell.exe", "pwsh", "pwsh.exe"})


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


def powershell_single_quote(value: str) -> str:
    """Return a PowerShell single-quoted literal for a shell command string.

    PowerShell single-quoted strings escape an embedded apostrophe by doubling it.
    Codex hook entries are command strings, so the script path must be quoted in
    the target shell's syntax instead of treated as a pre-split argv element.
    """
    return "'" + value.replace("'", "''") + "'"


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

    Applies to the python and native profiles only. The wrapper profile must
    keep reproducing the historical bytes so the documented rollback stays
    modal-free too.
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
    hook_runtime: str,
    platform: str,
    *,
    python_executable: str | None = None,
) -> HookTarget:
    """Resolve and validate the one stage-dependent hook process target.

    This is the only owner of wrapper/python/native selection. Serializers
    consume HookTarget without knowing which profile produced it.
    """
    requested_script = Path(script_path).expanduser()
    if not requested_script.is_absolute():
        raise ValueError(f"hook script path must be absolute: {requested_script}")

    if hook_runtime == "wrapper":
        wrapper_path = requested_script.with_suffix(".ps1" if host_os == "windows" else ".sh")
        _absolute_file(str(wrapper_path), "hook wrapper")
        if host_os == "windows":
            if platform == "codex":
                target = HookTarget(
                    "powershell.exe",
                    (
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        powershell_single_quote(str(wrapper_path)),
                    ),
                )
            else:
                target = HookTarget(
                    "powershell",
                    (
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        str(wrapper_path),
                    ),
                )
        else:
            target = HookTarget("bash", (str(wrapper_path),))
        return target

    if hook_runtime == "python":
        executable = _validate_spawnable_executable(
            python_executable if python_executable is not None else sys.executable,
            host_os,
        )
        script = _absolute_file(str(requested_script), "hook Python target")
        if script.suffix.lower() != ".py":
            raise ValueError(f"Python hook target must end in .py: {script}")
        target = HookTarget(str(executable), (str(script),))
        if platform == "codex" and host_os == "windows":
            target = _codex_windows_command_tokens(target)
            _validate_windows_unquoted_tokens(target)
        return target

    if hook_runtime == "native":
        native_path = requested_script.with_suffix(".exe" if host_os == "windows" else "")
        executable = _validate_spawnable_executable(str(native_path), host_os)
        target = HookTarget(str(executable), ())
        if platform == "codex" and host_os == "windows":
            target = _codex_windows_command_tokens(target)
            _validate_windows_unquoted_tokens(target)
        return target

    raise ValueError(f"unsupported hook runtime: {hook_runtime}")


def _with_event_matcher(
    entry: dict[str, Any], hook_event: str, tool_matcher: str | None = None
) -> dict[str, Any]:
    """Attach matcher only for hook events that consume one.

    tool_matcher overrides the default TOOL_MATCHER_REGEX for a hook that must
    fire on a different tool set (e.g. "Bash" for a shell-command guard). When
    None, the shared default applies, so every existing hook entry is unchanged.
    """
    if hook_event == "PreToolUse":
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
) -> dict[str, Any]:
    """Build the Codex shell-form entry for a resolved HookTarget."""
    tokens = (target.executable, *target.args)
    command_str = (
        " ".join(tokens)
        if host_os == "windows"
        else " ".join(shlex.quote(token) for token in tokens)
    )
    return _with_event_matcher(
        {
            "hooks": [
                {
                    "type": "command",
                    "command": command_str,
                }
            ],
        },
        hook_event,
        tool_matcher,
    )


def _hook_contains_marker(hook: dict[str, Any], script_marker: str) -> bool:
    """True if a single hook dict references our script via marker substring.

    Marker can appear in either:
      - The `command` shell-string (legacy shell form / Codex always-shell form).
      - Any element of the `args` array (exec form, where the script path is
        a literal argv element separate from the executable name).
    """
    command = hook.get("command", "")
    if isinstance(command, str) and script_marker in command:
        return True
    args_field = hook.get("args")
    if isinstance(args_field, list):
        for arg in args_field:
            if isinstance(arg, str) and script_marker in arg:
                return True
    return False


def find_our_entry_indices(hook_event_list: list[Any], script_marker: str) -> list[int]:
    """Return ALL indices whose hook references our script (by marker).

    Recognizes both legacy shell form (marker in `command`) and current exec
    form (marker in `args[k]`). This lets a re-install collapse an older
    shell-form entry into the new exec-form entry without leaving stale
    duplicates, and lets `--remove` clean up either form.

    Earlier versions of this script returned only the first match; that left
    duplicates firing if multiple of our entries were inserted by a buggy or
    racy install. Now: install collapses duplicates to a single entry; remove
    deletes every one of our entries.
    """
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
            if isinstance(hook, dict) and _hook_contains_marker(hook, script_marker):
                indices.append(idx)
                break
    return indices


def _hook_source_dirs(platform: str) -> tuple[tuple[str, str], ...]:
    if platform == "claude":
        return (
            ("scripts", "src.claude/agents/scripts"),
            ("hooks", "src.claude/agents/hooks"),
        )
    if platform == "codex":
        return (
            ("scripts", "src.codex/skills/lead/scripts"),
            ("hooks", "src.codex/skills/lead/hooks"),
        )
    raise ValueError(f"reclaim is unsupported for platform: {platform}")


def owned_hook_wrapper_sources(
    repo_root: Path,
    platform: str,
) -> tuple[Path, ...]:
    """Return source wrappers satisfying both accepted ownership conditions."""
    scripts_dir = Path(__file__).resolve().parent
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import universal_hooks_manifest as manifest

    candidates: list[Path] = []
    for subdir, source_rel in _hook_source_dirs(platform):
        source_dir = repo_root / source_rel
        pack_only_owner = (
            manifest.PACK_ONLY_SCRIPTS
            if subdir == "scripts"
            else manifest.PACK_ONLY_HOOKS
        )
        owned_names = set(manifest.canon_names(repo_root, subdir))
        owned_names.update(pack_only_owner[source_rel])
        for extension in (".ps1", ".sh"):
            for wrapper in sorted(source_dir.glob(f"*{extension}")):
                if wrapper.name not in owned_names:
                    continue
                if wrapper.stem in manifest.NON_REGISTERED_ENTRYPOINT_STEMS:
                    continue
                if not wrapper.with_suffix(".py").is_file():
                    continue
                candidates.append(wrapper)
    return tuple(candidates)


def profile_verification_exclusions(
    repo_root: Path,
    platform: str,
    hook_runtime: str,
) -> tuple[str, ...]:
    """Return provider-source-relative files intentionally absent by profile.

    This is the single owner used by all four installers' post-reclaim source
    verification. The wrapper profile requires every shipped wrapper. The
    Python profile permits only the same two-condition wrapper inventory that
    reclaim owns to be absent.
    """
    if hook_runtime != "python":
        return ()
    provider_root = repo_root / ("src.claude" if platform == "claude" else "src.codex")
    return tuple(
        sorted(
            wrapper.relative_to(provider_root).as_posix()
            for wrapper in owned_hook_wrapper_sources(repo_root, platform)
        )
    )


def reclaimable_hook_wrappers(
    repo_root: Path,
    installed_root: Path,
    platform: str,
) -> tuple[Path, ...]:
    """Return installed wrappers satisfying both accepted ownership conditions."""
    provider_root = repo_root / ("src.claude" if platform == "claude" else "src.codex")
    candidates: list[Path] = []
    for wrapper in owned_hook_wrapper_sources(repo_root, platform):
        source_relative = wrapper.relative_to(provider_root)
        if platform == "claude":
            installed_relative = source_relative.relative_to("agents")
        else:
            installed_relative = source_relative.relative_to("skills/lead")
        installed = installed_root / installed_relative
        if installed.is_file():
            candidates.append(installed)
    return tuple(candidates)


def _target_uses_wrapper(target: HookTarget) -> bool:
    executable_name = Path(target.executable).name.lower()
    if executable_name in WRAPPER_EXECUTABLES:
        return True
    return any(Path(arg.strip("'\"")).suffix.lower() in {".ps1", ".sh"} for arg in target.args)


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


def _registration_wrapper_state(
    data: dict[str, Any],
    expected_stems: set[str],
) -> bool:
    found: set[str] = set()
    wrapper_found = False
    for hook in _iter_command_hooks(data):
        for stem in expected_stems:
            if _hook_contains_marker(hook, stem):
                found.add(stem)
                command = hook.get("command", "")
                if isinstance(command, str):
                    if "args" in hook:
                        args = hook["args"]
                        if not isinstance(args, list) or not all(
                            isinstance(arg, str) for arg in args
                        ):
                            raise ValueError(
                                f"registered hook args are malformed for {stem}"
                            )
                        wrapper_found = wrapper_found or _target_uses_wrapper(
                            HookTarget(command, tuple(args))
                        )
                    else:
                        stripped = command.strip()
                        first = stripped.split(maxsplit=1)[0].strip("'\"") if stripped else ""
                        wrapper_found = wrapper_found or (
                            Path(first).name.lower() in WRAPPER_EXECUTABLES
                            or bool(
                                re.search(
                                    r"(?i)\.(?:ps1|sh)(?:['\"]?\s|$)",
                                    stripped,
                                )
                            )
                        )
                break
    missing = sorted(expected_stems - found)
    if missing:
        raise ValueError(
            "registered hook inventory is incomplete; refusing reclaim: "
            + ", ".join(missing)
        )
    return wrapper_found


def reclaim_stale_hook_wrappers(
    *,
    repo_root: Path,
    installed_root: Path,
    platform: str,
    registration_data: dict[str, Any],
    dry_run: bool,
    abort_policy: TestAbortPolicy = TestAbortPolicy(
        requested_stage=None,
        target_path=None,
    ),
) -> tuple[Path, ...]:
    """Reclaim last, only after direct registrations are present and verified."""
    candidates = reclaimable_hook_wrappers(repo_root, installed_root, platform)
    expected_stems = {path.stem for path in candidates}
    if not expected_stems:
        return ()
    if _registration_wrapper_state(registration_data, expected_stems):
        return ()
    abort_policy.checkpoint("reclaim")
    for candidate in candidates:
        if not dry_run:
            candidate.unlink()
    return candidates


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
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    # tempfile beside the REAL target so os.replace is atomic on the same FS.
    fd, tmp_path_str = tempfile.mkstemp(
        prefix=".install-hypothesis-hook.", suffix=".tmp", dir=str(real_target.parent)
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
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
) -> bool:
    """Insert our hook entry, removing any duplicates. Returns True if changed."""
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        sys.stderr.write("FAIL: 'hooks' key is not a JSON object\n")
        sys.exit(1)
    hook_entries = hooks.setdefault(hook_event, [])
    if not isinstance(hook_entries, list):
        sys.stderr.write(f"FAIL: 'hooks.{hook_event}' is not a JSON array\n")
        sys.exit(1)

    existing = find_our_entry_indices(hook_entries, script_marker)
    changed = False

    # If there are multiple of our entries (duplicates from earlier buggy
    # state), collapse them to a single entry containing the new content.
    if len(existing) > 1:
        # Delete duplicates from the end so earlier indices stay valid.
        for idx in reversed(existing[1:]):
            del hook_entries[idx]
        existing = [existing[0]]
        changed = True

    if existing:
        idx = existing[0]
        if hook_entries[idx] != new_entry:
            hook_entries[idx] = new_entry
            changed = True
    else:
        hook_entries.append(new_entry)
        changed = True

    return changed


def remove(data: dict[str, Any], hook_event: str, script_marker: str) -> bool:
    """Remove ALL of our hook entries. Returns True if changed."""
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return False
    hook_entries = hooks.get(hook_event)
    if not isinstance(hook_entries, list):
        return False
    indices = find_our_entry_indices(hook_entries, script_marker)
    if not indices:
        return False
    # Delete from the end so earlier indices stay valid.
    for idx in reversed(indices):
        del hook_entries[idx]
    # Clean up empty containers so the file does not gain ghost structure.
    if not hook_entries:
        del hooks[hook_event]
    if not hooks:
        del data["hooks"]
    return True


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
        help="Absolute installed .py hook target; wrapper/native paths are resolved from its stem",
    )
    parser.add_argument(
        "--host-os",
        choices=("posix", "windows"),
        default="posix",
        help="Host OS class used for target validation and Codex command serialization",
    )
    parser.add_argument(
        "--hook-runtime",
        choices=("wrapper", "python", "native"),
        default="python",
        help="Hook runtime profile (default: python; wrapper is rollback; native is reserved)",
    )
    parser.add_argument(
        "--hook-event",
        choices=("PreToolUse", "Stop", "SessionStart", "UserPromptSubmit"),
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
            "Override the PreToolUse matcher regex (default: "
            "Edit|Write|NotebookEdit|apply_patch). Use for a hook that must fire "
            "on a different tool set, e.g. 'Bash' for a shell-command guard. "
            "Ignored for the Stop event, which takes no matcher."
        ),
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
        "--reclaim-root",
        help="Installed provider root containing scripts/ and hooks/ to reclaim after verification",
    )
    parser.add_argument(
        "--repo-root",
        help="Repository root used to derive manifest ownership for reclaim",
    )
    parser.add_argument(
        "--preview-reclaim",
        action="store_true",
        help="Print the gated reclaim set without reading or mutating registration",
    )
    parser.add_argument(
        "--print-verification-exclusions",
        action="store_true",
        help="Print provider-source-relative files intentionally absent after reclaim",
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
        choices=TEST_TRANSACTION_STAGES[:-1],
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

        if args.print_verification_exclusions:
            if not args.repo_root:
                raise ValueError(
                    "--repo-root is required with --print-verification-exclusions"
                )
            for relative in profile_verification_exclusions(
                Path(args.repo_root).expanduser().resolve(),
                args.platform,
                args.hook_runtime,
            ):
                sys.stdout.write(relative + "\n")
            return 0

        if args.reclaim_root:
            if not args.repo_root:
                raise ValueError("--repo-root is required with --reclaim-root")
            if not args.test_install_scope:
                raise ValueError("--test-install-scope is required with --reclaim-root")
            repo_root = Path(args.repo_root).expanduser().resolve()
            installed_root = Path(args.reclaim_root).expanduser()
            install_scope = InstallScope(args.test_install_scope)
            abort_policy = TestAbortPolicy.resolve_and_preflight(
                None,
                install_scope,
                installed_root,
                repo_root,
            )
            candidates = reclaimable_hook_wrappers(
                repo_root,
                installed_root,
                args.platform,
            )
            if args.preview_reclaim:
                if not args.script_path:
                    raise ValueError("--script-path is required for --preview-reclaim")
                planned_target = resolve_hook_target(
                    args.script_path,
                    args.host_os,
                    args.hook_runtime,
                    args.platform,
                )
                if _target_uses_wrapper(planned_target):
                    sys.stdout.write("  wrapper profile: reclaim disabled\n")
                    return 0
                for candidate in candidates:
                    sys.stdout.write(f"  [dry-run] would reclaim hook wrapper: {candidate}\n")
                return 0

            registration_data = load_existing(target)
            removed = reclaim_stale_hook_wrappers(
                repo_root=repo_root,
                installed_root=installed_root,
                platform=args.platform,
                registration_data=registration_data,
                dry_run=args.dry_run,
                abort_policy=abort_policy,
            )
            if not removed:
                sys.stdout.write("  hook wrapper reclaim disabled or already complete\n")
            else:
                prefix = "[dry-run] would reclaim" if args.dry_run else "reclaimed"
                for candidate in removed:
                    sys.stdout.write(f"  {prefix} hook wrapper: {candidate}\n")
            return 0

        if args.remove:
            data = load_existing(target)
            changed = remove(data, args.hook_event, args.script_marker)
            action = "removed"
        else:
            if not args.script_path:
                raise ValueError("--script-path is required when installing a hook")
            hook_target = resolve_hook_target(
                args.script_path,
                args.host_os,
                args.hook_runtime,
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
                    hook_target, args.host_os, args.hook_event, args.tool_matcher
                )
            else:
                entry = build_generic_entry(
                    hook_target, args.hook_event, args.tool_matcher
                )
            data = load_existing(target)
            changed = install(data, entry, args.hook_event, args.script_marker)
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
