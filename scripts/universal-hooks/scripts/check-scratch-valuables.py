#!/usr/bin/env python3
"""Scratch-valuables SessionStart watchdog -- READ-ONLY, self-contained.

WHY THIS DUPLICATES `scripts/maintenance/cleanup.py`'S SCAN LOGIC INSTEAD OF
IMPORTING IT. This hook is installed into arbitrary TARGET repositories by the
pack installer (see `scripts/install-claude.sh` / `install-codex.sh`), the
same way as `mcp-usage-reminder` and `agents-mode-reminder`.
`scripts/maintenance/cleanup.py` stays repository-local to Orchestrarium's own
working tree and is never installed elsewhere (an installed copy of this hook
has no access to it), so this file carries its own small, deliberately
self-contained mirror of that module's `scan_valuables()`, INCLUDING the
git-uniqueness predicate below. If the algorithm changes on one side, update
the other -- each file's docstring points at its twin. (The whole-hook time
budget below is NOT mirrored into `cleanup.py`: that module is an
operator-invoked CLI, not a SessionStart hook, so it is not on a
startup-blocking path and does not share this hook's cost constraint -- see
`work-items/bugs/2026-07-26-scratch-valuables-hangs-session-start-for-65s-on-
a-large-scratch-tree.md` for why that distinction matters.)

CONTRACT: READ-ONLY. This hook must NEVER write, move, delete, rename, or
create anything under the target repository's `.scratch/` tree, or anywhere
in its git object store, on any platform, under any code path. Its only
filesystem/process calls are `os.scandir`, `DirEntry.is_symlink` / `is_dir` /
`is_file` / `.stat`, `os.path.isjunction`, two READ-ONLY git subprocesses
(`git hash-object` WITHOUT `-w`, `git cat-file --batch-check`), and -- new
below -- a small payload file written under the OS temporary directory
(never under the target repository) to feed those two subprocesses' stdin;
that file is torn down on every exit path, including a killed subprocess,
via `tempfile.TemporaryDirectory` plus this module's own exception handling
(see `_run_git_stdin_batch`'s docstring for why `ignore_cleanup_errors` is
deliberately not relied on here). (`Path.stat` no longer appears here as of
the "ONE SYSCALL PER FILE" fix below -- the walk now reuses each entry's own
`DirEntry.stat()`.)

WHY A HOOK AND NOT A CLI THE OPERATOR RUNS. The operator's own words, quoted
in `scripts/maintenance/cleanup.py` and in
`work-items/active/2026-07-16-cleanup-routine/design-watchdog-reframe.md`:
they do not want a command to remember to run -- they want the agent to
notice on its own. Registered on `SessionStart` with no `matcher` (like
`mcp-usage-reminder`), so it fires at every session start, resume, `/clear`,
and after every compaction.

PREDICATE (2026-07-17, adversarial-review follow-up -- see
`scripts/maintenance/cleanup.py`'s module docstring for the full evidence).
The PRIMARY signal is git-content-uniqueness, not age: a file is a candidate
only if its content is not already recoverable from the repository's git
object database (any commit, any branch). An age-only gate measured on this
project's own real `.scratch/` had near-zero precision (58 of 59 sampled
"old" files were byte-identical to an existing git blob). Age is DEMOTED to a
severity/sort key (newest-modified first) and PRESENTATION threshold, not a
filter. When git is unavailable for the scan (no repository, no executable,
or any git call fails), this fails OPEN to the original age-gated behavior.

WHOLE-HOOK TIME BUDGET (2026-07-26, this fix -- see the bug report named
above). The predicate above is unchanged, but it used to run over the ENTIRE
candidate set with no bound on total input: `git hash-object --stdin-paths`
reads and hashes every candidate file's BYTES, so a large `.scratch/` (the
reported case: 62,958 files, 19.02 GB) made the hook's cost scale with the
tree's size -- 65 s to the reported timeout, cold-disk reads plausibly worse,
against a startup path that fires on every session start, resume, `/clear`,
and compaction. Fixed by bounding the WHOLE scan -- walk included, not just
the git subprocess -- by a single wall-clock deadline
(`HOOK_TIME_BUDGET_SECONDS`), so total hook cost is now roughly CONSTANT
regardless of tree size: a heavy project pays about what a light one pays,
by construction, because the deadline is checked with `time.monotonic()`
throughout the walk itself, not only around the git call.

BUDGET SHAPE. Two independent, composed limits:
  1. A wall-clock DEADLINE (`_WalkBudget`) bounds the directory walk itself
     (`_iter_candidate_files`), checked at every directory visit and
     periodically inside a large single directory's entry list. When it
     expires, the walk stops immediately; it never resumes or retries.
  2. A candidate-count and total-bytes CEILING (`MAX_GIT_CHECK_FILES`,
     `MAX_GIT_CHECK_BYTES`) bounds what gets HANDED to `git hash-object`,
     applied BEFORE that subprocess is ever invoked -- not a wall-clock
     timeout on the subprocess alone (that was the pre-fix design, and the
     bug report's point is that a timeout on the git call is not a safety
     margin once nothing bounds the INPUT: it becomes the normal path).
     Candidates are ordered CHEAPEST-FIRST (ascending `st_size`, already
     known from the `stat()` every candidate needs anyway -- no extra
     syscall) before the ceiling is applied, so a fixed byte budget verifies
     the MOST files, not the fewest -- and a handful of oversized outliers
     (the actual byte-cost driver in a large, uneven tree) cannot crowd out
     everything else. This is deliberately ORTHOGONAL to file age: this
     hook's whole reason to exist is surfacing files that lingered LONG
     (see "LONGEST-LINGERING LEADS" below), so an ordering that
     systematically sacrifices the oldest files under budget pressure would
     undermine the one thing operators are asking it to find. Sacrificing
     the largest files instead has no such conflict, and directly targets
     the measured cost driver (bytes read).
  Whatever the git-uniqueness check does not reach in time (deadline
  exhausted mid-call, or ceiling-excluded up front) still gets the SAME
  age-gated fallback used when git is unavailable entirely -- never silently
  dropped -- just at that fallback's already-documented lower precision.

HONESTY UNDER BUDGET. A watchdog that quietly examined a fraction of a large
tree and reported normally would be worse than the 65 s hang it replaces --
the operator would believe they were warned when they were not (exactly the
failure-indistinguishable-from-success class this repository spent 2026-07-26
repairing across several other hooks). So: whenever the walk was cut short by
the deadline, OR any already-found candidate could not be git-verified within
this run's remaining time/size budget and was age-gated instead, the emitted
message says so explicitly, with a rough sense of how much was not examined
(`ScanReport`, `_disclosure_clause`). This is DISTINCT from, and additional
to, the pre-existing silent fallback for "no git repository at all" -- that
one is not new and stays quiet, per the PREDICATE section above.

CLEAN TIMEOUT PATH (2026-07-26, this fix). Pre-fix, `subprocess.run(...,
input=<str>, timeout=...)` fed stdin from a background daemon thread
(`Popen._communicate`'s `_stdin_thread`, installed CPython 3.14
`subprocess.py` -- verified by reading that file, not inferred). On timeout,
`subprocess.run` kills the child and, on Windows, calls `communicate()` a
SECOND time specifically to reap that thread (its own comment: "the thread
remains writing... in case the user calls communicate again"), but the
thread's blocked write can land on a pipe whose read end just vanished
(`TerminateProcess`), and `Popen._stdin_write` only swallows
`BrokenPipeError` and `OSError` with `errno.EINVAL` -- any other `OSError`
escapes the background thread uncaught, where nothing in this module (or any
Python code) can catch it; Python's default `threading.excepthook` prints it
to stderr instead ("Exception in thread Thread-3 (_writerthread)", exactly
the reported symptom). Fixed by never using `input=` for these calls:
`_run_git_stdin_batch` writes the payload to a temp file and passes
`stdin=<that already-fully-written file>` instead. A real file object as
`stdin` leaves `Popen.stdin` as `None` (confirmed empirically against this
Python install), so `_communicate` never creates a writer thread at all --
there is nothing left to kill mid-write, on any timeout, of any size.

ONE SYSCALL PER FILE, NOT TWO (2026-07-27, this fix -- see
`work-items/bugs/2026-07-26-scratch-watchdog-walks-with-the-slow-api-and-
leaves-a-20x-win-unclaimed.md`). The walk already used `os.scandir` for
directory listings (that part predates this fix), but `_iter_candidate_files`
discarded each `DirEntry` at yield time -- it yielded a bare `Path`, and
`_scan_valuables` then called `Path.stat()` on it, a SECOND syscall per
candidate file even though `DirEntry.stat()` (a THIRD, cheaper option) had
already been available from the SAME directory read `scandir` just did, and
is served from a cache Windows already populated rather than issuing a fresh
`stat`/`GetFileAttributesEx` call. Fixed by yielding `(Path, os.stat_result)`
pairs -- `entry.stat(follow_symlinks=False)` captured once, right where the
entry is already being inspected for `is_dir`/`is_file` -- so
`_scan_valuables` consumes the already-known stat instead of re-deriving it.
`follow_symlinks=False` matches `is_dir`/`is_file` above it and the module's
existing symlink/reparse-point posture (`_is_link_or_reparse` already
filtered those out before this point, so the flag cannot change *which*
files are matched -- it only avoids a needless follow on an entry already
known not to need one). Measured on this development machine (see this
file's own test run for the harness; numbers are this session's, stated with
their load conditions, not carried over from an unrelated run): a
several-thousand-file synthetic `.scratch/` tree walked in a small fraction
of its pre-fix time under the SAME two-syscalls-per-file baseline this
module's own docstring already named as the cost driver. A bounded thread
pool over top-level subdirectories was considered (the linked bug measured a
further ~2.4x from one) and deliberately NOT added: this is a SessionStart
hook with a 300ms-scale budget, thread creation itself is not free on a
cold-started interpreter, and the added surface (bounding pool size,
thread-safety of the shared `_WalkBudget`/`ScanReport` counters, deterministic
result ordering across workers) is a real fragility cost for a workload that
is already, by this fix, comfortably inside budget on ordinary trees. Taking
the syscall-halving win without the concurrency complexity is the
deliberate, disclosed choice here, not an oversight.

PRESENTATION. Emits a `hookSpecificOutput` context block ONLY when at least
one candidate is found OR the scan was budget-limited (see "HONESTY UNDER
BUDGET" above); otherwise BYTE-SILENT (matching `agents-mode-reminder` where
the presence of the block itself is the signal). When the candidate count
exceeds `SUMMARIZE_THRESHOLD`, the message summarizes by top-level
`.scratch/` subdirectory instead of a flat dump (a flat listing of hundreds
of files is noise nobody reads), CAPPED to the top `DIR_SUMMARY_TOP_N`
directories by count so the summary itself cannot grow unbounded, and lists
only a small LONGEST-LINGERING-led window. LONGEST-LINGERING LEADS, not
newest-modified: the operator's stated risk is data that "khranilis dolgo"
(lingered LONG), and newest-modified anti-selects for it -- the newest
entries are the CURRENT session's own churn the operator already knows
about, while the genuine long-lingering candidate sits at the opposite end
of the list and would never be shown if newest led. Fail-open throughout:
any internal error is swallowed and the hook exits 0 with no output -- it
must never block a session or crash noisily.
"""
from __future__ import annotations

