#!/usr/bin/env python3
"""Work-item sentinel adapter for the Stop hook.

THIS WRAPPER'S NAME IS A TRUST-PINNED WIRE IDENTIFIER, NOT A LABEL. Codex hook
trust hashes the hooks.json ENTRY (event, matcher, command string, timeout,
async flag, status message, context limit) and never the script file's own
contents (`design.md` §4.3, reproduced 2/2 against the live installed
entries). Renaming this file, or changing the hooks.json command string that
invokes it, would de-trust the entry and go silently dark on the Codex line.
The filename therefore stays `check-work-items-archival-stop` even though it
now hosts TWO invariants, not one -- see `## What this hosts, and why the
name is pinned` below.

WHAT THIS FILE IS: a thin per-event ADAPTER (extension seam S2/S3). It reads
the Stop envelope, builds one evaluation context, asks the invariant registry
in `workitem_sentinels.py` (seam S1 -- the actual root fix) which invariants
fire, and maps their severities onto the runtime's response tiers:

  RESOLVE -> {"decision": "block", "reason": ...}            costs one model turn
  NOTICE  -> {"systemMessage": ...}                            costs none

r7 (T-14, design.md §4.4c/§1.0): a THIRD tier, HALT
(`{"continue": false, "stopReason": ..., "systemMessage": ...}`), was measured
on the Codex line and REMOVED rather than shipped or left dormant: neither
`stopReason` nor `systemMessage` reached the operator inside a HALT payload,
and `--json` mode emitted no hook-status event at all, so a run-terminating
tier there would not merely be unattributed, it would be undetectable. The
three installed copies are byte-identical (G-2), so the tier would be
all-or-nothing across both lines, and the admitted incident happened on the
line where it does not work. The measured facts survive in
`references-codex/stop-hook-halting-primitives.md`, which is their canonical
home; this adapter no longer emits `continue` at all.

WHAT THIS HOSTS, AND WHY THE NAME IS PINNED (F-B3/DI-1 migration note):
  SEN-0 -- archival orphan     (RESOLVE) -- verdict-equivalent migration of
           this hook's ORIGINAL sole behavior; the shipped test suite in
           tests/test_work_items_archival_hook.py must pass unchanged. Its
           marker exemption also reads the operator's own genuine typed
           message (T1, F3), not only the model's last reply.
  SEN-1 -- dual-state item     (RESOLVE) -- new: a work-item slug present in
           BOTH work-items/active/ and work-items/archive/**. Detects the
           incident's temporal origin, on both provider lines.
Both logic bodies live in `workitem_sentinels.py`, imported (never separately
registered) so that adding a third invariant, or a fourth, never touches this
file, the installer, or hooks.json -- and therefore never re-trusts anything
on the Codex line (`design.md` §4.3 consequence 3).

r8 (design.md §0.9): a THIRD invariant, SEN-2 (delivery drought), was CUT
from this release after T-20 measured that a bare `systemMessage` NOTICE does
not reach the operator on the Codex line either -- the same line the
admitted incident happened on -- so the invariant produced nothing
observable there in any posture or band. Combined with the substrate defect
already found (git cannot attribute delivery to an item in the pack's own
default posture) and the coverage gap already named (file count cannot see
in-place revision), it carried more open design debt than the rest of the
design combined. Withdrawn, not narrowed again; re-proposed on a different
substrate (decision `2026-07-26-delivery-drought-needs-a-substrate-not-a-
threshold`, R-9's T0 turn/spend counter). **Only cross-line channel this
adapter emits is now RESOLVE, which addresses the model; every
operator-directed output (the §4.4a escalation, the FM-1 unavailability
notice) is Claude-line only; there is no run-terminating tier on either
line.**

stdin: Stop JSON envelope from Claude Code or Codex.
stdout: a RESOLVE or NOTICE payload (see above) if any invariant fires;
        nothing otherwise. Every text field is capped at 10,000 characters
        (the runtime's own documented limit on `systemMessage` / plain
        stdout) via `_cap_payload_text`, which degrades by dropping whole
        trailing lines and always states how many characters were dropped
        -- never a silent truncation (F10).
exit: always 0 (decision carried by stdout payload, not exit code; fail-open
      on any internal error so legitimate work is never blocked).

`stop_hook_active` is advisory metadata the RUNTIME sets and each hook is
expected to honor itself -- it is NOT an enforced recursion cap (measured:
`True` on 8 of 9 fires in the r3 primitive's own probe while the loop still
reached `num_turns: 10`; design.md §4.2). This adapter honors it by
suppressing every RESOLVE-tier finding (a RESOLVE recurses; a suppressed one
must not re-fire indefinitely) and, per the r5 tier-escalation rule (§4.4a),
additionally emits a turn-free NOTICE for each RESOLVE finding that still
holds -- so a condition the model was already given one continuation for and
did not fix reaches the operator instead of staying model-only forever.

Fail-open everywhere: any malformed envelope, missing directory, unimportable
registry module, or internal error emits nothing (or, for the registry-import
case, a turn-free NOTICE naming the gap) and always exits 0.
"""
from __future__ import annotations

