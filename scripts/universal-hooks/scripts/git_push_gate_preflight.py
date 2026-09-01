#!/usr/bin/env python3
"""Canonical immutable grammar and fast publication-gate preflight."""

from __future__ import annotations

import os
import re
import shlex
import types
from pathlib import Path
from typing import NamedTuple, get_args, get_origin, get_type_hints

from hook_common import (
    CURRENT_TURN_BYTE_CAP,
    STATUS_FOUND,
    extract_user_typed_text,
    parse_envelope,
    read_stdin_utf8,
    scan_current_turn_boundary,
)

APPROVE_MARKER_REGEX = re.compile(r"\[approve-publication\]", re.IGNORECASE)

class DataRegion(NamedTuple):
    kind: str
    start: int
    end: int

class PossibleCommandCandidate(NamedTuple):
    dialect: str
    source_span: tuple[int, int]
    words: tuple[str, ...]
    reason: str

class LexicalAtom(NamedTuple):
    value: str
    source_span: tuple[int, int]
    state: str
    literalized: bool
    operator_capable: bool
    token_membership: int

class LexicalOperation(NamedTuple):
    kind: str
    source_span: tuple[int, int]
    contribution: str

class _ShellLexicalState(NamedTuple):
    dialect: str
    atoms: tuple[LexicalAtom, ...]
    removed_spans: tuple[LexicalOperation, ...]
    data_regions: tuple[DataRegion, ...]
    status: str
    normalizations: tuple[LexicalOperation, ...]

class LexicalToken(NamedTuple):
    value: str
    source_spans: tuple[tuple[int, int], ...]
    states: tuple[str, ...]
    literalized: bool

class LexicalSegment(NamedTuple):
    tokens: tuple[str, ...]
    token_records: tuple[LexicalToken, ...]
    boundary_before: str
    boundary_after: str
    source_span: tuple[int, int]

class ShellLexicalRecord(NamedTuple):
    atoms: tuple[LexicalAtom, ...]
    operations: tuple[LexicalOperation, ...]
    removed_spans: tuple[LexicalOperation, ...]
    data_regions: tuple[DataRegion, ...]
    segments: tuple[LexicalSegment, ...]

class CommandIdentity(NamedTuple):
    dialect: str
    depth: int
    parent: CommandIdentity | None
    parent_source_span: tuple[int, int] | None
    ordinal: int
    input_kind: str
    wrapper_id: str | None
    payload_composition: str | None
    contributing_spans: tuple[tuple[int, int], ...]
    root_occurrence: str

class CommandInput(NamedTuple):
    kind: str
    dialect: str
    shell_text: str | None
    argv_records: tuple[LexicalToken, ...]
    payload_composition: str | None
    contributing_tokens: tuple[LexicalToken, ...]

class WrapperExecutableIdentity(NamedTuple):
    original_token: str
    exact_basename: str
    windows_folded_basename: str
    suffix_class: str
    dialect: str

class WrapperOptionSpec(NamedTuple):
    spelling: str
    accepted_forms: tuple[str, ...]
    arity: int
    mode: str | None
    requires_mode: str | None

class WrapperGrammar(NamedTuple):
    wrapper_id: str
    executable_names: tuple[str, ...]
    parent_dialects: tuple[str, ...]
    option_specs: tuple[WrapperOptionSpec, ...]
    option_terminator: str | None
    assignment_rule_id: str | None
    operand_rule: str
    payload_mode: str
    child_dialect: str
    case_sensitive: bool
    allow_payload_tail: bool

class TerminalParticipant(NamedTuple):
    kind: str
    token: LexicalToken
    structural_value: str | None
    classification: str
    reason: str

class WrapperProjection(NamedTuple):
    wrapper_id: str
    parent_identity: CommandIdentity
    consumed_options: tuple[LexicalToken, ...]
    consumed_assignments: tuple[LexicalToken, ...]
    operand_records: tuple[LexicalToken, ...]
    child_input: CommandInput | None
    terminal_state: str
    reason: str
    payload_composition: str | None
    contributing_tokens: tuple[LexicalToken, ...]
    candidate: PossibleCommandCandidate | None
    terminal_participants: tuple[TerminalParticipant, ...]

class StrictLiteralProjection(NamedTuple):
    status: str
    argv: tuple[str, ...]

class OptionOccurrence(NamedTuple):
    spelling: str
    role: str
    polarity: str
    consumed_value_index: int | None

class ExecutableCommand(NamedTuple):
    dialect: str
    tokens: tuple[str, ...]
    token_records: tuple[LexicalToken, ...]
    environment_assignments: tuple[str, ...]
    control_keywords: tuple[str, ...]
    executable: str
    arguments: tuple[str, ...]
    source_span: tuple[int, int]
    ordinal: int
    command_count: int
    boundary_before: str
    boundary_after: str
    sole_canonical_literal: bool
    nesting_context: str
    trailing_linebreak_only: bool
    confidence: str
    normalization_state: str

class GitPushInvocation(NamedTuple):
    command: ExecutableCommand | PossibleCommandCandidate
    executable: str
    environment_assignments: tuple[str, ...]
    git_global_options: tuple[str, ...]
    post_subcommand_tokens: tuple[str, ...]
    push_options: tuple[str, ...]
    positionals: tuple[str, ...]
    repository_context: str
    dry_run: bool
    only_direct_push: bool
    only_executable_command: bool
    git_global_occurrences: tuple[OptionOccurrence, ...]
    push_option_occurrences: tuple[OptionOccurrence, ...]
    option_status: str
    dry_run_state: str
    shell_context: str
    candidate: bool
    normalization_state: str

class EffectivePublicationRecord(NamedTuple):
    record_id: str
    identity: CommandIdentity
    kind: str
    push: GitPushInvocation
    certainty: str
    dry_credit_eligible: bool
    generic_credit_eligible: bool

class EffectivePublicationProjection(NamedTuple):
    records: tuple[EffectivePublicationRecord, ...]
    exact_complete: bool
    eligible_direct_dry: tuple[EffectivePublicationRecord, ...]
    eligible_direct_generic: tuple[EffectivePublicationRecord, ...]

class ShellParseResult(NamedTuple):
    identity: CommandIdentity
    dialect: str
    status: str
    lexical: ShellLexicalRecord
    segments: tuple[LexicalSegment, ...]
    commands: tuple[ExecutableCommand, ...]
    candidates: tuple[PossibleCommandCandidate, ...]
    strict_projection: StrictLiteralProjection
    wrapper_projections: tuple[WrapperProjection, ...]
    children: tuple[ShellParseResult, ...]
    pushes: tuple[GitPushInvocation, ...]
    effective_publications: EffectivePublicationProjection
    scan_execution: bool
    data_regions: tuple[DataRegion, ...]
    normalizations: tuple[LexicalOperation, ...]
    raw_command: str

class CommandDialectResolution(NamedTuple):
    dialect: str
    exact: bool

class GenericPushDecision(NamedTuple):
    status: str
    binding: tuple[str, str, str] | None

class PrRouteDenied(Exception):
    def __init__(self, failure_id: str):
        super().__init__(failure_id)
        self.failure_id = failure_id

def _wrapper_option(
    spelling: str,
    arity: int = 0,
    mode: str | None = None,
    requires_mode: str | None = None,
    accepted_forms: tuple[str, ...] | None = None,
) -> WrapperOptionSpec:
    forms = accepted_forms or (("DETACHED",) if arity else ("FLAG",))
    return WrapperOptionSpec(spelling, forms, arity, mode, requires_mode)

ASSIGNMENT_NAME_RULES = {
    "ENV_ASCII_SHELL_NAME_V1": r"[A-Za-z_][A-Za-z0-9_]*",
    "SUDO_ASCII_SHELL_NAME_V1": r"[A-Za-z_][A-Za-z0-9_]*",
}

