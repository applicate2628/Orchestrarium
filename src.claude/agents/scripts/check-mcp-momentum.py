#!/usr/bin/env python3
"""Claude PreToolUse binding for the shared MCP-continuity policy.

The shared policy remains the sole owner of confident source-navigation
classification.  This provider adapter binds only Claude
root conversations in effective ``mcpMode: force``.  Auto, unresolved modes,
and subagents preserve the existing advisory behavior.  Every failure remains
fail-open so a malformed envelope or unreadable config cannot create a retry
loop.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hook_common import (
    STATUS_FOUND,
    emit_advisory,
    last_genuine_user_text,
    parse_envelope,
    read_stdin_utf8,
)
from agents_mode_runtime import resolve_scalar
from mcp_continuity_policy import (
    classify_tool_choice,
    render_momentum_advisory,
)


RECOVERY_MARKER = "[approve-mcp-fallback:v1]"
TRANSCRIPT_BYTE_CAP = 4 * 1024 * 1024


def _emit_deny(envelope: dict) -> None:
    event = envelope.get("hook_event_name")
    if not isinstance(event, str) or not event:
        event = "PreToolUse"
    reason = (
        "[MCP-FORCE-1] Effective mcpMode is force and this root source-"
        "navigation choice requires an MCP checkpoint. Use runtime tool discovery "
        "as the only availability source and query the relevant tool now. If the MCP "
        "path is unavailable or inappropriate, the exact host-projected "
        f"user-role message {RECOVERY_MARKER} enables one recovery turn; it "
        "is not authenticated authorization."
    )
    payload = {
        "hookSpecificOutput": {
            "hookEventName": event,
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(payload, ensure_ascii=True))


def _emit_recovery(envelope: dict) -> None:
    emit_advisory(
        envelope,
        "[MCP-FORCE-RECOVERY] The exact host-projected user-role recovery "
        "marker allows this qualifying search. It excludes assistant/tool-text "
        "injection but is not authenticated authorship, changes no "
        "configuration, and expires at the next projected user-role message.",
    )


def _emit_mode_unresolved(envelope: dict) -> None:
    emit_advisory(
        envelope,
        "[MCP-FORCE-MODE-UNRESOLVED] A qualifying source-navigation choice "
        "was observed, but effective mcpMode is neither force nor auto. The "
        "hook is allowing the choice and is not treating an invalid, missing, "
        "or unreadable value as force.",
    )


def _exact_projected_user_recovery_marker(envelope: dict) -> bool:
    transcript_path = envelope.get("transcript_path")
    if not isinstance(transcript_path, str) or not transcript_path:
        return False
    text, status = last_genuine_user_text(
        transcript_path, byte_cap=TRANSCRIPT_BYTE_CAP
    )
    return status == STATUS_FOUND and text == RECOVERY_MARKER


def main() -> int:
    try:
        envelope = parse_envelope(read_stdin_utf8())
        if not isinstance(envelope, dict):
            return 0
        tool_input = envelope.get("tool_input")
        if not isinstance(tool_input, dict):
            return 0
        tool_name = str(envelope.get("tool_name") or "")
        if not classify_tool_choice(tool_name, tool_input, envelope.get("cwd")):
            return 0

        if "agent_id" in envelope:
            emit_advisory(envelope, render_momentum_advisory())
            return 0

        mode = resolve_scalar("mcpMode")
        if mode == "auto":
            emit_advisory(envelope, render_momentum_advisory())
            return 0
        if mode != "force":
            _emit_mode_unresolved(envelope)
            return 0
        if _exact_projected_user_recovery_marker(envelope):
            _emit_recovery(envelope)
            return 0
        _emit_deny(envelope)
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