import json
import os
import sys

from hook_common import last_genuine_user_text, parse_envelope, read_stdin_utf8

# design.md §4.5 (F2): the operator-override channel is read via a bounded
# REVERSE scan anchored on the turn boundary, not a fixed-line-count tail --
# see hook_common.last_genuine_user_text's own docstring for why
# `read_transcript_tail` (still used, byte-unchanged, by four OTHER hooks)
# is the wrong tool here. 64 MiB matches the design's own byte_cap.
TRANSCRIPT_OVERRIDE_BYTE_CAP = 64 * 1024 * 1024

# Literal FM-1 discriminator: the sweeper's own `info:` line is a second,
# weaker channel; this NOTICE is the one that reaches the operator on the
# always-on path, with no model turn, the moment the registry cannot be
# imported.
SENTINELS_UNAVAILABLE_NOTICE = "orchestrarium: sentinels unavailable (skipped)"

# F10: the runtime documents a 10,000-character cap on `systemMessage` and
# plain stdout (Claude Code hooks reference, fetched raw this session:
# "Hook output strings, including additionalContext, systemMessage, and plain
# stdout, are capped at 10,000 characters. Output that exceeds this limit is
# saved to a file and replaced with a preview and file path, the same way
# large tool results are handled."). A finding's message grows with the
# number of orphaned items/epics (SEN-0) it reports, not with the fixed,
# small number of registry entries -- so the combined payload is NOT bounded
# by construction and must be capped here, proactively, rather than left to
# whatever fallback (if any) the Codex line applies to an oversized
# `systemMessage`/stdout.
MAX_PAYLOAD_CHARS = 10_000


def _cap_payload_text(text: str, cap: int = MAX_PAYLOAD_CHARS) -> str:
    """Truncate `text` to fit within `cap` characters, degrading
    INFORMATIVELY -- stating how many characters were dropped -- never
    silently. Cuts on the last whole-line boundary inside the budget (never
    mid-word/mid-marker), so a truncated payload can never accidentally
    split, and thereby hide or fabricate, a real override marker such as
    [acknowledge-open-work-items] or [approve-review-continuation]."""
    if len(text) <= cap:
        return text
    notice_template = (
        "\n\n[... TRUNCATED: {dropped} of {total} characters omitted -- "
        "payload exceeded the {cap}-character runtime cap ...]"
    )
    reserve = len(notice_template.format(dropped=len(text), total=len(text), cap=cap))
    budget = max(0, cap - reserve)
    truncated = text[:budget]
    last_newline = truncated.rfind("\n")
    if last_newline > 0:
        truncated = truncated[:last_newline]
    dropped = len(text) - len(truncated)
    notice = notice_template.format(dropped=dropped, total=len(text), cap=cap)
    return truncated + notice


def _is_truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def _format_finding(finding) -> str:
    return f"[{finding.id}] {finding.message}"


def _format_escalation(finding) -> str:
    # r5 tier-escalation rule (§4.4a): the model was already granted a
    # continuation THIS TURN by *a* Stop hook (not necessarily this one, and
    # not necessarily for this finding specifically -- stop_hook_active is a
    # turn-wide flag, not a per-finding one), and the condition still holds.
    # Attribute to the turn, not to "this finding", per the closure review's
    # caution (review-fable-r5-closure.md F-F4).
    return (
        f"[{finding.id}] {finding.message}\n\n"
        "(Escalation: a Stop-hook continuation was already granted this turn "
        "(stop_hook_active), so this RESOLVE-tier finding is not re-issued to "
        "the model again -- it is surfaced here to the operator instead, "
        "because the condition still persists.)"
    )


