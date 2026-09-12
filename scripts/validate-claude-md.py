#!/usr/bin/env python3
"""Validate the composed shared-governance plus thin Claude entrypoint pair."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path


SIZE_CAP = 8_192
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
    24_671,
    "99b488a90b99f165bef799a84e966b0f23bcdfcee655d9fa7f4885ddcde81053",
)

SHARED_MANIFEST: dict[str, tuple[str, ...]] = {
    "shared owners": (
        "# Shared Governance",
        "## Role index",
        "## Common skills",
        "### Physical lifecycle V1",
        "### Session persistence rule (mandatory)",
        "## Core delegation principles",
        "## Engineering hygiene",
        "## Publication safety",
    ),
    "shared gates": (
        "`quick-fix`: target+steps",
        "before QA across phases/specialists, assign one integration owner",
        "**Repository orientation; Mechanism inventory before new paths:**",
        "REPOSITORY ORIENTATION: scope=<repo-relative path>; status=<live|mutable|frozen|archived|deprecated|superseded|conflict>; workflow=<repo-relative entry point(s)>; protected=<repo-relative path(s)|none>; evidence=<path:line[,path:line...]>",
        "**Hypothesis disclosure discipline:**",
        "**Pre-fix diagnostic gate:**",
        "**Evidence-based completion:**",
        "Human review before",
    ),
}

CLAUDE_MANIFEST: dict[str, tuple[str, ...]] = {
    "Claude tool mapping": (
        "## Claude tool mapping",
        "`Bash|PowerShell`",
        "`Edit|Write|NotebookEdit`",
        "commits apply all shared checkpoints",
    ),
    "Claude hooks": (
        "auto-installs thirteen `settings.json` entries",
        "nine structural hooks",
        "They are backstops; they do not replace `AGENTS.md`",
        "a subagent must never be blocked",
        "The first other valid root final receives one reconciliation pass",
        "`stop_hook_active` allows the next Stop",
        "[skip-bugfix-discipline]",
        "[approve-publication]",
        "[approve-mcp-fallback:v1]",
        "[acknowledge-passive-stop]",
    ),
    "Claude delegation": (
        "/agents-init-project",
        "externalProvider: auto | codex | claude | kimi | grok",
        "Every specialist invocation uses the Agent tool",
        "matching `subagent_type`",
        "curated inline role identities",
        "Lead is never spawned as a subagent",
        "requiresLead",
        "general-purpose",
        "approved thin wrapper",
        "independently verified and nonauthorizing",
        "Grok remains unavailable",
    ),
    "Claude commands and roles": (
        "## Slash command routing",
        ".claude/agents/team-templates/",
        ".claude/commands/agents-help.md",
        "Each command file owns its `## When to auto-invoke` rules",
        "## Role definitions",
        "initialPrompt: /lead",
        "Evaluate the shared `quick-fix` predicate before invoking a process skill",
        "process skills govern method; Orchestrarium governs delegation",
        "Pre-publication scan: run `/agents-check-safety`",
    ),
}

H2_HEADING = re.compile(r"^## [^\r\n]+", re.MULTILINE)


def _read_utf8(path: Path, label: str) -> tuple[bytes | None, str | None, list[str]]:
    if not path.is_file():
        return None, None, [f"FAIL: {label} file not found: {path}"]
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, None, [f"FAIL: unable to read {label}: {path}: {exc}"]
    try:
        return raw, raw.decode("utf-8", errors="strict"), []
    except UnicodeDecodeError as exc:
        return None, None, [f"FAIL: {label} is not valid UTF-8: {exc}"]


def validate(
    claude_md: Path,
    agents_md: Path,
    size_cap: int = SIZE_CAP,
) -> tuple[bool, list[str]]:
    """Return a fail-closed verdict for both semantic owners and their composition."""
    raw, text, messages = _read_utf8(claude_md, "Claude Markdown")
    _agents_raw, agents_text, agents_messages = _read_utf8(
        agents_md, "shared AGENTS Markdown"
    )
    messages.extend(agents_messages)
    if raw is None or text is None or agents_text is None:
        return False, messages

    code_points = len(text)
    utf8_bytes = len(raw)
    binding_size = max(code_points, utf8_bytes)
    warning_threshold = size_cap - WARNING_BAND
    messages = [
        f"Claude delta code points: {code_points}",
        f"Claude delta UTF-8 bytes: {utf8_bytes}",
        f"Claude delta binding size: {binding_size}",
        f"Claude delta size cap: {size_cap}",
        f"Warning threshold: {warning_threshold}",
    ]
    ok = True

    if binding_size > size_cap:
        ok = False
        messages.append(
            f"FAIL: Claude delta binding size {binding_size} > size cap {size_cap}"
        )
    elif binding_size >= warning_threshold:
        messages.append(
            f"WARNING: binding size {binding_size} is in warning band "
            f"[{warning_threshold}, {size_cap}]"
        )
    else:
        messages.append(
            f"PASS: Claude delta binding size {binding_size} is below "
            f"warning threshold {warning_threshold}"
        )

    import_count = text.splitlines().count("@AGENTS.md")
    if import_count != 1:
        ok = False
        messages.append(f"FAIL: managed @AGENTS.md import count {import_count} != 1")
    else:
        messages.append("PASS: exactly one managed @AGENTS.md import")

    shared_headings = set(H2_HEADING.findall(agents_text))
    claude_headings = set(H2_HEADING.findall(text))
    duplicate_headings = sorted(shared_headings & claude_headings)
    duplicate_bootstrap = sorted(
        heading for heading in claude_headings if heading.startswith("## Bootstrap")
    )
    if duplicate_headings or duplicate_bootstrap:
        ok = False
        duplicates = ", ".join((*duplicate_headings, *duplicate_bootstrap))
        messages.append(f"FAIL: Claude delta duplicates shared owner heading(s): {duplicates}")
    else:
        messages.append("PASS: Claude delta has no shared-owner headings")

    totals: dict[str, tuple[int, int]] = {}
    for owner, owner_text, manifest in (
        ("Shared", agents_text, SHARED_MANIFEST),
        ("Claude", text, CLAUDE_MANIFEST),
    ):
        missing_count = 0
        pinned = 0
        for group, tokens in manifest.items():
            missing = [token for token in tokens if token not in owner_text]
            pinned += len(tokens)
            missing_count += len(missing)
            if missing:
                ok = False
                messages.append(
                    f"FAIL: missing {len(missing)}/{len(tokens)} [{owner}: {group}]:"
                )
                messages.extend(f"         - {token}" for token in missing)
            else:
                messages.append(
                    f"PASS: all {len(tokens)} present [{owner}: {group}]"
                )
        totals[owner] = (pinned - missing_count, pinned)

    messages.append(f"Shared manifest: {totals['Shared'][0]}/{totals['Shared'][1]}")
    messages.append(f"Claude manifest: {totals['Claude'][0]}/{totals['Claude'][1]}")
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
        "--agents-md",
        type=Path,
        default=repo_root / "shared" / "AGENTS.shared.md",
        help="Shared governance owner paired with the Claude entrypoint.",
    )
    parser.add_argument(
        "--size-cap",
        type=int,
        default=SIZE_CAP,
        help=(
            "Maximum max(code points, UTF-8 bytes) for the Claude-only delta "
            f"(default: {SIZE_CAP})."
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

    ok, messages = validate(args.claude_md, args.agents_md, args.size_cap)
    mirror_ok, mirror_messages = validate_reference_mirror(
        args.reference, args.ru_reference
    )
    ok = ok and mirror_ok
    messages.extend(mirror_messages)
    print(
        f"=== Claude Markdown composition validation "
        f"({args.claude_md} + {args.agents_md}) ==="
    )
    for message in messages:
        print(message)
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