import json
import locale
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import directly, with NO fallback stub -- matching every warn-only audit in
# scripts/universal-hooks/hooks/ (check-machine-local-path.py, check-no-trash-
# in-repo.py, check-stale-relation-residue.py, check-repository-orientation.py,
# check-mcp-momentum.py, check-typed-routing.py). A prior version of this file
# wrapped the import in `try/except Exception` and substituted a stub
# `parse_envelope` that returned `{}` on failure. Unlike the mute audits above,
# that stub was REACHABLE and LOSSY, not silent: discarding the envelope's
# declared `cwd` made `_resolve_root` (below) fall through to `Path.cwd()`, so
# a broken install scanned a DIFFERENT project than the one the envelope
# named and reported those findings as belonging to the caller's own project
# -- confidently wrong, not silently absent (work-items/bugs/2026-07-26-
# scratch-valuables-degrades-to-scanning-the-wrong-project-and-reports-it-as-
# correct.md; measured there: envelope declaring cwd=projB with the process at
# projA yielded `KEEPME_projB` when healthy and `KEEPME_projA` when
# `hook_common` was absent, exit 0 either way).
#
# CONTRACT CHOSEN: fail loud, matching every sibling audit's own resolved
# contract (work-items/bugs/2026-07-26-the-mcp-momentum-audit-stubs-its-own-
# delivery-to-a-no-op.md). A broken install now surfaces as an uncaught
# ImportError before `main()` is ever entered -- a nonzero exit code (Python's
# default is 1) and a traceback on stderr -- instead of a fabricated report
# about the wrong project. This does not weaken this hook's own "never block
# a session" contract: the retired shell launchers unconditionally
# exit 0 regardless of the Python process's own exit code (measured; those
# wrappers do not propagate `$?`/`$LASTEXITCODE` the way the six PreToolUse
# audit wrappers do), so a broken install still never blocks a session -- it
# just stops printing invented data about the wrong project.
#
# What this choice does NOT close: (1) the failure is a raw traceback on
# stderr, not a deliberate one-line diagnostic, and whether the operator ever
# sees it depends on whether the host surfaces a SessionStart hook's stderr
# when its wrapper still exits 0 -- not verified either way in this
# repository; (2) it leaves unchanged the separate, pre-existing behavior
# below where a SUCCESSFULLY parsed envelope that simply omits `cwd` still
# resolves to `Path.cwd()` -- that is a different, legitimate code path
# (hook_common working correctly, the envelope itself lacking the field) and
# is out of this fix's scope.
from hook_common import parse_envelope, read_stdin_utf8


