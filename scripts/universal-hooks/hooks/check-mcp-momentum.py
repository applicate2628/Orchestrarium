#!/usr/bin/env python3
"""PreToolUse adapter for the shared MCP-continuity policy.

The semantic classifier and advisory live in the sibling ``scripts`` policy
module.  This adapter owns only the runtime envelope and model-visible delivery.
It is warn-only, fail-open, and never returns the blocking exit code 2.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from hook_common import emit_advisory, parse_envelope, read_stdin_utf8
from mcp_continuity_policy import (
    classify_tool_choice,
    render_momentum_advisory,
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
        emit_advisory(envelope, render_momentum_advisory())
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
