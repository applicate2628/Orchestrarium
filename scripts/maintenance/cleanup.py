#!/usr/bin/env python3
"""Repository-local `.scratch/` valuables watchdog -- READ-ONLY.

REFRAME (2026-07-17). The operator reset this tool's purpose and this rewrite
DELETES the entire prior mutation engine (sweep / quarantine / restore / purge /
`.hold` / manifest / digest machinery, v1-v20 of the janitor):

    "mne ne nuzhen skript dlya udaleniya scratch, ya mogu eto sdelat sam v
    lyuboy moment. mne nado chtoby v scratch sledili chtoby ne khranilis dolgo
    vazhnye poleznye dannye, kotorye ya mogu sluchayno zatert." + "za etim
    dolzhen sledit agent sam" (no user-run command; the agent watches).

    English: "I don't need a script to delete scratch -- I can do that myself
    any time. I need `.scratch/` WATCHED so that valuable data doesn't linger
    there long enough for me to accidentally overwrite it." + "the AGENT must
    watch this on its own."

See `work-items/active/2026-07-16-cleanup-routine/design-watchdog-reframe.md`
for the locked design this rewrite implements. Do NOT resurrect any
move/delete/quarantine/hold/restore path here -- that surface is exactly where
every prior data-loss round in this file's history lived.

PREDICATE REDESIGN (2026-07-17, adversarial-review follow-up). The first cut
of this watchdog gated purely on age (>7 days). Live-tree evidence killed that
gate: a random sample of flagged files on this repository's own `.scratch/`
showed 58 of 59 resolvable files were BYTE-IDENTICAL to a git blob already in
this repository's object history -- i.e. recoverable, not actually at risk of
loss, and the detector's real-world precision on age alone was near zero
(8631 flagged, almost all noise). The PRIMARY predicate is now git-content-
uniqueness: a file is a candidate only if its exact bytes do not already exist
as a blob anywhere in the local repository's object database (any commit, any
branch -- content git can already recover, regardless of whether this
particular copy was ever tracked). Age is DEMOTED from a gate to a severity /
sort key (newest-modified first). The junk denylist and the non-empty filter
remain SECONDARY filters on top of uniqueness. When `.scratch/` is not inside
a git repository, git is unavailable, or any git call fails, this fails OPEN
to the original age-gated behavior (see `scan_valuables`'s docstring) rather
than silently returning nothing.

The whole module is two functions:

  * `scan_valuables()` -- pure, read-only. Walks a `.scratch/` tree and
    returns every candidate valuable file (git-unique when git is available,
    else age-gated). It NEVER writes, moves, deletes, renames, or creates
    anything, on any platform, under any code path -- the filesystem/process
    calls anywhere in its call graph are `os.scandir`, `DirEntry.is_symlink` /
    `is_dir` / `is_file` / `.stat`, `os.path.isjunction`, `Path.stat`, and two
    READ-ONLY git subprocesses (`git hash-object` WITHOUT `-w`, and
    `git cat-file --batch-check`) -- neither writes to the object database.
  * `main()` -- a thin CLI that prints the scan as a human report (or JSON),
    for a developer to run by hand from this repository, purely for
    debugging. It performs no mutation either.

WHY THIS STAYS REPOSITORY-LOCAL, AND WHERE THE "AGENT WATCHES AUTOMATICALLY"
PIECE ACTUALLY LIVES. The mechanism the operator asked for -- the agent
watching without being told to run anything -- is the SessionStart hook at
`scripts/universal-hooks/scripts/check-scratch-valuables.py`. That hook is
installed into arbitrary target repositories by the pack installer (the same
way as `mcp-usage-reminder`), so it cannot import this module: this file
stays repository-local to Orchestrarium's own working tree (consistent with
the prior engine, which was never installed into provider packs either). The
hook therefore carries its own small, deliberately self-contained mirror of
the scan below, INCLUDING the git-uniqueness predicate. If the algorithm
changes here, update both -- each file's docstring points at the other.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat as stat_module
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence


SCRATCH_DIRNAME = ".scratch"

# Fallback-only now (see `scan_valuables`): used purely when git is
# unavailable for this scan. Overridable per call via
# `scan_valuables(..., fallback_age_days=...)` or `--fallback-age-days` on
# the CLI.
VALUABLE_AGE_THRESHOLD_DAYS = 7

SECONDS_PER_DAY = 24 * 60 * 60

# `os.path.isjunction` is 3.12+; on older interpreters fall back to the raw
# FILE_ATTRIBUTE_REPARSE_POINT stat bit (see `_is_link_or_reparse`).
_HAS_ISJUNCTION = hasattr(os.path, "isjunction")
_REPARSE_POINT_ATTR = getattr(stat_module, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

_GIT_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class JunkDenylist:
    """The watchdog's SECONDARY junk classification, applied on top of the
    primary git-uniqueness predicate (see the module docstring): a
    unique-but-junk file (a timestamped log, a capture artifact) is still
    excluded. Bias to OVER-warn (per the locked design) -- every list here
    stays NARROW and evidence-based (only patterns actually
    routine/transient in this repository's own `.scratch/` usage). A
    denylist entry is a decision to NEVER surface a match, so an over-broad
    entry silently hides real data from the operator; when in doubt, leave a
    pattern OUT and let the file be flagged.

    extensions:
        File suffixes (casefold, with the leading dot) that are always junk,
        wherever they sit -- routine tool stdout/stderr/log/temp churn plus
        common editor swap files (`.swp`/`.swo`). DELIBERATE SPEC CHOICE,
        stated here rather than left implicit: `.log`/`.out`/`.err` are a
        BLANKET extension rule (any file with one of these suffixes is junk
        regardless of location), which trades away some of the "bias to
        over-warn" principle -- a hand-authored `.log` would be silently
        excluded. That tradeoff is the locked design's own choice (see
        `design-watchdog-reframe.md`), not an oversight; narrowing it to a
        location-scoped rule is a possible future revision, not this one.
    junk_basenames:
        Exact file basenames (casefold) that are always junk wherever they
        sit -- OS/editor litter that carries no user-authored content
        (`Thumbs.db`, `.DS_Store`).
    unambiguous_cache_directory_names:
        Directory basenames (casefold) whose entire subtree is junk and is
        not even walked, pruned at ANY depth -- these names are never
        ambiguous with a hand-authored folder (nothing hand-authored ever
        lives inside `__pycache__`, `node_modules`, `.pytest_cache`,
        `.mypy_cache`, or `.ruff_cache`, no matter how deep they sit under
        `.scratch/`). A prior direct-child-only version of this rule leaked
        hundreds of nested `__pycache__/*.pyc` files from review-snapshot
        subtrees straight into the flagged set -- machine artifacts, not
        data to rescue.
    directory_names:
        Directory basenames (casefold) whose entire subtree is junk and is
        not even walked, but ONLY when a DIRECT child of `.scratch/` --
        `build`/`dist`/`.cache` COULD coincidentally name a hand-authored
        folder (e.g. `.scratch/plans/build/notes.md`, where `build` is
        nested two levels down), so a deeper match is walked normally and
        NOT pruned. This is the ambiguous half of directory pruning; see
        `unambiguous_cache_directory_names` for the any-depth half.
    prompt_capture_dirnames / prompt_capture_extensions:
        A narrower rule for one specific known-transient shape: an
        external-CLI dispatch's captured prompt plus its stdout/stderr,
        conventionally written as a `<stem>.md` / `<stem>.out` / `<stem>.err`
        triple (or an older `<stem>.stdout` / `.stderr` / `.stdout.txt` /
        `.stderr.txt` / `.last.txt` / `.events.txt` capture shape also seen
        in this repository's history) under a directory literally named
        `codex-prompts` or `claude-prompts`. Deliberately NOT a blanket
        "`.md` is junk" rule -- a `.md` note anywhere else in `.scratch/` is
        exactly the kind of hand-authored data this watchdog exists to
        protect. `prompt_capture_extensions` entries are matched by
        `str.endswith`, not `Path.suffix`, so the two-part suffixes above
        (`.stdout.txt` etc.) match correctly.
    self_report_basename:
        This watchdog writes nothing today (see the module docstring), but a
        future report persisted under `.scratch/` must never flag itself as
        a rescue candidate. Reserved now so that addition never needs a
        second denylist edit.
    """

    extensions: frozenset[str] = field(
        default_factory=lambda: frozenset({".tmp", ".log", ".out", ".err", ".swp", ".swo"})
    )
    junk_basenames: frozenset[str] = field(
        default_factory=lambda: frozenset({"thumbs.db", ".ds_store"})
    )
    unambiguous_cache_directory_names: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {
                "__pycache__",
                "node_modules",
                ".pytest_cache",
                ".mypy_cache",
                ".ruff_cache",
            }
        )
    )
    directory_names: frozenset[str] = field(
        default_factory=lambda: frozenset({".cache", "dist", "build"})
    )
    prompt_capture_dirnames: frozenset[str] = field(
        default_factory=lambda: frozenset({"codex-prompts", "claude-prompts"})
    )
    prompt_capture_extensions: frozenset[str] = field(
        default_factory=lambda: frozenset(
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
    )
    self_report_basename: str = ".scratch-valuables-report.json"

    def is_unambiguous_cache_directory(self, name: str) -> bool:
        return name.casefold() in {d.casefold() for d in self.unambiguous_cache_directory_names}

    def is_junk_directory(self, name: str) -> bool:
        return name.casefold() in {d.casefold() for d in self.directory_names}

    def is_junk_file(self, relative_path: Path) -> bool:
        if relative_path.name == self.self_report_basename:
            return True
        name_casefold = relative_path.name.casefold()
        if name_casefold in self.junk_basenames:
            return True
        suffix = relative_path.suffix.casefold()
        if suffix in self.extensions:
            return True
        if any(
            name_casefold.endswith(ext.casefold()) for ext in self.prompt_capture_extensions
        ) and any(
            part.casefold() in {d.casefold() for d in self.prompt_capture_dirnames}
            for part in relative_path.parts[:-1]
        ):
            return True
        return False


DEFAULT_JUNK_DENYLIST = JunkDenylist()


@dataclass(frozen=True)
class Valuable:
    """One flagged file: non-empty, non-junk, and (when git is available)
    git-content-unique; else age-gated in the fallback path."""

    relative_path: Path
    age_days: float
    size: int

    def as_dict(self) -> dict[str, object]:
        return {
            "path": self.relative_path.as_posix(),
            "age_days": round(self.age_days, 2),
            "size": self.size,
        }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_now(now: datetime | None) -> datetime:
    value = now or _utc_now()
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _age_days(mtime: float, now: datetime) -> float:
    return max(0.0, (now.timestamp() - mtime) / SECONDS_PER_DAY)


def _is_link_or_reparse(entry: os.DirEntry) -> bool:
    """True for a symlink OR any other reparse point -- notably an NTFS
    directory JUNCTION (`IO_REPARSE_TAG_MOUNT_POINT`), which is the gap this
    check exists to close. `entry.is_symlink()` alone only recognizes
    `IO_REPARSE_TAG_SYMLINK` and returns **False** for a junction (confirmed
    on this platform: `os.path.isjunction()` reports `True` and
    `DirEntry.is_symlink()` reports `False` for the identical entry), so a
    walker that trusted `is_symlink()` alone would DESCEND into a junction
    and enumerate files entirely outside `.scratch/` -- a direct violation of
    this module's "reparse points are never followed" invariant, and on the
    operator's own platform (win32).

    Prefers `os.path.isjunction` (3.12+, the correct stdlib primitive for
    this) and falls back to the raw `FILE_ATTRIBUTE_REPARSE_POINT` stat bit
    on older interpreters -- a broader check that also happens to catch
    every reparse tag, not just junctions, and is a harmless no-op on POSIX,
    where the attribute is simply absent."""

    try:
        if entry.is_symlink():
            return True
    except OSError:
        return True  # cannot tell -> treat as unsafe to descend/yield
    if _HAS_ISJUNCTION:
        try:
            return os.path.isjunction(entry.path)
        except OSError:
            return True
    try:
        info = entry.stat(follow_symlinks=False)
    except OSError:
        return True
    return bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT_ATTR)


def _iter_candidate_files(scratch_root: Path, denylist: JunkDenylist) -> Iterator[Path]:
    """Walk `scratch_root`, read-only. Symlinks and reparse points (including
    NTFS junctions -- see `_is_link_or_reparse`) are never followed (a link
    is not lingering data to rescue, and following one risks leaving
    `.scratch/` scope) and are simply skipped. Directory pruning is two-tier
    (see `JunkDenylist`): an UNAMBIGUOUS cache-directory name is pruned at
    ANY depth (nothing hand-authored ever lives inside one); an ambiguous
    name (`build`/`dist`/`.cache`) is pruned ONLY when it is a DIRECT child
    of `scratch_root` -- a deeper match is walked normally. Yields regular
    files only. The only filesystem calls here are `os.scandir` and the
    `DirEntry` type-check helpers -- nothing here can write, move, or
    delete."""

    stack = [scratch_root]
    while stack:
        directory = stack.pop()
        is_scratch_root = directory == scratch_root
        try:
            with os.scandir(directory) as entries:
                ordered = sorted(entries, key=lambda entry: entry.name.casefold())
        except OSError:
            continue  # unreadable directory: skip it, never fail hard (read-only tool)
        subdirs: list[Path] = []
        for entry in ordered:
            try:
                if _is_link_or_reparse(entry):
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if denylist.is_unambiguous_cache_directory(entry.name):
                        continue  # machine-cache directory: pruned at ANY depth
                    if is_scratch_root and denylist.is_junk_directory(entry.name):
                        continue  # ambiguous name: direct-child junk subtree only
                    subdirs.append(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    yield Path(entry.path)
            except OSError:
                continue
        stack.extend(subdirs)


def _find_git_root(start: Path) -> Path | None:
    """Walk up from `start` looking for a `.git` entry (a directory for an
    ordinary repository, or a file for a worktree/submodule gitlink). Returns
    None when `start` is not inside a git repository -- callers must treat
    that as "git unavailable for this scan" and fail open, never as an
    error. Read-only: only `Path.exists`."""

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


# In-process memoization only (see `scan_valuables`'s zero-mutation
# guarantee): keyed by (absolute path string, mtime, size) -> git blob SHA.
# Never persisted to disk -- a disk-backed cache would itself be a write,
# which this module must never perform. Its only benefit is avoiding
# redundant `git hash-object` calls across repeated `scan_valuables()` calls
# within the SAME process (e.g. a caller re-scanning); a fresh hook process
# starts with an empty cache every time, which is fine -- a single batched
# `git hash-object --stdin-paths` call is already fast (see module docstring
# evidence: seconds for ~14k files on this repository).
_BLOB_SHA_CACHE: dict[tuple[str, float, int], str] = {}


def _hash_object_batch(git_root: Path, paths: list[Path]) -> dict[Path, str] | None:
    """Read-only: `git hash-object --stdin-paths` (NEVER `-w`) computes each
    path's git blob SHA without writing anything to the object database.
    Returns `{path: sha}` for every input path, or `None` on ANY failure
    (missing git, non-zero exit, timeout, malformed/short output) so the
    caller can fail open rather than guess."""

    if not paths:
        return {}
    to_hash: list[Path] = []
    result: dict[Path, str] = {}
    stats: dict[Path, tuple[float, int]] = {}
    for path in paths:
        try:
            info = path.stat()
        except OSError:
            continue
        key = (str(path), info.st_mtime, info.st_size)
        cached = _BLOB_SHA_CACHE.get(key)
        if cached is not None:
            result[path] = cached
        else:
            to_hash.append(path)
            stats[path] = (info.st_mtime, info.st_size)
    if to_hash:
        stdin_payload = "\n".join(str(p) for p in to_hash) + "\n"
        try:
            proc = subprocess.run(
                ["git", "-C", str(git_root), "hash-object", "--stdin-paths"],
                input=stdin_payload,
                capture_output=True,
                text=True,
                timeout=_GIT_TIMEOUT_SECONDS,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if proc.returncode != 0:
            return None
        shas = proc.stdout.splitlines()
        if len(shas) != len(to_hash):
            return None
        for path, sha in zip(to_hash, shas):
            sha = sha.strip()
            if not sha:
                return None
            result[path] = sha
            mtime, size = stats[path]
            _BLOB_SHA_CACHE[(str(path), mtime, size)] = sha
    return result


def _blobs_missing_from_store(git_root: Path, shas: set[str]) -> set[str] | None:
    """Read-only: `git cat-file --batch-check` reports which of `shas` exist
    in the object database (loose or packed, from ANY commit/branch reachable
    in this repository's history -- not only the current working tree).
    Returns the SUBSET that is MISSING (content git cannot recover), or
    `None` on any failure so the caller can fail open."""

    if not shas:
        return set()
    stdin_payload = "\n".join(sorted(shas)) + "\n"
    try:
        proc = subprocess.run(
            ["git", "-C", str(git_root), "cat-file", "--batch-check"],
            input=stdin_payload,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    missing: set[str] = set()
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "missing":
            missing.add(parts[0])
    return missing


def _git_unique_paths(git_root: Path, paths: list[Path]) -> set[Path] | None:
    """The subset of `paths` whose exact content is NOT recoverable from
    `git_root`'s object database -- the PRIMARY valuable predicate (see the
    module docstring). Returns `None` (the fail-open signal) if any git call
    fails, so the caller falls back to the age gate rather than guessing."""

    shas = _hash_object_batch(git_root, paths)
    if shas is None:
        return None
    missing = _blobs_missing_from_store(git_root, set(shas.values()))
    if missing is None:
        return None
    return {path for path, sha in shas.items() if sha in missing}


def scan_valuables(
    scratch_root: Path,
    *,
    denylist: JunkDenylist = DEFAULT_JUNK_DENYLIST,
    now: datetime | None = None,
    fallback_age_days: float = VALUABLE_AGE_THRESHOLD_DAYS,
) -> list[dict[str, object]]:
    """Read-only scan of `scratch_root` for lingering valuable data.

    PRIMARY predicate: a file is a candidate only if its exact content is NOT
    already recoverable from this repository's git object database -- `git
    hash-object` computes its blob SHA and `git cat-file --batch-check`
    reports that SHA as MISSING from the store. Content that exists as a blob
    ANYWHERE in this repository's git history (any commit, any branch,
    whether or not this particular copy was ever tracked) is recoverable and
    is not a candidate. This is deliberately evidence-driven, not a tuning
    knob: on this repository's own `.scratch/`, an age-only gate flagged 8631
    files, and a random sample showed 58 of 59 resolvable ones were byte-
    identical to an existing git blob (recoverable). Non-junk and non-empty
    remain SECONDARY filters applied on top of uniqueness (a unique-but-junk
    capture artifact is still excluded).

    Age is NOT a gate here -- every git-unique, non-junk, non-empty file is
    returned, sorted NEWEST-modified first (`age_days` ascending, ties broken
    by path), so the caller can use age as a severity/sort signal.

    FAIL-OPEN, per the locked design: if `scratch_root` is not inside a git
    repository, git is not installed, or any git call fails, this falls back
    to the ORIGINAL age-gated behavior instead -- every non-junk, non-empty
    file strictly older than `fallback_age_days` (default 7) is a candidate,
    with no uniqueness check. This never crashes and never silently returns
    nothing or everything just because git happened to be unavailable.

    Returns each candidate as `{"path": <scratch-relative posix str>,
    "age_days": float, "size": int}`. If `scratch_root` does not exist (or is
    not a directory), returns `[]`.

    ZERO MUTATION, on every platform, under every code path, including the
    git-uniqueness path: `git hash-object` is called WITHOUT `-w` (computes
    only, never writes an object to the store) and `git cat-file
    --batch-check` never writes either. No filesystem write, move, delete,
    rename, mkdir, or file-open-for-write anywhere in this module.
    """

    current = _coerce_now(now)
    scratch_root = Path(scratch_root).resolve(strict=False)
    if not scratch_root.is_dir():
        return []

    candidates: list[tuple[Path, Path, os.stat_result]] = []
    for path in _iter_candidate_files(scratch_root, denylist):
        try:
            info = path.stat()
        except OSError:
            continue
        if info.st_size == 0:
            # DELIBERATE SPEC CHOICE (locked design): a 0-byte file is never
            # flagged, even if non-junk. This trades away some of the "bias
            # to over-warn" principle -- an empty placeholder a tool forgot
            # to fill in is silently skipped -- on the judgment that an
            # empty file carries no content an operator could lose.
            continue
        relative = path.relative_to(scratch_root)
        if denylist.is_junk_file(relative):
            continue
        candidates.append((path, relative, info))

    git_root = _find_git_root(scratch_root) if shutil.which("git") else None
    unique_paths: set[Path] | None = None
    if git_root is not None:
        unique_paths = _git_unique_paths(git_root, [c[0] for c in candidates])

    found: list[Valuable] = []
    if unique_paths is not None:
        # PRIMARY predicate available: gate on git-content-uniqueness, not age.
        for path, relative, info in candidates:
            if path not in unique_paths:
                continue
            age = _age_days(info.st_mtime, current)
            found.append(Valuable(relative_path=relative, age_days=age, size=info.st_size))
    else:
        # FAIL-OPEN fallback: no git repo / git missing / a git call failed.
        for path, relative, info in candidates:
            age = _age_days(info.st_mtime, current)
            if age <= fallback_age_days:
                continue
            found.append(Valuable(relative_path=relative, age_days=age, size=info.st_size))

    # Newest-modified first (severity ordering); path is only a tiebreak.
    found.sort(key=lambda v: (v.age_days, v.relative_path.as_posix().casefold()))
    return [v.as_dict() for v in found]


def print_report(valuables: Sequence[dict[str, object]]) -> None:
    """`valuables` arrives sorted newest-modified first (see `scan_valuables`'s
    docstring) -- that order is a stable, intentional part of the function's
    RETURN CONTRACT and is left untouched here. Presentation is a separate
    concern: the operator's actual risk is a file that has LINGERED, not the
    current session's own recent churn, so this prints LONGEST-LINGERING
    (oldest) FIRST -- a local reversal for display only."""

    if not valuables:
        print(f"scratch watchdog: no valuables found under {SCRATCH_DIRNAME}/")
        return
    print(
        f"scratch watchdog: {len(valuables)} valuable-looking file(s) under "
        f"{SCRATCH_DIRNAME}/ -- rescue before overwrite (this tool never deletes, "
        f"moves, or touches them), longest-lingering first:"
    )
    for item in reversed(valuables):
        print(f"  {item['path']}  (age={item['age_days']}d, size={item['size']}B)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            f"Read-only watchdog for {SCRATCH_DIRNAME}/: lists non-empty, non-junk files "
            "whose content is not already recoverable from this repository's git object "
            "database (age-gated fallback when git is unavailable). NEVER deletes, moves, "
            "or quarantines anything -- for debugging/manual inspection only. The automatic "
            "mechanism the operator asked for is the SessionStart hook, not this CLI."
        )
    )
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root (default: cwd)")
    parser.add_argument(
        "--fallback-age-days",
        type=float,
        default=VALUABLE_AGE_THRESHOLD_DAYS,
        help=(
            "Age threshold in days used ONLY when git is unavailable for this scan "
            f"(default: {VALUABLE_AGE_THRESHOLD_DAYS}); has no effect when the primary "
            "git-uniqueness predicate runs"
        ),
    )
    parser.add_argument("--json", action="store_true", help="Emit the result as JSON instead of a report")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    valuables = scan_valuables(root / SCRATCH_DIRNAME, fallback_age_days=args.fallback_age_days)
    if args.json:
        print(json.dumps({"valuables": valuables}, ensure_ascii=False))
    else:
        print_report(valuables)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
