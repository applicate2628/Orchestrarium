#!/usr/bin/env python3
"""Repository-orientation guard for PreToolUse — warn-only AUDIT mode.

Warn before a risky repository action when the current turn lacks exactly one
valid, task-scoped ``REPOSITORY ORIENTATION:`` record in assistant-authored
prose. This is a process backstop only: it never reads repository documents or
infers canonical status from deprecation words. The shared governance rule
remains binding. Every internal error fails open.

AUDIT mode: on a hit, ALWAYS ALLOW the action and never block. Deliver the
warning to the MODEL via `hookSpecificOutput.additionalContext` on stdout, exit
0 (see `hook_common.emit_advisory`). This is the corrected delivery channel: a
PreToolUse hook's previous stderr-plus-exit-1 form was measured to reach NOBODY
on either Claude Code 2.1.220 (transcript-only, model-invisible) or Codex CLI
0.145.0 (discarded entirely -- the non-2-exit branch never copies stderr). See
work-items/bugs/2026-07-26-mcp-reminder-uses-the-once-per-session-form-its-
sibling-calls-broken.md for the full falsification-controlled measurement
(mirrors machine-local-path / no-trash-in-repo / stale-relation-residue).
"""
from __future__ import annotations

import os
import re
import shlex
import sys
from pathlib import Path, PurePosixPath

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from hook_common import (  # noqa: E402
    emit_advisory,
    extract_assistant_prose,
    last_genuine_user_message,
    parse_envelope,
    read_stdin_utf8,
    read_transcript_tail,
)


RECORD_PREFIX = "REPOSITORY ORIENTATION:"
HISTORICAL_PREFIX = "USER-APPROVED HISTORICAL SCOPE:"
_RECORD_RE = re.compile(r"(?m)^\s*REPOSITORY ORIENTATION:\s*(\S.*)$")
_HISTORICAL_RE = re.compile(r"(?im)^\s*USER-APPROVED HISTORICAL SCOPE:\s*\S")
_EVIDENCE_RE = re.compile(r"(?:^|,)\s*[^,;\s]+:\d+(?:-\d+)?(?:\s*(?:,|$))")
_REQUIRED_FIELDS = ("scope", "status", "workflow", "protected", "evidence")
_STATUSES = {"live", "mutable", "frozen", "archived", "deprecated", "superseded", "conflict"}
_EXEMPT_SEGMENTS = {".scratch", ".reports", ".plans", "work-items"}
_STALE_SEGMENTS = {"archive": "archived", "deprecated": "deprecated", "superseded": "superseded", "frozen": "frozen"}
_SHELL_TOOLS = {"bash", "shell_command", "exec_command"}
_MUTATION_TOOLS = {"edit", "write", "notebookedit", "apply_patch"}
_SEPARATORS = set(";|&()")
_SHELL_KEYWORDS = {"if", "then", "elif", "else", "while", "until", "do", "!"}
_DISCOVERY_COMMANDS = {
    "cat", "find", "get-childitem", "get-content", "grep", "head", "ls", "pwd", "rg",
    "select-string", "tail", "test-path", "type", "where", "where.exe", "which",
}
_BUILD_TEST_RUN_COMMANDS = {"ctest", "make", "ninja", "msbuild", "pytest", "qmltestrunner"}


def _nearest_git_root(start: Path) -> Path | None:
    try:
        current = start.resolve(strict=False)
        if not current.is_dir():
            current = current.parent
        while True:
            if (current / ".git").exists():
                return current
            if current.parent == current:
                return None
            current = current.parent
    except Exception:
        return None


def _target_strings(tool_input: dict) -> list[str]:
    targets: list[str] = []
    for key in ("file_path", "notebook_path", "path"):
        value = tool_input.get(key)
        if isinstance(value, str) and value.strip():
            targets.append(value.strip())
    patch = tool_input.get("patch") or tool_input.get("input")
    if isinstance(patch, str):
        targets.extend(
            match.group(1).strip()
            for match in re.finditer(r"(?m)^\*\*\* (?:Add|Update|Delete) File:\s*(.+)$", patch)
        )
    return targets