class WrapperGrammarRegistry:
    """Minimal immutable R12 grammar; policy code never branches by wrapper."""

    _ROW_IDS = (
        "posix-eval",
        "posix-env",
        "posix-command",
        "posix-exec",
        "posix-sudo",
        "posix-shell-command",
        "powershell-host-command",
    )

    _ROWS = (
        WrapperGrammar(
            "posix-eval", ("eval",), ("posix",), (), None, None,
            "compose-all", "SPACE_JOIN_LOGICAL_ARGV", "same", True, True,
        ),
        WrapperGrammar(
            "posix-env", ("env",), ("posix",), (), "--", "ENV_ASCII_SHELL_NAME_V1",
            "direct", "DIRECT_ARGV", "same", True, True,
        ),
        WrapperGrammar(
            "posix-command", ("command",), ("posix",),
            (
                _wrapper_option("-p"),
                _wrapper_option("-v", mode="query"),
                _wrapper_option("-V", mode="query"),
            ),
            "--", None, "direct", "DIRECT_ARGV", "same", True, True,
        ),
        WrapperGrammar(
            "posix-exec", ("exec",), ("posix",),
            (
                _wrapper_option("-c"),
                _wrapper_option("-l"),
                _wrapper_option("-a", arity=1),
            ),
            "--", None, "direct", "DIRECT_ARGV", "same", True, True,
        ),
        WrapperGrammar(
            "posix-sudo", ("sudo",), ("posix",), (), "--", "SUDO_ASCII_SHELL_NAME_V1",
            "direct", "DIRECT_ARGV", "same", True, True,
        ),
        WrapperGrammar(
            "posix-shell-command", ("bash", "sh", "dash", "zsh"), ("posix",),
            (
                _wrapper_option("-c", arity=1, mode="command"),
                _wrapper_option("-lc", arity=1, mode="command"),
                _wrapper_option("-cl", arity=1, mode="command"),
                _wrapper_option("-l", requires_mode="command"),
                _wrapper_option("--login", requires_mode="command"),
            ),
            "--", None, "selector", "SINGLE_LOGICAL_TOKEN", "posix",
            True, True,
        ),
        WrapperGrammar(
            "powershell-host-command", ("powershell", "pwsh"),
            ("posix", "powershell"),
            (
                _wrapper_option("-Command", arity=1, mode="command"),
                _wrapper_option("-c", arity=1, mode="command"),
                _wrapper_option("-NoProfile"),
                _wrapper_option("-NonInteractive"),
                _wrapper_option("-NoLogo"),
                _wrapper_option("-Mta"),
                _wrapper_option("-Sta"),
                _wrapper_option("-ExecutionPolicy", arity=1),
                _wrapper_option("-InputFormat", arity=1),
                _wrapper_option("-OutputFormat", arity=1),
                _wrapper_option("-WindowStyle", arity=1),
                _wrapper_option("-File", arity=1, mode="file"),
                _wrapper_option("-f", arity=1, mode="file"),
            ),
            None, None, "selector", "SINGLE_LOGICAL_TOKEN", "powershell",
            False, False,
        ),
    )

    @classmethod
    def rows(cls) -> tuple[WrapperGrammar, ...]:
        cls.validate()
        return cls._ROWS

    @classmethod
    def validate(cls) -> None:
        rows = cls._ROWS
        if not isinstance(rows, tuple) or len(rows) != len(cls._ROW_IDS):
            raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
        if not all(isinstance(row, WrapperGrammar) for row in rows):
            raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
        if tuple(row.wrapper_id for row in rows) != cls._ROW_IDS:
            raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
        if tuple(ASSIGNMENT_NAME_RULES) != (
            "ENV_ASCII_SHELL_NAME_V1",
            "SUDO_ASCII_SHELL_NAME_V1",
        ):
            raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
        try:
            assignment_patterns_valid = all(
                isinstance(pattern, str)
                and bool(pattern)
                and re.compile(pattern) is not None
                for pattern in ASSIGNMENT_NAME_RULES.values()
            )
        except re.error:
            assignment_patterns_valid = False
        if not assignment_patterns_valid:
            raise PrRouteDenied("WPG-REGISTRY-SCHEMA")

        for row in rows:
            strings = (
                row.wrapper_id,
                row.operand_rule,
                row.payload_mode,
                row.child_dialect,
            )
            if not all(isinstance(value, str) and value for value in strings):
                raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
            if (
                not isinstance(row.executable_names, tuple)
                or not row.executable_names
                or not all(
                    isinstance(name, str) and bool(name)
                    for name in row.executable_names
                )
                or len(set(row.executable_names)) != len(row.executable_names)
            ):
                raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
            if (
                not isinstance(row.parent_dialects, tuple)
                or not row.parent_dialects
                or not all(
                    isinstance(dialect, str)
                    and dialect in {"posix", "powershell"}
                    for dialect in row.parent_dialects
                )
                or len(set(row.parent_dialects)) != len(row.parent_dialects)
            ):
                raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
            if not isinstance(row.option_specs, tuple):
                raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
            if row.option_terminator is not None and (
                not isinstance(row.option_terminator, str)
                or not row.option_terminator
            ):
                raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
            if row.assignment_rule_id is not None and (
                not isinstance(row.assignment_rule_id, str)
                or row.assignment_rule_id not in ASSIGNMENT_NAME_RULES
            ):
                raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
            if row.operand_rule not in {"compose-all", "direct", "selector"}:
                raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
            if row.payload_mode not in {
                "SPACE_JOIN_LOGICAL_ARGV",
                "DIRECT_ARGV",
                "SINGLE_LOGICAL_TOKEN",
            }:
                raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
            if row.child_dialect not in {"same", "posix", "powershell"}:
                raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
            if not isinstance(row.case_sensitive, bool) or not isinstance(
                row.allow_payload_tail, bool
            ):
                raise PrRouteDenied("WPG-REGISTRY-SCHEMA")

            option_names: set[str] = set()
            for option in row.option_specs:
                if not isinstance(option, WrapperOptionSpec):
                    raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
                if not isinstance(option.spelling, str) or not option.spelling:
                    raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
                option_key = (
                    option.spelling
                    if row.case_sensitive
                    else option.spelling.lower()
                )
                if option_key in option_names:
                    raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
                option_names.add(option_key)
                if (
                    not isinstance(option.accepted_forms, tuple)
                    or not option.accepted_forms
                    or not all(
                        isinstance(form, str)
                        and form in {
                            "FLAG",
                            "DETACHED",
                            "EQUALS_ATTACHED",
                            "SHORT_ATTACHED",
                        }
                        for form in option.accepted_forms
                    )
                    or len(set(option.accepted_forms)) != len(option.accepted_forms)
                ):
                    raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
                if (
                    not isinstance(option.arity, int)
                    or isinstance(option.arity, bool)
                    or option.arity not in {0, 1}
                ):
                    raise PrRouteDenied("WPG-REGISTRY-SCHEMA")
                for state in (option.mode, option.requires_mode):
                    if state is not None and (
                        not isinstance(state, str) or not state
                    ):
                        raise PrRouteDenied("WPG-REGISTRY-SCHEMA")

    @classmethod
    def identity(cls, executable: str, dialect: str) -> WrapperExecutableIdentity:
        exact = _basename(executable)
        suffix = "EXE" if exact.lower().endswith(".exe") else "NONE"
        folded = exact[:-4].lower() if suffix == "EXE" else exact.lower()
        return WrapperExecutableIdentity(executable, exact, folded, suffix, dialect)

    @classmethod
    def resolve(
        cls, executable: str | WrapperExecutableIdentity, dialect: str | None = None
    ) -> WrapperGrammar | None:
        identity = (
            executable
            if isinstance(executable, WrapperExecutableIdentity)
            else cls.identity(executable, dialect or "unsupported")
        )
        for row in cls.rows():
            if identity.dialect not in row.parent_dialects:
                continue
            names = (
                row.executable_names
                if row.case_sensitive
                else tuple(name.lower() for name in row.executable_names)
            )
            candidate = (
                identity.exact_basename
                if row.case_sensitive
                else identity.windows_folded_basename
            )
            if candidate in names:
                return row
        return None

MARKER_MAX_MESSAGE_LENGTH = 200

PUSH_INSTRUCTION_REGEX = re.compile(
    r"(?ix)"
    r"\bpush\b|git\s+push|\bpublish\b|"
    r"запушь|запушить|запушь?те|пушни|пушь|пуш|пушай|пушить|"
    r"залей|залить|"
    r"опубликуй|опубликовать|публикуй"
)

_GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}

_REPOSITORY_ENV_NAMES = {"GIT_DIR", "GIT_WORK_TREE"}

_REPOSITORY_GIT_OPTIONS = {"-C", "--git-dir", "--work-tree", "--namespace"}

_SAFE_PUSH_OPTIONS = {"-q", "--quiet", "-v", "--verbose", "--progress", "--no-progress", "--porcelain"}

_PUSH_REQUIRED_VALUE_OPTIONS = {
    "--repo", "--no-repo", "--receive-pack", "--no-receive-pack",
    "--exec", "--no-exec", "-o", "--push-option", "--no-push-option",
}

_PUSH_REQUIRED_ENUM_OPTIONS = {"--recurse-submodules", "--no-recurse-submodules"}

_PUSH_RECURSE_VALUES = {"check", "on-demand", "no"}

_PUSH_OPTIONAL_GLUED_OPTIONS = {"--force-with-lease", "--signed"}

_PUSH_BOOLEAN_OPTIONS = {
    "-q", "-v", "-n", "-f", "-u", "-4", "-6",
    "--quiet", "--verbose", "--dry-run", "--no-dry-run",
    "--all", "--no-all", "--branches", "--no-branches",
    "--mirror", "--no-mirror", "--delete", "--no-delete",
    "--tags", "--no-tags", "--porcelain", "--no-porcelain",
    "--force", "--no-force", "--force-if-includes", "--no-force-if-includes",
    "--thin", "--no-thin", "--set-upstream", "--no-set-upstream",
    "--progress", "--no-progress", "--prune", "--no-prune",
    "--verify", "--no-verify", "--follow-tags", "--no-follow-tags",
    "--atomic", "--no-atomic", "--ipv4", "--no-ipv4", "--ipv6", "--no-ipv6",
    "--no-force-with-lease", "--no-signed",
}

_SHELL_KEYWORDS = {"if", "then", "elif", "else", "while", "until", "do", "!"}

def _is_redirection_operator(token: str) -> bool:
    return ("<" in token or ">" in token) and all(character in "<>&" for character in token)

def _line_content(line: str) -> str:
    return line[:-2] if line.endswith("\r\n") else line[:-1] if line.endswith("\n") else line

def _mask_non_newlines(chars: list[str], start: int, end: int) -> None:
    for index in range(start, end):
        if chars[index] not in "\r\n":
            chars[index] = " "

def _posix_heredoc_specs(line: str) -> tuple[list[tuple[str, bool]], bool]:
    """Return literal heredoc delimiters from one command line.

    The parse is all-or-nothing.  POSIX ``<<<`` is an ordinary here-string
    redirection and never enters the heredoc queue.  A delimiter word is
    assembled across adjacent quoted/unquoted/backslash segments after quote
    removal; expansion-bearing or incomplete words are outside this bounded
    grammar and make the whole header uncertain.
    """
    specs: list[tuple[str, bool]] = []
    quote: str | None = None
    index = 0
    while index < len(line):
        character = line[index]
        if quote is not None:
            if quote == '"' and character == "\\":
                index += 2
                continue
            if character == quote:
                quote = None
            index += 1
            continue
        if character == "\\":
            index += 2
            continue
        if character == "#" and (index == 0 or line[index - 1] in " \t;|&()"):
            break
        if character in "'\"":
            quote = character
            index += 1
            continue
        if not line.startswith("<<", index):
            index += 1
            continue
        if line.startswith("<<<", index):
            index += 3
            continue
        index += 2
        strip_tabs = index < len(line) and line[index] == "-"
        if strip_tabs:
            index += 1
        while index < len(line) and line[index] in " \t":
            index += 1
        if index >= len(line):
            return [], False

        value: list[str] = []
        while index < len(line) and line[index] not in " \t;|&()<>":
            character = line[index]
            if character == "\\":
                index += 1
                if index >= len(line):
                    return [], False
                value.append(line[index])
                index += 1
                continue
            if character == "'":
                end = line.find("'", index + 1)
                if end < 0:
                    return [], False
                value.extend(line[index + 1:end])
                index = end + 1
                continue
            if character == '"':
                index += 1
                while index < len(line) and line[index] != '"':
                    character = line[index]
                    if character == "\\":
                        if index + 1 >= len(line):
                            return [], False
                        escaped = line[index + 1]
                        if escaped in '$`"\\':
                            value.append(escaped)
                            index += 2
                            continue
                        value.append("\\")
                        index += 1
                        continue
                    if character in "$`":
                        return [], False
                    value.append(character)
                    index += 1
                if index >= len(line):
                    return [], False
                index += 1
                continue
            if character in "$`":
                return [], False
            value.append(character)
            index += 1
        delimiter = "".join(value)
        if not delimiter:
            return [], False
        specs.append((delimiter, strip_tabs))
    return specs, True

def _powershell_data_regions(command: str) -> tuple[tuple[DataRegion, ...], str]:
    lines = command.splitlines(keepends=True)
    if command and (not lines or sum(len(line) for line in lines) < len(command)):
        lines.append(command[sum(len(line) for line in lines):])
    starts: list[int] = []
    offset = 0
    for line in lines:
        starts.append(offset)
        offset += len(line)

    regions: list[DataRegion] = []
    block_depth = 0
    block_start = 0
    quote: str | None = None
    line_index = 0
    start_index = 0
    while line_index < len(lines):
        content = _line_content(lines[line_index])
        index = start_index
        start_index = 0
        while index < len(content):
            character = content[index]
            if block_depth:
                if content.startswith("<#", index):
                    block_depth += 1
                    index += 2
                    continue
                if content.startswith("#>", index):
                    block_depth -= 1
                    index += 2
                    if block_depth == 0:
                        regions.append(DataRegion(
                            "powershell-block-comment", block_start, starts[line_index] + index
                        ))
                    continue
                index += 1
                continue
            if quote == "'":
                if character == "'" and index + 1 < len(content) and content[index + 1] == "'":
                    index += 2
                    continue
                if character == "'":
                    quote = None
                index += 1
                continue
            if quote == '"':
                if character == "`":
                    index += 2
                    continue
                if character == '"':
                    quote = None
                index += 1
                continue
            if character == "`":
                index += 2
                continue
            if character == "#":
                break
            if content.startswith("<#", index):
                block_start = starts[line_index] + index
                block_depth = 1
                index += 2
                continue
            if content.startswith(("@'", '@"'), index) and (
                index == 0 or content[index - 1].isspace() or content[index - 1] in "=,(;|&"
            ) and not content[index + 2:].strip():
                delimiter = content[index + 1] + "@"
                cursor = line_index + 1
                while cursor < len(lines):
                    candidate = _line_content(lines[cursor])
                    if candidate.startswith(delimiter) and (
                        len(candidate) == len(delimiter)
                        or candidate[len(delimiter)] in " \t;|&()"
                    ):
                        break
                    cursor += 1
                if cursor >= len(lines):
                    return (), "SCG-UNTERMINATED-DATA"
                regions.append(DataRegion(
                    "powershell-here-string",
                    starts[line_index] + index,
                    starts[cursor] + len(delimiter),
                ))
                line_index = cursor
                content = _line_content(lines[line_index])
                index = len(delimiter)
                continue
            if character in "'\"":
                quote = character
            index += 1
        line_index += 1
    if block_depth or quote is not None:
        return (), "SCG-AMBIGUOUS-DATA"
    return tuple(regions), "SCG-PARSED"

