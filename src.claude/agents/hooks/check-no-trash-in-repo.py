#!/usr/bin/env python3
"""Stray-artifact guard (PreToolUse, AUDIT mode) — unrequested worktrees, and
build/log artifacts written into the repository ROOT.

WHAT THIS WARNS ON, four triggers on the Bash/PowerShell command text:

  (1) `git worktree add` — the agent creating a git worktree. Unrequested side
      effect unless the user asked for one.
  (2) A MANGLED Windows redirect target — a drive-letter prefix with no path
      separator (`> r:Tempxbuild.log`). In Git Bash a target written
      `> r:\\Temp\\x\\build.log` loses its backslashes and produces ONE file
      literally named after the mangled path, while the command reports success.
  (3) A build/log ARTIFACT redirected into the repository ROOT (`> build.log`,
      `> probe.obj`) — a bare target with no directory component lands in the
      process CWD, which for a tool-run command is the repository root.
  (4) A COMPILER invocation whose output lands in the repository root. `ifx`,
      `ifort`, `icx`, `gfortran`, `cl`, `gcc` write `.obj`/`.o`/`.pdb` beside
      the invocation unless directed elsewhere, and the compile succeeds
      silently.

Triggers 2-4 close the half of the shared temporary-file-hygiene rule that
nothing enforced: every log, build capture, probe output and one-off script
belongs under a scratch directory, never in the repository root. Motivating
evidence (work-items/backlog/2026-08-16-root-artifact-write-guard.md): a
cleanup in a consuming repository removed 54 untracked build artifacts
totalling 16 MB from its root, 47 of them landing in two days — every one a
diagnostic probe (`*_probe.obj`, `*_oracle.obj`, `*_falsifier.obj`, `qa_*.obj`)
with a matching `.pdb`, i.e. mechanism (4).

WHY THESE ARE TRACTABLE WHERE "WRITES OUTSIDE THE REPO" WAS NOT (see Dropped,
below): that check needed an enumeration of every legitimate EXTERNAL
destination — an OPEN set that cannot be produced, so it false-positives. An
artifact extension written to the repository ROOT is CLOSED on both axes: the
extensions are enumerable and the destination is one directory. No allow-list
is required, and a legitimate root write of a compiler object does not exist.

WHY IT REPLACED THE NAME-BASED NO-TRASH CHECK: the previous version of this file
warned when a NEW directory whose name was in a hardcoded "author-process
vocabulary" list (`kosyaks`, `mistake-log`, ...) was created in the repo. That was
useless — those names are the *user's* personal vocabulary, not names the *agent*
(the actor a PreToolUse hook guards) ever writes, so it never fired. Directory-name
matching was the wrong axis. The real reported problem was the agent creating
stray artifacts, so this guard keys on the OPERATION, not on a name.

SCOPE:
  - `git worktree add` from Bash -> warn, UNLESS the command contains exactly one
    add and ends with the exact command-local marker
    `# orchestrarium:requested-isolation-worktree` (a protocol-requested isolation
    worktree). A missing, near-match, quoted, or not-final marker, or two-or-more
    adds with one marker, still warns — one marker never suppresses a batch.
    `git worktree list/remove/prune` are harmless and ignored.
  - Trigger (2) fires REGARDLESS of where the process is running: a drive-letter
    prefix with no separator is always a mistake, never a destination anyone
    chose. It is therefore not gated on the repository-root probe.
  - Triggers (3) and (4) fire only when the process CWD is CONFIRMED to be a
    repository root (`cwd/.git` exists — a clone has it as a directory, a
    worktree/submodule as a file; either counts) AND the command contains no
    directory change. A `cd`/`pushd` makes the destination undecidable, so the
    guard stays silent — that is the documented "run the tool from inside its own
    scratch output dir" pattern, not a defect.
  - Deferred: the Claude `Agent` tool's `isolation: "worktree"` form (needs a real
    PreToolUse envelope to confirm the field shape before matching it).
  - Dropped: "writes outside the repo" (a static allow-list false-positives on
    legitimate installs, temp prompts, global config, and memory/rules writes) and
    "arbitrary in-repo trash" (no reliable non-name signal — that stays governance,
    i.e. "all scratch goes to .scratch/", not a hook).

KNOWN, DELIBERATE UNDER-DETECTION (acceptable for a warn-only audit that always
fails open):
  - A compiler invocation carrying an explicit output flag (`-o`, `/Fo`, ...) is
    treated as directed and stays silent, even though MSVC-family compilers still
    drop `.obj` next to the invocation when only `/Fe` is given. Warning on every
    directed compile would be noise; the undirected case is the measured one.
  - Redirect destination is judged from the RAW command text, so only a target
    with no directory component at all is treated as root-destined. An absolute
    path that happens to resolve to the repository root is not matched.
  - Command-position parsing does not model wrappers (`sudo`/`env`/`xargs`/
    `bash -c`) or command substitution; those simply under-count.

AUDIT mode: on a hit, ALWAYS ALLOW the command and never block. Deliver the
warning to the MODEL via `hookSpecificOutput.additionalContext` on stdout, exit
0 (see `hook_common.emit_advisory`). This is the corrected delivery channel: a
PreToolUse hook's previous stderr-plus-exit-1 form was measured to reach NOBODY
on either Claude Code 2.1.220 (transcript-only, model-invisible) or Codex CLI
0.145.0 (discarded entirely — the non-2-exit branch never copies stderr). See
work-items/bugs/2026-07-26-mcp-reminder-uses-the-once-per-session-form-its-
sibling-calls-broken.md for the full falsification-controlled measurement.
Never blocks — every one of these can be legitimately intended, and the hook
cannot read intent. Fails open on any internal error (return 0).

NOTE: the filename/install-marker `check-no-trash-in-repo` is retained for
install-entry continuity. It is a REGISTERED hook stem for both platforms
(scripts/universal_hooks_manifest.py REGISTERED_HOOK_STEMS_BY_PLATFORM) and the
marker the installer finds existing entries by, so a rename would require a
settings.json/hooks.json migration in every consuming repository; keeping it
means an installed repo picks this widening up by file replacement alone, with
zero settings churn. A rename to `check-stray-artifact` remains a tracked
follow-up, deliberately not taken in this slice.
"""
from __future__ import annotations

