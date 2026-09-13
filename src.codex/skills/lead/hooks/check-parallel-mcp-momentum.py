#!/usr/bin/env python3
"""Soft root-only PreToolUse reminder for parallel and MCP work starts.

The Lead contract remains the sole owner of readiness, independence, admission,
capacity, and release decisions. This adapter only re-surfaces those duties at
deterministic repository-work starts. It never spawns, schedules, or blocks.
"""

from __future__ import annotations

import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from agents_mode_runtime import resolve_scalar
from hook_common import emit_advisory, parse_envelope, read_stdin_utf8


ACTIVE_MODES = frozenset({"auto", "force"})
REMINDER = (
    "[parallel and MCP momentum] Root Lead: if the user has not paused or parked "
    "new launches, recheck Ready before starting work; start useful compatible "
    "independent lanes without waiting and refill released capacity. Lead owns "
    "relevant MCP discovery and freshness for indexed results, and passes each "
    "lane only its needed tools and context. Keep leaves non-spawning; clean up "
    "owned stale processes, dead code, and disposable trash while preserving "
    "user or uncertain state. Advisory only: no decision, spawn, schedule, "
    "block, metering, or fan-out."
)


def _repository_context(envelope: dict) -> tuple[dict, Path, Path | None]:
    """Return the shared classifier, event cwd, and unambiguous repository root."""
    classifier = runpy.run_path(
        str(Path(__file__).resolve().with_name("check-repository-orientation.py"))
    )
    cwd_value = envelope.get("cwd")
    cwd = (
        Path(cwd_value).resolve(strict=False)
        if isinstance(cwd_value, str) and cwd_value
        else Path.cwd().resolve()
    )
    tool_input = envelope.get("tool_input")
    tool_name = str(envelope.get("tool_name", "")).lower()
    if isinstance(tool_input, dict) and tool_name in classifier["_MUTATION_TOOLS"]:
        raw_targets = classifier["_target_strings"](tool_input, tool_name=tool_name)
        target_paths = [classifier["_as_path"](value, cwd) for value in raw_targets]
        if target_paths:
            target_roots = [
                classifier["_nearest_git_root"](path) for path in target_paths
            ]
            root = target_roots[0]
            if root is None or any(candidate != root for candidate in target_roots):
                return classifier, cwd, None
            return classifier, cwd, root
    return classifier, cwd, classifier["_nearest_git_root"](cwd)


def _is_repository_work_start(
    envelope: dict,
    tool_input: dict,
    *,
    classifier: dict | None = None,
    cwd: Path | None = None,
    root: Path | None = None,
) -> bool:
    """Project this call through the existing repository-action classifier.

    Loading the sibling hook as source keeps its command/token/path rules as the
    single classifier owner. No module or cross-invocation cache is retained.
    """
    if classifier is None or cwd is None:
        classifier, cwd, discovered_root = _repository_context(envelope)
        if root is None:
            root = discovered_root
    tool_name = envelope["tool_name"].lower()
    raw_targets = classifier["_target_strings"](tool_input, tool_name=tool_name)
    target_paths = [classifier["_as_path"](value, cwd) for value in raw_targets]
    if root is None:
        return False

    # Production installers register this hook for the Claude `PowerShell`
    # tool as well as the shell aliases owned by the shared classifier. Project
    # that tool onto the same command-classification path instead of silently
    # dropping every registered PowerShell work start.
    if tool_name == "powershell":
        tool_name = "exec_command"
    if tool_name in classifier["_MUTATION_TOOLS"]:
        repository_targets = [
            path for path in target_paths if classifier["_inside"](path, root)
        ]
        return any(
            not classifier["_is_exempt"](path, root) for path in repository_targets
        )
    if tool_name in classifier["_SHELL_TOOLS"]:
        # Codex's canonical exec_command shape uses `cmd`; Claude/compatibility
        # shell wrappers use `command`. Accept both while keeping the command
        # classifier itself single-owned by check-repository-orientation.py.
        command = tool_input.get("cmd") if tool_name == "exec_command" else None
        if not isinstance(command, str) or not command:
            command = tool_input.get("command")
        if not isinstance(command, str) or not command:
            return False
        risky, _target = classifier["_risky_shell_target"](command, cwd, root)
        return bool(risky)
    return False


def main() -> int:
    try:
        envelope = parse_envelope(read_stdin_utf8())
        if not isinstance(envelope, dict) or "agent_id" in envelope:
            return 0
        if envelope.get("hook_event_name") != "PreToolUse":
            return 0
        if not isinstance(envelope.get("tool_name"), str) or not envelope["tool_name"]:
            return 0
        if not isinstance(envelope.get("tool_input"), dict):
            return 0
        classifier, cwd, root = _repository_context(envelope)
        if root is None:
            return 0
        if resolve_scalar("delegationMode", cwd=root) not in ACTIVE_MODES:
            return 0
        if resolve_scalar("parallelMode", cwd=root) not in ACTIVE_MODES:
            return 0
        if not _is_repository_work_start(
            envelope,
            envelope["tool_input"],
            classifier=classifier,
            cwd=cwd,
            root=root,
        ):
            return 0
        emit_advisory(envelope, REMINDER)
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
