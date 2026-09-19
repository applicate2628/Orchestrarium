#!/usr/bin/env python3
"""Shared semantic policy for MCP continuity across the three hook events.

This module is dependency-free and side-effect-free.  It classifies untrusted
hook input as data; it never executes shell text and never emits configuration
values.  Event adapters own envelope parsing and delivery.
"""

from __future__ import annotations

import ntpath
import os
import posixpath
import re
import shlex
import stat
from pathlib import Path
from typing import Any, Mapping, NamedTuple


SESSION_START_CONTEXT = "\n".join(
    (
        "[MCP/tools reminder - session start and compaction]",
        "For codebase, architecture, API/docs, search, browser, debugger, profiler, or repository-understanding work, discover connected MCP/tools at runtime, load the relevant schema, and use the fitting tool before ad-hoc shell reads. Under mcpMode: force this is mandatory; under mcpMode: auto, consider MCP first and explain a skip when MCP was explicitly requested.",
        "A connected but uninitialized, empty, or unindexed tool is not unavailable: initialize it by its own instructions and use or await the result.",
        "Before using stateful or indexed repository evidence after repository, project, branch, worktree, or indexed-input changes, check status/freshness; when stale or pending, sync/update/reindex, confirm fresh, and repeat the intended query. When selecting/changing a project or recovering stale state, verify the reported project/index identity matches the selected root before use. Report known omitted coverage. When instructions conflict with an installed tool, inspect its own supported entrypoint/help/version; do not invent or reimplement its pipeline. Before treating graph call, dependency, or blast-radius output as exact decision evidence, match the qualified symbol plus declaring type/file where applicable to the requested target; distinguish direct calls, callback/indirect reachability, and fuzzy suggestions. Ambiguous/unmatched rows require source verification; do not declare them exact. This is not a per-call version check. Never present stale evidence. Use another path only if refresh fails, the tool is unavailable, the user forbids it, or an explicit resource bound is exceeded; state why. Stateless or live tools need no refresh.",
        "For dispatched work, give each lane only needed MCP/tools and context; keep its role, scope, safety limits, and mandatory gates unchanged.",
    )
)

TURN_ANCHOR_CONTEXT = (
    "[turn anchor]\n"
    "Root Lead: resume the current primary task after compaction or a side question. Side"
    " questions, status, and clarifications are commentary; then resume. Stop only when it is"
    " complete, the user pauses, cancels, or stops it, or every remaining authorized action is"
    " concretely blocked. A block or required user decision pauses only dependent work; run"
    " useful independent ready work now. Earlier progress is not completion. A standalone"
    " question with no active task may end normally.\n"
    "Delegate useful ready work by task to the matching specialist. Under the current default,"
    " Root owns dispatch; provider and leaf agents do not spawn or recursively launch wrappers."
    " Give each lane only needed tools and context; keep mandatory gates.\n"
    "For repository understanding, discover fitting runtime MCP/tools before ad-hoc search."
    " After repository, project, branch, worktree, or indexed-input changes, check"
    " status/freshness, sync/update/reindex stale state, confirm fresh, and retry. When selecting/changing"
    " a project or recovering stale state, verify the reported project/index identity matches the selected"
    " root before use, report known omitted coverage, and when instructions conflict with an installed tool"
    " inspect its own supported entrypoint/help/version rather than invent or reimplement its pipeline; before"
    " treating graph call, dependency, or blast-radius output as exact decision evidence, match the qualified"
    " symbol plus declaring type/file where applicable to the requested target, distinguish direct calls,"
    " callback/indirect reachability, and fuzzy suggestions; ambiguous/unmatched rows require source verification"
    " and are not declared exact. This is not a per-call version check. Use fallback"
    " only if refresh fails, the tool is unavailable, the user forbids it, or an explicit"
    " resource bound is exceeded; state why and never use stale evidence.\n"
    "Universal no-self-residue checkpoint: before completion, commit, push, or handoff, and"
    " before transfer, settle every owned process/resource and remove temporary or dead"
    " alternatives; preserve pre-existing user state and treat ambiguous ownership as a"
    " destructive-action blocker. Do not invent work."
)