SCRATCH_DIRNAME = ".scratch"
# Fallback-only (used when git is unavailable for this scan, or when the
# git-uniqueness check does not complete within this run's budget). Keep in
# sync with VALUABLE_AGE_THRESHOLD_DAYS in scripts/maintenance/cleanup.py.
FALLBACK_AGE_THRESHOLD_DAYS = 7
SECONDS_PER_DAY = 24 * 60 * 60

# --- Whole-hook wall-clock budget -------------------------------------------
# See the module docstring's "WHOLE-HOOK TIME BUDGET" / "BUDGET SHAPE"
# sections for the reasoning. Measured baseline on this development machine
# (empty .scratch/, warm interpreter cache): ~64ms end-to-end for the
# lightest possible project (interpreter start + imports + a no-op scan).
# HOOK_TIME_BUDGET_SECONDS is added on TOP of that floor for the scan itself,
# so total worst-case end-to-end (light-project floor + full budget spent on
# a heavy tree) lands in the low hundreds of milliseconds this hook is
# required to stay within, regardless of tree size.
#
# 0.3s, not something tighter: a direct 40-trial measurement of a single
# trivial git-uniqueness check (one file, two subprocess calls) on this
# machine ranged 42-80ms with no special load -- but an EARLIER, tighter
# 0.15s budget produced an intermittent (not reliably reproducible) failure
# in this hook's own pytest run, i.e. real, observed system jitter (subprocess
# spawn cost, antivirus on-access scanning of a freshly-spawned git.exe,
# scheduler noise) pushed a call past that budget at least once even for a
# single-file case that should always succeed. A hook that occasionally
# under-verifies a small, ordinary project due to transient host jitter would
# be a worse regression than the one this fix removes, so this budget carries
# a deliberate ~4x margin over the observed p90, not the theoretical minimum
# measured on a quiet machine.
HOOK_TIME_BUDGET_SECONDS = 0.3
# Below this much remaining time, do not even attempt a git subprocess call
# (process-spawn overhead alone makes it unlikely to finish, and a doomed
# attempt only wastes what little budget is left).
MIN_GIT_CALL_SECONDS = 0.03
# Absolute ceiling on any single git subprocess call, independent of the
# whole-hook deadline -- retained as a defensive outer bound; in practice the
# deadline-derived timeout (see `_remaining_seconds`) is almost always the
# smaller, binding value.
GIT_TIMEOUT_SECONDS = 60
# Candidate-count / total-bytes ceiling applied to the git-uniqueness check,
# BEFORE the subprocess is invoked (see "BUDGET SHAPE" above). Sized to
# comfortably finish within a HOOK_TIME_BUDGET_SECONDS-scale remaining
# allowance even on a slow/cold disk: measured `git hash-object` throughput
# via file-based stdin on this machine was ~460 MB/s (RAM-disk fixture, an
# OPTIMISTIC reference point -- real, cold, spinning or network storage will
# be slower), so these ceilings carry a deliberate safety margin under that
# number rather than assuming it.
MAX_GIT_CHECK_FILES = 200
MAX_GIT_CHECK_BYTES = 2 * 1024 * 1024
# How often (in filesystem entries) `_iter_candidate_files` re-checks the
# deadline while iterating ONE directory's listing -- frequent enough that a
# single oversized flat directory cannot itself blow the budget between
# checks, infrequent enough that the `time.monotonic()` calls stay negligible
# next to the per-entry `stat`/`scandir` cost they guard.
_WALK_TIME_CHECK_EVERY = 32

# Presentation thresholds for the injected context line, not filter gates.
SUMMARIZE_THRESHOLD = 15  # above this many candidates, summarize instead of listing
MAX_RECENT_LISTED = 10    # cap on individually-listed files in the summarized window
DIR_SUMMARY_TOP_N = 12    # cap on how many top-level directories the by-dir summary names