def _mask_shell_data_regions(command: str, dialect: str) -> tuple[str, tuple[DataRegion, ...], str]:
    lines = command.splitlines(keepends=True)
    if command and (not lines or sum(len(line) for line in lines) < len(command)):
        lines.append(command[sum(len(line) for line in lines):])
    starts: list[int] = []
    offset = 0
    for line in lines:
        starts.append(offset)
        offset += len(line)
    pending_regions: list[DataRegion] = []
    if dialect in ("powershell", "posix-compat"):
        ps_regions, ps_status = _powershell_data_regions(command)
        if ps_status != "SCG-PARSED":
            return command, (), ps_status
        pending_regions.extend(ps_regions)

    line_index = 0
    while line_index < len(lines):
        content = _line_content(lines[line_index])
        if dialect in ("posix", "posix-compat"):
            specs, valid = _posix_heredoc_specs(content)
            if not valid:
                return command, (), "SCG-AMBIGUOUS-DATA"
            if specs:
                cursor = line_index + 1
                header_regions: list[DataRegion] = []
                for delimiter, strip_tabs in specs:
                    body_start = starts[cursor] if cursor < len(lines) else len(command)
                    while cursor < len(lines):
                        candidate = _line_content(lines[cursor])
                        comparable = candidate.lstrip("\t") if strip_tabs else candidate
                        if comparable == delimiter:
                            break
                        cursor += 1
                    if cursor >= len(lines):
                        return command, (), "SCG-UNTERMINATED-DATA"
                    region_end = starts[cursor] + len(_line_content(lines[cursor]))
                    header_regions.append(DataRegion("posix-heredoc", body_start, region_end))
                    cursor += 1
                pending_regions.extend(header_regions)
                line_index = cursor
                continue
        line_index += 1
    chars = list(command)
    for region in sorted(pending_regions, key=lambda item: (item.start, item.end)):
        _mask_non_newlines(chars, region.start, region.end)
    return "".join(chars), tuple(pending_regions), "SCG-PARSED"

_LEXICAL_WILDCARD = "\ufff0"

_POWERSHELL_UNSUPPORTED_ESCAPE_STARTERS = frozenset("0abefnrtuv")

def _build_shell_lexical_state(command: str, dialect: str) -> _ShellLexicalState:
    """Run the one bounded provenance-carrying lexical pass for ``command``."""
    _masked, data_regions, data_status = _mask_shell_data_regions(command, dialect)
    atoms: list[LexicalAtom] = []
    operations: list[LexicalOperation] = []
    removed: list[LexicalOperation] = []
    status = data_status
    quote: str | None = None
    token_open = False
    token_membership = -1
    index = 0
    region_index = 0

    def worsen(value: str) -> None:
        nonlocal status
        rank = {
            "SCG-PARSED": 0,
            "SCG-UNPARSEABLE": 1,
            "SCG-AMBIGUOUS-DATA": 2,
            "SCG-UNTERMINATED-DATA": 3,
            "SCG-UNSUPPORTED-ESCAPE": 4,
            "SCG-UNTERMINATED-ESCAPE": 5,
        }
        if rank.get(value, 6) > rank.get(status, 0):
            status = value

    def begin_token() -> int:
        nonlocal token_open, token_membership
        if not token_open:
            token_membership += 1
            token_open = True
        return token_membership

    def emit(
        value: str,
        start: int,
        end: int,
        state: str,
        *,
        literalized: bool = False,
        operator_capable: bool = False,
    ) -> None:
        nonlocal token_open
        if operator_capable or (
            state == "ordinary" and not literalized and value in " \t\r"
        ):
            membership = -1
            token_open = False
        else:
            membership = begin_token()
        atoms.append(LexicalAtom(
            value, (start, end), state, literalized, operator_capable, membership
        ))

    def record(kind: str, start: int, end: int, contribution: str, *, removed_span: bool) -> None:
        operation = LexicalOperation(kind, (start, end), contribution)
        operations.append(operation)
        if removed_span:
            removed.append(operation)

    def in_data(position: int) -> DataRegion | None:
        nonlocal region_index
        while region_index < len(data_regions) and position >= data_regions[region_index].end:
            region_index += 1
        if region_index < len(data_regions):
            region = data_regions[region_index]
            if region.start <= position < region.end:
                return region
        return None

    while index < len(command):
        region = in_data(index)
        if region is not None:
            if command[index] in "\r\n":
                end = index + 2 if command.startswith("\r\n", index) else index + 1
                emit(command[index:end], index, end, "data", operator_capable=True)
                index = end
            else:
                index += 1
            continue

        character = command[index]
        if dialect in ("posix", "posix-compat"):
            if quote == "'":
                if character == "'":
                    quote = None
                    index += 1
                else:
                    emit(character, index, index + 1, "single-quoted", literalized=True)
                    index += 1
                continue
            if quote == '"':
                if character == '"':
                    quote = None
                    index += 1
                    continue
                if character == "\\":
                    if index + 1 >= len(command):
                        worsen("SCG-UNTERMINATED-ESCAPE")
                        emit(_LEXICAL_WILDCARD, index, index + 1, "double-quoted", literalized=True)
                        index += 1
                        continue
                    if command[index + 1] == "\n":
                        record("posix-continuation", index, index + 2, "quoted-argument", removed_span=True)
                        index += 2
                        continue
                    escaped = command[index + 1]
                    if escaped in '$`"\\':
                        emit(escaped, index, index + 2, "double-quoted", literalized=True)
                        record("posix-literal-escape", index, index + 2, "quoted-argument", removed_span=False)
                        index += 2
                        continue
                    emit("\\", index, index + 1, "double-quoted", literalized=True)
                    index += 1
                    continue
                emit(character, index, index + 1, "double-quoted", literalized=True)
                index += 1
                continue
            if character == "#" and not token_open:
                while index < len(command) and command[index] not in "\r\n":
                    index += 1
                continue
            if character == "'":
                begin_token()
                quote = "'"
                index += 1
                continue
            if character == '"':
                begin_token()
                quote = '"'
                index += 1
                continue
            if character == "\\":
                if index + 1 >= len(command):
                    worsen("SCG-UNTERMINATED-ESCAPE")
                    emit(_LEXICAL_WILDCARD, index, index + 1, "ordinary", literalized=True)
                    index += 1
                    continue
                if command[index + 1] == "\n":
                    record("posix-continuation", index, index + 2, "command-token", removed_span=True)
                    index += 2
                    continue
                if command.startswith("\r\n", index + 1) or command[index + 1] == "\r":
                    end = index + 3 if command.startswith("\r\n", index + 1) else index + 2
                    worsen("SCG-UNSUPPORTED-ESCAPE")
                    emit(_LEXICAL_WILDCARD, index, end, "ordinary", literalized=True)
                    index = end
                    continue
                emit(command[index + 1], index, index + 2, "ordinary", literalized=True)
                record("posix-literal-escape", index, index + 2, "command-token", removed_span=False)
                index += 2
                continue
            operator = character in "();<>|&\n"
            emit(character, index, index + 1, "ordinary", operator_capable=operator)
            index += 1
            continue

        # PowerShell lexical subset.
        if quote == "'":
            if character == "'" and index + 1 < len(command) and command[index + 1] == "'":
                emit("'", index, index + 2, "single-quoted", literalized=True)
                index += 2
            elif character == "'":
                quote = None
                index += 1
            else:
                emit(character, index, index + 1, "single-quoted", literalized=True)
                index += 1
            continue
        if quote == '"':
            if character == '"':
                quote = None
                index += 1
                continue
            if character == "`":
                if index + 1 >= len(command):
                    worsen("SCG-UNTERMINATED-ESCAPE")
                    emit(_LEXICAL_WILDCARD, index, index + 1, "double-quoted", literalized=True)
                    index += 1
                    continue
                if command.startswith("\r\n", index + 1) or command[index + 1] == "\n":
                    end = index + 3 if command.startswith("\r\n", index + 1) else index + 2
                    value = command[index + 1:end]
                    emit(value, index, end, "double-quoted", literalized=True)
                    record("powershell-preserved-token-newline", index, end, "quoted-argument", removed_span=False)
                    index = end
                    continue
                if command[index + 1] == "\r":
                    worsen("SCG-UNSUPPORTED-ESCAPE")
                    emit(_LEXICAL_WILDCARD, index, index + 2, "double-quoted", literalized=True)
                    index += 2
                    continue
                escaped = command[index + 1]
                if not escaped.isascii() or not escaped.isprintable() or escaped.lower() in _POWERSHELL_UNSUPPORTED_ESCAPE_STARTERS:
                    unsupported_end = index + 2
                    if escaped.lower() == "u" and unsupported_end < len(command) and command[unsupported_end] == "{":
                        closing = command.find("}", unsupported_end + 1, min(len(command), unsupported_end + 9))
                        if closing >= 0:
                            unsupported_end = closing + 1
                    worsen("SCG-UNSUPPORTED-ESCAPE")
                    emit(_LEXICAL_WILDCARD, index, unsupported_end, "double-quoted", literalized=True)
                    index = unsupported_end
                else:
                    emit(escaped, index, index + 2, "double-quoted", literalized=True)
                    record("powershell-literal-escape", index, index + 2, "quoted-argument", removed_span=False)
                    index += 2
                continue
            emit(character, index, index + 1, "double-quoted", literalized=True)
            index += 1
            continue
        if character == "#":
            while index < len(command) and command[index] not in "\r\n":
                index += 1
            continue
        if character == "'":
            begin_token()
            quote = "'"
            index += 1
            continue
        if character == '"':
            begin_token()
            quote = '"'
            index += 1
            continue
        if character == "`":
            if index + 1 >= len(command):
                worsen("SCG-UNTERMINATED-ESCAPE")
                emit(_LEXICAL_WILDCARD, index, index + 1, "ordinary", literalized=True)
                index += 1
                continue
            if command.startswith("\r\n", index + 1):
                end = index + 3
                following = end
                while following < len(command) and command[following] in " \t":
                    following += 1
                if token_open:
                    emit("\n", index, end, "ordinary", operator_capable=True)
                    record("powershell-open-token-crlf-boundary", index, end, "separator-decision", removed_span=True)
                elif following < len(command) and command[following] not in "\r\n":
                    record("powershell-token-boundary-continuation", index, end, "separator-decision", removed_span=True)
                else:
                    worsen("SCG-UNSUPPORTED-ESCAPE")
                    emit(_LEXICAL_WILDCARD, index, end, "ordinary", literalized=True)
                index = end
                continue
            if command[index + 1] == "\n":
                end = index + 2
                following = end
                while following < len(command) and command[following] in " \t":
                    following += 1
                if not token_open and following < len(command) and command[following] not in "\r\n":
                    record("powershell-token-boundary-continuation", index, end, "separator-decision", removed_span=True)
                elif token_open:
                    emit("\n", index, end, "ordinary", literalized=True)
                    record("powershell-preserved-token-newline", index, end, "command-token", removed_span=False)
                else:
                    worsen("SCG-UNSUPPORTED-ESCAPE")
                    emit(_LEXICAL_WILDCARD, index, end, "ordinary", literalized=True)
                index = end
                continue
            if command[index + 1] == "\r":
                worsen("SCG-UNSUPPORTED-ESCAPE")
                emit(_LEXICAL_WILDCARD, index, index + 2, "ordinary", literalized=True)
                index += 2
                continue
            escaped = command[index + 1]
            if not escaped.isascii() or not escaped.isprintable() or escaped.lower() in _POWERSHELL_UNSUPPORTED_ESCAPE_STARTERS:
                unsupported_end = index + 2
                if escaped.lower() == "u" and unsupported_end < len(command) and command[unsupported_end] == "{":
                    closing = command.find("}", unsupported_end + 1, min(len(command), unsupported_end + 9))
                    if closing >= 0:
                        unsupported_end = closing + 1
                worsen("SCG-UNSUPPORTED-ESCAPE")
                emit(_LEXICAL_WILDCARD, index, unsupported_end, "ordinary", literalized=True)
                index = unsupported_end
            else:
                emit(escaped, index, index + 2, "ordinary", literalized=True)
                record("powershell-literal-escape", index, index + 2, "command-token", removed_span=False)
                index += 2
            continue
        operator = character in "();<>|&\n"
        emit(character, index, index + 1, "ordinary", operator_capable=operator)
        index += 1

    if quote is not None:
        worsen("SCG-UNPARSEABLE")
    return _ShellLexicalState(
        dialect, tuple(atoms), tuple(removed), data_regions, status, tuple(operations)
    )