def _as_path(value: str, cwd: Path) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else cwd / path).resolve(strict=False)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _is_exempt(path: Path, root: Path) -> bool:
    try:
        relative = path.relative_to(root)
    except ValueError:
        return True
    return bool(relative.parts) and relative.parts[0].lower() in _EXEMPT_SEGMENTS


def _tokenize_segments(command: str) -> list[list[str]] | None:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except (TypeError, ValueError):
        return None
    segments: list[list[str]] = []
    current: list[str] = []
    for token in tokens:
        if token and all(char in _SEPARATORS for char in token):
            if current:
                segments.append(current)
                current = []
            continue
        current.append(token)
    if current:
        segments.append(current)
    return segments


def _command_position(segment: list[str]) -> tuple[str, list[str]] | None:
    index = 0
    while index < len(segment):
        token = segment[index]
        if token.lower() in _SHELL_KEYWORDS:
            index += 1
            continue
        name = token.split("=", 1)[0]
        if "=" in token and name.isidentifier():
            index += 1
            continue
        return token, segment[index + 1 :]
    return None


def _local_path(token: str, cwd: Path, root: Path) -> Path | None:
    candidate_text = token.replace("\\", "/")
    if not (candidate_text.startswith(("./", "../")) or "/" in candidate_text):
        return None
    candidate = _as_path(candidate_text, cwd)
    if _inside(candidate, root) and candidate.exists():
        return candidate
    return None


def _first_non_option(args: list[str]) -> str | None:
    for token in args:
        if token == "--":
            continue
        if not token.startswith("-"):
            return token
    return None


def _risky_shell_target(command: str, cwd: Path, root: Path) -> tuple[bool, Path]:
    segments = _tokenize_segments(command)
    if segments is None:
        return False, cwd
    for segment in segments:
        position = _command_position(segment)
        if position is None:
            continue
        command_word, args = position
        name = Path(command_word.replace("\\", "/")).name.lower()
        if name in _DISCOVERY_COMMANDS:
            continue
        if name == "git":
            subcommand = _first_non_option(args)
            if subcommand in {"status", "log", "diff", "show"}:
                continue
        direct = _local_path(command_word, cwd, root)
        if direct is not None:
            return True, direct
        if name in _BUILD_TEST_RUN_COMMANDS:
            return True, cwd
        if name in {"cargo", "go", "dotnet", "npm", "pnpm", "yarn", "bun"}:
            if any(arg.lower() in {"build", "test", "run"} for arg in args):
                return True, cwd
        if name == "cmake" and "--build" in args:
            return True, cwd
        if name in {"python", "python3", "py", "node", "deno"}:
            lowered = [arg.lower() for arg in args]
            if "-m" in lowered:
                module_index = lowered.index("-m") + 1
                if module_index < len(lowered) and lowered[module_index] in {"pytest", "unittest"}:
                    return True, cwd
            script = _first_non_option(args)
            if script:
                local = _local_path(script, cwd, root)
                if local is not None:
                    return True, local
        if name in {"bash", "sh"}:
            script = _first_non_option(args)
            if script:
                local = _local_path(script, cwd, root)
                if local is not None:
                    return True, local
        if name in {"pwsh", "powershell", "powershell.exe"}:
            lowered = [arg.lower() for arg in args]
            for flag in ("-file", "-f"):
                if flag in lowered:
                    index = lowered.index(flag) + 1
                    if index < len(args):
                        local = _local_path(args[index], cwd, root)
                        if local is not None:
                            return True, local
    return False, cwd


def _parse_record(prose: str) -> dict[str, str] | None:
    matches = _RECORD_RE.findall(prose)
    if len(matches) != 1:
        return None
    fields: dict[str, str] = {}
    for item in matches[0].split(";"):
        if "=" not in item:
            return None
        key, value = (part.strip() for part in item.split("=", 1))
        if not key or not value or key in fields:
            return None
        fields[key] = value
    if any(not fields.get(field) for field in _REQUIRED_FIELDS):
        return None
    if fields["status"].lower() not in _STATUSES:
        return None
    if not _EVIDENCE_RE.search(fields["evidence"]):
        return None
    return fields


