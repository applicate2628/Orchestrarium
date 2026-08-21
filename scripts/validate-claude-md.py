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
import hashlib
import re
from pathlib import Path


SIZE_CAP = 36_771
WARNING_BAND = 250

REFERENCE_PAYLOAD_BEGIN = re.compile(
    rb"<!-- BEGIN ORCHESTRARIUM PAYLOAD: ([a-z0-9-]+) -->\r?\n"
)
REFERENCE_PAYLOAD_END = re.compile(
    rb"<!-- END ORCHESTRARIUM PAYLOAD: ([a-z0-9-]+) -->"
)
HOOK_SCRIPT_NAME = re.compile(r"\bcheck-[A-Za-z0-9_-]+\.py\b")
STATUS_ID = re.compile(r"\b[A-Z][A-Z0-9]*(?:-[A-Z0-9]+){2,}\b")
USER_CONTROL_MARKER = re.compile(
    r"\[(?:approve|skip|acknowledge|revoke)[^\]\r\n]*\]"
)
RU_HOOK_BEHAVIOR_PAYLOAD_PIN = (
    22_849,
    "37bcf9b3f9d904eb0f1d3235b515e2c1dfa29508883002b9b9c55bf3ebc97aea",
)

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


def _read_reference(path: Path, label: str) -> tuple[bytes | None, str | None, list[str]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, None, [f"FAIL CRM-REFERENCE-READ: {label}: {exc}"]
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        return None, None, [f"FAIL CRM-REFERENCE-UTF8: {label}: {exc}"]
    return raw, text, []


def _payload_inventory(raw: bytes) -> tuple[tuple[str, ...], dict[str, bytes] | None]:
    begins = tuple(
        match.group(1).decode("ascii") for match in REFERENCE_PAYLOAD_BEGIN.finditer(raw)
    )
    ends = tuple(
        match.group(1).decode("ascii") for match in REFERENCE_PAYLOAD_END.finditer(raw)
    )
    if begins != ends or len(begins) != len(set(begins)):
        return begins, None

    payloads: dict[str, bytes] = {}
    for payload_id in begins:
        begin = re.compile(
            rb"<!-- BEGIN ORCHESTRARIUM PAYLOAD: "
            + re.escape(payload_id.encode("ascii"))
            + rb" -->\r?\n"
        ).search(raw)
        end_marker = (
            f"<!-- END ORCHESTRARIUM PAYLOAD: {payload_id} -->".encode("ascii")
        )
        if begin is None:
            return begins, None
        finish = raw.find(end_marker, begin.end())
        if finish < 0:
            return begins, None
        payloads[payload_id] = raw[begin.end() : finish]
    return begins, payloads


def validate_reference_mirror(
    english_reference: Path,
    russian_reference: Path,
) -> tuple[bool, list[str]]:
    """Validate the mechanical contract shared by the English and Russian references."""
    en_raw, en_text, messages = _read_reference(english_reference, "English reference")
    ru_raw, ru_text, ru_messages = _read_reference(russian_reference, "Russian reference")
    messages.extend(ru_messages)
    if en_raw is None or en_text is None or ru_raw is None or ru_text is None:
        return False, messages

    en_ids, en_payloads = _payload_inventory(en_raw)
    ru_ids, ru_payloads = _payload_inventory(ru_raw)
    ok = True
    if en_payloads is None or ru_payloads is None:
        ok = False
        messages.append("FAIL CRM-PAYLOAD-BOUNDARY: malformed or duplicate payload boundary")
    if en_ids != ru_ids:
        ok = False
        messages.append(
            "FAIL CRM-PAYLOAD-ID-SET: English/Russian payload order or identity differs"
        )
    else:
        messages.append(f"PASS: Claude reference mirror payloads {len(en_ids)}/{len(en_ids)}")

    en_hooks = set(HOOK_SCRIPT_NAME.findall(en_text))
    ru_hooks = set(HOOK_SCRIPT_NAME.findall(ru_text))
    if en_hooks != ru_hooks:
        ok = False
        messages.append("FAIL CRM-HOOK-NAME-SET: English/Russian hook names differ")
    else:
        messages.append(f"PASS: Claude reference mirror hooks {len(en_hooks)}/{len(en_hooks)}")

    en_statuses = set(STATUS_ID.findall(en_text))
    ru_statuses = set(STATUS_ID.findall(ru_text))
    if en_statuses != ru_statuses:
        ok = False
        messages.append("FAIL CRM-STATUS-ID-SET: English/Russian status IDs differ")
    else:
        messages.append(
            f"PASS: Claude reference mirror status IDs {len(en_statuses)}/{len(en_statuses)}"
        )

    en_markers = set(USER_CONTROL_MARKER.findall(en_text))
    ru_markers = set(USER_CONTROL_MARKER.findall(ru_text))
    if en_markers != ru_markers:
        ok = False
        messages.append("FAIL CRM-USER-MARKER-SET: English/Russian user markers differ")
    else:
        messages.append(
            f"PASS: Claude reference mirror user markers {len(en_markers)}/{len(en_markers)}"
        )

    ru_hook_payload = (
        None if ru_payloads is None else ru_payloads.get("hook-behavior-contracts")
    )
    expected_size, expected_sha256 = RU_HOOK_BEHAVIOR_PAYLOAD_PIN
    if (
        ru_hook_payload is None
        or len(ru_hook_payload) != expected_size
        or hashlib.sha256(ru_hook_payload).hexdigest() != expected_sha256
    ):
        ok = False
        messages.append(
            "FAIL CRM-RU-HOOK-PAYLOAD-PIN: Russian hook-behavior-contracts "
            "payload changed without a reviewed pin update"
        )
    else:
        messages.append("PASS: Russian hook-behavior-contracts payload pin")

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
    parser.add_argument(
        "--reference",
        type=Path,
        default=repo_root / "references-claude" / "claude-md-structural-enforcement.md",
        help="English structural-enforcement maintainer reference.",
    )
    parser.add_argument(
        "--ru-reference",
        type=Path,
        default=(
            repo_root
            / "references-claude"
            / "ru"
            / "claude-md-structural-enforcement.md"
        ),
        help="Russian structural-enforcement maintainer reference.",
    )
    args = parser.parse_args(argv)

    ok, messages = validate(args.claude_md, args.size_cap)
    mirror_ok, mirror_messages = validate_reference_mirror(
        args.reference, args.ru_reference
    )
    ok = ok and mirror_ok
    messages.extend(mirror_messages)
    print(f"=== Claude Markdown validation ({args.claude_md}) ===")
    for message in messages:
        print(message)
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
