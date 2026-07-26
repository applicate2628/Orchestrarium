"""workitem_sentinels.py — the invariant registry (extension seam S1).

WHY THIS MODULE EXISTS. The pack ships exactly two always-on repository-state
gates (`check-work-items-archival-stop` on `Stop`, `check-scratch-valuables` on
`SessionStart`), and until this module existed each was a hard-coded,
single-purpose detector with no way to add a third invariant except writing a
new hook from scratch. That absence is itself the root defect this module
fixes: a repository-state invariant now lands here as ONE REGISTRY RECORD --
never a new hook, never a hooks.json/installer edit, and (because this module
is IMPORTED by its adapter rather than separately REGISTERED) never a Codex
re-trust. See `work-items/active/2026-07-25-review-round-cap-enforcement/
design.md` for the full design; this docstring summarizes only what a future
maintainer needs to add invariant #3.

WHAT A SENTINEL IS, AND WHAT IT IS NOT. A sentinel asks "has the process
failed?", not "does this document conform to its schema?" (that second
question belongs to `check-work-items-state.py` / `validate-work-item-state.py`
-- the VALIDATOR). A sentinel's signal budget on a healthy repository is ZERO
output; a validator's is not. **This module MUST NOT import
`check-work-items-state.py` or `validate-work-item-state.py`** -- binding the
always-on Stop path to a 4079-line-on-a-real-repo validator is the exact
mistake this design exists to prevent (guarded by G-5 in
`tests/test_workitem_sentinels.py`).

THE AUTHORSHIP LATTICE (T0/T1/T2/T3) -- who may clear which tier. Every
invariant below sorts its admissible exemptions by WHO WRITES the clearing
signal, not by what the signal claims to be about:

  T0 -- runtime-authored (envelope fields, transcript/rollout presence): the
        strongest tier, admissible for any invariant at any severity.
  T1 -- user-authored (the operator's own typed message): admissible for any
        invariant at any severity.
  T2 -- model-authored, free (assistant prose, a self-authored label, the run
        ledger, status.md): NEVER admissible to clear a run-terminating
        invariant. A RESOLVE-tier invariant may admit exactly one DECLARED T2
        tier-exception (SEN-0's marker, below) -- never as an ambient reader
        anywhere else in this module.
  T3 -- model-controllable at a cost, with a named erasure clause (an action
        that is itself T0-visible in the transcript's tool-call record):
        admissible for any invariant, because the clearing action leaves its
        own trace.

DI-4's guard (G-4) greps this file for `agent-runs` / `agent_run_ledger` /
`status.md` / `last_assistant_message` and requires NO match outside the one
explicitly delimited "DECLARED T2 EXEMPTION" block below (SEN-0's marker).
Anywhere else, reading one of those signals to decide a finding is exactly the
proven defect this design fixes -- the incident's failing session called the
fail-closed ledger helper 705 times, PASSED every time, then simply STOPPED
calling it; a gate keyed on the ledger, or on `status.md` conforming, is
escapable by not writing to it.

THE REGISTRY RECORD SHAPE. Each entry in `REGISTRY` is a plain dict:
`{id, event, scope, evaluate(ctx) -> Finding | None, exemptions}`. `event` is a
data field (today only `"Stop"` is populated; `"SessionStart"` is the declared
landing point for the future `check-scratch-valuables` migration -- see
`work-items/decisions/2026-07-25-*` and the follow-up filed in this item's
design §14). Adding invariant #3 means appending one more dict to `REGISTRY`
and writing its `evaluate(ctx)` function -- nothing else in this file, and
NOTHING outside it, needs to change. (r8: SEN-2, the previous invariant #3,
was CUT -- see the SEN-2 section comment below and design.md §0.9. The
registry currently holds SEN-0 and SEN-1.)

WHAT THIS MODULE DOES NOT OWN. The severity -> payload mapping (which JSON
shape a RESOLVE/NOTICE finding becomes, the `stop_hook_active` RESOLVE
suppression + tier-escalation-to-NOTICE rule, and the RESOLVE/NOTICE
precedence when several invariants fire at once) is owned by the ADAPTER
(`check-work-items-archival-stop.py`), not here -- that is seam S3. This
module is FAIL-OPEN internally per invariant (`evaluate_all` swallows any
single entry's exception so one broken invariant cannot crash its siblings or
the adapter), but it never touches process exit codes or hook payload shape.

READ-ONLY, ALWAYS. No function in this module writes, moves, deletes, or
renames anything under the target repository, on any platform, on any code
path. Every `git` invocation is read-only (`rev-parse`, `ls-tree`) and uses an
argument vector -- never `shell=True`, never string-interpolated into a shell
command.

Imports are a closed set: {argparse, json, re, subprocess, sys, datetime,
pathlib} plus stdlib builtins -- no new runtime dependency (claim 18).
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
# Severity vocabulary (the two response tiers; payload mapping lives at the
# adapter -- see module docstring).
#
# r7: HALT is REMOVED, not merely unused. T-14 measured that on the Codex
# line neither `stopReason` nor `systemMessage` reaches the operator inside a
# HALT payload, and that `--json` mode emits no hook-status event at all, so
# a run-terminating tier there is not merely unattributed, it is
# undetectable. The three installed copies are byte-identical (G-2), so the
# tier is all-or-nothing across both lines, and the admitted incident
# happened on the line where it does not work. See
# references-codex/stop-hook-halting-primitives.md and design.md §4.4c/§1.0.
# A tier reachable by re-adding one severity constant is the half-finished
# alternative beside live code the repo's own hygiene rules forbid -- hence
# deletion, not a dormant flag.
# ---------------------------------------------------------------------------

RESOLVE = "RESOLVE"
NOTICE = "NOTICE"


class Finding:
    """One invariant's verdict for this evaluation. `severity` is one of
    RESOLVE / NOTICE; a clean invariant returns None, never a Finding with a
    placeholder severity."""

    __slots__ = ("id", "severity", "message")

    def __init__(self, id: str, severity: str, message: str) -> None:
        self.id = id
        self.severity = severity
        self.message = message

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"Finding(id={self.id!r}, severity={self.severity!r})"


# ---------------------------------------------------------------------------
# Directory discovery -- migrated verbatim from check-work-items-archival-stop.py
# (this is the one traversal every invariant shares; §5.1 "One traversal").
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
    is unavailable. This is the deliberate fail-open shape: on the pack's own
    default posture (`/work-items/` gitignored on every project install --
    design.md §2.4), this ALWAYS returns [] and every invariant below
    collapses to its disk-only leg, which is the documented default, not an
    error."""
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
    UNION of the disk leg and the HEAD leg for both active/ and archive/. On
    the pack's default posture (`work-items/` gitignored) the HEAD leg is
    empty by construction and this collapses to a disk-only answer -- the
    documented default, not a degradation (design.md §2.4)."""
    return {
        "active": slug in (ctx.get("active_slugs") or set()),
        "archive": list((ctx.get("archive_slug_paths") or {}).get(slug, [])),
    }


# ---------------------------------------------------------------------------
# build_context -- the single traversal every registry entry reads from.
# ---------------------------------------------------------------------------


def build_context(
    cwd: str,
    *,
    last_assistant_message: str = "",
    user_message_text: str = "",
) -> dict:
    """Build the sentinel evaluation context once per Stop event. Every
    registry entry reads from this ctx rather than re-walking work-items/ or
    re-invoking git itself (§5.1 "One traversal").

    `user_message_text` is SEN-0's T1 operator-channel widening (F3): the
    operator's own last genuine typed message, read via
    `hook_common.last_genuine_user_text`'s bounded reverse scan (design.md
    §0.9.4). r8 removed the `user_message_status` companion field -- it
    existed only to feed SEN-2's `override-channel` discriminator, and SEN-2
    is cut; nothing else in this module reads a read-status, only the text
    itself, matched against a marker regardless of how it was obtained."""
    ctx: dict = {
        "cwd": cwd,
        "last_assistant_message": last_assistant_message or "",
        "user_message_text": user_message_text or "",
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
    """A child work-item is done iff it is archived (via the shared resolver),
    has closure.md, or its status.md carries a bare done-state line."""
    locations = resolve_slug_locations(ctx, slug)
    if locations["archive"]:
        return True
    active_dir = ctx.get("active_dir")
    if active_dir is None:
        return False
    item = active_dir / slug
    try:
        if (item / "closure.md").is_file():
            return True
    except Exception:
        pass
    text = _read_status(item)
    return bool(text and DONE_STATE_LINE_REGEX.search(text))


# ---------------------------------------------------------------------------
# SEN-0 -- archival orphan (migrated; verdict-equivalent, exemption narrowed
# to this entry alone). Logic, thresholds and reason text are the same as the
# shipped check-work-items-archival-stop.py hook (DI-1); only the slug-location
# lookup now routes through resolve_slug_locations (F-B11 fix).
# ---------------------------------------------------------------------------

# An active item counts as closed-but-not-moved when its status.md has a
# state/status/stage/outcome LINE whose VALUE BEGINS with a done/closed word.
# See check-work-items-archival-stop.py's original docstring for the full
# false-positive rationale (this regex is migrated byte-for-byte).
DONE_STATE_LINE_REGEX = re.compile(
    r"(?im)^\s*>?\s*(?:[-*+]\s+)?\*{0,3}\s*(?:current\s+|primary\s+task\s+)?(?:state|status|stage|outcome)"
    r"\s*\*{0,3}\s*:\s*\*{0,3}\s*(?:closed|done|complete|completed|archived)(?![\w-])"
    r"(?![ \t]*[*_]{0,2}[ \t]*[,—-]?[ \t]*(?:when|if|means|когда|если|означает)\b)"
)

SEN0_OVERRIDE_MARKER_REGEX = re.compile(r"\[acknowledge-open-work-items\]", re.IGNORECASE)

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
    try:
        if not epics_dir.is_dir():
            return []
        files = sorted(p for p in epics_dir.iterdir() if p.is_file() and p.suffix == ".md")
    except Exception:
        return []
    for epic in files:
        try:
            text = epic.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        status = _epic_status(text)
        if status not in ("active", "closed"):
            continue
        children = _parse_epic_children(text)
        if not children:
            continue  # a 0-child epic never flags
        all_done = all(_slug_is_done(ctx, c) for c in children)
        if status == "active" and all_done:
            orphans.append((epic.stem, "all child work-items are closed but the epic is still status: active (close it)"))
        elif status == "closed" and not all_done:
            orphans.append((epic.stem, "epic is status: closed but a child work-item is not closed (reopen the epic)"))
    return orphans


def _sen0_block_reason(item_orphans: list[tuple[str, str]], epic_orphans: list[tuple[str, str]]) -> str:
    parts = ["work-items archival Stop guard: task-memory items need a close action before stopping."]
    if item_orphans:
        lines = "\n".join(f"  - {name}: {why}" for name, why in item_orphans)
        parts.append(
            "One or more delivered/closed work-items are still sitting in "
            "work-items/active/ instead of being archived:\n\n"
            f"{lines}\n\n"
            "The Recovery rule's close step is as mandatory as the create step. "
            "Close each item: write closure.md (outcome, residual risk, archive "
            "location) if it is absent, move the folder to "
            "work-items/archive/<YYYY-MM>/<slug>/, and move its row in "
            "work-items/index.md from Active to Archived."
        )
    if epic_orphans:
        lines = "\n".join(f"  - {name}: {why}" for name, why in epic_orphans)
        parts.append(
            "One or more epics in work-items/epics/ are out of sync with their "
            "children:\n\n"
            f"{lines}\n\n"
            "Update the epic file's status line: close a ready-to-close epic "
            "(status: closed + ## Closure) or reopen an epic whose child reopened "
            "(status: active)."
        )
    parts.append(
        "If leaving this as-is is intentional this turn, include "
        "[acknowledge-open-work-items] in your reply. If this message reaches "
        "the operator instead of the model (this RESOLVE was escalated to a "
        "turn-free NOTICE because a continuation was already spent this "
        "turn -- §4.4a), the operator may clear it the same way: by including "
        "the same marker in their own next message."
    )
    return "\n\n".join(parts)


def _sen0_evaluate(ctx: dict) -> Finding | None:
    # --- BEGIN DECLARED T2 EXEMPTION (SEN-0 only; design.md F-B3 / DI-1b) ------
    # [acknowledge-open-work-items] in the model's own last assistant message is
    # a documented, shipped bypass for SEN-0 ALONE (verdict-equivalent migration
    # of the shipped hook's marker check). It must never clear SEN-1, which is
    # exactly why this check lives inside SEN-0's own evaluate() and nowhere
    # else in this module -- a marker check at the adapter would union across
    # every invariant (the F-B3 defect).
    #
    # F3 correction (design.md review-grounding, 2026-07-25; re-justified at
    # r8 §0.9.4 after SEN-2's cut removed the original HALT-payload
    # justification): this RESOLVE finding's text can reach the OPERATOR
    # instead of the model whenever it is escalated to a turn-free NOTICE
    # under stop_hook_active (adapter's _format_escalation, §4.4a) -- an
    # operator-only channel. A marker matched ONLY against
    # last_assistant_message is unclearable through it: the operator's own
    # reply is never re-checked, so the instruction above ("in your reply")
    # would tell the operator to do something that is silently ignored. This
    # block therefore ALSO admits a T1 exemption (the operator's own last
    # genuine typed message) -- T1 is admissible for any invariant at any
    # severity (design.md §3.1's tier rule), strictly stronger than the T2
    # channel this block already grants. Its own blast radius is honestly
    # small, and CORRECTED at r8's post-ship pass: losing it does not change
    # how often this finding re-fires (that is §4.4a's per-turn model,
    # independent of this marker) -- it removes only the OPERATOR's own
    # ability to clear the finding directly. Without it, an operator who
    # learned the marker from documentation (the in-context escalation NOTICE
    # that would otherwise teach it is Claude-line only) cannot clear SEN-0 by
    # typing it themselves, and the finding keeps re-firing to the model every
    # subsequent turn until the MODEL writes the marker itself (T2, always
    # available either way). A quality fix narrowing an operator-convenience
    # gap, not a safety-critical one, and not a one-turn cost (§0.9.4).
    last_assistant_message = ctx.get("last_assistant_message") or ""
    user_message_text = ctx.get("user_message_text") or ""
    if SEN0_OVERRIDE_MARKER_REGEX.search(last_assistant_message) or SEN0_OVERRIDE_MARKER_REGEX.search(
        user_message_text
    ):
        return None
    # --- END DECLARED T2 EXEMPTION ----------------------------------------------
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


# ---------------------------------------------------------------------------
# SEN-2 -- delivery drought. CUT at r8 (design.md §0.9): a bare `systemMessage`
# NOTICE from a Stop hook does not reach the operator on the Codex line
# either (T-20), the same line the admitted incident happened on, so the
# tier produced nothing observable there in any posture or band. Combined
# with the substrate defect F1 already found (git cannot attribute delivery
# to an item in the pack's own default posture) and the coverage gap R-6/R-19
# already named (file count cannot see in-place revision -- this work-item's
# own shape), the invariant carried more open design debt (seven residuals:
# R-3b, R-4, R-5, R-6, R-14, R-19, R-21) than the rest of the design
# combined. Withdrawn, not narrowed again, and re-proposed on a different
# substrate: decision `2026-07-26-delivery-drought-needs-a-substrate-not-a-
# threshold` (R-9's T0 turn/spend counter). Removed with it: the four
# threshold flags, the `override-channel` field, and every git
# delivery-attribution helper reachable only from this invariant (the
# per-commit file-diff walk, the process-path classifier, the item-attributed
# commit finder). `_git_is_repo` / `_git_head_dirnames` / `_git_archive_slug_pairs`
# are NOT part of that removal -- they are SEN-1's own HEAD-leg substrate,
# reached directly from `build_context`, and stay.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# The registry -- extension seam S1. Adding invariant #3 means appending one
# more record here and writing its evaluate(ctx) function; nothing else in
# this file, and nothing outside it, needs to change.
# ---------------------------------------------------------------------------

REGISTRY: tuple[dict, ...] = (
    {
        "id": "SEN-0",
        "event": "Stop",
        "scope": "work-items/active/ + work-items/epics/ (archival orphans)",
        "evaluate": _sen0_evaluate,
        "exemptions": "[acknowledge-open-work-items] in last_assistant_message (T2, SEN-0 only)",
    },
    {
        "id": "SEN-1",
        "event": "Stop",
        "scope": "work-items/active/ union work-items/archive/** (disk + HEAD)",
        "evaluate": _sen1_evaluate,
        "exemptions": "none beyond the adapter's (agent_id, ORCHESTRARIUM_DISPATCHED_REVIEW)",
    },
)


def evaluate_all(ctx: dict, event: str = "Stop") -> list[Finding]:
    """Select every registry entry for `event`, evaluate it against `ctx`, and
    return the non-empty Findings. Per-entry fail-open: one broken invariant
    must not crash the adapter or suppress its siblings."""
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
# Standalone CLI -- debug/manual invocation only. The hook adapter never
# shells out to this; it imports the module directly.
# ---------------------------------------------------------------------------


def _cli(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Standalone sentinel registry evaluator (debug/test entry point).")
    parser.add_argument("--root", default=".", help="Directory to start the work-items/active/ walk from.")
    parser.add_argument("--event", default="Stop")
    parser.add_argument("--last-assistant-message", default="")
    parser.add_argument("--user-message", default="")
    args = parser.parse_args(argv)
    ctx = build_context(
        args.root,
        last_assistant_message=args.last_assistant_message,
        user_message_text=args.user_message,
    )
    findings = evaluate_all(ctx, event=args.event)
    print(json.dumps([{"id": f.id, "severity": f.severity, "message": f.message} for f in findings], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
