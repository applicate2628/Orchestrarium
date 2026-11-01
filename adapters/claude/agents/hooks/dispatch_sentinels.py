"""dispatch_sentinels.py — the dispatch-time invariant registry (extension
seam: dispatch-time invariants get a registry, not a new hook).

WHY THIS MODULE EXISTS. The review-loop runtime owner caps a review family at
3 rounds (`scripts/review_loop_state.py::REVIEW_LOOP_ROUND_CAP`), and one
family ran eight rounds with nothing
firing. The structural reason: the schema validator's only input is a ledger
the observed party itself writes, so a run that writes nothing presents the
validator with nothing to reject (`work-items/bugs/2026-07-26-nothing-
observes-a-review-loop-that-ran-without-a-ledger.md`). This module is the
narrowed, internal-dispatch answer: it counts the ONE quantity the harness
writes and the policed model cannot decline to emit while still dispatching
-- how many times, within the current operator turn, the SAME `subagent_type`
has already been dispatched via the `Agent` tool -- and reports that count to
the model at the moment it decides to dispatch again. It decides nothing
else. Full design: `work-items/active/2026-07-26-registry-bug-sweep/
design-round-cap-observer.md`.

THIS MIRRORS SEAM S1 (`workitem_sentinels.py`) DELIBERATELY. Adding
dispatch-time invariant #2 means appending one more record to `REGISTRY` and
writing its `evaluate(ctx)` function -- nothing else in this file, and
NOTHING outside it, needs to change. The record shape is intentionally
identical: `{id, event, scope, evaluate(ctx) -> Finding | None, exemptions}`.

WHY THIS IS A NEW MODULE RATHER THAN AN ENTRY IN `workitem_sentinels.py`.
Different event (`PreToolUse`, not `Stop`), different ctx (a single dispatch
envelope plus a bounded transcript slice, not a work-items/ traversal), and a
different severity vocabulary (ADVISORY only -- see below). Importing this
module from `workitem_sentinels.py`, or vice versa, would blur two unrelated
event/ctx contracts into one file; keeping them separate is the same
ownership split seam S3 already established between `workitem_sentinels.py`
and its adapter.

SINGLE-TREE, CLAUDE-ONLY, NO MIRROR OBLIGATION. `check-typed-routing.py` (the
adapter this module is imported by) is `PACK_ONLY_HOOKS` for Claude
(`scripts/universal_hooks_manifest.py:65-70`) -- Codex CLI has no analogous
subagent-dispatch tool for either it or this module to observe. This module
is declared in that same `PACK_ONLY_HOOKS` set (see that file) so the
directory-parity gate in `tests/test_universal_hook_surfaces.py` does not
flag it as an undeclared pack-only file; there is no `scripts/universal-
hooks/hooks/` canon copy and no `sync-universal-hooks.py` propagation for
this file, by design.

THE COUNTING KEY -- `(current operator-turn boundary, subagent_type)`, both
runtime-authored (T0). Neither can be reworded: a dispatch cannot happen
without emitting its `tool_use` record, and the turn cannot advance without
the operator typing. A prompt-text-derived key was measured and discarded
(design.md §0.3): median within-role consecutive-dispatch path Jaccard
similarity is 0.00, so genuine review rounds legitimately reword themselves
and a text key is false-negative-prone even against a fully cooperating
actor.

STATE: NONE. The count is recomputed, on every call, from the transcript
between the turn boundary and now (`hook_common.current_turn_entries`'s
bounded reverse read -- 34-62 ms measured at the 8 MiB cap used here, against
the whole-file reader's 2157-2386 ms). No counter file, no ledger, nothing
for the observed party to decline to write.

SEVERITY VOCABULARY. This module emits only `ADVISORY` -- deliberately NOT
`workitem_sentinels.RESOLVE`/`NOTICE`, whose meanings are bound to the `Stop`
adapter's `block`/`systemMessage` payload mapping (a different event, a
different payload contract). Re-typing another module's severity constants
for a different payload contract is exactly law C1's named failure.

RESPONSE: WARN, NEVER BLOCK. The hook knows the count and cannot know
whether these dispatches are rounds on one artifact or genuinely distinct
subjects; the model knows the artifact and measurably does not track the
count. Blocking would require this module to answer a question its own
measurement (design.md §0.3) proves it cannot. Promotion to a blocking tier
is gated behind four pre-registered criteria in design.md §3.4 and is
explicitly NOT authorized by this implementation.

READ-ONLY, ALWAYS. No function in this module writes, moves, deletes, or
renames anything, on any platform, on any code path. The transcript is opened
read-only, seeked, and read within a fixed byte cap. No transcript content is
ever emitted in an advisory message -- only a role name, two integers, and a
fixed citation.

Imports are a closed set: {__future__, pathlib(via hook_common), sys} plus
stdlib builtins -- no new runtime dependency.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from hook_common import current_turn_entries, is_assistant_message  # noqa: E402

# ---------------------------------------------------------------------------
# Severity vocabulary -- ADVISORY only (see module docstring: deliberately NOT
# workitem_sentinels.RESOLVE/NOTICE, a different payload contract).
# ---------------------------------------------------------------------------

ADVISORY = "ADVISORY"


class Finding:
    """One invariant's verdict for this evaluation. `severity` is always
    ADVISORY in this module; a clean invariant returns None, never a Finding
    with a placeholder severity."""

    __slots__ = ("id", "severity", "message")

    def __init__(self, id: str, severity: str, message: str) -> None:
        self.id = id
        self.severity = severity
        self.message = message

    def __repr__(self) -> str:  # pragma: no cover - debug convenience only
        return f"Finding(id={self.id!r}, severity={self.severity!r})"


# ---------------------------------------------------------------------------
# Wire-shape constants for scanning HISTORICAL transcript tool_use blocks.
#
# DISCLOSED DUPLICATION (not silent drift): these two values are the SAME
# Phase-0-captured fact `check-typed-routing.py`'s own DISPATCH_TOOL /
# SUBAGENT_TYPE_FIELD constants name (the subagent-dispatch tool is literally
# "Agent" and carries `subagent_type` in its input) -- but this module cannot
# import them from that adapter. The declared dependency direction is
# adapter -> registry -> hook_common (design.md §8); a registry importing its
# own adapter would invert it. It is ALSO deliberate for failure isolation:
# the adapter's pre-existing typed-routing nudge must keep working even if
# this module is entirely missing or broken (see check-typed-routing.py's
# own try/except around importing this module), so the adapter cannot be
# the sole owner of a constant this module depends on either. Re-pin both
# copies together if a future Claude Code version ever renames the dispatch
# tool or moves the field (matching the adapter's own named-constant
# fail-safe: a mismatch makes the reader inert, never a false block).
AGENT_TOOL_NAME = "Agent"
SUBAGENT_TYPE_KEY = "subagent_type"

# Bounded reverse-read cap for the current-turn scan (design.md §3.6: 8 MiB
# measured at 34-62 ms, against the whole-file reader's 2157-2386 ms on the
# same transcripts). Named separately from
# check-work-items-archival-stop.py's own 64 MiB TRANSCRIPT_OVERRIDE_BYTE_CAP
# -- a different caller with a different measured budget, not a shared
# constant.
TURN_ENTRIES_BYTE_CAP = 8 * 1024 * 1024

# review-loop round cap 3 (review_loop_state.py::REVIEW_LOOP_ROUND_CAP) + 1:
# fire on the
# DISPATCH that would make this the 4th round for one role in one turn. This
# is a NEW, separately named quantity (turn-scoped same-role dispatch depth)
# -- NOT the generic Lead same-role/same-artifact correction-cycle limit.
ROUND_DEPTH_ADVISORY_THRESHOLD = 4

# The shipped round cap, cited in the advisory MESSAGE TEXT only -- never
# re-owned or re-enforced here. ``REVIEW_LOOP_ROUND_CAP`` remains the runtime
# owner; the dedicated drift guard checks this hard-boundary duplicate.
CITED_ROUND_CAP = 3


def _agent_subagent_types(entries: list[dict]) -> list[str]:
    """Every `subagent_type` string carried by an `Agent` tool_use block
    across `entries`, in no particular order (the caller only counts them).
    Reads the SAME `tool_use` block a live PreToolUse envelope's `tool_input`
    is copied verbatim from (Phase-0 capture, `check-typed-routing.py`'s own
    docstring) -- here read from its transcript-recorded form instead of a
    live envelope. Skips anything that is not an assistant-authored tool_use
    block for the named dispatch tool; a malformed block (non-dict `input`,
    absent/non-string `subagent_type`) is silently skipped, never guessed."""
    types: list[str] = []
    for entry in entries:
        if not is_assistant_message(entry):
            continue
        content = entry.get("content") if isinstance(entry, dict) else None
        if content is None and isinstance(entry, dict):
            msg = entry.get("message")
            if isinstance(msg, dict):
                content = msg.get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if not isinstance(item, dict) or item.get("type") != "tool_use":
                continue
            if item.get("name") != AGENT_TOOL_NAME:
                continue
            tool_input = item.get("input")
            if not isinstance(tool_input, dict):
                continue
            subagent_type = tool_input.get(SUBAGENT_TYPE_KEY)
            if isinstance(subagent_type, str) and subagent_type:
                types.append(subagent_type)
    return types


def _is_p4_checkpoint(dispatch_number: int, threshold: int) -> bool:
    """P4 emission policy (design.md §3.5, measured against four real
    transcripts): fire once at the threshold, then re-fire only at each
    doubling beyond it (threshold, 2*threshold, 4*threshold, ...) --
    concretely, with threshold=4: 4, 8, 16, 32, 64, ... This stays silent
    through the depths where a run often ends naturally (5/6/7) and re-fires
    only at genuinely pathological, exponentially rarer depths, matching the
    measured 2.7-8.4% fire rate and the P1 (every dispatch >= 4, up to 29.8%
    on one measured session) / P3 (fires once, then never again -- silent
    from depth 4 all the way to a real depth-23 run) alternatives design.md
    rejected. Depths were measured only up to 23 in this design's own
    four-transcript corpus (below the first re-fire past 32), so firing
    beyond 32 is this implementation's own extrapolation of the stated
    doubling pattern, not itself independently measured -- disclosed rather
    than silently assumed."""
    if dispatch_number < threshold:
        return False
    ratio = dispatch_number // threshold
    if dispatch_number % threshold != 0:
        return False
    return ratio & (ratio - 1) == 0  # ratio is a power of two (1, 2, 4, 8, ...)


def _format_message(subagent_type: str, depth: int, dispatch_number: int) -> str:
    past_cap = dispatch_number - CITED_ROUND_CAP
    plural = "" if depth == 1 else "s"
    return (
        f"[round-depth AUDIT] This turn has already dispatched `{subagent_type}` "
        f"{depth} time{plural}; this is dispatch {dispatch_number}. The shipped "
        f"cap is {CITED_ROUND_CAP} rounds for one role on one artifact "
        "(review-loop.md:45). If these are rounds on one artifact, you are "
        f"{past_cap} past the cap -- stop and escalate the deadlock rather than "
        "dispatching again. If they are separate subjects, this does not apply. "
        "AUDIT -- allowing."
    )


# ---------------------------------------------------------------------------
# build_context -- the single read every registry entry evaluates against.
# ---------------------------------------------------------------------------


def build_context(envelope: dict) -> dict:
    """Build the dispatch-sentinel evaluation context for one PreToolUse
    envelope. Deliberately self-contained (re-derives `subagent_type` from
    the envelope rather than trusting a caller to have already validated it)
    so this module stays independently unit-testable without replaying the
    adapter's own guards."""
    ctx: dict = {
        "subagent_type": None,
        "turn_entries": [],
        "entries_status": "absent",
    }
    if not isinstance(envelope, dict):
        return ctx

    tool_input = envelope.get("tool_input")
    if isinstance(tool_input, dict):
        subagent_type = tool_input.get(SUBAGENT_TYPE_KEY)
        if isinstance(subagent_type, str) and subagent_type:
            ctx["subagent_type"] = subagent_type

    transcript_path = envelope.get("transcript_path") or ""
    if not isinstance(transcript_path, str):
        transcript_path = ""

    entries, status = current_turn_entries(transcript_path, byte_cap=TURN_ENTRIES_BYTE_CAP)
    ctx["turn_entries"] = entries
    ctx["entries_status"] = status
    return ctx