def _scope_contains(scope: str, targets: list[Path], root: Path) -> bool:
    normalized = scope.replace("\\", "/").strip().strip("/") or "."
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or ".." in pure.parts:
        return False
    scope_parts = () if normalized == "." else tuple(part.lower() for part in pure.parts)
    for target in targets:
        try:
            target_parts = tuple(part.lower() for part in target.relative_to(root).parts)
        except ValueError:
            return False
        if target_parts[: len(scope_parts)] != scope_parts:
            return False
    return True


def _stale_requirement(targets: list[Path], root: Path) -> str | None:
    for target in targets:
        try:
            parts = target.relative_to(root).parts
        except ValueError:
            continue
        for part in parts:
            required = _STALE_SEGMENTS.get(part.lower())
            if required:
                return required
    return None


def main() -> int:
    try:
        envelope = parse_envelope(read_stdin_utf8())
        if not envelope or envelope.get("agent_id"):
            return 0
        tool_input = envelope.get("tool_input")
        if not isinstance(tool_input, dict):
            return 0
        cwd_value = envelope.get("cwd")
        cwd = Path(cwd_value).resolve(strict=False) if isinstance(cwd_value, str) and cwd_value else Path.cwd().resolve()
        raw_targets = _target_strings(tool_input)
        target_paths = [_as_path(value, cwd) for value in raw_targets]
        root = _nearest_git_root(target_paths[0] if target_paths else cwd) or _nearest_git_root(cwd)
        if root is None:
            return 0

        tool_name = str(envelope.get("tool_name", "")).lower()
        risky = False
        action_targets: list[Path] = []
        if tool_name in _MUTATION_TOOLS:
            repository_targets = [path for path in target_paths if _inside(path, root)]
            action_targets = [path for path in repository_targets if not _is_exempt(path, root)]
            risky = bool(action_targets)
        elif tool_name in _SHELL_TOOLS:
            command = tool_input.get("command")
            if isinstance(command, str) and command:
                risky, shell_target = _risky_shell_target(command, cwd, root)
                action_targets = [shell_target]
        if not risky:
            return 0

        transcript_path = envelope.get("transcript_path")
        if not isinstance(transcript_path, str) or not Path(transcript_path).is_file():
            return 0
        entries = read_transcript_tail(transcript_path, 200)
        _user, _typed, current_turn = last_genuine_user_message(entries)
        if _user is None:
            return 0
        prose = "\n".join(filter(None, (extract_assistant_prose(entry) for entry in current_turn)))
        record = _parse_record(prose)
        valid = (
            record is not None
            and record["status"].lower() != "conflict"
            and _scope_contains(record["scope"], action_targets, root)
        )
        messages: list[str] = []
        if not valid:
            messages.append(
                "[repository-orientation AUDIT] risky repository action lacks exactly one valid, "
                "in-scope `REPOSITORY ORIENTATION:` record with scope/status/workflow/protected/"
                "evidence and a path:line citation, or records status=conflict. This is a warn-only "
                "backstop; the shared repository-orientation rule remains binding. AUDIT mode -- allowing."
            )

        required_status = _stale_requirement(action_targets, root)
        historical_scope = bool(_HISTORICAL_RE.search(prose))
        if required_status and (
            record is None or record.get("status", "").lower() != required_status or not historical_scope
        ):
            messages.append(
                f"[repository-orientation STALE-TARGET AUDIT] action target contains the path segment "
                f"requiring status={required_status!s} but the assistant record lacks that matching "
                "non-live status plus an explicit `USER-APPROVED HISTORICAL SCOPE:` statement. "
                "No repository prose was scanned and no canonical status was inferred. AUDIT mode -- allowing."
            )

        # Both findings share ONE hookSpecificOutput emission -- the harness reads
        # a single JSON object per hook call, so two independent print()s would
        # not compose the way two separate stderr lines used to.
        if messages:
            emit_advisory(envelope, " ".join(messages))
        # Exit 0: the advisory reaches the model via hookSpecificOutput.
        # additionalContext (see hook_common.emit_advisory) -- never exit 2 (block).
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    sys.exit(main())
