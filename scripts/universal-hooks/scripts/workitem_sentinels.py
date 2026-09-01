"""Shared read-only work-item inspection for the periodic state checker.

This module owns physical active/archive discovery, location resolution, and
informational lifecycle findings used by
``scripts/check-work-items-state.py``. It is imported support code, not a
registered hook entry. Physical location owns lifecycle membership: status and
closure text can identify a move still due, but never make an active record
terminal.

The module does not write, move, delete, or rename repository data. Every git
invocation is read-only and uses an argument vector. Per-finding evaluation is
fail-open so one optional diagnostic cannot suppress its siblings or crash the
required periodic checker.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Informational finding vocabulary retained for periodic checker output.
# ---------------------------------------------------------------------------

RESOLVE = "RESOLVE"
NOTICE = "NOTICE"


class Finding:
    """One optional periodic diagnostic; a clean check returns ``None``."""

    __slots__ = ("id", "severity", "message")

    def __init__(self, id: str, severity: str, message: str) -> None:
        self.id = id
        self.severity = severity
        self.message = message

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"Finding(id={self.id!r}, severity={self.severity!r})"


# ---------------------------------------------------------------------------
# Directory discovery shared by every periodic diagnostic.
# ---------------------------------------------------------------------------

# How far up from the session cwd to search for a work-items/active directory.
MAX_PARENTS = 40

def _find_active_dir(start: Path) -> Path | None:
    """Walk up from the session cwd to the nearest work-items/active directory,
    stopping at the first ancestor that is itself a repository root (contains
    .git).

    This operator nests projects (Orchestrator/Orchestrarium,
    Orchestrator/benchmarks, ...). Without a repo boundary, an orphan sitting in
    a PARENT directory's work-items/active/ (a different, unrelated project)
    would fire for every session in every child project once the walk climbed
    past the child repo's own root. Checking the candidate directory BEFORE the
    boundary check means the common case (work-items/active/ living beside .git
    at the repo root) still resolves in one step.

    Returns None when no work-items/active directory exists within the current
    repository -> every invariant below fails open (no findings)."""
    try:
        cur = start.resolve()
    except Exception:
        return None
    for _ in range(MAX_PARENTS):
        candidate = cur / "work-items" / "active"
        try:
            if candidate.is_dir():
                return candidate
        except Exception:
            return None
        try:
            is_repo_root = (cur / ".git").exists()
        except Exception:
            is_repo_root = False
        if is_repo_root:
            break  # do not walk past this repository's own root
        if cur.parent == cur:
            break
        cur = cur.parent
    return None


def _disk_dir_names(d: Path) -> set[str]:
    try:
        return {p.name for p in d.iterdir() if p.is_dir()}
    except Exception:
        return set()


def _disk_archive_slug_pairs(archive_dir: Path) -> list[tuple[str, str]]:
    """(slug, relative-path-string) for every directory found under
    work-items/archive/ on disk: the canonical work-items/archive/<YYYY-MM>/
    <slug>/ layout, the flat/mis-filed work-items/archive/<slug>/ form, AND a
    non-month category directory work-items/archive/<anything>/<slug>/.

    This is a verdict-equivalent migration of the shipped hook's
    `_slug_is_done`, which checked `archive_dir / slug` (flat) and
    `archive_dir.glob(f"*/{slug}")` (one level under ANY immediate
    subdirectory, unconditional on what that subdirectory is named -- a
    month-shaped name was never part of that contract). An earlier revision
    of this function imposed a `^\\d{4}-\\d{2}$` check on the INTERMEDIATE
    directory before descending into it; that silently dropped an archived
    slug filed under a non-month category directory (e.g.
    `archive/legacy/kid/`) from SEN-0's epic-orphan detection and SEN-1's
    dual-state detection alike -- a real regression against the layout
    present in `VFEM_fort/work-items/archive/clean-wave-port/`
    (design.md review-grounding F4). Every immediate child of archive_dir is
    therefore registered BOTH as a flat candidate slug (mirrors the old
    `archive_dir / slug` check) and, if it itself has subdirectories, each of
    those is registered too (mirrors the old `archive_dir.glob(f"*/{slug}")`
    check, one level down, unconditional on the intermediate name)."""
    pairs: list[tuple[str, str]] = []
    try:
        children = sorted(p for p in archive_dir.iterdir() if p.is_dir())
    except Exception:
        return pairs
    for child in children:
        pairs.append((child.name, child.name))
        try:
            grandchildren = sorted(p for p in child.iterdir() if p.is_dir())
        except Exception:
            continue
        for slug_dir in grandchildren:
            pairs.append((slug_dir.name, f"{child.name}/{slug_dir.name}"))
    return pairs


# ---------------------------------------------------------------------------
# Read-only git helpers. Every call is an argument vector (no shell=True, no
# string interpolation of repository content into a command line) and every
# failure mode (git absent, not a repo, path missing from a given tree) fails
# open to an empty result -- never an exception the caller must anticipate.
# ---------------------------------------------------------------------------

GIT_TIMEOUT_SECONDS = 15


def _run_git(root: Path, args: list[str], *, stdin_text: str | None = None) -> tuple[int, str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except Exception:
        return 1, ""
    return result.returncode, result.stdout


def _git_is_repo(root: Path | None) -> bool:
    if root is None:
        return False
    code, out = _run_git(root, ["rev-parse", "--is-inside-work-tree"])
    return code == 0 and out.strip() == "true"


def _git_head_dirnames(root: Path, tree_path: str) -> list[str]:
    """Immediate directory names under `tree_path` in HEAD's tree, or [] when
    the path does not exist in HEAD, there is no HEAD (no commits yet), or git
    is unavailable. This is the deliberate fail-open shape: when `work-items/`
    has no tree in HEAD, this returns [] and every invariant below collapses to
    its disk-only leg, which is expected rather than an error."""
    code, out = _run_git(root, ["ls-tree", "-d", "--name-only", f"HEAD:{tree_path}"])
    if code != 0:
        return []
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def _git_archive_slug_pairs(root: Path) -> list[tuple[str, str]]:
    """Git-HEAD equivalent of `_disk_archive_slug_pairs` above -- same
    three-layout coverage (canonical month directory, flat/mis-filed,
    non-month category directory), unconditional on whether the intermediate
    directory name matches a month pattern (design.md review-grounding F4:
    the month-only check silently dropped a non-month-filed archived slug
    from both SEN-0's epic detection and SEN-1's dual-state detection)."""
    pairs: list[tuple[str, str]] = []
    for child in _git_head_dirnames(root, "work-items/archive"):
        pairs.append((child, f"HEAD:work-items/archive/{child}"))
        for slug in _git_head_dirnames(root, f"work-items/archive/{child}"):
            pairs.append((slug, f"HEAD:work-items/archive/{child}/{slug}"))
    return pairs


# ---------------------------------------------------------------------------
# resolve_slug_locations -- THE single owner of "where does this slug live"
# (claim 15 / F-B11 fix). SEN-0 and SEN-1 both route through this instead of
# maintaining their own first-hit predicate; the ctx it reads
# (`active_slugs` / `archive_slug_paths`) is built ONCE by build_context.
# ---------------------------------------------------------------------------


def resolve_slug_locations(ctx: dict, slug: str) -> dict:
    """Returns {"active": bool, "archive": [relative-path-string, ...]}, the
    UNION of the disk leg and the HEAD leg for both active/ and archive/. When
    `work-items/` has no tree in HEAD, this collapses to a disk-only answer,
    which is expected rather than a degradation."""
    return {
        "active": slug in (ctx.get("active_slugs") or set()),
        "archive": list((ctx.get("archive_slug_paths") or {}).get(slug, [])),
    }


# ---------------------------------------------------------------------------
# build_context -- the single traversal every registry entry reads from.
# ---------------------------------------------------------------------------


def build_context(
    cwd: str,
    **_unused: object,
) -> dict:
    """Build one shared context for periodic checker diagnostics."""
    ctx: dict = {
        "cwd": cwd,
        "active_dir": None,
        "archive_dir": None,
        "epics_dir": None,
        "root": None,
        "active_slugs": set(),
        "archive_slug_paths": {},
        "legs": "disk",
    }
    active_dir = _find_active_dir(Path(cwd))
    if active_dir is None:
        return ctx

    root = active_dir.parent.parent
    archive_dir = root / "work-items" / "archive"
    epics_dir = root / "work-items" / "epics"
    ctx["active_dir"] = active_dir
    ctx["archive_dir"] = archive_dir
    ctx["epics_dir"] = epics_dir
    ctx["root"] = root

    head_contributed = False
    is_repo = _git_is_repo(root)

    disk_active = _disk_dir_names(active_dir)
    head_active: set[str] = set()
    if is_repo:
        head_active = set(_git_head_dirnames(root, "work-items/active"))
        if head_active:
            head_contributed = True
    ctx["active_slugs"] = disk_active | head_active

    archive_slug_paths: dict[str, list[str]] = {}
    for slug, rel in _disk_archive_slug_pairs(archive_dir):
        archive_slug_paths.setdefault(slug, []).append(rel)
    if is_repo:
        head_pairs = _git_archive_slug_pairs(root)
        if head_pairs:
            head_contributed = True
        for slug, rel in head_pairs:
            archive_slug_paths.setdefault(slug, []).append(rel)
    ctx["archive_slug_paths"] = archive_slug_paths
    ctx["legs"] = "both" if head_contributed else "disk"
    return ctx


def _read_status(item: Path) -> str:
    status = item / "status.md"
    try:
        if status.is_file():
            return status.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return ""


def _slug_is_done(ctx: dict, slug: str) -> bool:
    """A child work-item is done only after it physically enters archive/."""

    return bool(resolve_slug_locations(ctx, slug)["archive"])


# ---------------------------------------------------------------------------
# SEN-0 -- periodic lifecycle diagnostic for evidence that an archive move is
# still due. It reports only; physical location remains authoritative.
# ---------------------------------------------------------------------------

# An active item counts as closed-but-not-moved when its status.md has a
# state/status/stage/outcome LINE whose VALUE BEGINS with a done/closed word.
# The anchored value grammar avoids matching explanatory prose.
DONE_STATE_LINE_REGEX = re.compile(
    r"(?im)^\s*>?\s*(?:[-*+]\s+)?\*{0,3}\s*(?:current\s+|primary\s+task\s+)?(?:state|status|stage|outcome)"
    r"\s*\*{0,3}\s*:\s*\*{0,3}\s*(?:closed|done|complete|completed|archived)(?![\w-])"
    r"(?![ \t]*[*_]{0,2}[ \t]*[,—-]?[ \t]*(?:when|if|means|когда|если|означает)\b)"
)

EPIC_HEADING_RE = re.compile(r"#{1,6}\s")
EPIC_CHILDREN_HEADING_RE = re.compile(r"##\s+children\b", re.IGNORECASE)
EPIC_CHILD_LINE_RE = re.compile(r"-\s*([A-Za-z0-9][\w.-]*)\s*\((?:active|closed)\)\s*$", re.IGNORECASE)
EPIC_FRONTMATTER_STATUS_RE = re.compile(r"\s*status\s*:\s*([A-Za-z]+)", re.IGNORECASE)


def _epic_status(text: str) -> str | None:
    """Read the epic status from its leading --- ... --- frontmatter ONLY. A
    body line that happens to start with 'status: closed' must NOT be treated
    as the epic status (FP-critical on a resolve-tier hook)."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for line in lines[1:]:
        if line.strip() == "---":
            break
        match = EPIC_FRONTMATTER_STATUS_RE.match(line)
        if match:
            return match.group(1).lower()
    return None