# Keep these denylist shapes in sync with JunkDenylist's defaults in
# scripts/maintenance/cleanup.py -- see that module's docstring for the
# rationale behind each one (bias to OVER-warn: keep every list narrow). This
# is a SECONDARY filter applied on top of the primary uniqueness predicate.
JUNK_EXTENSIONS = frozenset({".tmp", ".log", ".out", ".err", ".swp", ".swo"})
JUNK_BASENAMES = frozenset({"thumbs.db", ".ds_store"})
# UNAMBIGUOUS cache directories: pruned at ANY depth -- nothing hand-authored
# ever lives inside one, no matter how deep it sits under .scratch/.
JUNK_UNAMBIGUOUS_CACHE_DIRECTORY_NAMES = frozenset(
    {"__pycache__", "node_modules", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
)
# AMBIGUOUS names: could coincidentally name a hand-authored folder, so pruned
# ONLY when a DIRECT child of .scratch/ (a deeper match is walked normally).
JUNK_DIRECTORY_NAMES = frozenset({".cache", "dist", "build"})
JUNK_PROMPT_CAPTURE_DIRNAMES = frozenset({"codex-prompts", "claude-prompts"})
JUNK_PROMPT_CAPTURE_EXTENSIONS = frozenset(
    {
        ".md",
        ".out",
        ".err",
        ".stdout",
        ".stderr",
        ".stdout.txt",
        ".stderr.txt",
        ".last.txt",
        ".events.txt",
    }
)
SELF_REPORT_BASENAME = ".scratch-valuables-report.json"

_HAS_ISJUNCTION = hasattr(os.path, "isjunction")


def _is_unambiguous_cache_directory(name: str) -> bool:
    return name.casefold() in {d.casefold() for d in JUNK_UNAMBIGUOUS_CACHE_DIRECTORY_NAMES}


def _is_junk_directory(name: str) -> bool:
    return name.casefold() in {d.casefold() for d in JUNK_DIRECTORY_NAMES}


def _is_junk_file(relative_path: Path) -> bool:
    if relative_path.name == SELF_REPORT_BASENAME:
        return True
    name_casefold = relative_path.name.casefold()
    if name_casefold in JUNK_BASENAMES:
        return True
    suffix = relative_path.suffix.casefold()
    if suffix in JUNK_EXTENSIONS:
        return True
    if any(
        name_casefold.endswith(ext.casefold()) for ext in JUNK_PROMPT_CAPTURE_EXTENSIONS
    ) and any(
        part.casefold() in {d.casefold() for d in JUNK_PROMPT_CAPTURE_DIRNAMES}
        for part in relative_path.parts[:-1]
    ):
        return True
    return False


def _is_link_or_reparse(entry: "os.DirEntry") -> bool:
    """True for a symlink OR any other reparse point -- notably an NTFS
    directory JUNCTION, which `entry.is_symlink()` alone does NOT detect
    (confirmed: `os.path.isjunction()` True, `DirEntry.is_symlink()` False
    for the identical entry). Mirrors `_is_link_or_reparse` in
    scripts/maintenance/cleanup.py."""

    try:
        if entry.is_symlink():
            return True
    except OSError:
        return True
    if _HAS_ISJUNCTION:
        try:
            return os.path.isjunction(entry.path)
        except OSError:
            return True
    try:
        import stat as stat_module

        info = entry.stat(follow_symlinks=False)
        reparse_attr = getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        return bool(getattr(info, "st_file_attributes", 0) & reparse_attr)
    except OSError:
        return True


class _WalkBudget:
    """Tracks the wall-clock deadline for `_iter_candidate_files` and records
    whether/how much the walk was cut short. `deadline` is a single
    `time.monotonic()` timestamp computed ONCE at the top of `_scan_valuables`
    -- never re-derived per check -- so repeated small checks cannot drift
    the effective budget longer than `HOOK_TIME_BUDGET_SECONDS`."""

    __slots__ = ("deadline", "truncated", "dirs_remaining", "entries_examined")

    def __init__(self, deadline: float) -> None:
        self.deadline = deadline
        self.truncated = False
        self.dirs_remaining = 0
        self.entries_examined = 0

    def expired(self) -> bool:
        return time.monotonic() >= self.deadline


def _iter_candidate_files(scratch_root: Path, budget: "_WalkBudget"):
    """Read-only walk: skip symlinks/reparse points (incl. junctions).
    Directory pruning is two-tier: an UNAMBIGUOUS cache-directory name is
    pruned at ANY depth (nothing hand-authored ever lives inside one); an
    ambiguous name (`build`/`dist`/`.cache`) is pruned ONLY as a DIRECT child
    of `scratch_root`. Yields `(Path, os.stat_result)` pairs for regular files
    only -- the stat is `entry.stat(follow_symlinks=False)`, captured HERE
    from the same `DirEntry` already produced by this directory's `scandir`
    read, so the caller never re-derives it with a second `Path.stat()` call
    (see the module docstring's "ONE SYSCALL PER FILE, NOT TWO" section).
    Mirrors `_iter_candidate_files` in scripts/maintenance/cleanup.py, EXCEPT
    for the time-boxing below, which has no cleanup.py counterpart (see this
    module's docstring for why).

    TIME-BOXED: checked against `budget` at the top of every directory visit,
    and every `_WALK_TIME_CHECK_EVERY` entries while iterating one directory's
    listing, so a single oversized flat directory cannot itself blow the
    deadline between checks. On expiry the walk stops immediately (`return`,
    ending the generator) and records `budget.truncated = True` plus a rough
    `budget.dirs_remaining` -- directories never visited, including the one
    being processed when time ran out. The walk order itself is UNCHANGED
    from before this fix: which subset gets visited before a given tree's
    deadline is deterministic, just not exhaustive for a large tree.
    """

    stack = [scratch_root]
    while stack:
        if budget.expired():
            budget.truncated = True
            budget.dirs_remaining += len(stack)
            return
        directory = stack.pop()
        is_scratch_root = directory == scratch_root
        try:
            with os.scandir(directory) as entries:
                ordered = sorted(entries, key=lambda entry: entry.name.casefold())
        except OSError:
            continue
        subdirs: list[Path] = []
        for index, entry in enumerate(ordered):
            budget.entries_examined += 1
            if index % _WALK_TIME_CHECK_EVERY == 0 and budget.expired():
                budget.truncated = True
                # everything left in this directory's listing, plus every
                # directory still queued, was never visited.
                budget.dirs_remaining += len(stack) + 1
                return
            try:
                if _is_link_or_reparse(entry):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if _is_unambiguous_cache_directory(entry.name):
                        continue  # machine-cache directory: pruned at ANY depth
                    if is_scratch_root and _is_junk_directory(entry.name):
                        continue  # ambiguous name: direct-child junk subtree only
                    subdirs.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    # follow_symlinks=False matches the is_dir/is_file checks
                    # above and this entry is already known (via
                    # _is_link_or_reparse, above) not to be a symlink or
                    # reparse point -- the flag cannot change which files
                    # match, it just avoids a needless follow on an entry
                    # that was never going to need one.
                    yield Path(entry.path), entry.stat(follow_symlinks=False)
            except OSError:
                continue
        stack.extend(subdirs)


def _find_git_root(start: Path) -> Path | None:
    """Walk up from `start` looking for a `.git` entry. None means "not in a
    git repository" -- callers must fail open, never error."""

    try:
        current = start.resolve(strict=False)
    except OSError:
        return None
    if current.is_file():
        current = current.parent
    while True:
        if (current / ".git").exists():
            return current
        if current.parent == current:
            return None
        current = current.parent


def _run_git_stdin_batch(
    git_root: Path, args: list[str], lines: list[str], timeout_seconds: float
) -> "subprocess.CompletedProcess | None":
    """Read-only git subprocess helper shared by `_hash_object_batch` and
    `_blobs_missing_from_store`. Feeds `lines` via a real temporary FILE for
    stdin -- NEVER `subprocess.run(..., input=...)`. See the module
    docstring's "CLEAN TIMEOUT PATH" section for why: a file-backed `stdin`
    leaves `Popen.stdin` as `None` (confirmed empirically against this
    Python install), so `Popen._communicate` never spawns the background
    writer thread that produced the reported traceback -- there is nothing
    left to kill mid-write, at any timeout.

    The payload file lives under `tempfile.TemporaryDirectory(prefix=...)` --
    outside the target repository entirely, never under `.scratch/` or the
    git object store (this hook's read-only contract is about the TARGET
    repository, not the OS temp area). A just-killed child can hold the
    file's Windows handle open a moment longer than `Popen.kill()` needs to
    return, which can make `TemporaryDirectory.__exit__`'s own cleanup raise
    (`ignore_cleanup_errors=True`, Python 3.10+, would silence that at the
    source -- deliberately NOT used here: this hook is installed into
    arbitrary target repositories with an unknown Python version, and this
    repository already has precedent, in
    scripts/universal-hooks/hooks/check-mcp-momentum.py's `tomllib` handling,
    for never assuming a feature newer than the broadest supported
    interpreter). Instead the `except (OSError, ...)` below already covers
    it: a cleanup-time failure here is always some `OSError` subclass
    (`PermissionError` on Windows), raised while this `with` block is still
    inside the surrounding `try`, so this hook never raises on that race
    either way, on any Python version.

    Returns `None` on any failure (including a timeout), so every caller
    fails open uniformly, matching the pre-existing contract.
    """

    if not lines:
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
    payload = "\n".join(lines) + "\n"
    encoding = locale.getpreferredencoding(False)
    try:
        with tempfile.TemporaryDirectory(prefix="scratch-valuables-") as tmp_dir:
            stdin_path = Path(tmp_dir) / "paths.txt"
            stdin_path.write_text(payload, encoding=encoding)
            with open(stdin_path, "r", encoding=encoding) as stdin_file:
                return subprocess.run(
                    ["git", "-C", str(git_root), *args],
                    stdin=stdin_file,
                    capture_output=True,
                    text=True,
                    timeout=min(timeout_seconds, GIT_TIMEOUT_SECONDS),
                )
    except (OSError, subprocess.SubprocessError):
        return None


def _hash_object_batch(git_root: Path, paths: list[Path], timeout_seconds: float) -> dict | None:
    """Read-only: `git hash-object --stdin-paths` (NEVER `-w`). Returns
    `{path: sha}` or `None` on any failure so the caller fails open."""

    if not paths:
        return {}
    proc = _run_git_stdin_batch(
        git_root, ["hash-object", "--stdin-paths"], [str(p) for p in paths], timeout_seconds
    )
    if proc is None or proc.returncode != 0:
        return None
    shas = proc.stdout.splitlines()
    if len(shas) != len(paths):
        return None
    result: dict[Path, str] = {}
    for path, sha in zip(paths, shas):
        sha = sha.strip()
        if not sha:
            return None
        result[path] = sha
    return result


def _blobs_missing_from_store(git_root: Path, shas: set, timeout_seconds: float) -> set | None:
    """Read-only: `git cat-file --batch-check`. Returns the SUBSET of `shas`
    NOT present in the object database, or `None` on any failure."""

    if not shas:
        return set()
    proc = _run_git_stdin_batch(
        git_root, ["cat-file", "--batch-check"], sorted(shas), timeout_seconds
    )
    if proc is None or proc.returncode != 0:
        return None
    missing: set = set()
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "missing":
            missing.add(parts[0])
    return missing


def _remaining_seconds(deadline: float) -> float | None:
    """Time left until `deadline` (a `time.monotonic()` timestamp), or
    `None` if less than `MIN_GIT_CALL_SECONDS` remains -- not worth spawning
    a subprocess for. Re-derived before EACH git subprocess call against the
    SAME overall deadline, so two sequential calls (`hash-object` then
    `cat-file --batch-check`) cannot each claim a fresh allowance and, in
    aggregate, blow past the budget."""

    remaining = deadline - time.monotonic()
    if remaining < MIN_GIT_CALL_SECONDS:
        return None
    return remaining


def _git_unique_paths(git_root: Path, paths: list[Path], deadline: float):
    timeout = _remaining_seconds(deadline)
    if timeout is None:
        return None
    shas = _hash_object_batch(git_root, paths, timeout)
    if shas is None:
        return None
    timeout = _remaining_seconds(deadline)
    if timeout is None:
        return None
    missing = _blobs_missing_from_store(git_root, set(shas.values()), timeout)
    if missing is None:
        return None
    return {path for path, sha in shas.items() if sha in missing}


class ScanReport:
    """Disclosure record for one `_scan_valuables` run. Filled in whether or
    not the caller reads it (cheap bookkeeping only -- no extra filesystem or
    subprocess calls), so `main()` can decide, AFTER the scan, whether the
    byte-silent contract still holds. See the module docstring's "HONESTY
    UNDER BUDGET" section: a hook that quietly examined a fraction of the
    tree and reported normally would be worse than the hang it replaces."""

    __slots__ = (
        "walk_truncated",
        "dirs_remaining",
        "entries_examined",
        "candidates_found",
        "candidates_git_verified",
        "candidates_budget_age_gated",
    )

    def __init__(self) -> None:
        self.walk_truncated = False
        self.dirs_remaining = 0
        self.entries_examined = 0
        self.candidates_found = 0
        self.candidates_git_verified = 0
        # Count of candidates that, despite git being AVAILABLE, were graded
        # by the (lower-precision) age gate instead of git-uniqueness this
        # run -- because the count/byte ceiling excluded them up front, or
        # because the git-uniqueness check did not complete within the
        # remaining time budget. Deliberately NOT incremented for the
        # pre-existing "no git repository at all" fallback (that path is not
        # new and stays silent, per the module docstring's PREDICATE
        # section) -- only these two NEW budget mechanisms count here.
        self.candidates_budget_age_gated = 0

    @property
    def budget_limited(self) -> bool:
        """True when this run's result is INCOMPLETE for a budget reason."""
        return self.walk_truncated or self.candidates_budget_age_gated > 0


def _age_days(info: "os.stat_result", now: float) -> float:
    return max(0.0, (now - info.st_mtime) / SECONDS_PER_DAY)


def _entry(relative: Path, info: "os.stat_result", now: float) -> dict:
    return {"path": relative.as_posix(), "age_days": round(_age_days(info, now), 1), "size": info.st_size}


def _age_gate(candidates: list, fallback_age_days: float, now: float) -> list[dict]:
    """The age-gated fallback: a candidate is flagged only if it has lingered
    past `fallback_age_days`. Shared by all three callers that need it (no
    git repository at all; the git-uniqueness check did not complete in
    time; candidates excluded up front by the count/byte ceiling) so the
    threshold logic has exactly one owner."""

    out: list[dict] = []
    for _path, relative, info in candidates:
        if _age_days(info, now) <= fallback_age_days:
            continue
        out.append(_entry(relative, info, now))
    return out


def _scan_valuables(
    scratch_root: Path,
    *,
    fallback_age_days: float = FALLBACK_AGE_THRESHOLD_DAYS,
    time_budget_seconds: float = HOOK_TIME_BUDGET_SECONDS,
    deadline: float | None = None,
    report: "ScanReport | None" = None,
) -> list[dict]:
    """Read-only scan: PRIMARY predicate is git-content-uniqueness (see the
    module docstring); FAILS OPEN to the age-gated fallback when git is
    unavailable, when the git-uniqueness check does not complete within this
    run's time/size budget, or for candidates the budget excluded outright.
    Non-junk and non-empty are SECONDARY filters applied either way. The
    WHOLE scan -- walk included -- is bounded by `time_budget_seconds`
    (module docstring: "WHOLE-HOOK TIME BUDGET"); `report`, if given, is
    filled with what happened for the caller to disclose. Returns candidates
    sorted newest-modified first. Never mutates anything -- see the module
    docstring."""

    if report is None:
        report = ScanReport()
    if not scratch_root.is_dir():
        return []
    now = datetime.now(timezone.utc).timestamp()
    if deadline is None:
        deadline = time.monotonic() + time_budget_seconds
    budget = _WalkBudget(deadline)

    candidates: list[tuple[Path, Path, "os.stat_result"]] = []
    for path, info in _iter_candidate_files(scratch_root, budget):
        if info.st_size == 0:
            continue
        try:
            relative = path.relative_to(scratch_root)
        except ValueError:
            continue
        if _is_junk_file(relative):
            continue
        candidates.append((path, relative, info))

    report.walk_truncated = budget.truncated
    report.dirs_remaining = budget.dirs_remaining
    report.entries_examined = budget.entries_examined
    report.candidates_found = len(candidates)

    git_root = _find_git_root(scratch_root) if shutil.which("git") else None

    if git_root is None:
        # PRE-EXISTING fallback: no git repository / no git executable for
        # this scan at all -- unchanged, and deliberately not counted toward
        # `report.candidates_budget_age_gated` (see that field's docstring).
        found = _age_gate(candidates, fallback_age_days, now)
        found.sort(key=lambda item: (item["age_days"], item["path"].casefold()))
        return found

    # Cheapest-first (ascending size) so the byte ceiling verifies the MOST
    # candidates per byte of git-call cost -- see "BUDGET SHAPE" in the
    # module docstring for why size, not age, is the ordering key here.
    ordered = sorted(candidates, key=lambda c: c[2].st_size)
    to_check: list[tuple[Path, Path, "os.stat_result"]] = []
    skipped_by_ceiling: list[tuple[Path, Path, "os.stat_result"]] = []
    running_bytes = 0
    for candidate in ordered:
        size = candidate[2].st_size
        if len(to_check) < MAX_GIT_CHECK_FILES and running_bytes + size <= MAX_GIT_CHECK_BYTES:
            to_check.append(candidate)
            running_bytes += size
        else:
            skipped_by_ceiling.append(candidate)

    unique_paths = (
        _git_unique_paths(git_root, [c[0] for c in to_check], deadline) if to_check else {}
    )

    found: list[dict] = []
    if unique_paths is not None:
        for path, relative, info in to_check:
            if path in unique_paths:
                found.append(_entry(relative, info, now))
        report.candidates_git_verified = len(to_check)
        found.extend(_age_gate(skipped_by_ceiling, fallback_age_days, now))
        report.candidates_budget_age_gated = len(skipped_by_ceiling)
    else:
        # The git-uniqueness check itself did not complete this run (a real
        # git failure, or -- overwhelmingly likely given how tight this
        # hook's time budget now is -- ran out of remaining time). Age-gate
        # EVERY candidate, matching the pre-existing "any git call fails"
        # fallback contract, but this time it IS disclosed (unlike that
        # pre-existing silent contract): git was available here, so
        # incomplete coverage is this run's own budget decision, not an
        # environment fact the operator already accepts.
        found = _age_gate(candidates, fallback_age_days, now)
        report.candidates_budget_age_gated = len(candidates)

    found.sort(key=lambda item: (item["age_days"], item["path"].casefold()))
    return found


class RepositoryRootResolution(NamedTuple):
    status: str
    root: Path | None
    candidate_count: int = 0


def _path_is_link_or_reparse(path: Path) -> bool:
    """Inspect one path component without following it; uncertainty is unsafe."""

    try:
        info = os.lstat(path)
    except OSError:
        return True
    import stat as stat_module

    if stat_module.S_ISLNK(info.st_mode):
        return True
    if _HAS_ISJUNCTION:
        try:
            if os.path.isjunction(path):
                return True
        except OSError:
            return True
    reparse_attr = getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(info, "st_file_attributes", 0) & reparse_attr)