import os
import re
import shlex
import sys
from pathlib import Path

# hook_common lives in the sibling scripts/ dir (shared with the grandfathered
# hooks); this hook lives in the typed hooks/ dir per the source-hygiene rule,
# so add the sibling scripts/ dir to the import path before importing it.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from hook_common import emit_advisory, parse_envelope, read_stdin_utf8


# `git` global options that consume a SEPARATE following token as their value;
# when scanning for the subcommand we must skip the value too, or `git -C /x
# worktree add` would look like the subcommand is `/x`.
_GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}

# Shell keywords that PRECEDE a command (they do not consume the command slot —
# the real command word follows them). Treating them as transparent lets the
# parser see `git` in control-flow scripting like `for d in a b; do git worktree
# add $d; done` and `if ...; then git worktree add x; fi`. Loop/branch headers
# (`for`/`case`/`select`) and terminators (`fi`/`done`/`esac`) are NOT listed:
# they are harmlessly treated as ordinary (non-`git`) command words, and the
# keyword that actually precedes the `git` invocation (`do`/`then`) is here.
_SHELL_KEYWORDS = {"if", "then", "elif", "else", "while", "until", "do", "!"}

# The exact command-local marker that authorizes ONE requested-isolation worktree
# per the parallel-isolation protocol (operating-model.md). A command with exactly
# one `git worktree add` whose text ends with this marker is a protocol-requested
# isolation worktree and is not warned; anything else (missing/near-match/quoted/
# not-final marker, or two-or-more adds) still warns. One marker never suppresses a
# batch of adds.
REQUESTED_ISOLATION_MARKER = "# orchestrarium:requested-isolation-worktree"