def _parse_epic_children(text: str) -> list[str]:
    """Extract child work-item slugs from the epic file's ## Children section.
    Reset on ANY ATX heading; require the documented '- <slug> (active|closed)'
    marker so a prose bullet under ## Children is not mis-read as a phantom
    child."""
    children: list[str] = []
    in_children = False
    for raw in text.splitlines():
        stripped = raw.strip()
        if EPIC_HEADING_RE.match(stripped):
            in_children = bool(EPIC_CHILDREN_HEADING_RE.match(stripped))
            continue
        if in_children:
            match = EPIC_CHILD_LINE_RE.match(stripped)
            if match:
                children.append(match.group(1))
    return children


def resolve_epic_locations(epics_dir: Path, slug: str) -> dict:
    """Resolve one epic slug without selecting an ambiguous copy.

    Active epics are direct ``work-items/epics/<slug>.md`` files. Closed
    epics are one level below ``work-items/epics/archive/<YYYY-MM>/``. The
    returned ``state`` is one of ``missing``, ``active``, ``archived``, or
    ``duplicate``; callers must treat ``duplicate`` as invalid rather than
    choosing a path by traversal order.
    """
    active_path = epics_dir / f"{slug}.md"
    active = (active_path,) if active_path.is_file() else ()
    archive_dir = epics_dir / "archive"
    try:
        archived = tuple(sorted(
            path
            for path in archive_dir.glob(f"*/{slug}.md")
            if path.is_file()
        ))
    except OSError:
        archived = ()
    locations = active + archived
    if not locations:
        state = "missing"
    elif len(locations) > 1:
        state = "duplicate"
    elif active:
        state = "active"
    else:
        state = "archived"
    return {
        "state": state,
        "active": active,
        "archive": archived,
        "locations": locations,
    }