# ---------------------------------------------------------------------------
# SEN-D1 -- round depth. How many times, within the current operator turn,
# this same subagent_type has already been dispatched via the Agent tool.
# ADVISORY tier only -- see module docstring for why this never blocks.
# ---------------------------------------------------------------------------


def _sen_d1_evaluate(ctx: dict) -> Finding | None:
    subagent_type = ctx.get("subagent_type")
    if not subagent_type:
        return None
    # Fail-closed in the SAFE direction (design.md §3.6): a window that
    # misses the turn boundary might span SEVERAL turns and OVER-count, so
    # anything short of a positively located boundary stays silent rather
    # than guessing. This is the only mode that suppresses a genuine
    # detection, and it is the deliberately chosen safe direction.
    if ctx.get("entries_status") != "found":
        return None

    key = subagent_type.strip().casefold()
    depth = sum(
        1
        for observed in _agent_subagent_types(ctx.get("turn_entries") or [])
        if observed.strip().casefold() == key
    )
    dispatch_number = depth + 1
    if not _is_p4_checkpoint(dispatch_number, ROUND_DEPTH_ADVISORY_THRESHOLD):
        return None

    return Finding("SEN-D1", ADVISORY, _format_message(subagent_type, depth, dispatch_number))


# ---------------------------------------------------------------------------
# The registry -- one record per dispatch-time invariant. Adding invariant #2
# means appending one more record here and writing its evaluate(ctx)
# function; nothing else in this file, and nothing outside it, needs to
# change.
# ---------------------------------------------------------------------------

REGISTRY: tuple[dict, ...] = (
    {
        "id": "SEN-D1",
        "event": "PreToolUse",
        "scope": "current operator turn (Agent dispatches of one subagent_type since the last genuine user-typed message)",
        "evaluate": _sen_d1_evaluate,
        "exemptions": "none beyond the adapter's own (agent_id present, tool_name != Agent, subagent_type absent/malformed)",
    },
)


def evaluate_all(ctx: dict, event: str = "PreToolUse") -> list[Finding]:
    """Select every registry entry for `event`, evaluate it against `ctx`,
    and return the non-empty Findings. Per-entry fail-open: one broken
    invariant must not crash the adapter or suppress its siblings (DI-2)."""
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