def _tokenize_shell_lexical_state(
    state: _ShellLexicalState,
) -> tuple[LexicalSegment, ...]:
    segments: list[LexicalSegment] = []
    tokens: list[str] = []
    token_records: list[LexicalToken] = []
    token_atoms: list[LexicalAtom] = []
    segment_atoms: list[LexicalAtom] = []
    boundary_before = "start"
    skip_redirection_target = False

    def flush_token() -> None:
        nonlocal token_atoms, skip_redirection_target
        if not token_atoms:
            return
        value = "".join(atom.value for atom in token_atoms)
        if skip_redirection_target:
            skip_redirection_target = False
        else:
            tokens.append(value)
            states = tuple(dict.fromkeys(atom.state for atom in token_atoms))
            token_records.append(LexicalToken(
                value,
                tuple(atom.source_span for atom in token_atoms),
                states,
                any(atom.literalized for atom in token_atoms),
            ))
            segment_atoms.extend(token_atoms)
        token_atoms = []

    def flush_segment(boundary_after: str) -> None:
        nonlocal tokens, token_records, segment_atoms
        flush_token()
        if not tokens:
            return
        start = min(atom.source_span[0] for atom in segment_atoms)
        end = max(atom.source_span[1] for atom in segment_atoms)
        segments.append(LexicalSegment(
            tuple(tokens), tuple(token_records), boundary_before, boundary_after, (start, end)
        ))
        tokens = []
        token_records = []
        segment_atoms = []

    index = 0
    atoms = state.atoms
    while index < len(atoms):
        atom = atoms[index]
        if atom.operator_capable:
            flush_token()
            operator_atoms = [atom]
            index += 1
            while index < len(atoms):
                following = atoms[index]
                if not following.operator_capable or following.source_span[0] != operator_atoms[-1].source_span[1]:
                    break
                operator_atoms.append(following)
                index += 1
            operator = "".join(item.value for item in operator_atoms)
            if _is_redirection_operator(operator):
                if tokens and tokens[-1].isdigit() and segment_atoms and (
                    segment_atoms[-1].source_span[1] == operator_atoms[0].source_span[0]
                ) and all(
                    item.state == "ordinary" and not item.literalized
                    for item in segment_atoms
                    if item.token_membership == segment_atoms[-1].token_membership
                ):
                    tokens.pop()
                    token_records.pop()
                    io_membership = segment_atoms[-1].token_membership
                    segment_atoms = [
                        item for item in segment_atoms if item.token_membership != io_membership
                    ]
                skip_redirection_target = True
                continue
            flush_segment(operator)
            boundary_before = operator
            continue
        if atom.state == "ordinary" and not atom.literalized and atom.value in " \t\r":
            flush_token()
        else:
            token_atoms.append(atom)
        index += 1
    flush_segment("end")
    return tuple(segments)

def _candidate_word_matches(value: str, target: str) -> bool:
    normalized = _normalized_command_word(value)
    pieces = normalized.split(_LEXICAL_WILDCARD)
    pattern = "^" + ".?".join(re.escape(piece) for piece in pieces) + "$"
    return re.fullmatch(pattern, target, re.IGNORECASE) is not None

def _candidate_patterns_from_segments(
    segments: tuple[LexicalSegment, ...], dialect: str, reason: str
) -> tuple[PossibleCommandCandidate, ...]:
    candidates: list[PossibleCommandCandidate] = []
    for segment in segments:
        words: list[str] = []
        for token in segment.tokens:
            pieces = token.split()
            words.extend(pieces if pieces else (token,))
        for index in range(len(words) - 1):
            if _candidate_word_matches(words[index], "git") and _candidate_word_matches(words[index + 1], "push"):
                candidates.append(PossibleCommandCandidate(
                    dialect, segment.source_span, ("git", "push"), reason
                ))
                break
    return tuple(candidates)

def _nesting_context(dialect: str, before: str, after: str) -> str:
    boundaries = before + after
    if "(" in boundaries or ")" in boundaries:
        return "subshell"
    if "|" in boundaries and "||" not in boundaries:
        return "pipeline"
    if "&" in boundaries and "&&" not in boundaries:
        if dialect == "powershell" and before == "&":
            return "call-operator"
        return "background"
    if before != "start" or after != "end":
        if all(character in "\r\n" for character in after) and before == "start":
            return "top-level"
        return "compound"
    return "top-level"

def _strict_literal_projection(
    command: str,
    dialect: str,
    status: str,
    candidates: tuple[PossibleCommandCandidate, ...],
    normalizations: tuple[LexicalOperation, ...],
    commands: tuple[ExecutableCommand, ...],
) -> StrictLiteralProjection:
    if status != "SCG-PARSED" or candidates:
        return StrictLiteralProjection("uncertain", ())
    if normalizations or len(commands) != 1:
        return StrictLiteralProjection("noncanonical", ())
    record = commands[0]
    argv = record.tokens
    if len(argv) not in (4, 6):
        return StrictLiteralProjection("noncanonical", ())
    if dialect == "posix" and shlex.join(argv) == command:
        return StrictLiteralProjection("canonical", argv)
    if dialect == "powershell" and (
        record.boundary_before == "&"
        and record.boundary_after == "end"
        and all(token.states == ("single-quoted",) for token in record.token_records)
        and _serialize_powershell_literal(argv) == command
    ):
        return StrictLiteralProjection("canonical", argv)
    return StrictLiteralProjection("noncanonical", ())

def _token_source_span(token: LexicalToken) -> tuple[int, int]:
    return (
        min(span[0] for span in token.source_spans),
        max(span[1] for span in token.source_spans),
    )

def _argument_records(record: ExecutableCommand) -> tuple[LexicalToken, ...]:
    executable_index = len(record.tokens) - len(record.arguments) - 1
    return record.token_records[executable_index + 1:]

def _records_can_publish(records: tuple[LexicalToken, ...]) -> bool:
    words: list[str] = []
    for token in records:
        pieces = token.value.split()
        words.extend(pieces if pieces else (token.value,))
    return any(
        _candidate_word_matches(words[index], "git")
        and _candidate_word_matches(words[index + 1], "push")
        for index in range(len(words) - 1)
    )

def _candidate_from_records(
    records: tuple[LexicalToken, ...], dialect: str, reason: str
) -> PossibleCommandCandidate | None:
    if not records or not _records_can_publish(records):
        return None
    start = min(_token_source_span(token)[0] for token in records)
    end = max(_token_source_span(token)[1] for token in records)
    return PossibleCommandCandidate(dialect, (start, end), ("git", "push"), reason)