ADMITTED_TOOLS = frozenset(
    {"Grep", "Bash", "PowerShell", "shell_command", "exec_command"}
)
SHELL_TOOLS = frozenset({"Bash", "PowerShell", "shell_command", "exec_command"})
SEARCH_COMMANDS = frozenset({"grep", "rg", "ag", "ack"})
DIRECTORY_CHANGE_COMMANDS = frozenset({"cd", "chdir", "pushd", "set-location"})
EXEMPT_SCOPE_SEGMENTS = frozenset({"work-items", ".reports", ".plans", ".scratch"})
SOURCE_SCOPE_SEGMENTS = frozenset({"src", "scripts", "tests", "lib", "app"})
CODE_SUFFIXES = frozenset(
    {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".go",
        ".rs",
        ".c",
        ".h",
        ".cpp",
        ".hpp",
        ".java",
        ".cs",
        ".rb",
        ".php",
    }
)

CODE_PATTERN_RE = re.compile(
    r"(def |class |function |func |impl |interface |struct |"
    r"import |from \w+ import|require\(|#include|"
    r"\bcall(er|ee)s?\b|\bdefinition\b|\breferences?\b)",
    re.IGNORECASE,
)
SHELL_OPERATORS = frozenset({";", "&&", "||", "|", "&", "(", ")"})
OPTIONS_WITH_VALUES = frozenset(
    {"-g", "--glob", "--type", "-t", "--include", "--exclude", "--iglob"}
)
WINDOWS_DRIVE_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
WINDOWS_ENV_SCOPE_RE = re.compile(r"%[^%]+%")


def _path_segments(value: str) -> tuple[str, ...]:
    normalized = value.strip("'\"").replace("\\", "/")
    return tuple(part.casefold() for part in normalized.split("/") if part not in {"", "."})


def _path_flavor(value: str) -> str | None:
    if WINDOWS_DRIVE_ABSOLUTE_RE.match(value) or value.startswith(("\\\\", "//")):
        return "windows"
    if value.startswith("/"):
        return "posix"
    return None


def _normalize_absolute_path(value: str, flavor: str) -> str | None:
    if not value or "\x00" in value:
        return None
    if flavor == "windows":
        normalized = ntpath.normpath(value.replace("/", "\\"))
        drive, tail = ntpath.splitdrive(normalized)
        if not drive or not tail.startswith("\\") or not ntpath.isabs(normalized):
            return None
        return normalized
    if flavor == "posix":
        if "\\" in value or not posixpath.isabs(value):
            return None
        return posixpath.normpath(value)
    return None


def _same_or_descendant(candidate: str, parent: str, flavor: str) -> bool:
    separator = "\\" if flavor == "windows" else "/"
    if flavor == "windows":
        candidate = candidate.casefold()
        parent = parent.casefold()
    if candidate == parent:
        return True
    prefix = parent if parent.endswith(separator) else parent + separator
    return candidate.startswith(prefix)