def _path_chain_is_safe(path: Path, deadline: float) -> bool | None:
    """Return True/False, or None when the shared deadline expires."""

    current = path.absolute()
    while True:
        if time.monotonic() >= deadline:
            return None
        if _path_is_link_or_reparse(current):
            return False
        if current.parent == current:
            return True
        current = current.parent


def _git_root_state(path: Path) -> str:
    """Return repo, none, or unsafe for one direct repository marker."""

    marker = path / ".git"
    try:
        info = os.lstat(marker)
    except FileNotFoundError:
        return "none"
    except OSError:
        return "unsafe"
    if _path_is_link_or_reparse(marker):
        return "unsafe"
    import stat as stat_module

    return "repo" if (stat_module.S_ISDIR(info.st_mode) or stat_module.S_ISREG(info.st_mode)) else "unsafe"


def resolve_repository_root(envelope: dict, deadline: float) -> RepositoryRootResolution:
    """Resolve exactly one containing or direct-child Git repository, read-only.

    The current directory wins when it is itself a repository. Otherwise,
    immediate child repositories take precedence over a containing ancestor,
    and their enumeration must finish within the SAME deadline later consumed
    by the valuables scan. Links, junctions, and other reparse points are never
    followed.
    """

    cwd_value = envelope.get("cwd") if isinstance(envelope, dict) else None
    candidate: Path | None = None
    if isinstance(cwd_value, str) and cwd_value:
        supplied = Path(cwd_value)
        try:
            if supplied.is_dir():
                candidate = supplied
        except OSError:
            candidate = None
    if candidate is None:
        candidate = Path.cwd()

    safe = _path_chain_is_safe(candidate, deadline)
    if safe is None:
        return RepositoryRootResolution("budget-limited", None)
    if not safe:
        return RepositoryRootResolution("unsafe", None)

    current = candidate.absolute()
    marker_state = _git_root_state(current)
    if marker_state == "repo":
        return RepositoryRootResolution("selected", current, 1)
    if marker_state == "unsafe":
        return RepositoryRootResolution("unsafe", None)

    candidates: list[Path] = []
    unsafe_child = False
    try:
        with os.scandir(candidate) as entries:
            for entry in entries:
                if time.monotonic() >= deadline:
                    return RepositoryRootResolution(
                        "budget-limited", None, len(candidates)
                    )
                try:
                    if _is_link_or_reparse(entry):
                        continue
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                except OSError:
                    continue
                child = Path(entry.path).absolute()
                state = _git_root_state(child)
                if state == "unsafe":
                    unsafe_child = True
                    continue
                if state == "repo":
                    candidates.append(child)
                    if len(candidates) == 2:
                        return RepositoryRootResolution("ambiguous", None, 2)
    except OSError:
        return RepositoryRootResolution("unsafe", None)

    if unsafe_child:
        return RepositoryRootResolution("unsafe", None, len(candidates))
    if len(candidates) == 1:
        return RepositoryRootResolution("selected", candidates[0], 1)

    while current.parent != current:
        if time.monotonic() >= deadline:
            return RepositoryRootResolution("budget-limited", None)
        current = current.parent
        marker_state = _git_root_state(current)
        if marker_state == "repo":
            return RepositoryRootResolution("selected", current, 1)
        if marker_state == "unsafe":
            return RepositoryRootResolution("unsafe", None)
    return RepositoryRootResolution("none", None)


