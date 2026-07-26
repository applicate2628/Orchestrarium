#!/usr/bin/env python3
"""MCP-momentum nudge for the PreToolUse hook — AUDIT mode (never blocks).

WHY THIS EXISTS, AND WHY IT IS NOT A SessionStart REMINDER.
The pack already ships `mcp-usage-reminder` on SessionStart. It fires once per
session/compaction, and its own text pleads "do not forget MCP just because the
context was summarized". It is forgotten anyway. The operator's report was blunt:
"постоянно забывают использовать mcp (после того как я напомню, какое-то время
используют потом снова сваливаются)".

The mechanism is NOT distance-from-injection, and getting that wrong is what made
the first fix attempt useless. First-person evidence from the session that wrote
this hook: the reminder never left the context window — it was present, verbatim,
the whole time. What happened is that ~100 consecutive shell calls all SUCCEEDED,
so no error ever prompted reconsideration, and the next tool choice came from the
momentum of the last fifty actions rather than from a rule sitting quietly in
context. Recency and repetition beat text.

That is why this is a PreToolUse hook and not another reminder: the failure moment
is the TOOL CHOICE, mid-turn. A UserPromptSubmit anchor fires at turn start and
decays inside a long turn exactly as SessionStart decays across a session. Only a
hook at the decision point reaches it.

SCOPE — deliberately narrow, because a nudge that fires on every read is noise and
noise trains the reader to ignore the whole class (the same reason the pack refuses
a "find all literals" validator):
  * only the code-NAVIGATION shapes: a symbol/definition/reference hunt across the
    tree, i.e. Grep with a code-ish pattern, or a shell `grep -r`/`rg` over source.
  * never a targeted read of a known file, never a content search in docs/scratch.
  * only when a code-intelligence MCP is actually configured for this user — an
    unconditional nudge would be a lie on a machine without one.

AUDIT mode: ALWAYS allow the tool call, never block. On a nudge, deliver the
warning to the MODEL via `hookSpecificOutput.additionalContext` on stdout, exit
0 (see `hook_common.emit_advisory`). This is the corrected delivery channel: a
PreToolUse hook's previous stderr-plus-exit-1 form was measured to reach NOBODY
on either Claude Code 2.1.220 (transcript-only, model-invisible) or Codex CLI
0.145.0 (discarded entirely -- the non-2-exit branch never copies stderr). See
work-items/bugs/2026-07-26-mcp-reminder-uses-the-once-per-session-form-its-
sibling-calls-broken.md for the full falsification-controlled measurement. The
pack's promotion discipline is dry-run first, measure the false-positive rate,
then decide block-vs-warn -- a silent audit would make that measurement
impossible, the same defect the sibling machine-local-path / no-trash-in-repo /
stale-relation-residue audits had before this fix. Three blocking-hook false
positives were paid for by the operator in a single session; a nudge that
cannot block (never exit 2) cannot repeat that.

Fail-open everywhere on internal error (return 0).
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

try:
    from hook_common import emit_advisory, parse_envelope, read_stdin_utf8
except Exception:  # pragma: no cover - fail open when the shared helper is absent
    def read_stdin_utf8() -> str:  # type: ignore[misc]
        return ""

    def parse_envelope(_: str) -> dict:  # type: ignore[misc]
        return {}

    def emit_advisory(_envelope: object, _message: str, **_kwargs: object) -> None:  # type: ignore[misc]
        pass


# A code-intelligence server is one that answers "where is this symbol / who calls
# it / what does this file mean" better than a text scan. Matched against the user's
# configured MCP server names, so the hook stays silent on a machine without one.
CODE_INTEL_HINTS = (
    "codegraph",
    "serena",
    "language-server",
    "lsp",
    "repomix",
)

# Shapes that mean "I am hunting for code", not "I am reading a file I already know".
CODE_PATTERN_RE = re.compile(
    r"(def |class |function |func |impl |interface |struct |"
    r"import |from \w+ import|require\(|#include|"
    r"\bcall(er|ee)s?\b|\bdefinition\b|\breferences?\b)",
    re.IGNORECASE,
)
SHELL_TREE_SEARCH_RE = re.compile(
    r"\b(?:grep|rg|ag|ack)\b[^|;]*?(?:\s-\w*r\w*\b|\s--recursive\b|\s--include\b)",
)
CODE_GLOB_RE = re.compile(r"\.(?:py|ts|tsx|js|jsx|go|rs|c|h|cpp|hpp|java|cs|rb|php)\b")


def _configured_code_intel_servers() -> list[str]:
    """Names of code-intelligence MCP servers this user actually has configured.

    Reads the user's own config; a hardcoded server list would be wrong to ship
    (the same reason `mcp-usage-reminder` names no server). Probes BOTH
    platforms' global config locations this hook is installed into: Claude
    Code's `~/.claude.json` / `~/.claude/settings.json` (`mcpServers` JSON
    object) and Codex CLI's `~/.codex/config.toml` (`[mcp_servers.<name>]`
    TOML tables, per https://learn.chatgpt.com/codex/extend/mcp) -- so this
    hook is not silently inert on the Codex pack it also ships into. TOML
    parsing needs `tomllib` (Python 3.11+, stdlib); an older interpreter just
    skips the Codex probe rather than crashing, matching the fail-open
    posture of the JSON probe above it.
    """
    found: list[str] = []
    home = Path(os.path.expanduser("~"))
    for candidate in (
        home / ".claude.json",
        home / ".claude" / "settings.json",
    ):
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception:
            continue
        servers = data.get("mcpServers")
        if isinstance(servers, dict):
            for name in servers:
                low = str(name).casefold()
                if any(hint in low for hint in CODE_INTEL_HINTS):
                    found.append(str(name))

    try:
        import tomllib
    except Exception:
        tomllib = None  # Python < 3.11: skip the Codex probe, do not crash
    if tomllib is not None:
        try:
            with (home / ".codex" / "config.toml").open("rb") as fh:
                codex_data = tomllib.load(fh)
        except Exception:
            codex_data = None
        if isinstance(codex_data, dict):
            codex_servers = codex_data.get("mcp_servers")
            if isinstance(codex_servers, dict):
                for name in codex_servers:
                    low = str(name).casefold()
                    if any(hint in low for hint in CODE_INTEL_HINTS):
                        found.append(str(name))

    return sorted(set(found))


def _looks_like_code_navigation(tool_name: str, tool_input: dict) -> bool:
    if tool_name == "Grep":
        pattern = str(tool_input.get("pattern") or "")
        glob = str(tool_input.get("glob") or "")
        type_ = str(tool_input.get("type") or "")
        if not pattern:
            return False
        if type_ or CODE_GLOB_RE.search(glob):
            return True
        return bool(CODE_PATTERN_RE.search(pattern))
    if tool_name == "Bash":
        command = str(tool_input.get("command") or "")
        if not SHELL_TREE_SEARCH_RE.search(command):
            return False
        return bool(CODE_GLOB_RE.search(command) or CODE_PATTERN_RE.search(command))
    return False


def main() -> int:
    try:
        envelope = parse_envelope(read_stdin_utf8())
    except Exception:
        return 0
    if not isinstance(envelope, dict):
        return 0
    # A dispatched subagent runs its own tool policy; the nudge is for the
    # orchestrating session that chooses between MCP and a text scan.
    if envelope.get("agent_id"):
        return 0

    tool_name = str(envelope.get("tool_name") or "")
    tool_input = envelope.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0

    try:
        if not _looks_like_code_navigation(tool_name, tool_input):
            return 0
        servers = _configured_code_intel_servers()
        if not servers:
            return 0  # nothing better is available; a nudge would be a lie
        # Name a few, not all: a real host has a dozen, and a wall of server names is
        # exactly the noise this hook exists to avoid.
        shown = ", ".join(servers[:3])
        if len(servers) > 3:
            shown += f" (+{len(servers) - 3} more)"
        emit_advisory(
            envelope,
            "[mcp-momentum AUDIT] this looks like a code-navigation search, and a "
            f"code-intelligence MCP is configured: {shown}. "
            "A text scan finds strings; those answer symbols, callers, and "
            "definitions. Load the tool schema (ToolSearch) and ask it, or proceed "
            "if the text scan is genuinely the right instrument here. "
            "(Fired at the tool choice on purpose: the once-per-session reminder "
            "loses to the momentum of your last fifty calls. AUDIT mode -- allowing.)",
        )
        # Exit 0: the advisory reaches the model via hookSpecificOutput.
        # additionalContext (see hook_common.emit_advisory) -- never exit 2 (block).
        return 0
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
