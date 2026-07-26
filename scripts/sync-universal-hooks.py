#!/usr/bin/env python3
"""Propagate the pack-neutral canon under scripts/universal-hooks/ to its two
byte-identical mirrors, so editing the canon is enough — a lane no longer has
to hand-copy to "the other two" and hope it remembered which two.

CANONICAL DIRECTION (stated here, not inferred per-run from file contents):

    scripts/universal-hooks/scripts/  --canon-of-->  src.claude/agents/scripts/
                                                       src.codex/skills/lead/scripts/
    scripts/universal-hooks/hooks/    --canon-of-->  src.claude/agents/hooks/
                                                       src.codex/skills/lead/hooks/

Evidence for this direction (load-bearing citations, not a guess):
  - tests/test_universal_hook_surfaces.py:10-11 (as of the commit this script was
    added): the canon dir comment states it "IS the single owner of which universal
    hooks exist" and the required-name lists are derived from it by glob.
  - The `filecmp.cmp` call inside `test_pack_neutral_hook_sources_exist_and_match_
    production_packs` in tests/test_universal_hook_surfaces.py (line number not
    cited here on purpose — it has already moved twice in this same session as
    the file grew; anchor on the method name, not a line number, or re-grep
    `filecmp.cmp` in that file for the current line): the parity assertion
    compares each provider copy AGAINST the universal dir and reports drift as
    "{provider file} drifted from universal hook source" — the universal dir is
    never described as the thing that can drift. (Two earlier drafts of this
    citation pointed at stale line numbers — :99, a docstring line, then :69/:73,
    already superseded by the next edit — which is exactly why this citation no
    longer pins one.)
  - shared/references/repository-source-hygiene.md:42: hook copies are described as
    "byte-identical to its scripts/universal-hooks/hooks/ canon source".
  - work-items/decisions/2026-07-11-hook-placement-gate-semantics.md:16-21: the
    placement register states copies as "byte-identical to canon", with
    scripts/universal-hooks/ as the referenced canon dir.
  - scripts/validate-agents-mode-installers.py:90-95 (`universal_hook_helper_paths`):
    an independent, unrelated validator's own docstring also calls
    scripts/universal-hooks/ "the pack-neutral canon", derived by glob, and uses it
    to check the gemini/qwen installer regression.
  - scripts/install-claude.sh and scripts/install-codex.sh each copy their OWN pack
    tree (src.claude/agents/*, src.codex/skills/lead/*) to the runtime install target;
    neither reads scripts/universal-hooks/ at install time. That tree exists
    specifically as the pack-neutral reference the gemini/qwen installers copy FROM
    (see tests/test_universal_hook_surfaces.py::test_gemini_qwen_installers_copy_
    universal_hook_helpers) and that every citation above already names as canon.
    Canon status is a stated fact of this repository's own governing docs, not
    something this script re-derives from file contents, mtimes, or which copy
    "looks newer".

THE OBLIGATION THIS SCRIPT ENFORCES: a lane changing the behavior of a mirrored
script/hook MUST edit the copy under scripts/universal-hooks/, never a mirror
directly, and then run this script (`--sync`, or at minimum `--check` before
reporting a result). See docs/new-session-guide.md for where this is stated as
the standard workflow step.

WHY THE DIRECTION IS NEVER GUESSED PER FILE, ONLY THE SAFETY GATE IS: knowing WHICH
tree is canonical is a fixed, stated fact (above). What this script cannot always
know is whether it is SAFE to overwrite a drifted mirror — file bytes alone cannot
tell "canon changed, mirror is simply stale" apart from "someone edited the mirror
directly instead of canon, so the mirror holds real unrecorded work" — both produce
the identical snapshot (canon differs from exactly one mirror). This script does not
resolve that ambiguity by majority vote or by mtime (mtime is not reliable evidence
here: a git checkout/clone resets it, and editors do not preserve it consistently —
see the shared "Determinism and ambient-input control" rule). Instead it asks git
which side has UNCOMMITTED changes: a mirror file that differs from canon AND differs
from its own last commit is proof someone is relying on that mirror's current content
right now, so this script REFUSES to overwrite it and reports a CONFLICT instead of
guessing. A mirror file that differs from canon but is IDENTICAL to its own last
commit has nothing uncommitted to lose, so overwriting it with canon is safe (and
even then, recoverable via git history).

MANIFEST SPLIT (why the name lists and drift detection are NOT in this file): the
canon name-lists, declared pack-only exceptions, and drift-detection logic live in
the sibling module `universal_hooks_manifest.py`, imported below. See that module's
own docstring for the full reasoning; short version: tests/test_universal_hook_
surfaces.py imports that small, dependency-free module directly, so a defect in
THIS file's argparse/subprocess/git-integration code can never take the parity
gate's ability to collect down with it. A real defect here (a `dataclasses` +
Python-3.14 interaction, since fixed by moving `DriftEntry` to the manifest as a
`NamedTuple`) briefly did exactly that before this split existed.

Usage:
    python scripts/sync-universal-hooks.py --check
        Read-only, fast. For a lane's own targeted pass, before reporting a result.
        Exit 0 if every mirror matches canon; exit 1 and list every drifted file
        otherwise. Never writes anything.

    python scripts/sync-universal-hooks.py --sync [--dry-run] [--force]
        Propagate canon -> mirrors for every file it is safe to overwrite (see
        above). Prints SYNCED for files it touches and CONFLICT for files it
        refuses. --dry-run previews without writing. --force bypasses the
        git-uncommitted-changes safety gate entirely (dangerous: only pass this
        if you have manually verified no drifted mirror carries unrecorded work,
        e.g. because git itself is unavailable in this environment).
        Exit 0 if the tree ends fully in sync, 2 if any CONFLICT remains unresolved.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

# The manifest + drift-detection module is a sibling file in this same
# directory. Explicit sys.path insert (not relying on the "running a script
# adds its own dir to sys.path[0]" default, which does not apply when this
# file is loaded via importlib from a test at an arbitrary cwd) — same
# pattern this repo's own hooks already use to reach hook_common.py (e.g.
# scripts/universal-hooks/hooks/check-repository-orientation.py:28).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import universal_hooks_manifest as manifest  # noqa: E402

HOOK_EXTS = manifest.HOOK_EXTS
PACK_ONLY_SCRIPTS = manifest.PACK_ONLY_SCRIPTS
PACK_ONLY_HOOKS = manifest.PACK_ONLY_HOOKS
canon_root = manifest.canon_root
canon_names = manifest.canon_names
DriftEntry = manifest.DriftEntry
find_drift = manifest.find_drift


def cmd_check(root: Path) -> int:
    drift = find_drift(root)
    if not drift:
        print("PASS: universal-hooks canon in sync with both mirrors")
        return 0
    for entry in drift:
        print(
            f"DRIFT: {entry.mirror_rel} differs from canon "
            f"{entry.canon_path.relative_to(root).as_posix()}",
            file=sys.stderr,
        )
    print(
        f"FAIL: {len(drift)} mirrored file(s) drifted from scripts/universal-hooks/ canon. "
        "Run `python scripts/sync-universal-hooks.py --sync` to propagate "
        "(edit the canon, never the mirrors directly).",
        file=sys.stderr,
    )
    return 1


# ---------------------------------------------------------------------------
# Propagation (the --sync surface), gated by git-uncommitted-changes safety.
# ---------------------------------------------------------------------------

def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(root), "-c", "core.quotepath=false", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=30,
    )


def git_available(root: Path) -> bool:
    try:
        result = _git(root, "rev-parse", "--is-inside-work-tree")
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0 and result.stdout.strip() == "true"


def git_dirty_relpaths(root: Path, relpaths: list[str]) -> set[str]:
    """Return the subset of repo-root-relative posix paths that carry
    uncommitted changes (staged or unstaged, including untracked) relative to
    HEAD, per `git status --porcelain=v1`. A path absent from the output is
    byte-identical to what HEAD already has committed."""
    if not relpaths:
        return set()
    result = _git(root, "status", "--porcelain=v1", "--", *relpaths)
    dirty: set[str] = set()
    for line in result.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:  # rename/copy status lines: "R  old -> new"
            path = path.split(" -> ", 1)[1]
        dirty.add(path.strip('"'))
    return dirty


def cmd_sync(root: Path, dry_run: bool, force: bool) -> int:
    drift = find_drift(root)
    if not drift:
        print("PASS: universal-hooks canon already in sync with both mirrors; nothing to do")
        return 0

    if force:
        dirty: set[str] = set()
    else:
        if not git_available(root):
            print(
                "REFUSE: git is not available (or this is not a working git tree), so this "
                "tool cannot prove a drifted mirror has no uncommitted local work. Refusing "
                "to overwrite anything rather than guess. Pass --force to proceed WITHOUT "
                "that safety check (only if you have manually verified none of the drifted "
                "mirrors below carry unrecorded work).",
                file=sys.stderr,
            )
            for entry in drift:
                print(f"  UNRESOLVED: {entry.mirror_rel}", file=sys.stderr)
            return 2
        relpaths = [entry.mirror_path.relative_to(root).as_posix() for entry in drift]
        dirty = git_dirty_relpaths(root, relpaths)

    synced: list[DriftEntry] = []
    conflicts: list[DriftEntry] = []
    for entry in drift:
        mirror_rel_posix = entry.mirror_path.relative_to(root).as_posix()
        if not force and mirror_rel_posix in dirty:
            conflicts.append(entry)
            print(
                f"CONFLICT: {entry.mirror_rel} has uncommitted local changes AND differs "
                f"from canon ({entry.canon_path.relative_to(root).as_posix()}) -- refusing to "
                "guess which side is correct. Resolve by hand: diff the mirror against canon, "
                "fold any real work into the canon copy, then re-run --sync.",
                file=sys.stderr,
            )
            continue
        if dry_run:
            print(f"WOULD SYNC: {entry.mirror_rel} <- {entry.canon_path.relative_to(root).as_posix()}")
        else:
            entry.mirror_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(entry.canon_path, entry.mirror_path)
            print(f"SYNCED: {entry.mirror_rel} <- {entry.canon_path.relative_to(root).as_posix()}")
        synced.append(entry)

    verb = "Would sync" if dry_run else "Synced"
    print(f"{verb} {len(synced)} file(s); {len(conflicts)} conflict(s) left unresolved.")
    return 0 if not conflicts else 2


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--root", default=".", help="repository root")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="read-only drift report; exit 1 on drift")
    mode.add_argument("--sync", action="store_true", help="propagate canon -> mirrors where safe")
    parser.add_argument("--dry-run", action="store_true", help="with --sync, preview without writing")
    parser.add_argument(
        "--force", action="store_true",
        help="with --sync, bypass the git-uncommitted-changes safety gate (dangerous)",
    )
    args = parser.parse_args()

    if args.dry_run and not args.sync:
        parser.error("--dry-run only makes sense with --sync")
    if args.force and not args.sync:
        parser.error("--force only makes sense with --sync")

    root = Path(args.root).resolve()
    if args.check:
        return cmd_check(root)
    return cmd_sync(root, dry_run=args.dry_run, force=args.force)


if __name__ == "__main__":
    raise SystemExit(main())
