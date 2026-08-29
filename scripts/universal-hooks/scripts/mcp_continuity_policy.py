#!/usr/bin/env python3
"""Shared semantic policy for MCP continuity across the three hook events.

This module is dependency-free and side-effect-free.  It classifies untrusted
hook input as data; it never executes shell text and never emits configuration
values.  Event adapters own envelope parsing and delivery.
"""

from __future__ import annotations

import json
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
        "[MCP / tools reminder - re-shown at session start and after every compaction]",
        "MCP servers may be connected in this environment. For codebase, architecture, API/docs, search, browser, debugger, profiler, or repository-understanding tasks, make MCP/tool-discovery an explicit checkpoint before falling back to ad-hoc shell reads.",
        "MCP tools load on demand: use the platform's tool discovery (e.g. ToolSearch) to see the connected servers and load a tool's schema, then call the relevant tool. If a relevant MCP is unavailable or broken, say so briefly instead of silently substituting a weaker path.",
        'CONNECTED but uninitialized is not unavailable: do NOT skip a connected MCP reporting "not initialized", "no index", "empty", or "no data yet". Many servers require or build their own index/state on first use — when they report no index, INITIALIZE them per the server\'s own instructions (e.g. run a code-graph server\'s init / check its status; codegraph builds its initial index via `codegraph init`, then a file-watcher keeps it fresh) and use or await the result — never silently substitute ad-hoc shell/grep. Only a genuinely absent server (not connected, not installed, or absent from tool discovery) may be skipped with an explanation.',
        "When mcpMode: force is active, relevant MCP use is a standing instruction. Under mcpMode: auto, still consider MCP first when it fits the task and record why it was skipped if the task explicitly asked for MCP.",
        "For a connected stateful or indexed MCP, repository/project/branch/worktree/indexed-input changes invalidate any earlier answer: use that MCP's own status/freshness probe; when it reports stale or pending, run its documented sync/update/reindex, confirm freshness again, then repeat the intended query. Example: CodeGraph `status -> sync -> fresh status -> repeat query`. If refresh fails, report it explicitly and do not present stale output as current. Stateless or live MCPs need no refresh.",
        "High-value categories when present: semantic code navigation and code-graph, Repomix or repository packers, language-server / LSP, current library / framework / API docs (use these instead of answering API questions from memory), debuggers and profilers, browser automation, memory, search, and fetch utilities.",
        "This STILL APPLIES AFTER COMPACTION - do not forget MCP just because the context was summarized.",
        "SUBAGENTS: dispatched agents inherit the runtime tool surface. In the dispatch prompt, explicitly allow relevant MCP discovery/use within the assigned role, scope, and safety limits; do not accidentally hide MCP availability, but keep any deliberate tool limits honest.",
    )
)

TURN_ANCHOR_CONTEXT = (
    "[turn anchor - re-shown every turn because a once-per-session reminder is overwritten"
    " by whatever you did last]\n"
    "Root main conversation (as Lead): continue until blocked; a passed slice is not completion."
    " Record it, take the next unchecked action, and dispatch the next admitted role. A final-"
    "style summary while a known next action remains IS the defect. If you genuinely need the"
    " operator, name the blocker or decision as the reason for stopping.\n"
    "Dispatched subagent: continue only the bounded work for your assigned profession, artifact,"
    " and gate; then return evidence and an optional non-binding recommended next role to the"
    " root, and stop. Never adopt $lead, dispatch a peer or downstream stage, advance the"
    " pipeline, or write agent-runs.jsonl.\n"
    "Universal no-self-residue checkpoint: before completion, commit, push, or handoff, settle"
    " every agent-owned process/resource and remove dead or temporary alternatives; preserve"
    " pre-existing user state, and treat ambiguous ownership as a destructive-action blocker.\n"
    "Root-only delegation: at the first decision point of non-trivial work, the root main"
    " conversation holding $lead classifies and routes to the matching specialist role/skill via"
    " the host delegation surface; take external-launch flags from the external-dispatch contract,"
    " never from memory. The root may directly launch a configured external wrapper; no provider"
    " or leaf may recursively launch another wrapper.\n"
    "MCP checkpoint: for repository navigation or understanding, discover and use the"
    " relevant configured MCP before an ad-hoc shell search; if shell is genuinely the"
    " right instrument, state why. For stateful/indexed MCPs, after repository/project/"
    " branch/worktree/indexed-input changes, use the MCP's own freshness probe; stale or"
    " pending means sync/update/reindex, fresh recheck, then repeat the query. Report a"
    " refresh failure; stateless/live MCPs are exempt."
)