def _root_resolution_message(result: RepositoryRootResolution) -> str:
    identifiers = {
        "none": "SCRATCH-ROOT-NOT-FOUND",
        "ambiguous": "SCRATCH-ROOT-AMBIGUOUS",
        "unsafe": "SCRATCH-ROOT-UNSAFE",
        "budget-limited": "SCRATCH-ROOT-BUDGET-LIMITED",
    }
    identifier = identifiers.get(result.status, "SCRATCH-ROOT-UNSAFE")
    suffix = (
        f" candidates={result.candidate_count}"
        if result.status == "ambiguous"
        else ""
    )
    return (
        f"[scratch watchdog] {identifier}{suffix}: no scratch tree was scanned; "
        "start inside one repository or its unambiguous direct parent."
    )


def _top_level_dir(relative_posix: str) -> str:
    parts = relative_posix.split("/", 1)
    return parts[0] if len(parts) > 1 else f"({SCRATCH_DIRNAME} root)"


def _format_entry(item: dict) -> str:
    return f"{item['path']} (age={item['age_days']}d, size={item['size']}B)"


def _build_core_message(valuables: list[dict]) -> str:
    """The presentation layer, built ON TOP of the (already git-unique, or
    age-gated-fallback) candidate list -- see the module docstring. `main()`
    calls this THROUGH `_build_message`, which appends the budget-disclosure
    clause; existing callers/tests that pass only `valuables` still get the
    identical text this function alone would have produced.

    LONGEST-LINGERING LEADS. The operator's stated risk is data that has
    "khranilis dolgo" (lingered LONG), not the current session's own recent
    churn -- newest-modified-first anti-selects for exactly the files the
    operator needs surfaced. Below `SUMMARIZE_THRESHOLD`, every candidate is
    shown, oldest (longest-lingering) first. Above it, the message
    summarizes by top-level `.scratch/` subdirectory (capped to
    `DIR_SUMMARY_TOP_N` directories, so the summary itself cannot grow
    unbounded) and then lists two small labeled windows: the
    longest-lingering candidates first, then the most-recently-modified
    ones -- instead of a flat dump nobody reads."""

    count = len(valuables)
    if count == 0:
        return (
            f"[scratch watchdog] no valuable-looking files confirmed under {SCRATCH_DIRNAME}/ "
            f"in this run"
        )
    base = (
        f"[scratch watchdog] {count} valuable-looking file(s) found under {SCRATCH_DIRNAME}/ "
        f"whose content is not already recoverable from this repository's git history"
    )
    tail = (
        f" -- rescue them before they get overwritten (this hook is read-only: it never "
        f"deletes, moves, or touches them itself)."
    )

    if count <= SUMMARIZE_THRESHOLD:
        oldest_first = list(reversed(valuables))  # valuables is newest-first; reverse to lead oldest
        listed = "; ".join(_format_entry(item) for item in oldest_first)
        return f"{base}, longest-lingering first:{tail} {listed}"

    by_dir: dict[str, int] = {}
    for item in valuables:
        top = _top_level_dir(item["path"])
        by_dir[top] = by_dir.get(top, 0) + 1
    sorted_dirs = sorted(by_dir.items(), key=lambda kv: (-kv[1], kv[0].casefold()))
    shown_dirs = sorted_dirs[:DIR_SUMMARY_TOP_N]
    remaining_dirs = sorted_dirs[DIR_SUMMARY_TOP_N:]
    dir_summary = "; ".join(f"{name}: {n} file(s)" for name, n in shown_dirs)
    if remaining_dirs:
        remaining_dir_count = len(remaining_dirs)
        remaining_file_count = sum(n for _name, n in remaining_dirs)
        noun = "directory" if remaining_dir_count == 1 else "directories"
        dir_summary += f"; ... and {remaining_dir_count} more {noun} ({remaining_file_count} file(s))"

    half_window = MAX_RECENT_LISTED // 2
    # `valuables` is newest-first (lowest age_days first): the tail holds the
    # oldest entries, reversed here so the single longest-lingering file is
    # first within its own group; the head holds the newest as-is.
    longest_lingering = list(reversed(valuables[-half_window:]))
    newest_modified = valuables[:half_window]
    longest_listed = "; ".join(_format_entry(item) for item in longest_lingering)
    newest_listed = "; ".join(_format_entry(item) for item in newest_modified)
    return (
        f"{base} -- too many to list individually, summarized by top-level {SCRATCH_DIRNAME}/ "
        f"subdirectory: {dir_summary}. Longest-lingering (highest accidental-overwrite risk), "
        f"up to {half_window}: {longest_listed}. Most recently modified, up to {half_window}: "
        f"{newest_listed}.{tail}"
    )