class WrapperArgvMachine:
    """Generic state machine over one immutable wrapper registry row."""

    @staticmethod
    def _same_spelling(grammar: WrapperGrammar, left: str, right: str) -> bool:
        return left == right if grammar.case_sensitive else left.lower() == right.lower()

    @classmethod
    def _match_option(
        cls, grammar: WrapperGrammar, value: str
    ) -> tuple[WrapperOptionSpec | None, str | None, str | None]:
        for spec in grammar.option_specs:
            if cls._same_spelling(grammar, value, spec.spelling):
                form = "DETACHED" if spec.arity else "FLAG"
                return spec, form, None
            compare_value = value if grammar.case_sensitive else value.lower()
            compare_spelling = spec.spelling if grammar.case_sensitive else spec.spelling.lower()
            if compare_value.startswith(compare_spelling) and len(value) > len(spec.spelling):
                suffix = value[len(spec.spelling):]
                if suffix.startswith("=") and "EQUALS_ATTACHED" in spec.accepted_forms:
                    return spec, "EQUALS_ATTACHED", suffix[1:]
                if suffix and "SHORT_ATTACHED" in spec.accepted_forms:
                    return spec, "SHORT_ATTACHED", suffix
                return spec, "UNSUPPORTED_ATTACHED", suffix.lstrip("=:")
        return None, None, None

    @staticmethod
    def _participant(
        kind: str,
        token: LexicalToken,
        classification: str,
        reason: str,
        structural_value: str | None = None,
    ) -> TerminalParticipant:
        return TerminalParticipant(kind, token, structural_value, classification, reason)

    @classmethod
    def evaluate(
        cls, record: ExecutableCommand, identity: CommandIdentity
    ) -> WrapperProjection | None:
        executable_identity = WrapperGrammarRegistry.identity(
            record.executable, record.dialect
        )
        grammar = WrapperGrammarRegistry.resolve(executable_identity)
        if grammar is None:
            return None
        arguments = _argument_records(record)
        options: list[LexicalToken] = []
        assignments: list[LexicalToken] = []
        participants: list[TerminalParticipant] = []

        def projection(
            state: str,
            reason: str,
            *,
            operands: tuple[LexicalToken, ...] = (),
            child_input: CommandInput | None = None,
            payload_composition: str | None = None,
            contributing: tuple[LexicalToken, ...] = (),
            candidate: PossibleCommandCandidate | None = None,
        ) -> WrapperProjection:
            return WrapperProjection(
                grammar.wrapper_id,
                identity,
                tuple(options),
                tuple(assignments),
                operands,
                child_input,
                state,
                reason,
                payload_composition,
                contributing,
                candidate,
                tuple(participants),
            )

        def terminal_candidate(
            reason: str,
            retained: tuple[LexicalToken, ...] | None = None,
        ) -> WrapperProjection:
            records = retained if retained is not None else arguments
            candidate = _candidate_from_records(records, record.dialect, reason)
            return projection(
                "CANDIDATE", reason, operands=records, candidate=candidate
            )

        if grammar.operand_rule == "compose-all":
            if not arguments:
                return projection("EXACT_NO_CHILD", "WPG-NO-OPERAND")
            if arguments[0].value.startswith("-"):
                participants.append(cls._participant(
                    "OPTION_TOKEN", arguments[0], "UNRESOLVED",
                    "WPG-UNSUPPORTED-OPTION",
                ))
                return terminal_candidate("WPG-UNSUPPORTED-OPTION")
            participants.extend(
                cls._participant("OPERAND", token, "EXACT", "WPG-EXACT")
                for token in arguments
            )
            payload = " ".join(token.value for token in arguments)
            child_input = CommandInput(
                "COMPOSED_SHELL_TEXT", record.dialect, payload, (),
                grammar.payload_mode, arguments,
            )
            return projection(
                "EXACT_CHILD", "WPG-EXACT", operands=arguments,
                child_input=child_input, payload_composition=grammar.payload_mode,
                contributing=arguments,
            )

        index = 0
        mode = "execute"
        required_modes: list[str] = []
        selector_payload: LexicalToken | None = None
        option_terminated = False
        while index < len(arguments):
            token = arguments[index]
            value = token.value
            if (
                not option_terminated
                and grammar.option_terminator is not None
                and value == grammar.option_terminator
            ):
                options.append(token)
                participants.append(cls._participant(
                    "TERMINATOR", token, "EXACT", "WPG-EXACT"
                ))
                option_terminated = True
                index += 1
                break
            if not option_terminated and value.startswith("-"):
                spec, form, attached_value = cls._match_option(grammar, value)
                if spec is None:
                    participants.append(cls._participant(
                        "OPTION_TOKEN", token, "UNRESOLVED",
                        "WPG-UNSUPPORTED-OPTION",
                    ))
                    structural = value.split("=", 1)[1] if "=" in value else None
                    if structural is not None:
                        participants.append(cls._participant(
                            "ATTACHED_VALUE", token, "UNRESOLVED",
                            "WPG-ATTACHED-PAYLOAD-UNSUPPORTED", structural,
                        ))
                    return terminal_candidate("WPG-UNSUPPORTED-OPTION")
                if form == "UNSUPPORTED_ATTACHED":
                    participants.append(cls._participant(
                        "OPTION_TOKEN", token, "UNRESOLVED",
                        "WPG-ATTACHED-PAYLOAD-UNSUPPORTED",
                    ))
                    participants.append(cls._participant(
                        "ATTACHED_VALUE", token, "UNRESOLVED",
                        "WPG-ATTACHED-PAYLOAD-UNSUPPORTED", attached_value,
                    ))
                    return terminal_candidate("WPG-ATTACHED-PAYLOAD-UNSUPPORTED")
                if spec.mode is not None and mode != "execute":
                    participants.append(cls._participant(
                        "MODE", token, "UNRESOLVED", "WPG-CONFLICTING-MODE"
                    ))
                    return terminal_candidate("WPG-CONFLICTING-MODE")
                if index + spec.arity >= len(arguments):
                    participants.append(cls._participant(
                        "OPTION_TOKEN", token, "UNRESOLVED",
                        "WPG-OPTION-MISSING-VALUE",
                    ))
                    return terminal_candidate("WPG-OPTION-MISSING-VALUE")
                options.append(token)
                values = arguments[index + 1:index + 1 + spec.arity]
                options.extend(values)
                participants.append(cls._participant(
                    "OPTION_TOKEN", token, "EXACT", "WPG-EXACT"
                ))
                participants.extend(
                    cls._participant(
                        "DETACHED_VALUE", option_value, "EXACT", "WPG-EXACT",
                        option_value.value,
                    )
                    for option_value in values
                )
                if spec.mode is not None:
                    mode = spec.mode
                    selector_payload = values[0] if values else None
                if spec.requires_mode is not None:
                    required_modes.append(spec.requires_mode)
                index += 1 + spec.arity
                if spec.mode in ("command", "file"):
                    break
                continue
            break

        if required_modes and any(required != mode for required in required_modes):
            if options:
                participants.append(cls._participant(
                    "MODE", options[-1], "UNRESOLVED", "WPG-OPTION-WRONG-STATE"
                ))
            return terminal_candidate("WPG-OPTION-WRONG-STATE")

        if grammar.operand_rule == "selector":
            if mode == "command" and selector_payload is not None:
                remainder = arguments[index:]
                if remainder and not grammar.allow_payload_tail:
                    participants.extend(
                        cls._participant(
                            "SUFFIX", item, "UNRESOLVED",
                            "WPG-UNSUPPORTED-COMPOSITION",
                        )
                        for item in remainder
                    )
                    return terminal_candidate("WPG-UNSUPPORTED-COMPOSITION")
                participants.extend(
                    cls._participant("SUFFIX", item, "EXACT", "WPG-EXACT")
                    for item in remainder
                )
                child_dialect = (
                    record.dialect if grammar.child_dialect == "same"
                    else grammar.child_dialect
                )
                child_input = CommandInput(
                    "SHELL_TEXT", child_dialect, selector_payload.value, (),
                    grammar.payload_mode, (selector_payload,),
                )
                return projection(
                    "EXACT_CHILD", "WPG-EXACT",
                    operands=(selector_payload, *remainder),
                    child_input=child_input,
                    payload_composition=grammar.payload_mode,
                    contributing=(selector_payload,),
                )
            opaque = arguments[index:]
            participants.extend(
                cls._participant("OPERAND", item, "EXACT", "WPG-OPERAND-OPAQUE")
                for item in opaque
            )
            return projection(
                "EXACT_NO_CHILD", "WPG-OPERAND-OPAQUE", operands=opaque
            )

        if grammar.assignment_rule_id is not None:
            exact_pattern = ASSIGNMENT_NAME_RULES[grammar.assignment_rule_id]
            while index < len(arguments):
                value = arguments[index].value
                if "=" not in value:
                    break
                name, _assigned = value.split("=", 1)
                if value.count("=") != 1 or re.fullmatch(exact_pattern, name) is None:
                    participants.append(cls._participant(
                        "ASSIGNMENT_LIKE", arguments[index], "UNRESOLVED",
                        "WPG-ASSIGNMENT-MALFORMED", name,
                    ))
                    return terminal_candidate("WPG-ASSIGNMENT-MALFORMED")
                assignments.append(arguments[index])
                participants.append(cls._participant(
                    "ASSIGNMENT_LIKE", arguments[index], "EXACT", "WPG-EXACT", name
                ))
                index += 1

        if mode == "query":
            opaque = arguments[index:]
            participants.extend(
                cls._participant("OPERAND", item, "EXACT", "WPG-QUERY-MODE")
                for item in opaque
            )
            return projection("EXACT_NO_CHILD", "WPG-QUERY-MODE", operands=opaque)
        operands = arguments[index:]
        if not operands:
            return projection("EXACT_NO_CHILD", "WPG-NO-OPERAND")
        participants.extend(
            cls._participant("OPERAND", item, "EXACT", "WPG-EXACT")
            for item in operands
        )
        child_dialect = (
            record.dialect if grammar.child_dialect == "same" else grammar.child_dialect
        )
        child_input = CommandInput(
            "DIRECT_ARGV", child_dialect, None, operands, grammar.payload_mode,
            operands,
        )
        return projection(
            "EXACT_CHILD", "WPG-EXACT", operands=operands,
            child_input=child_input, payload_composition=grammar.payload_mode,
            contributing=operands,
        )

def _effective_record_id(identity: CommandIdentity, ordinal: int) -> str:
    chain: list[str] = []
    cursor: CommandIdentity | None = identity
    while cursor is not None:
        chain.append(f"{cursor.wrapper_id or 'root'}:{cursor.ordinal}")
        cursor = cursor.parent
    chain.reverse()
    return f"{identity.root_occurrence}|{'/'.join(chain)}|{ordinal}"

def _assemble_effective_publications(
    identity: CommandIdentity,
    status: str,
    candidates: tuple[PossibleCommandCandidate, ...],
    pushes: tuple[GitPushInvocation, ...],
    projections: tuple[WrapperProjection, ...],
    children: tuple[ShellParseResult, ...],
) -> EffectivePublicationProjection:
    records: list[EffectivePublicationRecord] = []
    for push in pushes:
        kind = "CANDIDATE" if push.candidate else "DIRECT"
        records.append(EffectivePublicationRecord(
            _effective_record_id(identity, len(records)), identity, kind, push,
            "possible" if push.candidate else "exact",
            not push.candidate and push.dry_run_state == "DRY-ENABLED",
            not push.candidate,
        ))
    for child in children:
        for child_record in child.effective_publications.records:
            relative_depth = child_record.identity.depth - identity.depth
            records.append(child_record._replace(
                kind="WRAPPER_CHILD" if relative_depth == 1 else "NESTED",
                dry_credit_eligible=False,
                generic_credit_eligible=False,
            ))
    exact_complete = (
        status == "SCG-PARSED"
        and not candidates
        and all(
            projection.terminal_state != "CANDIDATE"
            and all(
                participant.classification == "EXACT"
                for participant in projection.terminal_participants
            )
            for projection in projections
        )
        and all(child.effective_publications.exact_complete for child in children)
    )
    immutable = tuple(records)
    return EffectivePublicationProjection(
        immutable,
        exact_complete,
        tuple(record for record in immutable if record.dry_credit_eligible),
        tuple(record for record in immutable if record.generic_credit_eligible),
    )

def _assemble_command_records(
    segments: tuple[LexicalSegment, ...],
    dialect: str,
    normalizations: tuple[LexicalOperation, ...],
) -> tuple[ExecutableCommand, ...]:
    commands: list[ExecutableCommand] = []
    command_count = len(segments)
    normalization_state = "normalized" if normalizations else "literal"
    for ordinal, segment in enumerate(segments):
        tokens = list(segment.tokens)
        boundary_before = segment.boundary_before
        boundary_after = segment.boundary_after
        prefix_index = 0
        assignments: list[str] = []
        keywords: list[str] = []
        while prefix_index < len(tokens):
            token = tokens[prefix_index]
            if "=" in token and re.fullmatch(
                r"[A-Za-z_][A-Za-z0-9_]*", token.split("=", 1)[0]
            ) is not None:
                assignments.append(token)
            elif token in _SHELL_KEYWORDS:
                keywords.append(token)
            else:
                break
            prefix_index += 1
        executable = tokens[prefix_index] if prefix_index < len(tokens) else ""
        arguments = tuple(tokens[prefix_index + 1:]) if executable else ()
        commands.append(ExecutableCommand(
            dialect,
            tuple(tokens),
            segment.token_records,
            tuple(assignments),
            tuple(keywords),
            executable,
            arguments,
            segment.source_span,
            ordinal,
            command_count,
            boundary_before,
            boundary_after,
            False,
            _nesting_context(dialect, boundary_before, boundary_after),
            boundary_before == "start" and boundary_after != "end"
            and all(character in "\r\n" for character in boundary_after),
            "exact",
            normalization_state,
        ))
    return tuple(commands)

def _parse_command_input(
    command_input: CommandInput,
    identity: CommandIdentity,
) -> ShellParseResult:
    dialect = command_input.dialect
    raw_command = command_input.shell_text or ""
    if command_input.kind == "DIRECT_ARGV":
        records = command_input.argv_records
        source_span = (
            min(_token_source_span(token)[0] for token in records),
            max(_token_source_span(token)[1] for token in records),
        )
        segments = (LexicalSegment(
            tuple(token.value for token in records), records, "start", "end", source_span
        ),)
        status = "SCG-PARSED"
        lexical = ShellLexicalRecord((), (), (), (), segments)
        data_regions: tuple[DataRegion, ...] = ()
        normalizations: tuple[LexicalOperation, ...] = ()
        initial_candidates: tuple[PossibleCommandCandidate, ...] = ()
    else:
        lexical_dialect = (
            dialect if dialect in ("posix", "powershell", "posix-compat")
            else "posix-compat"
        )
        state = _build_shell_lexical_state(raw_command, lexical_dialect)
        status = state.status if dialect == lexical_dialect else "SCG-UNSUPPORTED-DIALECT"
        segments = _tokenize_shell_lexical_state(state)
        initial_candidates = (
            _candidate_patterns_from_segments(segments, dialect, status)
            if status != "SCG-PARSED" else ()
        )
        lexical = ShellLexicalRecord(
            state.atoms, state.normalizations, state.removed_spans,
            state.data_regions, segments,
        )
        data_regions = state.data_regions
        normalizations = state.normalizations

    command_records = _assemble_command_records(segments, dialect, normalizations)
    strict_projection = (
        _strict_literal_projection(
            raw_command, dialect, status, initial_candidates,
            normalizations, command_records,
        )
        if command_input.kind != "DIRECT_ARGV"
        else StrictLiteralProjection("noncanonical", ())
    )
    if strict_projection.status == "canonical":
        command_records = (
            command_records[0]._replace(sole_canonical_literal=True),
        )

    projections: list[WrapperProjection] = []
    children: list[ShellParseResult] = []
    candidates = list(initial_candidates)
    for record in command_records:
        projection = WrapperArgvMachine.evaluate(record, identity)
        if projection is None:
            continue
        if projection.child_input is not None and identity.depth >= 4:
            candidate = _candidate_from_records(
                projection.contributing_tokens, dialect, "WPG-DEPTH-LIMIT"
            )
            unresolved = tuple(
                TerminalParticipant(
                    "SUFFIX", token, token.value, "UNRESOLVED",
                    "WPG-NESTED-UNRESOLVED",
                )
                for token in projection.contributing_tokens
            )
            projection = projection._replace(
                child_input=None,
                terminal_state="CANDIDATE",
                reason="WPG-NESTED-UNRESOLVED",
                candidate=candidate,
                terminal_participants=(
                    *projection.terminal_participants, *unresolved
                ),
            )
        projections.append(projection)
        if projection.candidate is not None:
            candidates.append(projection.candidate)
        if projection.child_input is not None:
            child_tokens = projection.contributing_tokens
            child_span = (
                min(_token_source_span(token)[0] for token in child_tokens),
                max(_token_source_span(token)[1] for token in child_tokens),
            )
            child_identity = CommandIdentity(
                projection.child_input.dialect,
                identity.depth + 1,
                identity,
                child_span,
                record.ordinal,
                projection.child_input.kind,
                projection.wrapper_id,
                projection.payload_composition,
                tuple(_token_source_span(token) for token in child_tokens),
                identity.root_occurrence,
            )
            children.append(_parse_command_input(projection.child_input, child_identity))

    immutable_candidates = tuple(candidates)
    immutable_children = tuple(children)
    pushes = _project_git_push_records(command_records, immutable_candidates)
    effective_publications = _assemble_effective_publications(
        identity, status, immutable_candidates, pushes, tuple(projections),
        immutable_children
    )
    scan_execution = _project_scan_execution_graph(
        status, immutable_candidates, command_records
    )
    return ShellParseResult(
        identity,
        dialect,
        status,
        lexical,
        segments,
        command_records,
        immutable_candidates,
        strict_projection,
        tuple(projections),
        immutable_children,
        pushes,
        effective_publications,
        scan_execution,
        data_regions,
        normalizations,
        raw_command,
    )

