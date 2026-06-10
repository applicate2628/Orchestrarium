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
# declaration. Tolerates a leading blockquote '>' and bold '*' wrappers (so
# '> **CURRENT STATE: DONE**' matches); the trailing (?![\w-]) stops
# 'closed-loop' / 'completed-by' style hyphenated continuations.
DONE_STATE_LINE_REGEX = re.compile(
    r"(?im)^\s*>?\s*\*{0,3}\s*(?:current\s+)?(?:state|status|stage|outcome)"
    r"\s*\*{0,3}\s*:\s*\*{0,3}\s*(?:closed|done|complete|completed|archived)(?![\w-])"
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
    """Walk up from the session cwd to the nearest work-items/active directory.

    Returns None when no such directory exists in any ancestor (e.g. a session
    for a project that does not use Orchestrarium task memory) -> fail open."""
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


def _block_reason(orphans: list[tuple[str, str]]) -> str:
    lines = "\n".join(f"  - {name}: {why}" for name, why in orphans)
    return (
        "work-items archival Stop guard: one or more delivered/closed work-items "
        "are still sitting in work-items/active/ instead of being archived:\n\n"
        f"{lines}\n\n"
        "The Recovery rule's close step is as mandatory as the create step: a "
        "delivered item must not be left in active/. Before stopping, pick one:\n\n"
        "  (a) Close each item now: write closure.md (outcome, residual risk, "
        "archive location) if it is absent, move the folder to "
        "work-items/archive/<YYYY-MM>/<slug>/, and move its row in "
        "work-items/index.md from Active to Archived.\n\n"
        "  (b) If leaving a closed-marked item in active/ is intentional this "
        "turn (e.g. closure.md is written but the archive move is deferred for a "
        "stated reason), include [acknowledge-open-work-items] in your reply."
    )


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

        last_message = envelope.get("last_assistant_message")
        if isinstance(last_message, str) and OVERRIDE_MARKER_REGEX.search(last_message):
            return 0  # explicit override; allow

        start_raw = envelope.get("cwd") or os.getcwd()
        active_dir = _find_active_dir(Path(str(start_raw)))
        if active_dir is None:
            return 0  # no work-items/active in scope; allow

        orphans = _detect_orphans(active_dir)
        if not orphans:
            return 0

        print(json.dumps({"decision": "block", "reason": _block_reason(orphans)}))
        return 0
    except Exception:
        return 0  # fail open on any internal error


if __name__ == "__main__":
    sys.exit(main())
