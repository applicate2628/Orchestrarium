#!/usr/bin/env python3
"""SessionStart hook that re-injects the MCP/tools reminder.

Python is the sole runtime owner. The reminder deliberately names no specific
server; the agent discovers connected tools at runtime. The payload comes from
``mcp_continuity_policy.SESSION_START_CONTEXT`` and is emitted through
``hook_common.emit_session_start_context`` with the host's structured
``hookSpecificOutput`` shape.

The hook has no stdin dependency. It emits the same unconditional context for
startup, resume, clear, and compaction, including dispatched subagents. Errors
remain fail-open and the process exits 0.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hook_common import emit_session_start_context
from mcp_continuity_policy import SESSION_START_CONTEXT


def main() -> int:
    emit_session_start_context(SESSION_START_CONTEXT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