# Path separators, as plain characters. Deliberately NOT a regex character class:
# expressing a literal backslash inside one requires layered escaping that is easy
# to get silently wrong (an earlier draft's `[^\s/\\'"]` collapsed to an escaped
# quote, so backslash was never excluded and a well-formed Windows path matched
# the mangled-target trigger). Plain `in`-tests are unambiguous.
_PATH_SEPARATORS = ("/", "\\")

# Build/log artifact extensions. CLOSED set — this is the axis that makes the
# root-destination triggers decidable without an allow-list.
_ARTIFACT_EXTENSIONS = frozenset({
    ".obj", ".o", ".pdb", ".ilk", ".mod", ".smod", ".lib", ".exe", ".log",
})

# Compilers that write object/debug output beside the invocation by default.
_COMPILERS = frozenset({
    "ifx", "ifort", "icx", "icx-cl", "icpx", "icc",
    "gfortran", "gcc", "g++", "clang", "clang++", "cl",
})

# Source-file extensions; a compiler invocation with none of these compiles
# nothing (`gcc --version`) and therefore writes nothing.
_SOURCE_EXTENSIONS = frozenset({
    ".c", ".cc", ".cpp", ".cxx", ".c++", ".cu",
    ".f", ".for", ".f90", ".f95", ".f03", ".f08",
    ".m", ".mm", ".s",
})

# Commands that move the process CWD, after which the destination of a bare
# redirect or a compiler's default output is no longer decidable -> fail open.
_DIRECTORY_CHANGE_COMMANDS = frozenset({"cd", "pushd", "popd"})

_EXPLICIT_OUTPUT_FLAGS = frozenset({"-o", "--output", "-out", "/out"})

# The token following a `>`/`>>` in the RAW command text. Read raw, not from the
# tokenizer, for two independent reasons: posix `shlex` eats backslashes, so
# `> r:\Temp\x\build.log` and the mangled `> r:Tempxbuild.log` tokenize
# IDENTICALLY (verified) and trigger (2) could never tell them apart; and a
# legitimate Windows scratch path `> .scratch\t\build.log` would collapse to a
# bare name and falsely look root-destined to trigger (3). `&` is excluded so
# `2>&1` yields no target.
_RAW_REDIRECT_RE = re.compile(r">>?\s*([^\s>&|;()]+)")


def _tokenize(command: str) -> list[str] | None:
    """Shell-aware tokenization, or None when the text cannot be parsed.

    Single owner of "how this hook splits a command into tokens"; every
    command-position consumer below derives from it. A tokenizer error (e.g.
    unbalanced quotes) returns None so callers fail open."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        return list(lexer)
    except ValueError:
        return None


def _is_redirect_operator(token: str) -> bool:
    """A redirection operator (`>`, `>>`, `<`, `2>`-tail, `>&`, ...) — NOT a
    command separator; the token after it is a target filename, not a command."""
    return ("<" in token or ">" in token) and all(c in "<>&" for c in token)


def _command_segments(tokens: list[str]) -> list[list[str]]:
    """Split tokens into command segments, each `[command_word, *operands]`.

    Single owner of command-position tracking for this hook. Handles separators
    (`;`, `&&`, `||`, `|`, `&`, `(`, `)`), env-assignment prefixes (`FOO=bar git
    ...`), command-slot-transparent shell keywords (`if`/`then`/`do`/...), and
    drops redirection operators together with their target so a redirect target
    is never mistaken for an operand. Segments with no command word are omitted.

    Scope: confidently parses the COMMON forms. Constructs that hide the real
    command word behind another (`sudo`/`env`/`xargs`/`eval`/`bash -c`) and
    command substitution are not modelled and simply under-count — acceptable
    for a warn-only AUDIT hook that always fails open and never blocks."""
    segments: list[list[str]] = []
    current: list[str] = []
    expect_command = True
    skip_redirect_target = False
    for token in tokens:
        if not token:
            continue
        if skip_redirect_target:
            skip_redirect_target = False
            continue
        if _is_redirect_operator(token):
            skip_redirect_target = True
            continue
        if all(c in ";|&()" for c in token):
            if current:
                segments.append(current)
            current = []
            expect_command = True
            continue
        if expect_command:
            # `FOO=bar git ...` — the assignment prefix does not consume the
            # command slot; the command word is still ahead.
            if "=" in token and token.split("=", 1)[0].isidentifier():
                continue
            # `if`/`then`/`do`/... do not consume the command slot either.
            if token in _SHELL_KEYWORDS:
                continue
            expect_command = False
        current.append(token)
    if current:
        segments.append(current)
    return segments


def _basename(token: str) -> str:
    """The command word's bare name, lowercased, without a `.exe` suffix."""
    name = token
    for separator in _PATH_SEPARATORS:
        name = name.rsplit(separator, 1)[-1]
    name = name.lower()
    return name[:-4] if name.endswith(".exe") else name


