#!/usr/bin/env python3
"""Work-items archival guard for the Stop hook.

Catches the systemic 'create-but-never-close' failure: the main conversation
creates a work-item under work-items/active/<slug>/ (mandated by the Recovery
rule's create step) but the matching close step is never executed, so delivered
items pile up in active/ forever. This hook fires at turn end and BLOCKS the
stop when an active item is actually CLOSED-but-not-MOVED, telling the model to
finish the close (write closure.md if absent, move the folder to
work-items/archive/<YYYY-MM>/<slug>/, and update work-items/index.md).

Why a Stop hook, and why blocking: a warn-only Stop hook is invisible to the
model (only a block reason is surfaced back), and the whole point is that the
text rule alone gets ignored. The detector is deliberately narrow so blocking
only fires on UNAMBIGUOUS orphans:

  An active item is an orphan iff EITHER:
    (1) it contains a closure.md  -> closure was written but the folder was
        never moved out of active/ (the canonical post-rule orphan signal); or
    (2) its status.md has a state/status/stage/outcome LINE whose value begins
        with a done/closed word (closed|done|complete|completed|archived).
        Anchoring to the state-key line -- not a free substring anywhere in the
        file -- is FP-critical: chatty active-item prose like 'nothing pending
        on our side' or 'phase 1 shipped + pushed' must NOT be read as a
        whole-item-done declaration.

A merely-active or parked item (state active/parked/in-progress, no closure.md)
does NOT trigger. Override with
[acknowledge-open-work-items] in the final assistant message for the rare case
where leaving a closed-marked item in active/ is intentional this turn.

Fail-open everywhere: any malformed envelope, missing directory, or internal
error returns 0 (allow), so legitimate work is never blocked by a hook bug.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from hook_common import parse_envelope, read_stdin_utf8

OVERRIDE_MARKER_REGEX = re.compile(r"\[acknowledge-open-work-items\]", re.IGNORECASE)

# An active item counts as closed-but-not-moved when its status.md has a
# state/status/stage/outcome LINE whose VALUE BEGINS with a done/closed word.
# Anchoring to the state-key line (not a free substring anywhere in the file) is
# deliberate and FP-critical: chatty active-item prose like 'nothing pending on
# our side' or 'phase 1 shipped + pushed' must NOT be read as a whole-item-done
# declaration. Tolerates a leading blockquote '>', a bullet marker ('-'/'*'/'+'),
# and bold '*' wrappers (so '> **CURRENT STATE: DONE**' AND the CANONICAL
# status.md marker from subagent-contracts.md, '- **Primary task status**:
# closed', both match); an optional 'current '/'primary task ' modifier before
# the bare key word covers both forms. The trailing (?![\w-]) stops
# 'closed-loop' / 'completed-by' style hyphenated continuations, and the
# trailing negative lookahead excludes a done word that is actually a
# completion CRITERION ('Outcome: complete WHEN all tests pass' is a condition,
# not a whole-item-done declaration) rather than a state. That exclusion tolerates
# closing markdown emphasis ('*'/'**'/'_') and light punctuation (','/'—'/'-')
# between the done word and the conditional keyword -- '[ \t]' alone missed
# 'Outcome: **complete** when ...' and 'Outcome: complete, when ...', which
# still false-fired the orphan block (review-found FP). Bounded to a few
# optional single characters via [ \t]/[*_]{0,2}/[,—-]?, so it can never bleed
# across a newline into an unrelated later clause.
DONE_STATE_LINE_REGEX = re.compile(
    r"(?im)^\s*>?\s*(?:[-*+]\s+)?\*{0,3}\s*(?:current\s+|primary\s+task\s+)?(?:state|status|stage|outcome)"
    r"\s*\*{0,3}\s*:\s*\*{0,3}\s*(?:closed|done|complete|completed|archived)(?![\w-])"
    r"(?![ \t]*[*_]{0,2}[ \t]*[,—-]?[ \t]*(?:when|if|means|когда|если|означает)\b)"
)

# How far up from the session cwd to search for a work-items/active directory.
MAX_PARENTS = 40


def _is_truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _find_active_dir(start: Path) -> Path | None:
    """Walk up from the session cwd to the nearest work-items/active directory,
    stopping at the first ancestor that is itself a repository root (contains
    .git).

    This operator nests projects (Orchestrator/Orchestrarium,
    Orchestrator/benchmarks, ...). Without a repo boundary, an orphan sitting in
    a PARENT directory's work-items/active/ (a different, unrelated project)
    would block every session in every child project once the walk climbed past
    the child repo's own root. Checking the candidate directory BEFORE the
    boundary check means the common case (work-items/active/ living beside .git
    at the repo root) still resolves in one step, whether cwd IS the repo root
    or a subdirectory several levels below it.

    Returns None when no work-items/active directory exists within the current
    repository (or at all, for a session outside any git-tracked project, or
    one that does not use Orchestrarium task memory) -> fail open."""
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


def _read_status(item: Path) -> str:
    status = item / "status.md"
    try:
        if status.is_file():
            return status.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    return ""


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


# --- Epic lifecycle orphans (work-items/epics/) ------------------------------
# The same Stop guard also catches epics that drifted out of sync with their
# children (the docs/epics.md "Known limitation"): a ready-to-close epic that was
# never closed, or a closed epic whose child was reopened. Fail-open when
# work-items/epics/ is absent (it may not exist yet).

EPIC_HEADING_RE = re.compile(r"#{1,6}\s")
EPIC_CHILDREN_HEADING_RE = re.compile(r"##\s+children\b", re.IGNORECASE)
EPIC_CHILD_LINE_RE = re.compile(r"-\s*([A-Za-z0-9][\w.-]*)\s*\((?:active|closed)\)\s*$", re.IGNORECASE)
EPIC_FRONTMATTER_STATUS_RE = re.compile(r"\s*status\s*:\s*([A-Za-z]+)", re.IGNORECASE)


def _epic_status(text: str) -> str | None:
    """Read the epic status from its leading --- ... --- frontmatter ONLY. A body
    line that happens to start with 'status: closed' must NOT be treated as the
    epic status (FP-critical on a blocking hook). Returns None when there is no
    frontmatter status -> the epic is skipped (fail-open)."""
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


def _slug_is_done(active_dir: Path, archive_dir: Path, slug: str) -> bool:
    """A child work-item is done iff it is archived, has closure.md, or its
    status.md carries a bare done-state line — the same predicate used for items,
    resolved across work-items/active/ + work-items/archive/."""
    try:
        for cand in [archive_dir / slug, *archive_dir.glob(f"*/{slug}")]:
            if cand.is_dir():
                return True
    except Exception:
        pass
    item = active_dir / slug
    try:
        if (item / "closure.md").is_file():
            return True
    except Exception:
        pass
    text = _read_status(item)
    return bool(text and DONE_STATE_LINE_REGEX.search(text))


def _parse_epic_children(text: str) -> list[str]:
    """Extract child work-item slugs from the epic file's ## Children section.

    Hardened against false BLOCKs on a closed epic: reset the section on ANY ATX
    heading (so an h3 under ## Children does not keep collecting), and require the
    documented '- <slug> (active|closed)' marker (so a prose note bullet under
    ## Children is not mis-read as a phantom child). Dropping a marker-less child
    line is fail-safe: it can only suppress a flag, never create one."""
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


def _detect_epic_orphans(active_dir: Path) -> list[tuple[str, str]]:
    orphans: list[tuple[str, str]] = []
    epics_dir = active_dir.parent / "epics"
    archive_dir = active_dir.parent / "archive"
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
        all_done = all(_slug_is_done(active_dir, archive_dir, c) for c in children)
        if status == "active" and all_done:
            orphans.append((epic.stem, "all child work-items are closed but the epic is still status: active (close it)"))
        elif status == "closed" and not all_done:
            orphans.append((epic.stem, "epic is status: closed but a child work-item is not closed (reopen the epic)"))
    return orphans


def _block_reason(item_orphans: list[tuple[str, str]], epic_orphans: list[tuple[str, str]]) -> str:
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
        "[acknowledge-open-work-items] in your reply."
    )
    return "\n\n".join(parts)


def main() -> int:
    try:
        envelope = parse_envelope(read_stdin_utf8())
        if not envelope:
            return 0
        # Subagent safety: a subagent's envelope carries `agent_id`; a
        # main-conversation envelope does not (confirmed by captured envelopes
        # on this development line). Work-item lifecycle is owned by the MAIN
        # conversation, never a subagent, so a subagent context must never be
        # blocked here. This hook is also registered ONLY on the Stop event
        # (not SubagentStop); the agent_id skip is belt-and-suspenders so a hook
        # can never interfere with a subagent doing its work.
        if envelope.get("agent_id"):
            return 0
        if _is_truthy(envelope.get("stop_hook_active")):
            return 0  # avoid recursive Stop loops
        # Dispatched-review safety: an external review is not the main
        # conversation and must never be blocked by main-conversation Stop guards.
        if os.environ.get("ORCHESTRARIUM_DISPATCHED_REVIEW"):
            return 0

        last_message = envelope.get("last_assistant_message")
        if isinstance(last_message, str) and OVERRIDE_MARKER_REGEX.search(last_message):
            return 0  # explicit override; allow

        start_raw = envelope.get("cwd") or os.getcwd()
        active_dir = _find_active_dir(Path(str(start_raw)))
        if active_dir is None:
            return 0  # no work-items/active in scope; allow

        item_orphans = _detect_orphans(active_dir)
        epic_orphans = _detect_epic_orphans(active_dir)
        if not item_orphans and not epic_orphans:
            return 0

        print(json.dumps({"decision": "block", "reason": _block_reason(item_orphans, epic_orphans)}))
        return 0
    except Exception:
        return 0  # fail open on any internal error


if __name__ == "__main__":
    sys.exit(main())
