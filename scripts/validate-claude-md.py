#!/usr/bin/env python3
"""Validate the always-loaded Claude Code entrypoint size and rule manifest.

The post-extraction cap is the freshly verified 36,271-unit binding size plus
an exact 500-unit guard after the maintainer narrative moved to
references-claude/claude-md-structural-enforcement.md.  The inclusive 250-unit
warning band begins at 36,521, leaving 250 units between the live source and
the first warning.  The binding metric conservatively uses the larger of
Unicode code points and UTF-8 bytes because the upstream warning unit is not
empirically pinned in this repository.
"""

from __future__ import annotations

import argparse
from pathlib import Path


SIZE_CAP = 36_771
WARNING_BAND = 250

INSTALL_ANCHORS = (
    "@AGENTS.md",
    "## Delegation rule",
    "## Publication safety scan",
)

BOOTSTRAP_TEETH = (
    "STOP. Universal premise rule first",
    "**(a0) Pre-action orientation trigger**",
    "**(a) Pre-fix trigger**",
    "**(b) Pre-commit trigger**",
    "REPOSITORY ORIENTATION: scope=",
    "**Diagnostic data.**",
    "**Hypothesis inventory.**",
    "ASSUMPTION (UNVERIFIED)",
    "**Scope proportionality.**",
    "Fix means correct logic, not workaround",
    "**Recovery readiness.**",
    "most likely means",
    "while I'm here let me also",
    "I'll just commit this and we can fix it if wrong",
)

STRUCTURAL_ENFORCEMENT_TEETH = (
    "They are backstops; they do not replace the text rules above.",
    "prompts should allow relevant MCP use",
    "gate captures and directly executes the verified",
    "a subagent must never be blocked",
    "This exemption never transfers ownership: the dispatching main conversation still owns diagnostic discipline and publication authorization",
    "Transcript/manual results cannot authorize",
    "Stop hooks do not replace the main conversation's current-turn status checks or work-item close/archive ownership",
    "Reminder hooks re-anchor Model Context Protocol (MCP) discovery/use after compaction, active delegation/recovery, scratch preservation, and every-turn continuity",
    "AUDIT mode",
    "fail-open",
    "[skip-bugfix-discipline]` bypasses the PreToolUse guard for the next turn",
    "[approve-publication]` opens the git-push gate for one turn — honored ONLY when it appears in the user's own last message",
    "[acknowledge-passive-stop]` bypasses one passive-polling Stop decision when the assistant is intentionally handing off to the user",
    "Physical location owns lifecycle membership",
)

DELEGATION_AND_RECOVERY_TEETH = (
    "/agents-init-project",
    "externalProvider: auto | codex | claude | gemini | qwen",
    "Gemini and Qwen are `WEAK MODEL / NOT RECOMMENDED`",
    "never a provider entry inside `externalPriorityProfiles`",
    "Every specialist invocation MUST use the Agent tool",
    "Lead is never spawned as a subagent",
    "The main conversation owns `work-items/`",
    "**Close is mandatory.**",
)

ROUTING_AND_ROLE_TEETH = (
    "## Slash command auto-invocation",
    "**Auto-invocation contract:**",
    "**Dispatch index**",
    "## Coexistence with the superpowers plugin",
    "New feature, exploration, or unclear request → invoke `brainstorming` first, then pick a template.",
    "Already in mid-flow with admitted scope",
    "## Role definitions",
    "Pre-publication scan: run `/agents-check-safety`",
)

MANIFEST: dict[str, tuple[str, ...]] = {
    "install anchors": INSTALL_ANCHORS,
    "bootstrap teeth": BOOTSTRAP_TEETH,
    "structural-enforcement teeth": STRUCTURAL_ENFORCEMENT_TEETH,
    "delegation and recovery teeth": DELEGATION_AND_RECOVERY_TEETH,
    "routing and role teeth": ROUTING_AND_ROLE_TEETH,
}


def validate(claude_md: Path, size_cap: int = SIZE_CAP) -> tuple[bool, list[str]]:
    """Return a fail-closed result and human-readable validation messages."""
    if not claude_md.is_file():
        return False, [f"FAIL: Claude Markdown file not found: {claude_md}"]

    try:
        raw = claude_md.read_bytes()
    except OSError as exc:
        return False, [f"FAIL: unable to read Claude Markdown: {claude_md}: {exc}"]

    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        return False, [f"FAIL: Claude Markdown is not valid UTF-8: {exc}"]

    code_points = len(text)
    utf8_bytes = len(raw)
    binding_size = max(code_points, utf8_bytes)
    warning_threshold = size_cap - WARNING_BAND
    messages = [
        f"Code points: {code_points}",
        f"UTF-8 bytes: {utf8_bytes}",
        f"Binding size: {binding_size}",
        f"Size cap: {size_cap}",
        f"Warning threshold: {warning_threshold}",
    ]
    ok = True

    if binding_size > size_cap:
        ok = False
        messages.append(
            f"FAIL: Claude Markdown binding size {binding_size} > size cap {size_cap}"
        )
    elif binding_size >= warning_threshold:
        messages.append(
            f"WARNING: binding size {binding_size} is in warning band "
            f"[{warning_threshold}, {size_cap}]"
        )
    else:
        messages.append(
            f"PASS: Claude Markdown binding size {binding_size} is below "
            f"warning threshold {warning_threshold}"
        )

    total_missing = 0
    for group, tokens in MANIFEST.items():
        missing = [token for token in tokens if token not in text]
        total_missing += len(missing)
        if missing:
            ok = False
            messages.append(f"FAIL: missing {len(missing)}/{len(tokens)} [{group}]:")
            messages.extend(f"         - {token}" for token in missing)
        else:
            messages.append(f"PASS: all {len(tokens)} present [{group}]")

    pinned = sum(len(tokens) for tokens in MANIFEST.values())
    messages.append(f"Manifest: {pinned - total_missing}/{pinned}")
    return ok, messages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    repo_root = Path(__file__).resolve().parent.parent
    parser.add_argument(
        "--claude-md",
        type=Path,
        default=repo_root / "src.claude" / "CLAUDE.md",
        help="Claude Code entrypoint to validate (default: src.claude/CLAUDE.md).",
    )
    parser.add_argument(
        "--size-cap",
        type=int,
        default=SIZE_CAP,
        help=(
            "Maximum max(code points, UTF-8 bytes) value "
            f"(post-extraction default: {SIZE_CAP})."
        ),
    )
    args = parser.parse_args(argv)

    ok, messages = validate(args.claude_md, args.size_cap)
    print(f"=== Claude Markdown validation ({args.claude_md}) ===")
    for message in messages:
        print(message)
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