def _build_payload(findings: list, stop_hook_active: bool) -> dict | None:
    """The severity -> payload mapping (seam S3) and the precedence rule
    (design.md §4.4, amended r7): any (non-suppressed) RESOLVE emits the
    block payload, with any NOTICE text folded into `systemMessage`; else any
    NOTICE alone; else nothing. There is no HALT arm -- r7 removed it (see
    module docstring); a registry entry cannot even construct one, because
    `workitem_sentinels.HALT` no longer exists as a severity constant."""
    import workitem_sentinels as sentinels

    resolves = [f for f in findings if f.severity == sentinels.RESOLVE]
    notices = [f for f in findings if f.severity == sentinels.NOTICE]

    notice_texts = [_format_finding(f) for f in notices]

    if stop_hook_active and resolves:
        # A RESOLVE is a continuation; it must never recurse (§4.2). Escalate
        # each suppressed finding to a turn-free NOTICE instead of dropping it
        # silently (§4.4a / DI-12 / G-13).
        notice_texts.extend(_format_escalation(f) for f in resolves)
        resolves = []

    if resolves:
        payload = {"decision": "block", "reason": _cap_payload_text("\n\n".join(_format_finding(f) for f in resolves))}
        if notice_texts:
            payload["systemMessage"] = _cap_payload_text("\n\n".join(notice_texts))
        return payload

    if notice_texts:
        return {"systemMessage": _cap_payload_text("\n\n".join(notice_texts))}

    return None


def main() -> int:
    try:
        envelope = parse_envelope(read_stdin_utf8())
        if not envelope:
            return 0

        # Subagent safety (T0, adapter-level, suppresses ALL invariants): a
        # subagent's envelope carries `agent_id`; a main-conversation envelope
        # does not. Work-item lifecycle is owned by the MAIN conversation,
        # never a subagent. This hook is registered only on Stop (not
        # SubagentStop); the agent_id skip is belt-and-suspenders.
        if envelope.get("agent_id"):
            return 0

        # Dispatched-review safety (T3 ambient env, adapter-level, suppresses
        # ALL invariants): an external review is not the main conversation and
        # must never be blocked by main-conversation Stop guards. Preserved
        # deliberately, declared, not endorsed -- see design.md §6 and AF-9.
        if os.environ.get("ORCHESTRARIUM_DISPATCHED_REVIEW"):
            return 0

        try:
            import workitem_sentinels as sentinels
        except Exception:
            print(json.dumps({"systemMessage": SENTINELS_UNAVAILABLE_NOTICE}))
            return 0

        stop_hook_active = _is_truthy(envelope.get("stop_hook_active"))
        last_assistant_message = envelope.get("last_assistant_message") or ""
        if not isinstance(last_assistant_message, str):
            last_assistant_message = ""

        transcript_path = envelope.get("transcript_path") or ""
        if not isinstance(transcript_path, str):
            # Codex documents transcript_path as `string | null`; guard the
            # same way last_assistant_message is guarded above rather than
            # assume the envelope always types it as a string.
            transcript_path = ""
        # design.md §0.9.4 / §4.5 (F3's T1 widening for SEN-0): a BOUNDED
        # REVERSE SCAN to the turn boundary, not read_transcript_tail's fixed
        # 100-line window -- measured to miss the operator's own message in
        # 36.8% of real turns, which would leave SEN-0's newly-added operator
        # marker channel failing better than a third of the time (a
        # half-fix). An absent/unreadable transcript degrades gracefully
        # here (empty text -> no marker match -> no exemption) exactly like
        # the pack's other transcript-reading hooks (check-bugfix-
        # discipline.py, check-git-push-gate.py, check-repository-
        # orientation.py) fail open on the same condition. The read-status
        # half of this helper's return value has no live consumer after
        # SEN-2's cut (it existed only to feed SEN-2's override-channel
        # discriminator) and is intentionally discarded.
        user_message_text, _user_message_status = last_genuine_user_text(
            transcript_path, byte_cap=TRANSCRIPT_OVERRIDE_BYTE_CAP
        )

        start_raw = envelope.get("cwd") or os.getcwd()
        ctx = sentinels.build_context(
            str(start_raw),
            last_assistant_message=last_assistant_message,
            user_message_text=user_message_text,
        )

        findings = sentinels.evaluate_all(ctx, event="Stop")
        if not findings:
            return 0

        payload = _build_payload(findings, stop_hook_active)
        if payload is not None:
            print(json.dumps(payload))
        return 0
    except Exception:
        return 0  # fail open on any internal error


if __name__ == "__main__":
    sys.exit(main())
