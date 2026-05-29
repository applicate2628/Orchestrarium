#!/usr/bin/env python3
"""No-trash-in-repo guard (PreToolUse, AUDIT mode) — redesigned (Task 9).

Warns only when an operation CREATES A NEW directory inside the repo whose
newly-created name is high-signal author-process vocabulary (`kosyaks`,
`journal`, `diary`, `mistakes`, `mistake-log`, `personal`, `private`, `mine`).
Author-process journals and mistake logs belong in the author's external rules
library outside any project repo; `.scratch/` is the in-repo gitignored
evidence area and is always allowed.

Why redesigned: the first version matched directory NAMES alone and treated
ordinary project dirs (`dev/`, `notes/`, `docs/`, `scratch/`) as suspicious, so
it fired on essentially every edit across varied repos. This version is
FP-resistant: it warns only when ALL of the following hold (Codex design pass):
  1. the target path is inside the repo and not under `.scratch/`;
  2. the operation CREATES A NEW directory — a parent directory that does not
     yet exist on disk; editing or writing under an EXISTING directory never
     warns (so an established `dev/` or `notes/` source dir is silent);
  3. a newly-created directory segment is a high-signal personal name;
  4. git does not already track files under that path (an established tracked
     project directory is suppressed). Git is a SUPPRESSOR only and fails open:
     any git error, timeout, or non-repo state just means "no git suppression",
     never a crash and never a false block.

Ambiguous names (`dev`, `notes`, `scratch`, `docs`, `tools`, `tmp`, `temp`) are
NOT suspicious by themselves — they are common legitimate project structure.

Fires on the edit's own `tool_input` (`Write`/`Edit` `file_path`, Bash `mkdir`
operand). AUDIT mode: on a hit, warn to stderr and ALLOW (exit 0). Promotion to
a blocking `deny` is a separate reviewed step once the false-positive rate is
measured. Fail-open everywhere on internal error (return 0).
"""
from __future__ import annotations

import os
import shlex
import subprocess
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


# High-signal author-process directory names. These are rarely product
# structure; ambiguous names (dev, notes, docs, tools, tmp, scratch) are
# deliberately NOT here. Dot-prefixed segments (.scratch) are always allowed.
HIGH_SIGNAL_NAMES = {
    "kosyaks",
    "journal",
    "diary",
    "mistakes",
    "mistake-log",
    "personal",
    "private",
    "mine",
}


def repo_root(envelope: dict) -> str | None:
    """Best-effort repo/project root from the hook envelope, normalized to `/`."""
    cwd = envelope.get("cwd")
    if isinstance(cwd, str) and cwd:
        return cwd.replace("\\", "/").rstrip("/")
    pd = os.environ.get("CLAUDE_PROJECT_DIR")
    if pd:
        return pd.replace("\\", "/").rstrip("/")
    return None


def to_absolute(path: str, root: str | None) -> str | None:
    """Resolve a candidate to an absolute `/`-normalized path, or None.

    A relative path needs the repo root to resolve; without a known root we
    cannot run the new-directory existence check, so we return None and the
    caller fails open (no warning) rather than guessing."""
    p = path.replace("\\", "/")
    is_absolute = p.startswith("/") or (len(p) > 1 and p[1] == ":")
    if is_absolute:
        joined = p
    elif root:
        joined = root.rstrip("/") + "/" + p.lstrip("/")
    else:
        return None
    # Normalize `.`/`..` so a path that escapes the repo (e.g. `../personal/x`)
    # resolves to its real location and is then rejected by inside_repo, instead
    # of being accepted on the lexical in-repo prefix.
    return os.path.normpath(joined).replace("\\", "/").rstrip("/")


def inside_repo(abs_path: str, root: str | None) -> bool:
    """True if abs_path is the repo root or lives under it."""
    if not root:
        return False
    a = abs_path.lower()
    r = root.rstrip("/").lower()
    return a == r or a.startswith(r + "/")