def _extension_of(name: str) -> str:
    """The lowercased final extension of `name`, or "" when it has none."""
    base = name
    for separator in _PATH_SEPARATORS:
        base = base.rsplit(separator, 1)[-1]
    if "." not in base:
        return ""
    return "." + base.rsplit(".", 1)[-1].lower()


def count_git_worktree_adds(command: str) -> int:
    """Count the confidently-parsed `git worktree add` invocations in `command`.

    Uses the same shell-aware, command-position approach as before: tokenize with
    `shlex` (so quotes are honored and `git` inside a quoted string is not a
    command), track command position across separators (`;`, `&&`, `||`, `|`, `&`,
    `(`, `)`), allow an env-assignment prefix (`FOO=bar git ...`), treat leading
    shell keywords (`if`/`then`/`elif`/`else`/`while`/`until`/`do`/`!`) as
    command-slot-transparent (so `for d in ...; do git worktree add $d; done` and
    `if ...; then git worktree add x; fi` are counted), and only treat `git` (or
    `.../git`) as a command word in command position. After `git`, skip global
    options (and the value of value-taking ones), then require the subcommand to be
    `worktree` followed by `add`. `git worktree list/remove/prune/...` is not
    counted. Instead of returning on the first detected add it scans every command
    segment and returns the TOTAL count, so the caller can distinguish one requested
    add from a batch. Any tokenizer error fails open (returns 0).

    Scope: confidently parses the COMMON forms (`git worktree add ...`,
    `cd x && git worktree add ...`, `FOO=bar git worktree add`, control-flow loops
    and branches). Constructs that hide `git` behind another command word in the
    command slot are not modelled and simply under-count: external command-wrappers
    (`sudo`/`env`/`nice`/`xargs`/`eval`/`bash -c`), command substitution
    (`$(...)`), and a value-taking global option whose value is itself a flag. That
    under-count is acceptable for a warn-only AUDIT hook that always fails open and
    never blocks.

    Command-position tracking itself now lives in `_command_segments` (shared with
    the root-destination triggers) so this hook has ONE owner of "where is a
    command word"; only the git-specific interpretation of a segment stays here."""
    tokens = _tokenize(command)
    if tokens is None:
        return 0  # unbalanced quotes / unparseable -> fail open

    count = 0
    for segment in _command_segments(tokens):
        head = segment[0]
        if not (head == "git" or head.endswith("/git")):
            continue
        seen_worktree = False
        skip_value = False
        for tok in segment[1:]:
            if skip_value:
                skip_value = False
                continue
            if tok in _GIT_VALUE_OPTS:
                skip_value = True  # `-C <path>`, `-c <k=v>`, ... -> skip the value
                continue
            if tok.startswith("-"):
                continue  # other git option (incl. `--opt=val` / bare `--flag`)
            if not seen_worktree:
                # first non-option token after `git` = the subcommand
                if tok != "worktree":
                    break  # a different git subcommand -> not our concern
                seen_worktree = True
                continue
            # first non-option token after `worktree`
            if tok == "add":
                count += 1
            break  # add counted, or list/remove/prune/... -> done with this git
    return count