def _parse_shell_command_identity(
    command: str,
    dialect: str,
    identity: CommandIdentity,
) -> ShellParseResult:
    return _parse_command_input(
        CommandInput("SHELL_TEXT", dialect, command, (), None, ()), identity
    )

def parse_shell_command(command: str, dialect: str = "posix-compat") -> ShellParseResult:
    WrapperGrammarRegistry.validate()
    identity = CommandIdentity(
        dialect, 0, None, None, 0, "SHELL_TEXT", None, None, (), "live"
    )
    return _parse_shell_command_identity(command, dialect, identity)

def _global_option_is_repository_redirect(option: str) -> bool:
    return option in _REPOSITORY_GIT_OPTIONS or any(
        option.startswith(prefix)
        for prefix in ("-C", "--git-dir=", "--work-tree=", "--namespace=")
    )

def _parse_push_options(
    post_tokens: tuple[str, ...]
) -> tuple[
    tuple[OptionOccurrence, ...], tuple[str, ...], tuple[str, ...], str, str, str
]:
    occurrences: list[OptionOccurrence] = []
    option_tokens: list[str] = []
    operands: list[str] = []
    repository_context = "ambient"
    option_status = "GPO-PARSED"
    positive_dry = 0
    negative_dry = 0
    options_open = True
    index = 0

    def worsen(status: str) -> None:
        nonlocal option_status
        rank = {"GPO-PARSED": 0, "GPO-UNKNOWN": 1, "GPO-AMBIGUOUS": 2, "GPO-MISSING-VALUE": 3}
        if rank[status] > rank[option_status]:
            option_status = status

    while index < len(post_tokens):
        token = post_tokens[index]
        if not options_open:
            operands.append(token)
            index += 1
            continue
        if token == "--":
            occurrences.append(OptionOccurrence(token, "end-of-options", "neutral", None))
            option_tokens.append(token)
            options_open = False
            index += 1
            continue

        name, has_equals, glued_value = token.partition("=")
        if name in _PUSH_REQUIRED_VALUE_OPTIONS:
            option_tokens.append(token)
            value_index: int | None
            if has_equals:
                value_index = index
                if not glued_value:
                    worsen("GPO-MISSING-VALUE")
            elif index + 1 < len(post_tokens):
                value_index = index + 1
            else:
                value_index = None
                worsen("GPO-MISSING-VALUE")
            occurrences.append(OptionOccurrence(name, "required-value", "neutral", value_index))
            if name in ("--repo", "--no-repo"):
                repository_context = "redirected" if value_index is not None else "indeterminate"
            index += 1 if has_equals or value_index is None else 2
            continue
        if token.startswith("-o") and token != "-o":
            option_tokens.append(token)
            occurrences.append(OptionOccurrence("-o", "required-value", "neutral", index))
            index += 1
            continue
        if name in _PUSH_REQUIRED_ENUM_OPTIONS:
            option_tokens.append(token)
            value_index = index if has_equals else index + 1 if index + 1 < len(post_tokens) else None
            value = glued_value if has_equals else post_tokens[value_index] if value_index is not None else ""
            if value_index is None:
                worsen("GPO-MISSING-VALUE")
            elif value not in _PUSH_RECURSE_VALUES:
                worsen("GPO-AMBIGUOUS")
            occurrences.append(OptionOccurrence(name, "required-enum", "neutral", value_index))
            index += 1 if has_equals or value_index is None else 2
            continue
        if name in _PUSH_OPTIONAL_GLUED_OPTIONS:
            option_tokens.append(token)
            if has_equals and not glued_value:
                worsen("GPO-AMBIGUOUS")
            occurrences.append(OptionOccurrence(
                name, "optional-glued-value", "neutral", index if has_equals else None
            ))
            index += 1
            continue
        if token in _PUSH_BOOLEAN_OPTIONS:
            option_tokens.append(token)
            polarity = "positive"
            if token.startswith("--no-"):
                polarity = "negative"
            if token == "--dry-run":
                positive_dry += 1
            elif token == "--no-dry-run":
                negative_dry += 1
            occurrences.append(OptionOccurrence(token, "boolean", polarity, None))
            index += 1
            continue
        if token.startswith("-"):
            option_tokens.append(token)
            occurrences.append(OptionOccurrence(token, "unknown", "neutral", None))
            worsen("GPO-UNKNOWN")
            index += 1
            continue
        operands.append(token)
        index += 1

    if option_status != "GPO-PARSED" or (positive_dry and negative_dry):
        dry_run_state = "DRY-INDETERMINATE"
    elif positive_dry:
        dry_run_state = "DRY-ENABLED"
    else:
        dry_run_state = "DRY-NOT-CREDITABLE"
    return (
        tuple(occurrences), tuple(option_tokens), tuple(operands),
        repository_context, option_status, dry_run_state,
    )

def _project_git_push_records(
    commands: tuple[ExecutableCommand, ...],
    candidates: tuple[PossibleCommandCandidate, ...],
) -> tuple[GitPushInvocation, ...]:
    pushes: list[GitPushInvocation] = []
    for record in commands:
        if _normalized_command_word(record.executable) != "git":
            continue
        arguments = list(record.arguments)
        global_options: list[str] = []
        global_occurrences: list[OptionOccurrence] = []
        index = 0
        post_tokens: tuple[str, ...] | None = None
        while index < len(arguments):
            token = arguments[index]
            if token == "push":
                post_tokens = tuple(arguments[index + 1:])
                break
            if token in _GIT_VALUE_OPTS:
                if index + 1 >= len(arguments):
                    break
                global_options.extend((token, arguments[index + 1]))
                global_occurrences.append(OptionOccurrence(token, "required-value", "neutral", index + 1))
                index += 2
                continue
            if token.startswith(("-C", "-c")) and token not in ("-C", "-c"):
                global_options.append(token)
                global_occurrences.append(OptionOccurrence(token[:2], "required-value", "neutral", index))
                index += 1
                continue
            if token.startswith("--") and "=" in token:
                global_options.append(token)
                global_occurrences.append(OptionOccurrence(token.split("=", 1)[0], "required-value", "neutral", index))
                index += 1
                continue
            if token.startswith("-"):
                global_options.append(token)
                global_occurrences.append(OptionOccurrence(token, "unknown", "neutral", None))
                index += 1
                continue
            break
        if post_tokens is None:
            continue

        (
            push_occurrences, push_options, positionals, repository_context,
            option_status, dry_run_state,
        ) = _parse_push_options(post_tokens)

        env_names = {item.split("=", 1)[0] for item in record.environment_assignments}
        if env_names & _REPOSITORY_ENV_NAMES or any(
            _global_option_is_repository_redirect(option) for option in global_options
        ):
            repository_context = "redirected"
        pushes.append(GitPushInvocation(
            record,
            record.executable,
            record.environment_assignments,
            tuple(global_options),
            post_tokens,
            tuple(push_options),
            tuple(positionals),
            repository_context,
            dry_run_state == "DRY-ENABLED",
            False,
            len(commands) == 1 and not candidates,
            tuple(global_occurrences),
            push_occurrences,
            option_status,
            dry_run_state,
            record.nesting_context,
            False,
            record.normalization_state,
        ))
    for candidate in candidates:
        pushes.append(GitPushInvocation(
            candidate, "git", (), (), (), (), (), "indeterminate", False,
            False, False, (), (), "GPO-AMBIGUOUS", "DRY-INDETERMINATE",
            "uncertain", True, "uncertain",
        ))
    only_direct_push = len(pushes) == 1
    return tuple(push._replace(only_direct_push=only_direct_push) for push in pushes)

def find_git_push_records(parsed: ShellParseResult) -> list[GitPushInvocation]:
    """Return the one parser-owned effective publication projection."""
    return [record.push for record in parsed.effective_publications.records]

def classify_generic_push(parsed: ShellParseResult) -> GenericPushDecision:
    projection = parsed.effective_publications
    if not projection.exact_complete:
        return GenericPushDecision("PGG-PARSE-UNCERTAIN", None)
    if parsed.normalizations:
        return GenericPushDecision("PGG-LEXICAL-NORMALIZATION", None)
    if (
        len(parsed.commands) != 1
        or len(projection.records) != 1
        or len(projection.eligible_direct_generic) != 1
    ):
        return GenericPushDecision("PGG-COMPOUND-CONTEXT", None)
    push = projection.eligible_direct_generic[0].push
    if not isinstance(push.command, ExecutableCommand):
        return GenericPushDecision("PGG-PARSE-UNCERTAIN", None)
    if push.command.control_keywords or push.shell_context != "top-level" or (
        push.command.boundary_before != "start"
        or (
            push.command.boundary_after != "end"
            and not push.command.trailing_linebreak_only
        )
    ):
        return GenericPushDecision("PGG-COMPOUND-CONTEXT", None)
    if push.repository_context != "ambient":
        return GenericPushDecision("PGG-REPOSITORY-REDIRECT", None)
    if push.environment_assignments:
        return GenericPushDecision("PGG-ENV-PREFIX", None)
    if push.git_global_options:
        return GenericPushDecision("PGG-GIT-GLOBAL-OPTION", None)
    if push.option_status in ("GPO-MISSING-VALUE", "GPO-AMBIGUOUS"):
        return GenericPushDecision("PGG-OPTION-ARITY", None)
    if push.option_status == "GPO-UNKNOWN" or any(
        option not in _SAFE_PUSH_OPTIONS for option in push.push_options
    ):
        return GenericPushDecision("PGG-PUSH-OPTION", None)
    if not push.positionals:
        return GenericPushDecision("PGG-REMOTE-CARDINALITY", None)
    if len(push.positionals) != 2:
        return GenericPushDecision("PGG-REFSPEC-CARDINALITY", None)
    remote, refspec = push.positionals
    if ":" in refspec:
        source, destination = refspec.split(":", 1)
    else:
        source = destination = refspec
    if not destination:
        return GenericPushDecision("PGG-DESTINATION-SHAPE", None)
    return GenericPushDecision("PGG-ADMISSIBLE", (remote, destination, source))