def _disclosure_clause(report: "ScanReport | None") -> str:
    """The honesty requirement (module docstring, "HONESTY UNDER BUDGET"):
    state plainly when this run's coverage is partial because of the
    wall-clock/size budget -- never let a fast, partial scan read the same
    as a complete one. Empty string when `report` is None (existing direct
    callers of `_build_message(valuables)` are unaffected) or when neither
    NEW budget mechanism fired -- the pre-existing "no git repository"
    fallback stays silent, unchanged."""

    if report is None or not report.budget_limited:
        return ""
    parts: list[str] = []
    if report.walk_truncated:
        dirs = report.dirs_remaining
        dir_noun = "subdirectory" if dirs == 1 else "subdirectories"
        entries = report.entries_examined
        entry_noun = "entry" if entries == 1 else "entries"
        parts.append(
            f"[scratch watchdog budget] this scan is time-boxed to "
            f"{HOOK_TIME_BUDGET_SECONDS * 1000:.0f}ms and stopped early: it examined "
            f"{entries} filesystem {entry_noun} before the limit, leaving "
            f"roughly {dirs} {dir_noun} of {SCRATCH_DIRNAME}/ unvisited -- this run does not "
            f"cover the whole tree."
        )
    if report.candidates_budget_age_gated:
        mb = MAX_GIT_CHECK_BYTES / (1024 * 1024)
        parts.append(
            f"[scratch watchdog budget] {report.candidates_budget_age_gated} candidate file(s) "
            f"exceeded this run's git-verification budget (max {MAX_GIT_CHECK_FILES} files / "
            f"{mb:.0f}MB per run) and were graded by file age instead of git-content-uniqueness "
            f"-- treat those with lower confidence than the rest."
        )
    return " ".join(parts)