def _epic_slugs(epics_dir: Path) -> list[str]:
    """Return every slug visible in the active root or monthly archive."""
    slugs: set[str] = set()
    try:
        slugs.update(path.stem for path in epics_dir.glob("*.md") if path.is_file())
        archive_dir = epics_dir / "archive"
        slugs.update(path.stem for path in archive_dir.glob("*/*.md") if path.is_file())
    except OSError:
        return []
    return sorted(slugs)


def _detect_orphans(active_dir: Path) -> list[tuple[str, str]]:
    orphans: list[tuple[str, str]] = []
    try:
        items = sorted(p for p in active_dir.iterdir() if p.is_dir())
    except Exception:
        return []
    for item in items:
        try:
            has_closure = (item / "closure.md").is_file()
        except Exception:
            has_closure = False
        if has_closure:
            orphans.append((item.name, "has closure.md but is still in active/ (move it to archive/)"))
            continue
        text = _read_status(item)
        if text and DONE_STATE_LINE_REGEX.search(text):
            orphans.append((item.name, "status.md marks it closed/done but it is still in active/"))
    return orphans


def _detect_epic_orphans(ctx: dict) -> list[tuple[str, str]]:
    orphans: list[tuple[str, str]] = []
    active_dir = ctx.get("active_dir")
    epics_dir = ctx.get("epics_dir")
    if active_dir is None or epics_dir is None:
        return []
    if not epics_dir.is_dir():
        return []
    for slug in _epic_slugs(epics_dir):
        resolution = resolve_epic_locations(epics_dir, slug)
        if resolution["state"] == "duplicate":
            rendered = ", ".join(
                path.relative_to(epics_dir).as_posix()
                for path in resolution["locations"]
            )
            orphans.append((slug, f"epic slug resolves to multiple locations ({rendered}); reconcile to one location"))
            continue
        if resolution["state"] == "missing":
            continue
        epic = resolution["locations"][0]
        try:
            text = epic.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        status = _epic_status(text)
        if status not in ("active", "closed"):
            continue
        location_state = resolution["state"]
        if location_state == "active" and status == "closed":
            orphans.append((slug, "epic is status: closed but remains in the active root (archive it)"))
            continue
        if location_state == "archived" and status == "active":
            orphans.append((slug, "epic is archived but status: active (restore it to the active root)"))
            continue
        children = _parse_epic_children(text)
        if not children:
            continue  # a 0-child epic never flags
        all_done = all(_slug_is_done(ctx, c) for c in children)
        if location_state == "active" and status == "active" and all_done:
            orphans.append((epic.stem, "all child work-items are closed but the epic is still status: active (close it)"))
        elif location_state == "archived" and status == "closed" and not all_done:
            orphans.append((epic.stem, "archived epic has a child work-item that is not closed (restore and reopen the epic)"))
    return orphans


