#!/usr/bin/env python3
"""Repository publication gate: leak scan, work-item state, and release notes."""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def _run(args: list[str], *, text: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
    )


def _git_root() -> Path:
    proc = _run(["git", "rev-parse", "--show-toplevel"])
    if proc.returncode:
        raise RuntimeError("not inside a git repository")
    return Path(proc.stdout.strip())


def _fail(message: str) -> int:
    print(f"FAIL: {message}", file=sys.stderr)
    return 1


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--release-notes-exempt", metavar="REASON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.release_notes_exempt is not None and not args.release_notes_exempt.strip():
        _parser().error("--release-notes-exempt requires a non-empty reason")
    try:
        root = _git_root()
    except RuntimeError as exc:
        return _fail(str(exc))

    scanner = root / "src.codex" / "skills" / "lead" / "scripts" / "check-publication-safety.py"
    scan = subprocess.run([sys.executable, str(scanner)], cwd=root)
    if scan.returncode:
        return scan.returncode

    active = root / "work-items" / "active"
    if active.is_dir():
        state = subprocess.run(
            [sys.executable, str(root / "scripts" / "check-work-items-state.py"), "--root", "."],
            cwd=root,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if state.returncode:
            return _fail(
                "work-items state check failed (open REVISE obligation or invalid ledger) "
                "— run: python scripts/check-work-items-state.py"
            )

    staged_proc = _run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMRTUXB", "-z", "--"],
        text=False,
    )
    if staged_proc.returncode:
        return _fail("could not enumerate staged tracked paths")
    staged = [
        part.decode("utf-8", "surrogateescape")
        for part in staged_proc.stdout.split(b"\0")
        if part
    ]
    if not staged:
        print("PASS: no staged tracked changes")
        return 0

    relevant: list[str] = []
    release_notes_staged = False
    for path in staged:
        if path == "RELEASE_NOTES.md":
            release_notes_staged = True
            continue
        if path.startswith("work-items/"):
            return _fail("work-items/ is local-only task memory and must not be staged for publication")
        if path.startswith((".reports/", ".plans/", ".scratch/")):
            continue
        relevant.append(path)

    if not relevant:
        print("PASS: staged tracked changes are release-notes-exempt by path class")
        return 0
    if args.release_notes_exempt:
        print(
            "PASS: release-notes requirement explicitly exempted by reviewer: "
            f"{args.release_notes_exempt}"
        )
        return 0
    if not release_notes_staged:
        print(
            "FAIL: release-relevant staged changes require a matching RELEASE_NOTES.md "
            "update or --release-notes-exempt <reason>",
            file=sys.stderr,
        )
        print("release-relevant staged paths:", file=sys.stderr)
        for path in relevant:
            print(f"  - {path}", file=sys.stderr)
        return 1

    notes = root / "RELEASE_NOTES.md"
    if not notes.is_file():
        return _fail("missing RELEASE_NOTES.md at repo root")
    content = notes.read_text(encoding="utf-8")
    if re.search(r"^## Unreleased$", content, re.MULTILINE):
        return _fail(
            "RELEASE_NOTES.md must use dated sections and must not keep a long-lived "
            "'## Unreleased' bucket"
        )
    dates = re.findall(r"^## ([0-9]{4}-[0-9]{2}-[0-9]{2})$", content, re.MULTILINE)
    if not dates:
        return _fail("RELEASE_NOTES.md must contain at least one top-level '## YYYY-MM-DD' section")
    if len(dates) != len(set(dates)):
        duplicate = next(date for date in dates if dates.count(date) > 1)
        return _fail(f"duplicate dated section in RELEASE_NOTES.md: {duplicate}")
    if dates != sorted(dates, reverse=True):
        return _fail("RELEASE_NOTES.md date sections must stay in reverse-chronological order")

    diff = _run(["git", "diff", "--cached", "--unified=0", "--", "RELEASE_NOTES.md"])
    if diff.returncode:
        return _fail("could not inspect staged RELEASE_NOTES.md diff")
    if not re.search(r"^\+(?:## [0-9]{4}-[0-9]{2}-[0-9]{2}|- )", diff.stdout, re.MULTILINE):
        return _fail(
            "staged RELEASE_NOTES.md update must add a dated section or at least one explanatory bullet"
        )

    print("PASS: publication gate passed (leak scan clean, release notes present, dated structure valid)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