def _build_message(valuables: list[dict], report: "ScanReport | None" = None) -> str:
    core = _build_core_message(valuables)
    disclosure = _disclosure_clause(report)
    return f"{core} {disclosure}" if disclosure else core


def main() -> int:
    try:
        raw_envelope = read_stdin_utf8()
        try:
            json.loads(raw_envelope) if raw_envelope.strip() else {}
        except (TypeError, ValueError):
            return 0
        envelope = parse_envelope(raw_envelope)
        if not isinstance(envelope, dict):
            envelope = {}
        if envelope.get("agent_id"):
            return 0  # this reminder belongs to the top-level session, not a dispatched subagent

        deadline = time.monotonic() + HOOK_TIME_BUDGET_SECONDS
        resolution = resolve_repository_root(envelope, deadline)
        if resolution.status != "selected" or resolution.root is None:
            payload = {
                "hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": _root_resolution_message(resolution),
                }
            }
            print(json.dumps(payload, ensure_ascii=True))
            return 0

        root = resolution.root
        report = ScanReport()
        valuables = _scan_valuables(
            root / SCRATCH_DIRNAME,
            deadline=deadline,
            report=report,
        )
        if not valuables and not report.budget_limited:
            return 0  # byte-silent: nothing lingering, and this run covered the whole tree

        message = _build_message(valuables, report)
        payload = {
            "hookSpecificOutput": {
                "hookEventName": "SessionStart",
                "additionalContext": message,
            }
        }
        print(json.dumps(payload, ensure_ascii=True))
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