def _sen0_block_reason(item_orphans: list[tuple[str, str]], epic_orphans: list[tuple[str, str]]) -> str:
    parts = ["work-items periodic lifecycle check: archive reconciliation is still due."]
    if item_orphans:
        lines = "\n".join(f"  - {name}: {why}" for name, why in item_orphans)
        parts.append(
            "One or more delivered/closed work-items are still sitting in "
            "work-items/active/ instead of being archived:\n\n"
            f"{lines}\n\n"
            "The Recovery rule's close step is as mandatory as the create step. "
            "Close each item: write closure.md (outcome, residual risk, archive "
            "location) if it is absent, move the folder to "
            "work-items/archive/<YYYY-MM>/<slug>/ through the lifecycle owner, "
            "which refreshes the generated work-items/README.md read-model."
        )
    if epic_orphans:
        lines = "\n".join(f"  - {name}: {why}" for name, why in epic_orphans)
        parts.append(
            "One or more epics violate the active/archive lifecycle contract:\n\n"
            f"{lines}\n\n"
            "For closure, write status: closed + ## Closure, then move the file "
            "to work-items/epics/archive/<YYYY-MM>/<slug>.md. For reopening, "
            "move it back to work-items/epics/<slug>.md and set status: active "
            "in the same lifecycle operation. Reconcile duplicate slugs before "
            "selecting either copy."
        )
    return "\n\n".join(parts)


