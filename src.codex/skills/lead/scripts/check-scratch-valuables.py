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
the other -- each file's docstring points at its twin.

CONTRACT: READ-ONLY. This hook must NEVER write, move, delete, rename, or
create anything under the target repository's `.scratch/` tree, or anywhere
in its git object store, on any platform, under any code path. Its only
filesystem/process calls are `os.scandir`, `DirEntry.is_symlink` / `is_dir` /
`is_file` / `.stat`, `os.path.isjunction`, `Path.stat`, and two READ-ONLY git
subprocesses (`git hash-object` WITHOUT `-w`, `git cat-file --batch-check`).

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

PRESENTATION. Emits a `hookSpecificOutput` context block ONLY when at least
one candidate is found; otherwise BYTE-SILENT (matching `agents-mode-reminder`
where the presence of the block itself is the signal). When the candidate
count exceeds `SUMMARIZE_THRESHOLD`, the message summarizes by top-level
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
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from hook_common import parse_envelope, read_stdin_utf8
except Exception:  # pragma: no cover - fail open when the shared helper is absent
    def read_stdin_utf8() -> str:  # type: ignore[misc]
        return ""

    def parse_envelope(stdin_text: str) -> dict:  # type: ignore[misc]
        return {}


SCRATCH_DIRNAME = ".scratch"
# Fallback-only (used when git is unavailable for this scan). Keep in sync
# with VALUABLE_AGE_THRESHOLD_DAYS in scripts/maintenance/cleanup.py.
FALLBACK_AGE_THRESHOLD_DAYS = 7
SECONDS_PER_DAY = 24 * 60 * 60
GIT_TIMEOUT_SECONDS = 60

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


def _iter_candidate_files(scratch_root: Path):
    """Read-only walk: skip symlinks/reparse points (incl. junctions).
    Directory pruning is two-tier: an UNAMBIGUOUS cache-directory name is
    pruned at ANY depth (nothing hand-authored ever lives inside one); an
    ambiguous name (`build`/`dist`/`.cache`) is pruned ONLY as a DIRECT child
    of `scratch_root`. Yields regular files only. Mirrors
    `_iter_candidate_files` in scripts/maintenance/cleanup.py."""

    stack = [scratch_root]
    while stack:
        directory = stack.pop()
        is_scratch_root = directory == scratch_root
        try:
            with os.scandir(directory) as entries:
                ordered = sorted(entries, key=lambda entry: entry.name.casefold())
        except OSError:
            continue
        subdirs: list[Path] = []
        for entry in ordered:
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
                    yield Path(entry.path)
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


def _hash_object_batch(git_root: Path, paths: list[Path]) -> dict | None:
    """Read-only: `git hash-object --stdin-paths` (NEVER `-w`). Returns
    `{path: sha}` or `None` on any failure so the caller fails open."""

    if not paths:
        return {}
    stdin_payload = "\n".join(str(p) for p in paths) + "\n"
    try:
        proc = subprocess.run(
            ["git", "-C", str(git_root), "hash-object", "--stdin-paths"],
            input=stdin_payload,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
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


def _blobs_missing_from_store(git_root: Path, shas: set) -> set | None:
    """Read-only: `git cat-file --batch-check`. Returns the SUBSET of `shas`
    NOT present in the object database, or `None` on any failure."""

    if not shas:
        return set()
    stdin_payload = "\n".join(sorted(shas)) + "\n"
    try:
        proc = subprocess.run(
            ["git", "-C", str(git_root), "cat-file", "--batch-check"],
            input=stdin_payload,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    missing: set = set()
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "missing":
            missing.add(parts[0])
    return missing


def _git_unique_paths(git_root: Path, paths: list[Path]):
    shas = _hash_object_batch(git_root, paths)
    if shas is None:
        return None
    missing = _blobs_missing_from_store(git_root, set(shas.values()))
    if missing is None:
        return None
    return {path for path, sha in shas.items() if sha in missing}


def _scan_valuables(scratch_root: Path, *, fallback_age_days: float = FALLBACK_AGE_THRESHOLD_DAYS) -> list[dict]:
    """Read-only scan: PRIMARY predicate is git-content-uniqueness (see the
    module docstring); FAILS OPEN to the age-gated fallback when git is
    unavailable or any git call fails. Non-junk and non-empty are SECONDARY
    filters applied either way. Returns candidates sorted newest-modified
    first. Never mutates anything -- see the module docstring."""

    if not scratch_root.is_dir():
        return []
    now = datetime.now(timezone.utc).timestamp()

    candidates: list[tuple[Path, Path, os.stat_result]] = []
    for path in _iter_candidate_files(scratch_root):
        try:
            info = path.stat()
        except OSError:
            continue
        if info.st_size == 0:
            continue
        try:
            relative = path.relative_to(scratch_root)
        except ValueError:
            continue
        if _is_junk_file(relative):
            continue
        candidates.append((path, relative, info))

    git_root = _find_git_root(scratch_root) if shutil.which("git") else None
    unique_paths = _git_unique_paths(git_root, [c[0] for c in candidates]) if git_root is not None else None

    found: list[dict] = []
    if unique_paths is not None:
        for path, relative, info in candidates:
            if path not in unique_paths:
                continue
            age = max(0.0, (now - info.st_mtime) / SECONDS_PER_DAY)
            found.append({"path": relative.as_posix(), "age_days": round(age, 1), "size": info.st_size})
    else:
        for path, relative, info in candidates:
            age = max(0.0, (now - info.st_mtime) / SECONDS_PER_DAY)
            if age <= fallback_age_days:
                continue
            found.append({"path": relative.as_posix(), "age_days": round(age, 1), "size": info.st_size})

    found.sort(key=lambda item: (item["age_days"], item["path"].casefold()))
    return found


def _resolve_root(envelope: dict) -> Path:
    cwd_value = envelope.get("cwd") if isinstance(envelope, dict) else None
    if isinstance(cwd_value, str) and cwd_value:
        candidate = Path(cwd_value)
        if candidate.is_dir():
            return candidate
    return Path.cwd()


def _top_level_dir(relative_posix: str) -> str:
    parts = relative_posix.split("/", 1)
    return parts[0] if len(parts) > 1 else f"({SCRATCH_DIRNAME} root)"


def _format_entry(item: dict) -> str:
    return f"{item['path']} (age={item['age_days']}d, size={item['size']}B)"


def _build_message(valuables: list[dict]) -> str:
    """The presentation layer, built ON TOP of the (already git-unique)
    candidate list -- see the module docstring. `valuables` arrives sorted
    newest-modified first (that is `_scan_valuables`'s RETURN CONTRACT,
    useful to programmatic callers); this function does not mutate that
    order, it only decides what to SHOW and in what order to show it.

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


def main() -> int:
    try:
        envelope = parse_envelope(read_stdin_utf8())
        if not isinstance(envelope, dict):
            envelope = {}
        if envelope.get("agent_id"):
            return 0  # this reminder belongs to the top-level session, not a dispatched subagent

        root = _resolve_root(envelope)
        valuables = _scan_valuables(root / SCRATCH_DIRNAME)
        if not valuables:
            return 0  # byte-silent: nothing lingering, nothing to say

        message = _build_message(valuables)
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