def _plain_git_marker(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if reparse_flag and getattr(metadata, "st_file_attributes", 0) & reparse_flag:
        return False
    return stat.S_ISDIR(metadata.st_mode) or stat.S_ISREG(metadata.st_mode)


def _ancestor_coordinates(value: str, flavor: str) -> tuple[str, ...]:
    path_module = ntpath if flavor == "windows" else posixpath
    ancestors: list[str] = []
    current = value
    while True:
        ancestors.append(current)
        parent = path_module.dirname(current)
        if parent == current:
            return tuple(ancestors)
        current = parent


class _ScopeCoordinate(NamedTuple):
    repository_root: str
    cwd: str
    flavor: str

    @classmethod
    def from_paths(
        cls,
        repository_root: object,
        cwd: object,
        flavor: str,
    ) -> _ScopeCoordinate | None:
        """Build a pure lexical coordinate without touching a target path."""
        if not isinstance(repository_root, str) or not isinstance(cwd, str):
            return None
        root = _normalize_absolute_path(repository_root, flavor)
        current = _normalize_absolute_path(cwd, flavor)
        if root is None or current is None or not _same_or_descendant(current, root, flavor):
            return None
        return cls(repository_root=root, cwd=current, flavor=flavor)

    @classmethod
    def from_cwd(cls, raw_cwd: object) -> _ScopeCoordinate | None:
        """Find the nearest plain .git marker from the provider-supplied cwd."""
        if not isinstance(raw_cwd, str) or not raw_cwd:
            return None
        flavor = _path_flavor(raw_cwd)
        if flavor is None or (os.name == "nt") != (flavor == "windows"):
            return None
        current = _normalize_absolute_path(raw_cwd, flavor)
        if current is None:
            return None
        for candidate in _ancestor_coordinates(current, flavor):
            if _plain_git_marker(Path(candidate) / ".git"):
                return cls.from_paths(candidate, current, flavor)
        return None

    def normalize_scope(self, value: object, relative_ambiguous: bool = False) -> str | None:
        if not isinstance(value, str):
            return None
        raw = value.strip()
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {"'", '"'}:
            raw = raw[1:-1]
        if (
            not raw
            or raw.startswith("~")
            or any(marker in raw for marker in ("$", "`", "*", "?", "[", "]", "{", "}"))
            or WINDOWS_ENV_SCOPE_RE.search(raw)
        ):
            return None

        path_module = ntpath if self.flavor == "windows" else posixpath
        if self.flavor == "windows":
            raw = raw.replace("/", "\\")
            drive, _tail = ntpath.splitdrive(raw)
            if drive and not ntpath.isabs(raw):
                return None
            absolute = ntpath.isabs(raw) and bool(drive)
        else:
            if "\\" in raw or WINDOWS_DRIVE_ABSOLUTE_RE.match(raw) or raw.startswith("//"):
                return None
            absolute = posixpath.isabs(raw)
        if relative_ambiguous and not absolute:
            return None
        combined = raw if absolute else path_module.join(self.cwd, raw)
        return _normalize_absolute_path(combined, self.flavor)


def _scope_is_exempt(
    value: object,
    coordinate: _ScopeCoordinate | None,
    relative_ambiguous: bool = False,
) -> bool:
    if coordinate is None:
        return False
    target = coordinate.normalize_scope(value, relative_ambiguous)
    if target is None:
        return False
    path_module = ntpath if coordinate.flavor == "windows" else posixpath
    return any(
        _same_or_descendant(
            target,
            path_module.join(coordinate.repository_root, segment),
            coordinate.flavor,
        )
        for segment in EXEMPT_SCOPE_SEGMENTS
    )


def _all_scopes_are_exempt(
    scopes: tuple[str, ...],
    coordinate: _ScopeCoordinate | None,
    relative_ambiguous: bool = False,
) -> bool:
    return bool(scopes) and all(
        _scope_is_exempt(scope, coordinate, relative_ambiguous) for scope in scopes
    )


def _scope_is_source_like(value: str) -> bool:
    segments = _path_segments(value)
    return any(segment in SOURCE_SCOPE_SEGMENTS for segment in segments) or any(
        value.casefold().endswith(suffix) for suffix in CODE_SUFFIXES
    )


def _scope_is_known_file(value: str) -> bool:
    normalized = value.strip("'\"").replace("\\", "/")
    name = normalized.rsplit("/", 1)[-1]
    return bool(name and "." in name and not any(char in name for char in "*?[]{}"))


def _shell_segments(command: str) -> tuple[tuple[str, ...], ...]:
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except (TypeError, ValueError):
        return ()
    segments: list[tuple[str, ...]] = []
    current: list[str] = []
    for token in tokens:
        if token in SHELL_OPERATORS or all(char in ";&|()" for char in token):
            if current:
                segments.append(tuple(current))
                current = []
            continue
        current.append(token)
    if current:
        segments.append(tuple(current))
    return tuple(segments)


def _search_invocations(command: str) -> tuple[tuple[str, tuple[str, ...], bool], ...]:
    invocations: list[tuple[str, tuple[str, ...], bool]] = []
    relative_ambiguous = False
    for segment in _shell_segments(command):
        index = 0
        while index < len(segment) and "=" in segment[index] and not segment[index].startswith("-"):
            index += 1
        if index < len(segment) and segment[index].casefold() in {"command", "env"}:
            index += 1
        if index >= len(segment):
            continue
        executable = Path(segment[index]).name.casefold()
        if executable in DIRECTORY_CHANGE_COMMANDS:
            relative_ambiguous = True
            continue
        if executable in SEARCH_COMMANDS:
            invocations.append((executable, segment[index + 1 :], relative_ambiguous))
    return tuple(invocations)


def _search_parts(
    args: tuple[str, ...], files_mode: bool = False
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    query = ""
    scopes: list[str] = []
    selectors: list[str] = []
    index = 0
    while index < len(args):
        token = args[index]
        low = token.casefold()
        if low in OPTIONS_WITH_VALUES:
            if index + 1 < len(args):
                selectors.append(args[index + 1])
                index += 2
                continue
        if any(low.startswith(prefix + "=") for prefix in ("--glob", "--type", "--include", "--iglob")):
            selectors.append(token.split("=", 1)[1])
        elif token.startswith("-"):
            pass
        elif files_mode:
            scopes.append(token)
        elif not query:
            query = token
        else:
            scopes.append(token)
        index += 1
    return query, tuple(scopes), tuple(selectors)


def _shell_search_is_navigation(
    executable: str,
    args: tuple[str, ...],
    coordinate: _ScopeCoordinate | None,
    relative_ambiguous: bool = False,
) -> bool:
    if executable == "grep" and not any(
        token in {"-r", "-R", "--recursive"}
        or (token.startswith("-") and not token.startswith("--") and "r" in token.casefold())
        for token in args
    ):
        return False
    files_mode = executable == "rg" and "--files" in args
    query, scopes, selectors = _search_parts(args, files_mode=files_mode)
    all_scopes_exempt = _all_scopes_are_exempt(scopes, coordinate, relative_ambiguous)
    if all_scopes_exempt:
        return False
    selector_is_code = any(
        selector.casefold().endswith(tuple(CODE_SUFFIXES))
        or any(suffix in selector.casefold() for suffix in CODE_SUFFIXES)
        or selector.casefold().lstrip(".") in {"py", "ts", "js", "go", "rs", "cpp", "java"}
        for selector in selectors
    )
    source_scope = any(_scope_is_source_like(scope) for scope in scopes)
    if files_mode:
        return not scopes or selector_is_code or source_scope
    if selector_is_code or source_scope:
        return True
    if query and CODE_PATTERN_RE.search(query):
        return not scopes or not all(_scope_is_known_file(scope) for scope in scopes)
    return False


def classify_tool_choice(
    tool_name: str,
    tool_input: Mapping[str, Any],
    raw_cwd: object = None,
) -> bool:
    """Classify one admitted PreToolUse choice as code navigation or not."""
    if tool_name not in ADMITTED_TOOLS or not isinstance(tool_input, Mapping):
        return False
    coordinate = _ScopeCoordinate.from_cwd(raw_cwd)
    if tool_name == "Grep":
        pattern = str(tool_input.get("pattern") or "")
        if not pattern:
            return False
        path = str(tool_input.get("path") or "")
        if path and _all_scopes_are_exempt((path,), coordinate):
            return False
        glob = str(tool_input.get("glob") or "")
        type_name = str(tool_input.get("type") or "")
        if type_name or any(suffix in glob.casefold() for suffix in CODE_SUFFIXES):
            return True
        if path and _scope_is_known_file(path):
            return False
        return bool(CODE_PATTERN_RE.search(pattern) or (path and _scope_is_source_like(path)))

    command_key = "cmd" if tool_name == "exec_command" and tool_input.get("cmd") else "command"
    command = tool_input.get(command_key)
    if not isinstance(command, str) or not command.strip():
        return False
    return any(
        _shell_search_is_navigation(executable, args, coordinate, relative_ambiguous)
        for executable, args, relative_ambiguous in _search_invocations(command)
    )


def render_momentum_advisory() -> str:
    """Render one provider-neutral runtime-discovery checkpoint."""
    return (
        "[mcp-momentum AUDIT] this looks like a code-navigation search. Use runtime "
        "tool discovery as the only availability source, load the relevant tool schema, "
        "and query it when it fits. A text scan finds strings; semantic tools can answer "
        "symbols, callers, and definitions. Names in configuration, documentation, or "
        "examples are non-normative and never select a tool. Proceed if the shell scan is "
        "genuinely the right instrument here. AUDIT mode -- allowing."
    )