ADMITTED_TOOLS = frozenset(
    {"Grep", "Bash", "PowerShell", "shell_command", "exec_command"}
)
SHELL_TOOLS = frozenset({"Bash", "PowerShell", "shell_command", "exec_command"})
SEARCH_COMMANDS = frozenset({"grep", "rg", "ag", "ack"})
DIRECTORY_CHANGE_COMMANDS = frozenset({"cd", "chdir", "pushd", "set-location"})
CODE_INTEL_HINTS = (
    "codegraph",
    "serena",
    "language-server",
    "lsp",
    "repomix",
)
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
SAFE_SERVER_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,80}$")
SHELL_OPERATORS = frozenset({";", "&&", "||", "|", "&", "(", ")"})
OPTIONS_WITH_VALUES = frozenset(
    {"-g", "--glob", "--type", "-t", "--include", "--exclude", "--iglob"}
)
WINDOWS_DRIVE_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
WINDOWS_ENV_SCOPE_RE = re.compile(r"%[^%]+%")


def _home_from(environ: Mapping[str, str]) -> Path:
    raw = environ.get("USERPROFILE") or environ.get("HOME")
    return Path(raw).expanduser() if raw else Path.home()


def _accepted_server_name(value: object) -> str | None:
    name = str(value)
    if not SAFE_SERVER_NAME_RE.fullmatch(name):
        return None
    low = name.casefold()
    return name if any(hint in low for hint in CODE_INTEL_HINTS) else None


def configured_code_intel_servers(
    environ: Mapping[str, str] | None = None,
) -> tuple[str, ...]:
    """Return only safe matching server names, never server configuration values."""
    source = os.environ if environ is None else environ
    home = _home_from(source)
    found: set[str] = set()
    for candidate in (home / ".claude.json", home / ".claude" / "settings.json"):
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        servers = data.get("mcpServers") if isinstance(data, dict) else None
        if isinstance(servers, dict):
            for value in servers:
                accepted = _accepted_server_name(value)
                if accepted is not None:
                    found.add(accepted)

    try:
        import tomllib
    except Exception:
        tomllib = None
    if tomllib is not None:
        try:
            with (home / ".codex" / "config.toml").open("rb") as handle:
                data = tomllib.load(handle)
        except Exception:
            data = None
        servers = data.get("mcp_servers") if isinstance(data, dict) else None
        if isinstance(servers, dict):
            for value in servers:
                accepted = _accepted_server_name(value)
                if accepted is not None:
                    found.add(accepted)
    return tuple(sorted(found, key=str.casefold))


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


def render_momentum_advisory(servers: tuple[str, ...]) -> str:
    """Render only up to three server names plus the remaining-name count."""
    shown = ", ".join(servers[:3])
    if len(servers) > 3:
        shown += f" (+{len(servers) - 3} more)"
    return (
        "[mcp-momentum AUDIT] this looks like a code-navigation search, and a "
        f"code-intelligence MCP is configured: {shown}. "
        "A text scan finds strings; those tools answer symbols, callers, and definitions. "
        "Load the relevant tool schema and ask it, or proceed if the shell scan is "
        "genuinely the right instrument here. AUDIT mode -- allowing."
    )