_SCAN_SCRIPT_BASENAMES = {
    "check-publication-safety.py", "check-publication-safety.sh",
    "check-publication-gate.py", "check-publication-gate.sh",
}

_SHELL_INTERPRETERS = {"bash", "sh", "dash", ".", "source"}

_PYTHON_INTERPRETERS = {"python", "python3", "py"}

_PS_FILE_FLAGS = {"-file"}

_PS_COMMAND_FLAGS = {"-command", "-c"}

def _basename(path: str) -> str:
    return path.replace("\\", "/").rsplit("/", 1)[-1]

def _normalized_command_word(token: str) -> str:
    """Lowercased basename of `token` with a trailing `.exe` suffix stripped.

    Scan and push projections reuse this normalization for the same shell-word
    identity question instead of maintaining independently drifting copies.

    `_basename`'s backslash-to-forward-slash + rsplit handles a Windows
    absolute path (`C:\\Program Files\\Git\\bin\\git.exe`); `.lower()`
    handles Windows' case-insensitive command resolution (`GIT push`,
    `Git push`, `git.EXE push` all resolve and run identically to `git
    push` -- measured live, 2026-07-26: the pre-fix exact-match head test
    caught none of these); the `.exe` strip handles the Windows executable
    suffix both `git` and the PowerShell interpreters ship under, with or
    without a path prefix."""
    base = _basename(token).lower()
    if base.endswith(".exe"):
        base = base[:-4]
    return base

def _record_runs_scan_script(record: ExecutableCommand) -> bool:
    """Project scan execution from the parser-owned command record."""
    if not record.executable:
        return False
    head_base = _basename(record.executable).lower()
    arguments = list(record.arguments)

    # Direct exec: the command word itself IS the scanner
    # (`./check-publication-safety.sh`, a bare basename on PATH, or an
    # absolute/relative path to it).
    if head_base in _SCAN_SCRIPT_BASENAMES:
        return True

    # Interpreter + script-path-as-first-operand (`bash check-...sh`, ...).
    if head_base in _SHELL_INTERPRETERS or _normalized_command_word(record.executable) in _PYTHON_INTERPRETERS:
        return bool(arguments) and _basename(arguments[0]).lower() in _SCAN_SCRIPT_BASENAMES

    # PowerShell / pwsh, any casing, optional `.exe` suffix -- reuses
    # `_normalized_command_word` (see its docstring) rather than repeating
    # the basename/lower/`.exe`-strip sequence inline a second time; the push
    # projection shares this exact function instead of carrying its own copy.
    ps_name = _normalized_command_word(record.executable)
    if ps_name in ("powershell", "pwsh"):
        i = 0
        while i < len(arguments):
            flag = arguments[i].lower()
            if flag in _PS_FILE_FLAGS:
                return i + 1 < len(arguments) and _basename(arguments[i + 1]).lower() in _SCAN_SCRIPT_BASENAMES
            if flag in _PS_COMMAND_FLAGS:
                return False
            i += 1
        return False
    return False

def _project_scan_execution_graph(
    status: str,
    candidates: tuple[PossibleCommandCandidate, ...],
    commands: tuple[ExecutableCommand, ...],
) -> bool:
    if status != "SCG-PARSED" or candidates or len(commands) != 1:
        return False
    record = commands[0]
    powershell_call = (
        record.dialect == "powershell"
        and record.nesting_context == "call-operator"
        and record.boundary_before == "&"
    )
    if record.nesting_context != "top-level" and not powershell_call:
        return False
    if record.boundary_before != "start" and not powershell_call:
        return False
    if record.boundary_after != "end" and not record.trailing_linebreak_only:
        return False
    if _record_runs_scan_script(record):
        return True
    return False

def resolve_command_dialect(tool_name: object) -> CommandDialectResolution:
    if tool_name == "PowerShell":
        return CommandDialectResolution("powershell", True)
    if tool_name == "Bash":
        return CommandDialectResolution("posix", True)
    if tool_name in ("shell_command", "exec_command"):
        return CommandDialectResolution(
            "powershell" if os.name == "nt" else "posix", True
        )
    return CommandDialectResolution("unsupported", False)


def parse_transcript_command(
    command_text: str,
    tool_name: object,
    root_occurrence: str,
    ordinal: int,
) -> ShellParseResult:
    """Parse one transcript command through the canonical grammar owner."""
    if type(command_text) is not str or type(root_occurrence) is not str:
        raise TypeError("invalid transcript command input")
    if type(ordinal) is not int or ordinal < 0:
        raise TypeError("invalid transcript command ordinal")
    resolution = resolve_command_dialect(tool_name)
    identity = CommandIdentity(
        resolution.dialect, 0, None, None, ordinal,
        "SHELL_TEXT", None, None, (), root_occurrence,
    )
    return _parse_shell_command_identity(command_text, resolution.dialect, identity)

def _serialize_powershell_literal(argv: tuple[str, ...]) -> str:
    return "& " + " ".join("'" + word.replace("'", "''") + "'" for word in argv)


def _host_command_dialect() -> str:
    return "powershell" if os.name == "nt" else "posix"


def _is_exact_direct_literal(command: str, parsed: ShellParseResult) -> bool:
    effective = parsed.effective_publications
    if (
        parsed.dialect not in ("posix", "powershell")
        or parsed.strict_projection.status != "canonical"
        or not effective.exact_complete
        or len(effective.records) != 1
        or effective.records[0].kind != "DIRECT"
        or effective.records[0].certainty != "exact"
    ):
        return False
    serialized = (
        shlex.join(parsed.strict_projection.argv)
        if parsed.dialect == "posix"
        else _serialize_powershell_literal(parsed.strict_projection.argv)
    )
    return serialized == command


def _recover_mislabeled_command_dialect(
    command: str,
    resolution: CommandDialectResolution,
    parsed: ShellParseResult,
) -> tuple[CommandDialectResolution, ShellParseResult]:
    """Recover only one exact host-shell literal from a supported wrong label."""
    host_dialect = _host_command_dialect()
    primary_publications = parsed.effective_publications.records
    if (
        not resolution.exact
        or resolution.dialect not in ("posix", "powershell")
        or resolution.dialect == host_dialect
        or host_dialect != "powershell"
        or not command.startswith("& '")
        or parsed.strict_projection.status == "canonical"
        or len(primary_publications) != 1
        or primary_publications[0].kind != "DIRECT"
        or primary_publications[0].certainty != "exact"
    ):
        return resolution, parsed
    candidates: list[tuple[str, ShellParseResult]] = []
    for dialect in ("posix", "powershell"):
        candidate = parsed if dialect == resolution.dialect else parse_shell_command(command, dialect)
        if _is_exact_direct_literal(command, candidate):
            candidates.append((dialect, candidate))
    if len(candidates) != 1 or candidates[0][0] != host_dialect:
        return resolution, parsed
    dialect, candidate = candidates[0]
    return CommandDialectResolution(dialect, True), candidate

def _has_solitary_direct_dry_credit(parsed: ShellParseResult) -> bool:
    """Return true only for one exact root-level positive long-form dry push."""
    effective = parsed.effective_publications
    if (
        not effective.exact_complete
        or parsed.normalizations
        or len(effective.records) != 1
        or len(effective.eligible_direct_dry) != 1
    ):
        return False
    record = effective.records[0]
    eligible = effective.eligible_direct_dry[0]
    push = record.push
    return (
        (record is eligible or record.record_id == eligible.record_id)
        and record.kind == "DIRECT"
        and record.certainty == "exact"
        and push.only_direct_push
        and push.only_executable_command
        and push.dry_run_state == "DRY-ENABLED"
        and any(
            occurrence.spelling == "--dry-run"
            and occurrence.polarity == "positive"
            for occurrence in push.push_option_occurrences
        )
    )


def _has_malformed_minus_c_push_candidate(parsed: ShellParseResult) -> bool:
    if len(parsed.commands) != 1:
        return False
    tokens = parsed.commands[0].tokens
    return (
        len(tokens) >= 3
        and _normalized_command_word(tokens[0]) == "git"
        and "-C" in tokens[1:]
        and "push" in tokens[2:]
    )


class PreflightResult(NamedTuple):
    outcome: str
    reason_id: str
    continuation: str
    command: str | None
    dialect: str | None
    transcript_path: str
    parsed: ShellParseResult | None
    current_turn_status: str | None
    generic_decision: GenericPushDecision | None
    push_instruction: bool
    failure_id: str | None
    repository_workdir: str = ""
    repository_workdir_source: str = ""


_OUTCOMES = frozenset(("ALLOW_FINAL", "DEFER"))
_CONTINUATIONS = frozenset(("NONE", "RENDER_DENY", "EVALUATE_HEAVY"))
_DIALECTS = frozenset(("posix", "powershell", "unsupported"))
_CURRENT_TURN_STATUSES = frozenset(
    ("found", "absent", "unreadable", "invalid", "limit", "not-in-window")
)
_PREFLIGHT_REASONS = frozenset((
    "PFP-ALLOW-SUBAGENT", "PFP-ALLOW-NO-COMMAND", "PFP-ALLOW-NON-PUSH",
    "PFP-DENY-PARSE", "PFP-ALLOW-DRY-RUN", "PFP-DENY-TRANSCRIPT",
    "PFP-ALLOW-USER-APPROVED", "PFP-HEAVY", "PFP-DENY-KNOWN",
    "PFP-DENY-INTERNAL", "PFP-ALLOW-MALFORMED",
))
_GENERIC_STATUSES = frozenset((
    "PGG-ADMISSIBLE", "PGG-PARSE-UNCERTAIN", "PGG-LEXICAL-NORMALIZATION",
    "PGG-COMPOUND-CONTEXT", "PGG-REPOSITORY-REDIRECT", "PGG-ENV-PREFIX",
    "PGG-GIT-GLOBAL-OPTION", "PGG-OPTION-ARITY", "PGG-PUSH-OPTION",
    "PGG-REMOTE-CARDINALITY", "PGG-REFSPEC-CARDINALITY",
    "PGG-DESTINATION-SHAPE",
))
_PREFLIGHT_FAILURE_IDS = frozenset((
    "PGG-PARSE-UNCERTAIN", "PRG-TRANSCRIPT-UNAVAILABLE",
    "PRG-WORKDIR-INVALID",
))
_PREFLIGHT_BRANCHES = {
    "PFP-ALLOW-SUBAGENT": ("ALLOW_FINAL", "NONE", frozenset(), None),
    "PFP-ALLOW-NO-COMMAND": ("ALLOW_FINAL", "NONE", frozenset(), None),
    "PFP-ALLOW-NON-PUSH": (
        "ALLOW_FINAL", "NONE", frozenset(("command", "dialect", "parsed")), None,
    ),
    "PFP-ALLOW-DRY-RUN": (
        "ALLOW_FINAL", "NONE", frozenset(("command", "dialect", "parsed")), None,
    ),
    "PFP-ALLOW-USER-APPROVED": (
        "ALLOW_FINAL", "NONE",
        frozenset((
            "command", "dialect", "transcript_path", "parsed",
            "current_turn_status", "generic_decision",
        )),
        None,
    ),
    "PFP-ALLOW-MALFORMED": ("ALLOW_FINAL", "NONE", frozenset(), None),
    "PFP-DENY-PARSE": (
        "DEFER", "RENDER_DENY",
        frozenset(("command", "dialect", "parsed", "failure_id")),
        "PGG-PARSE-UNCERTAIN",
    ),
    "PFP-DENY-TRANSCRIPT": (
        "DEFER", "RENDER_DENY",
        frozenset(("command", "dialect", "parsed", "failure_id")),
        "PRG-TRANSCRIPT-UNAVAILABLE",
    ),
    "PFP-DENY-KNOWN": (
        "DEFER", "RENDER_DENY", frozenset(("failure_id",)), "REGISTERED",
    ),
    "PFP-DENY-INTERNAL": ("DEFER", "RENDER_DENY", frozenset(), None),
    "PFP-HEAVY": (
        "DEFER", "EVALUATE_HEAVY",
        frozenset((
            "command", "dialect", "transcript_path", "parsed",
            "current_turn_status", "generic_decision", "repository_workdir",
            "repository_workdir_source",
        )),
        None,
    ),
}
_PREFLIGHT_OPTIONAL_DEFAULTS = {
    "command": None,
    "dialect": None,
    "transcript_path": "",
    "parsed": None,
    "current_turn_status": None,
    "generic_decision": None,
    "failure_id": None,
    "repository_workdir": "",
    "repository_workdir_source": "",
}