def newly_created_high_signal_segment(abs_dir: str, root: str) -> str | None:
    """First high-signal personal name among the directory segments abs_dir
    would NEWLY create (those that do not exist on disk yet, from the first
    missing ancestor down to abs_dir), or None.

    An already-existing directory is not "created", so editing/writing under it
    never matches — that keeps an established project dir silent. A segment that
    is itself dot-prefixed, OR that lives under a dot-prefixed ancestor (e.g.
    anything inside `.scratch/`), is allowed: `.scratch/` is the in-repo
    gitignored evidence area where local trash legitimately lives."""
    root_n = root.rstrip("/")
    abs_dir = abs_dir.rstrip("/")
    if not (abs_dir.lower() == root_n.lower() or abs_dir.lower().startswith(root_n.lower() + "/")):
        return None
    rel = abs_dir[len(root_n):].strip("/")
    if not rel:
        return None
    segs = [s for s in rel.split("/") if s and s not in (".", "..")]

    # Index of the first segment that does not exist on disk yet (walking down
    # from the repo root); segments at/after it are the newly-created ones.
    first_new = len(segs)
    cur = root_n
    for i, s in enumerate(segs):
        cur = cur + "/" + s
        if not os.path.exists(cur):
            first_new = i
            break
    if first_new == len(segs):
        return None  # every directory already exists -> nothing created

    for i in range(first_new, len(segs)):
        seg = segs[i]
        if seg.startswith("."):
            continue  # the dot-dir itself (e.g. .scratch) is allowed
        if any(a.startswith(".") for a in segs[:i]):
            continue  # inside a dot-prefixed dir (e.g. under .scratch/) -> allowed
        if seg.lower() in HIGH_SIGNAL_NAMES:
            return seg
    return None