def _sen0_evaluate(ctx: dict) -> Finding | None:
    active_dir = ctx.get("active_dir")
    if active_dir is None:
        return None
    item_orphans = _detect_orphans(active_dir)
    epic_orphans = _detect_epic_orphans(ctx)
    if not item_orphans and not epic_orphans:
        return None
    return Finding("SEN-0", RESOLVE, _sen0_block_reason(item_orphans, epic_orphans))


# ---------------------------------------------------------------------------
# SEN-1 -- dual-state item (instance C). A slug present under BOTH
# work-items/active/ and work-items/archive/**, in the union of disk and HEAD.
# Binary, no threshold: the pack's own contract places an item in exactly one
# location, so this contradicts the contract rather than estimating a
# heuristic. RESOLVE tier -- cheap, unambiguous, model-fixable.
# ---------------------------------------------------------------------------


def _closure_date(ctx: dict, slug: str) -> str | None:
    active_dir = ctx.get("active_dir")
    if active_dir is None:
        return None
    closure = active_dir / slug / "closure.md"
    try:
        if closure.is_file():
            return datetime.fromtimestamp(closure.stat().st_mtime, tz=UTC).date().isoformat()
    except Exception:
        pass
    return None


def _sen1_evaluate(ctx: dict) -> Finding | None:
    active_slugs = ctx.get("active_slugs") or set()
    archive_slug_paths = ctx.get("archive_slug_paths") or {}
    dual = sorted(slug for slug in active_slugs if archive_slug_paths.get(slug))
    if not dual:
        return None
    legs = ctx.get("legs", "disk")
    lines = []
    for slug in dual:
        locations = resolve_slug_locations(ctx, slug)
        archive_paths = ", ".join(locations["archive"])
        detail = f"archive copy at: {archive_paths}" if archive_paths else "archive copy present"
        closure_date = _closure_date(ctx, slug)
        if closure_date:
            detail += f"; closure.md dated {closure_date}"
        lines.append(f"  - {slug}: present in BOTH active/ and archive/ ({detail})")
    message = (
        "work-items dual-state sentinel (SEN-1): a work-item slug is present in "
        "BOTH work-items/active/ AND work-items/archive/, which the pack's own "
        f"contract forbids -- an item lives in exactly one location (legs={legs}):\n\n"
        + "\n".join(lines)
        + "\n\nRe-open it properly: confirm which location is authoritative for "
        "this item's current work, then reconcile the two copies through the "
        "normal close/reopen procedure so only one remains. Do not leave both "
        "copies in place."
    )
    return Finding("SEN-1", RESOLVE, message)


REGISTRY: tuple[dict, ...] = (
    {
        "id": "SEN-0",
        "event": "PeriodicCheck",
        "scope": "work-items/active/ + work-items/epics/ (archival orphans)",
        "evaluate": _sen0_evaluate,
        "exemptions": "none",
    },
    {
        "id": "SEN-1",
        "event": "PeriodicCheck",
        "scope": "work-items/active/ union work-items/archive/** (disk + HEAD)",
        "evaluate": _sen1_evaluate,
        "exemptions": "none",
    },
)


def evaluate_all(ctx: dict, event: str = "PeriodicCheck") -> list[Finding]:
    """Select every registry entry for `event`, evaluate it against `ctx`, and
    return the non-empty Findings. Per-entry fail-open: one broken diagnostic
    must not crash the periodic checker or suppress its siblings."""
    findings: list[Finding] = []
    for entry in REGISTRY:
        if entry["event"] != event:
            continue
        try:
            finding = entry["evaluate"](ctx)
        except Exception:
            continue
        if finding is not None:
            findings.append(finding)
    return findings


# ---------------------------------------------------------------------------
# Standalone CLI for debug/manual periodic evaluation.
# ---------------------------------------------------------------------------


def _cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Standalone periodic work-item diagnostic evaluator.")
    parser.add_argument("--root", default=".", help="Directory to start the work-items/active/ walk from.")
    parser.add_argument("--event", default="PeriodicCheck")
    args = parser.parse_args(argv)
    ctx = build_context(args.root)
    findings = evaluate_all(ctx, event=args.event)
    print(json.dumps([{"id": f.id, "severity": f.severity, "message": f.message} for f in findings], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
