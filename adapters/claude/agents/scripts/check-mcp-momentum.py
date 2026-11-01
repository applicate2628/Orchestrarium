#!/usr/bin/env python3
"""Claude PreToolUse binding for the shared MCP-continuity policy.

The shared policy remains the sole owner of confident source-navigation
classification.  This provider adapter reminds Claude root conversations of
their mandatory duty in effective ``mcpMode: force`` without determining
compliance.  Auto, unresolved modes, and subagents preserve the existing
advisory behavior.  Every failure remains
fail-open so a malformed envelope or unreadable config cannot create a retry
loop.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hook_common import (
    emit_advisory,
    parse_envelope,
    read_stdin_utf8,
)
from agents_mode_runtime import resolve_scalar
from mcp_continuity_policy import (
    classify_tool_choice,
    render_momentum_advisory,
)


def _emit_mode_unresolved(envelope: dict) -> None:
    emit_advisory(
        envelope,
        "[MCP-FORCE-MODE-UNRESOLVED] A qualifying source-navigation choice "
        "was observed, but effective mcpMode is neither force nor auto. The "
        "hook is allowing the choice and is not treating an invalid, missing, "
        "or unreadable value as force.",
    )


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
        emit_advisory(
            envelope,
            "[MCP-FORCE-ADVISORY] Effective mcpMode is force. Runtime tool "
            "discovery, relevant tool schema and fitting MCP use are mandatory, "
            "including selected-root/currentness checks. This source-navigation "
            "heuristic has not determined compliance. Follow the shared MCP-"
            "continuity requirements and existing alternative-path restrictions; "
            "this reminder grants no permission and does not override host refusals.",
        )
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