def git_tracks_path(rel_path: str, root: str) -> bool:
    """True iff git tracks any file under rel_path (an established project dir
    -> suppress the warning). Git is a SUPPRESSOR only: any error, timeout, or
    non-repo state returns False so the filesystem check stands and the hook
    never crashes or blocks on git."""
    if not rel_path:
        return False
    try:
        out = subprocess.run(
            ["git", "-C", root, "ls-files", "--", rel_path],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return out.returncode == 0 and out.stdout.strip() != ""
    except Exception:
        return False


def mkdir_targets(command: str) -> list[str]:
    """Extract directory operands from confident `mkdir` invocations using a
    shell-aware tokenizer (`shlex`), so quotes are honored the way bash honors
    them: `mkdir "a b"` is ONE operand, `mkdir dev/"kosyaks"` resolves to
    `dev/kosyaks`, and a `mkdir` appearing inside a quoted string (e.g.
    `echo "mkdir personal"`) is NOT treated as a command. Operands that carry a
    shell variable, glob, or command substitution are skipped as unconfident.
    Command position and redirections are tracked: `echo mkdir x` and
    `echo > mkdir x` do not warn (mkdir is an argument / a redirect target),
    while `mkdir > out x` does (the redirection does not end the command).

    A `cd` ANYWHERE in the command stops operand resolution. Once the working
    directory is changed, both the cwd a later `mkdir` runs in AND whether a
    guarded `mkdir` runs at all become runtime-dependent: `cd .scratch && mkdir
    personal` creates an exempt dir, `cd x || mkdir y` runs mkdir only if cd
    FAILED, `cd x || exit; mkdir y` runs it only if cd SUCCEEDED. A static parser
    cannot resolve that without the filesystem, so after any `cd` the hook
    UNDER-warns rather than risk a false positive (modelling cd cwd precisely
    produced a string of FP/under-warn regressions and is a losing game). This is
    the deliberate tradeoff for a warn-only AUDIT hook: the common forms
    (`mkdir kosyaks`, `mkdir -p a/kosyaks`, a `Write` into `journal/x.md`) carry
    no `cd` and still warn; only cd-prefixed forms are skipped.

    Any tokenizer error (e.g. unbalanced quotes) fails open by returning none.
    Scope: this confidently parses the COMMON mkdir forms; exotic constructs
    (`xargs mkdir`, `find -execdir mkdir`, `eval`, subshell pipelines) are not
    parsed and will simply under-warn — acceptable for this warn-only AUDIT hook
    that always fails open and never blocks. The goal is FP-resistance (never
    warn on an ordinary command), not exhaustive shell coverage."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return []  # unbalanced quotes / unparseable -> fail open
    targets: list[str] = []
    expect_command = True  # command position: line start, and after each separator
    in_mkdir = False
    cd_seen = False        # a `cd` appeared earlier in the command. After a cd the
                           # cwd a later mkdir runs in — and whether a guarded
                           # mkdir runs at all — is runtime-dependent, so we stop
                           # resolving mkdir operands and under-warn (fail open,
                           # false-positive-free) instead of modelling shell cwd.
    skip_next = False      # the next token is a redirection TARGET (a filename)
    for tok in tokens:
        if skip_next:
            skip_next = False
            continue
        if not tok:
            continue
        # A redirection operator (`>`, `>>`, `<`, `2>`, `&>`, `>&`, ...) is NOT a
        # command separator: it redirects the CURRENT command, and the next
        # token is the target filename (not a command word and not an operand).
        # `mkdir > out personal` still creates `personal`; `echo > mkdir personal`
        # does not run mkdir (the `mkdir` here is a redirect target).
        if ("<" in tok or ">" in tok) and all(c in "<>&" for c in tok):
            skip_next = True
            continue
        # Command separators: `;`, `&&`, `||`, `|`, `&`, `(`, `)` -> next token
        # starts a new command.
        if all(c in ";|&()" for c in tok):
            expect_command = True
            in_mkdir = False
            continue
        if expect_command:
            # An env-var assignment prefix (`FOO=bar mkdir ...`) does not consume
            # the command slot — the command word is still ahead.
            if "=" in tok and tok.split("=", 1)[0].isidentifier():
                continue
            # `mkdir` (or `/path/to/mkdir`) and `cd` count ONLY in command
            # position. `echo mkdir personal` has `mkdir` as an ARGUMENT of
            # another command and must not be treated as a mkdir.
            if tok == "cd":
                cd_seen = True  # cwd now runtime-dependent -> stop resolving operands
            in_mkdir = tok == "mkdir" or tok.endswith("/mkdir")
            expect_command = False
            continue
        if not in_mkdir:
            continue  # operand of some non-mkdir command
        if tok.startswith("-"):
            continue  # flag such as -p
        if any(c in tok for c in "$*?`(){}"):
            continue  # variable / glob / substitution -> not confident
        if cd_seen:
            continue  # a `cd` ran earlier -> operand path is runtime-dependent
        targets.append(tok)
    return targets


def main() -> int:
    try:
        envelope = parse_envelope(read_stdin_utf8())
    except Exception:
        return 0  # malformed envelope -> fail open

    tool_input = envelope.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0

    root = repo_root(envelope)

    # (path, is_dir_target): a write `file_path`'s last segment is a filename,
    # so the directory to test is its parent; a `mkdir` operand IS the directory.
    candidates: list[tuple[str, bool]] = []
    for key in ("file_path", "notebook_path", "path"):
        v = tool_input.get(key)
        if isinstance(v, str) and v:
            candidates.append((v, False))
    command = tool_input.get("command")
    if isinstance(command, str) and command:
        candidates.extend((t, True) for t in mkdir_targets(command))

    for cand, is_dir_target in candidates:
        abs_path = to_absolute(cand, root)
        if abs_path is None or not inside_repo(abs_path, root):
            continue  # outside the repo, or unresolvable -> fail open (skip)
        abs_dir = abs_path if is_dir_target else abs_path.rsplit("/", 1)[0]
        seg = newly_created_high_signal_segment(abs_dir, root)
        if not seg:
            continue
        rel_dir = abs_dir[len(root.rstrip("/")) + 1:] if root else ""
        if git_tracks_path(rel_dir, root):
            continue  # established tracked project directory -> suppress
        _emit(
            f"[no-trash-in-repo AUDIT] creating a new high-signal personal-process "
            f"directory '{seg}/' inside the repo ({cand}). Author-process journals, "
            f"mistake logs, and scratchpads belong in your external rules library "
            f"outside any project repo, not in the project tree; use .scratch/ for "
            f"in-repo gitignored local evidence. AUDIT mode -- allowing.\n"
        )
        return 0  # one warning is enough; AUDIT always allows

    return 0


if __name__ == "__main__":
    sys.exit(main())
