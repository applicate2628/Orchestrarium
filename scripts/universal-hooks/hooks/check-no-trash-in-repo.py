#!/usr/bin/env python3
"""Stray-artifact guard (PreToolUse, AUDIT mode) — unrequested `git worktree add`.

WHAT THIS WARNS ON: a Bash command that confidently runs `git worktree add`, i.e.
the agent creating a git worktree. Worktrees are an unrequested side effect when
the user did not ask for one; this hook surfaces them so they can be caught.

WHY IT REPLACED THE NAME-BASED NO-TRASH CHECK: the previous version of this file
warned when a NEW directory whose name was in a hardcoded "author-process
vocabulary" list (`kosyaks`, `mistake-log`, ...) was created in the repo. That was
useless — those names are the *user's* personal vocabulary, not names the *agent*
(the actor a PreToolUse hook guards) ever writes, so it never fired. Directory-name
matching was the wrong axis. The real reported problem was the agent creating
stray artifacts — chiefly unrequested worktrees — so this guard keys on the
OPERATION, not on a name.

SCOPE (per the parallel-isolation protocol):
  - `git worktree add` from Bash -> warn, UNLESS the command contains exactly one
    add and ends with the exact command-local marker
    `# orchestrarium:requested-isolation-worktree` (a protocol-requested isolation
    worktree). A missing, near-match, quoted, or not-final marker, or two-or-more
    adds with one marker, still warns — one marker never suppresses a batch.
    `git worktree list/remove/prune` are harmless and ignored.
  - Deferred: the Claude `Agent` tool's `isolation: "worktree"` form (needs a real
    PreToolUse envelope to confirm the field shape before matching it).
  - Dropped: "writes outside the repo" (a static allow-list false-positives on
    legitimate installs, temp prompts, global config, and memory/rules writes) and
    "arbitrary in-repo trash" (no reliable non-name signal — that stays governance,
    i.e. "all scratch goes to .scratch/", not a hook).

AUDIT mode: on a hit, warn to stderr and ALLOW the command -- but exit 1 (never
2, which would block) so the warning actually surfaces. Per Claude Code's hooks
reference, exit 0's stderr is written only to the debug log and is invisible in
the transcript; any other non-zero, non-2 exit code is a non-blocking error that
shows a "<hook name> hook error" notice plus the first stderr line in the
transcript, and execution continues exactly as it does on exit 0. Exit 1 on a
hit (0 otherwise) is what makes the AUDIT warning visible enough to actually
measure the false-positive rate this posture exists to measure. Never blocks —
a worktree can be legitimately requested, and the hook cannot read intent.
Fails open on any internal error (return 0).

NOTE: the filename/install-marker `check-no-trash-in-repo` is retained for
install-entry continuity (avoids a settings.json/hooks.json migration in this
first cut). A rename to `check-stray-artifact` is a tracked follow-up.
"""
from __future__ import annotations

import os
import shlex
import sys

# hook_common lives in the sibling scripts/ dir (shared with the grandfathered
# hooks); this hook lives in the typed hooks/ dir per the source-hygiene rule,
# so add the sibling scripts/ dir to the import path before importing it.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from hook_common import parse_envelope, read_stdin_utf8


def _emit(msg: str) -> None:
    """Write a warning to stderr as UTF-8 bytes, regardless of console codepage.

    On Windows the default stderr encoding is the console codepage (e.g. cp1252);
    Claude Code and the test harness both read hook stderr as UTF-8. Writing
    UTF-8 bytes directly keeps the warning readable everywhere. Fail-open."""
    try:
        sys.stderr.buffer.write(msg.encode("utf-8"))
        sys.stderr.buffer.flush()
    except Exception:
        try:
            sys.stderr.write(msg)
        except Exception:
            pass


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
    never blocks."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return 0  # unbalanced quotes / unparseable -> fail open

    count = 0
    expect_command = True   # command position: line start, and after each separator
    in_git = False          # the current command word is `git`
    seen_worktree = False    # the `worktree` subcommand has been seen for this git
    skip_value = False       # the previous token was a value-taking git global option
    skip_redir_target = False  # the previous token was a redirection operator
    for tok in tokens:
        if not tok:
            continue
        if skip_redir_target:
            skip_redir_target = False
            continue
        if skip_value:
            skip_value = False
            continue
        # A redirection operator (`>`, `>>`, `<`, `2>`, `&>`, ...) is NOT a command
        # separator; the next token is its target filename, not a command/arg.
        if ("<" in tok or ">" in tok) and all(c in "<>&" for c in tok):
            skip_redir_target = True
            continue
        # Command separators -> the next token starts a new command.
        if all(c in ";|&()" for c in tok):
            expect_command = True
            in_git = False
            seen_worktree = False
            continue
        if expect_command:
            # An env-var assignment prefix (`FOO=bar git ...`) does not consume the
            # command slot — the command word is still ahead.
            if "=" in tok and tok.split("=", 1)[0].isidentifier():
                continue
            # A leading shell keyword (`if`/`then`/`do`/...) does not consume the
            # command slot either — stay in command position for the word after it.
            if tok in _SHELL_KEYWORDS:
                continue
            in_git = tok == "git" or tok.endswith("/git")
            seen_worktree = False
            expect_command = False
            continue
        if not in_git:
            continue  # operand of some non-git command
        if tok in _GIT_VALUE_OPTS:
            skip_value = True  # `-C <path>`, `-c <k=v>`, ... -> skip the value too
            continue
        if tok.startswith("-"):
            continue  # other git option (incl. `--opt=val` / bare `--flag`)
        if not seen_worktree:
            # first non-option token after `git` = the subcommand
            if tok == "worktree":
                seen_worktree = True
            else:
                in_git = False  # a different git subcommand -> not our concern
            continue
        # first non-option token after `worktree`
        if tok == "add":
            count += 1
        # done with this git invocation (add counted, or list/remove/prune/...);
        # ignore its remaining operands until the next command separator.
        in_git = False
        seen_worktree = False
    return count


def main() -> int:
    try:
        envelope = parse_envelope(read_stdin_utf8())
    except Exception:
        return 0  # malformed envelope -> fail open

    tool_input = envelope.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0

    command = tool_input.get("command")
    if isinstance(command, str) and command:
        add_count = count_git_worktree_adds(command)
        # A protocol-requested isolation worktree is exactly one add whose command
        # ends with the exact marker; anything else (missing/near-match/quoted/
        # not-final marker, or a batch of adds) still warns.
        requested = add_count == 1 and command.rstrip().endswith(REQUESTED_ISOLATION_MARKER)
        if add_count and not requested:
            _emit(
                "[stray-artifact AUDIT] this command creates a git worktree "
                "(`git worktree add`). A worktree is an unrequested side effect unless "
                "you were explicitly asked for one — confirm it is intended, and do not "
                "create worktrees or other throwaway artifacts the user did not request. "
                "A protocol-requested isolation worktree must be a SINGLE `git worktree "
                "add` whose command ends with the exact marker "
                "`# orchestrarium:requested-isolation-worktree`, added only after naming "
                "the lane and isolation reason. AUDIT mode -- allowing.\n"
            )
            # Exit 1 (never 2): a non-blocking "<hook name> hook error" transcript
            # notice with the first stderr line, so the warning is actually
            # visible -- exit 0 here is invisible outside --debug.
            return 1
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