def _repository_workdir(envelope: dict, tool_input: dict) -> tuple[str, str]:
    explicit = "workdir" in tool_input
    raw = tool_input["workdir"] if explicit else envelope.get("cwd")
    if type(raw) is not str or not raw or "\x00" in raw:
        raise PrRouteDenied("PRG-WORKDIR-INVALID")
    candidate = Path(raw)
    if not candidate.is_absolute():
        raise PrRouteDenied("PRG-WORKDIR-INVALID")
    return raw, "tool" if explicit else "envelope"


def _validate_declared_value(value: object, annotation: object, path: str) -> None:
    """Validate exact immutable values against their declared recursive shape."""
    if annotation is object:
        if isinstance(value, (list, dict, set, bytearray)):
            raise TypeError(f"mutable value at {path}")
        return
    origin = get_origin(annotation)
    arguments = get_args(annotation)
    if origin in (types.UnionType, getattr(__import__('typing'), 'Union')):
        for option in arguments:
            try:
                _validate_declared_value(value, option, path)
            except (TypeError, ValueError):
                continue
            return
        raise TypeError(f"wrong union member at {path}")
    if origin is tuple:
        if type(value) is not tuple:
            raise TypeError(f"non-tuple at {path}")
        if len(arguments) == 2 and arguments[1] is Ellipsis:
            for index, item in enumerate(value):
                _validate_declared_value(item, arguments[0], f"{path}[{index}]")
            return
        if len(value) != len(arguments):
            raise TypeError(f"wrong tuple arity at {path}")
        for index, (item, expected) in enumerate(zip(value, arguments)):
            _validate_declared_value(item, expected, f"{path}[{index}]")
        return
    if annotation is type(None):
        if value is not None:
            raise TypeError(f"non-None at {path}")
        return
    if annotation in (str, bool, int, bytes):
        if type(value) is not annotation:
            raise TypeError(f"wrong scalar type at {path}")
        return
    if isinstance(annotation, type) and issubclass(annotation, tuple):
        if type(value) is not annotation:
            raise TypeError(f"foreign tuple class at {path}")
        hints = get_type_hints(annotation, globals(), locals())
        for field in annotation._fields:
            _validate_declared_value(
                getattr(value, field), hints[field], f"{path}.{field}"
            )
        return
    raise TypeError(f"unsupported declared shape at {path}")


def project_scan_range_binding(parsed: ShellParseResult) -> tuple[str, str] | None:
    """Project one canonical scanner range binding from parser-owned output."""
    _validate_declared_value(parsed, ShellParseResult, "parsed")
    if not parsed.scan_execution or len(parsed.commands) != 1:
        return None
    record = parsed.commands[0]
    executable = _basename(record.executable).lower()
    arguments = list(record.arguments)
    scanner: str | None = None
    scanner_args: list[str] = []
    if executable in _SCAN_SCRIPT_BASENAMES:
        scanner, scanner_args = executable, arguments
    elif (
        executable in _SHELL_INTERPRETERS
        or _normalized_command_word(record.executable) in _PYTHON_INTERPRETERS
    ) and arguments:
        candidate = _basename(arguments[0]).lower()
        if candidate in _SCAN_SCRIPT_BASENAMES:
            scanner, scanner_args = candidate, arguments[1:]
    elif _normalized_command_word(record.executable) in ("powershell", "pwsh"):
        for index, argument in enumerate(arguments):
            if argument.lower() in _PS_FILE_FLAGS and index + 1 < len(arguments):
                candidate = _basename(arguments[index + 1]).lower()
                if candidate in _SCAN_SCRIPT_BASENAMES:
                    scanner, scanner_args = candidate, arguments[index + 2:]
                break
    if scanner is None or len(scanner_args) != 3 or scanner_args[0] != "--range":
        return None
    remote, destination = scanner_args[1:]
    return (remote, destination) if remote and destination else None


def validate_preflight_result(result: object) -> PreflightResult:
    if type(result) is not PreflightResult:
        raise TypeError("foreign preflight result")
    _validate_declared_value(result, PreflightResult, "preflight")
    if result.outcome not in _OUTCOMES:
        raise ValueError("invalid preflight outcome")
    if result.reason_id not in _PREFLIGHT_REASONS:
        raise ValueError("invalid preflight reason")
    if result.continuation not in _CONTINUATIONS:
        raise ValueError("invalid preflight continuation")
    if result.dialect is not None and result.dialect not in _DIALECTS:
        raise ValueError("invalid command dialect")
    if (
        result.current_turn_status is not None
        and result.current_turn_status not in _CURRENT_TURN_STATUSES
    ):
        raise ValueError("invalid current-turn status")
    if result.generic_decision is not None:
        if result.generic_decision.status not in _GENERIC_STATUSES:
            raise ValueError("invalid generic decision status")
        binding = result.generic_decision.binding
        if (result.generic_decision.status == "PGG-ADMISSIBLE") != (binding is not None):
            raise ValueError("inconsistent generic decision binding")
    if result.failure_id is not None and result.failure_id not in _PREFLIGHT_FAILURE_IDS:
        raise ValueError("invalid preflight failure identifier")
    if result.repository_workdir_source not in ("", "tool", "envelope"):
        raise ValueError("invalid repository workdir source")
    branch = _PREFLIGHT_BRANCHES[result.reason_id]
    expected_outcome, expected_continuation, present_fields, expected_failure = branch
    if (result.outcome, result.continuation) != (
        expected_outcome, expected_continuation
    ):
        raise ValueError("preflight reason is inconsistent with its branch")
    for field, default in _PREFLIGHT_OPTIONAL_DEFAULTS.items():
        value = getattr(result, field)
        if field in present_fields:
            if value == default or (type(value) is str and not value):
                raise ValueError(f"missing branch field: {field}")
        elif value != default:
            raise ValueError(f"unexpected branch field: {field}")
    if (
        result.reason_id not in {"PFP-ALLOW-USER-APPROVED", "PFP-HEAVY"}
        and result.push_instruction
    ):
        raise ValueError("unexpected branch push instruction")
    if expected_failure == "REGISTERED":
        if result.failure_id not in _PREFLIGHT_FAILURE_IDS:
            raise ValueError("missing registered preflight failure")
    elif result.failure_id != expected_failure:
        raise ValueError("preflight failure is inconsistent with its reason")
    return result


def _result(
    outcome: str,
    reason_id: str,
    continuation: str,
    *,
    command: str | None = None,
    dialect: str | None = None,
    transcript_path: str = "",
    parsed: ShellParseResult | None = None,
    current_turn_status: str | None = None,
    generic_decision: GenericPushDecision | None = None,
    push_instruction: bool = False,
    failure_id: str | None = None,
    repository_workdir: str = "",
    repository_workdir_source: str = "",
) -> PreflightResult:
    return validate_preflight_result(PreflightResult(
        outcome, reason_id, continuation, command, dialect, transcript_path,
        parsed, current_turn_status, generic_decision, push_instruction, failure_id,
        repository_workdir,
        repository_workdir_source,
    ))


def build_preflight(envelope: dict) -> PreflightResult:
    try:
        if envelope.get("agent_id"):
            return _result("ALLOW_FINAL", "PFP-ALLOW-SUBAGENT", "NONE")
        tool_input = envelope.get("tool_input")
        if not isinstance(tool_input, dict):
            return _result("ALLOW_FINAL", "PFP-ALLOW-NO-COMMAND", "NONE")
        command = tool_input.get("command")
        if not isinstance(command, str) or not command:
            return _result("ALLOW_FINAL", "PFP-ALLOW-NO-COMMAND", "NONE")
        resolution = resolve_command_dialect(envelope.get("tool_name"))
        parsed = parse_shell_command(command, resolution.dialect)
        resolution, parsed = _recover_mislabeled_command_dialect(
            command, resolution, parsed
        )
        pushes = find_git_push_records(parsed)
        minus_c_candidate = _has_malformed_minus_c_push_candidate(parsed)
        if (
            not pushes
            and not minus_c_candidate
            and parsed.effective_publications.exact_complete
        ):
            return _result(
                "ALLOW_FINAL", "PFP-ALLOW-NON-PUSH", "NONE",
                command=command, dialect=resolution.dialect, parsed=parsed,
            )
        if not pushes and not minus_c_candidate:
            return _result(
                "DEFER", "PFP-DENY-PARSE", "RENDER_DENY",
                command=command, dialect=resolution.dialect, parsed=parsed,
                failure_id="PGG-PARSE-UNCERTAIN",
            )
        if _has_solitary_direct_dry_credit(parsed):
            return _result(
                "ALLOW_FINAL", "PFP-ALLOW-DRY-RUN", "NONE",
                command=command, dialect=resolution.dialect, parsed=parsed,
            )
        transcript_path = envelope.get("transcript_path") or ""
        if not transcript_path:
            return _result(
                "DEFER", "PFP-DENY-TRANSCRIPT", "RENDER_DENY",
                command=command, dialect=resolution.dialect, parsed=parsed,
                failure_id="PRG-TRANSCRIPT-UNAVAILABLE",
            )
        last_user, _after_user, status = scan_current_turn_boundary(
            transcript_path, byte_cap=CURRENT_TURN_BYTE_CAP
        )
        user_text = (
            extract_user_typed_text(last_user)
            if status == STATUS_FOUND and last_user is not None
            else ""
        )
        instruction = PUSH_INSTRUCTION_REGEX.search(user_text) is not None
        grammar = classify_generic_push(parsed)
        if APPROVE_MARKER_REGEX.search(user_text) and len(user_text) <= MARKER_MAX_MESSAGE_LENGTH:
            return _result(
                "ALLOW_FINAL", "PFP-ALLOW-USER-APPROVED", "NONE",
                command=command, dialect=resolution.dialect,
                transcript_path=transcript_path, parsed=parsed,
                current_turn_status=status, generic_decision=grammar,
                push_instruction=instruction,
            )
        repository_workdir, repository_workdir_source = _repository_workdir(
            envelope, tool_input
        )
        return _result(
            "DEFER", "PFP-HEAVY", "EVALUATE_HEAVY",
            command=command, dialect=resolution.dialect,
            transcript_path=transcript_path, parsed=parsed,
            current_turn_status=status, generic_decision=grammar,
            push_instruction=instruction, repository_workdir=repository_workdir,
            repository_workdir_source=repository_workdir_source,
        )
    except PrRouteDenied as exc:
        return _result(
            "DEFER", "PFP-DENY-KNOWN", "RENDER_DENY",
            failure_id=exc.failure_id,
        )
    except Exception:
        return _result("DEFER", "PFP-DENY-INTERNAL", "RENDER_DENY")


def build_preflight_from_stdin() -> PreflightResult:
    try:
        envelope = parse_envelope(read_stdin_utf8())
    except Exception:
        return _result("ALLOW_FINAL", "PFP-ALLOW-MALFORMED", "NONE")
    return build_preflight(envelope)