def raw_redirect_targets(command: str) -> list[str]:
    """Redirect targets as they appear in the RAW command text, unquoted.

    Read raw rather than tokenized on purpose — see `_RAW_REDIRECT_RE`: posix
    tokenization destroys exactly the backslash evidence triggers (2) and (3)
    depend on."""
    return [match.strip("'\"") for match in _RAW_REDIRECT_RE.findall(command)]


def _has_directory_component(target: str) -> bool:
    return any(separator in target for separator in _PATH_SEPARATORS)


def mangled_windows_targets(command: str) -> list[str]:
    """Trigger (2): redirect targets carrying a drive-letter prefix and NO path
    separator — the Git Bash backslash-eating signature (`r:Tempxbuild.log`).

    A well-formed `r:\\Temp\\x\\build.log` or `r:/Temp/x/build.log` still holds
    its separators and is not matched. Requires at least one character after the
    colon, so a bare `r:` (which is what a well-formed backslash path leaves in
    front of its first separator) never matches."""
    found: list[str] = []
    for target in raw_redirect_targets(command):
        if _has_directory_component(target):
            continue
        if len(target) > 2 and target[1] == ":" and target[0].isalpha():
            found.append(target)
    return found


def root_destined_artifact_targets(command: str) -> list[str]:
    """Trigger (3): redirect targets with no directory component whose name is a
    build/log artifact — i.e. written straight into the process CWD.

    The CALLER is responsible for confirming the CWD is a repository root and
    that the command performs no directory change; this function only decides
    the destination-and-name half."""
    found: list[str] = []
    for target in raw_redirect_targets(command):
        name = target[2:] if target.startswith("./") else target
        if not name or _has_directory_component(name):
            continue
        if _extension_of(name) in _ARTIFACT_EXTENSIONS:
            found.append(name)
    return found


def changes_directory(command: str) -> bool:
    """Does the command move the process CWD (`cd`/`pushd`/`popd`)?

    When it does, the destination of a bare redirect or of a compiler's default
    output is no longer decidable from the command text, so the root-destination
    triggers fail open. Running a tool from inside its own scratch output
    directory is the documented, correct pattern — not a defect to warn about."""
    tokens = _tokenize(command)
    if tokens is None:
        return True  # unparseable -> fail open (suppress the root triggers)
    return any(
        _basename(segment[0]) in _DIRECTORY_CHANGE_COMMANDS
        for segment in _command_segments(tokens)
    )


def _directs_output(argument: str) -> bool:
    """Does this argument send compiler output somewhere explicit?

    Covers POSIX `-o`/`--output` and the MSVC/Intel-Windows `/Fo`, `/Fe`, `/Fd`
    family. The capital `F` is load-bearing: it distinguishes those output flags
    from gcc's lowercase `-f...` feature flags, so `-fopenmp` is NOT mistaken for
    an output redirection (which would silently suppress the trigger)."""
    lowered = argument.lower()
    if lowered in _EXPLICIT_OUTPUT_FLAGS:
        return True
    if lowered.startswith(("--output=", "-out:", "/out:")):
        return True
    return (
        len(argument) >= 3
        and argument[0] in "-/"
        and argument[1] == "F"
        and argument[2] in "oOeEdD"
    )


def compilers_writing_to_cwd(command: str) -> list[str]:
    """Trigger (4): compiler invocations that compile at least one source file
    and direct their output nowhere, so `.obj`/`.o`/`.pdb` land in the CWD.

    Requiring a source operand keeps probes such as `gcc --version` silent (they
    compile nothing and write nothing). The CALLER confirms the CWD is a
    repository root and that no directory change occurs."""
    tokens = _tokenize(command)
    if tokens is None:
        return []
    found: list[str] = []
    for segment in _command_segments(tokens):
        name = _basename(segment[0])
        if name not in _COMPILERS:
            continue
        operands = segment[1:]
        if any(_directs_output(argument) for argument in operands):
            continue
        if not any(_extension_of(a) in _SOURCE_EXTENSIONS for a in operands):
            continue
        found.append(name)
    return found


def is_repository_root(cwd_value: object) -> bool:
    """Is this exact directory a repository root (`cwd/.git` present)?

    A normal clone carries `.git` as a directory, a worktree or submodule
    checkout as a file; `exists()` accepts either. Deliberately NOT a walk-up
    "find the nearest enclosing root" search (the distinct question
    check-repository-orientation.py's own `_nearest_git_root` answers): the
    triggers here need to know whether the write lands IN the root, so a
    subdirectory must answer False. Any failure answers False, which suppresses
    the root-destination triggers — fail open."""
    if not isinstance(cwd_value, str) or not cwd_value:
        return False
    try:
        return (Path(cwd_value) / ".git").exists()
    except Exception:
        return False


def main() -> int:
    try:
        envelope = parse_envelope(read_stdin_utf8())
    except Exception:
        return 0  # malformed envelope -> fail open

    tool_input = envelope.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0

    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        return 0

    reasons: list[str] = []

    add_count = count_git_worktree_adds(command)
    # A protocol-requested isolation worktree is exactly one add whose command
    # ends with the exact marker; anything else (missing/near-match/quoted/
    # not-final marker, or a batch of adds) still warns.
    requested = add_count == 1 and command.rstrip().endswith(REQUESTED_ISOLATION_MARKER)
    if add_count and not requested:
        reasons.append(
            "this command creates a git worktree (`git worktree add`). A worktree is "
            "an unrequested side effect unless you were explicitly asked for one — "
            "confirm it is intended, and do not create worktrees or other throwaway "
            "artifacts the user did not request. A protocol-requested isolation "
            "worktree must be a SINGLE `git worktree add` whose command ends with the "
            "exact marker `# orchestrarium:requested-isolation-worktree`, added only "
            "after naming the lane and isolation reason."
        )

    # Trigger (2) is NOT gated on the repository-root probe: a drive-letter prefix
    # with no separator is always a mistake, wherever the process is running.
    mangled = mangled_windows_targets(command)
    if mangled:
        reasons.append(
            "this redirect target looks like a MANGLED Windows path: "
            f"{', '.join(mangled)}. A drive letter with no path separator is the "
            "signature of a shell eating the backslashes of `r:\\Temp\\...`, which "
            "silently creates ONE file named after the whole mangled path while the "
            "command reports success. Write the target with forward slashes or as a "
            "repository-relative path."
        )

    # Triggers (3)/(4) need a CONFIRMED repository-root CWD and no directory change.
    if is_repository_root(envelope.get("cwd")) and not changes_directory(command):
        artifacts = root_destined_artifact_targets(command)
        if artifacts:
            reasons.append(
                "this redirect writes a build/log artifact into the repository ROOT: "
                f"{', '.join(artifacts)}. A target with no directory component lands "
                "in the process working directory, which here is the repository root. "
                "Send run logs and build captures to a scratch directory instead "
                "(e.g. `.scratch/<topic>/`); durable evidence belongs in a tracked "
                "validation package, never loose in the root."
            )
        compilers = compilers_writing_to_cwd(command)
        if compilers:
            reasons.append(
                "this compiler invocation "
                f"({', '.join(sorted(set(compilers)))}) directs its output nowhere, so "
                "object and debug files (`.obj`/`.o`/`.pdb`) land in the repository "
                "ROOT and are easy to miss — this is the mechanism behind a recorded "
                "cleanup of 54 stray build artifacts. Compile from inside a scratch "
                "directory, or pass an explicit output path (`-o`, `/Fo`)."
            )

    if reasons:
        emit_advisory(
            envelope,
            "[stray-artifact AUDIT] " + " ALSO: ".join(reasons) + " AUDIT mode -- allowing.",
        )
        # Exit 0: the advisory reaches the model via hookSpecificOutput.
        # additionalContext (see hook_common.emit_advisory) -- never exit 2 (block).
    return 0


if __name__ == "__main__":
    sys.exit(main())
