"""Structural guard for the "$lead is a role held BY the main conversation" invariant.

Two prior REVISE cycles kept finding lead-vs-main-conversation SPLIT residues in
ever-new textual forms (backticks, "main session" vs "conversation", slashes) that
narrow greps missed one at a time. This test converts "hope the grep caught
everything" into a build gate: it scans the shipped packs and FAILS if it finds
either

  (a) a dispatch-of-lead phrasing   -> $lead treated as a spawnable subagent, or
  (b) a split-owner duality         -> $lead and the main conversation presented as
                                       TWO owners/participants, or a LIVE
                                       `orchestrator: main|lead` field / "template,
                                       orchestrator" frontmatter list (the retired
                                       field that encoded that duality).

WRONG (this test fails on it):
  - "`$lead`/main-conv move it", "the lead or main session", "main session or lead"
  - "closing role / `$lead`", "orchestrator: lead" as a LIVE field
  - "subagent_type: lead" as a live dispatch, "You are the `lead` subagent",
    "spawn/dispatch/invoke `$lead`", "`$lead` ... spawned/dispatched"

FINE (allow-listed — this test must stay green on it):
  - "$lead" as a bare ROLE NAME held by the main conversation
  - "the main conversation (as Lead)", "the main session IS the lead",
    "hold the Lead role AS the main conversation"
  - explicitly LABELED legacy notes with a read-mapping ("legacy", "renamed",
    "older `status.md` ...")
  - the fail-closed refusal stub's own negation/refusal lines
    ("is never spawned", "is not a dispatch target", "fail-closed", "refuses", ...)

Scope: src.claude, src.codex, shared, docs. NOT work-items / .scratch / changelogs /
dated-plan snapshots (those legitimately record superseded relations).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Shipped-pack trees only. work-items/, .scratch/, changelogs, and dated-plan
# snapshots are excluded (see _is_excluded) because recording a superseded
# relation there is legitimate provenance, not a live split.
SCAN_DIRS = ("src.claude", "src.codex", "shared", "docs")

TEXT_SUFFIXES = {".md", ".sh", ".ps1", ".py", ".yaml", ".yml", ".toml", ".json", ".txt"}

# Path segments / shapes that are out of scope for the live-tree invariant.
_EXCLUDED_PARTS = {
    "work-items",
    ".scratch",
    ".git",
    "__pycache__",
    "node_modules",
    "archive",
    "_archive",
    "legacy",
    "plans",  # dated plan snapshots live under .../plans/
}
_DATED_BASENAME = re.compile(r"^\d{4}-\d{2}-\d{2}")
_CHANGELOG_BASENAME = re.compile(r"^(RELEASE_NOTES|CHANGELOG|HISTORY)", re.IGNORECASE)


def _is_excluded(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    if parts & _EXCLUDED_PARTS:
        return True
    if _DATED_BASENAME.match(path.name):  # e.g. 2026-05-03-agent-execution-tracking.md
        return True
    if _CHANGELOG_BASENAME.match(path.name):
        return True
    return False


# --- FORBIDDEN patterns -------------------------------------------------------
# Each entry: (name, compiled regex). A line hitting any of these is a violation
# UNLESS an allow-list pattern also matches that line.
FORBIDDEN = [
    # (a) dispatch-of-lead: $lead treated as a spawnable subagent
    ("dispatch:subagent_type-lead", re.compile(r"subagent_type:\s*`?\*?lead\b", re.IGNORECASE)),
    ("dispatch:you-are-lead-subagent", re.compile(r"you are the\s+`?lead`?\s+subagent", re.IGNORECASE)),
    (
        "dispatch:verb-lead",
        re.compile(r"\b(?:dispatch|spawn|launch|invoke)(?:ed|s|ing)?\s+(?:a\s+|an\s+|the\s+)?`?\$lead\b", re.IGNORECASE),
    ),
    (
        "dispatch:lead-spawned",
        re.compile(r"\$lead`?[^.\n]{0,20}?\b(?:spawned|dispatched|invoked as a subagent)\b", re.IGNORECASE),
    ),
    # (b) split-owner duality: $lead and the main conversation as TWO owners
    (
        "duality:lead-slash-main",
        re.compile(r"\$?lead`?\s*/\s*`?\*?main[- ]?(?:conv|conversation|session)", re.IGNORECASE),
    ),
    (
        "duality:main-slash-lead",
        re.compile(r"main[- ]?(?:conv|conversation|session)`?\s*/\s*`?\$?lead\b", re.IGNORECASE),
    ),
    ("duality:lead-or-main", re.compile(r"\blead\s+or\s+main\b", re.IGNORECASE)),
    ("duality:main-or-lead", re.compile(r"\bmain[- ]?(?:conv\w*|session)\s+or\s+`?\$?lead\b", re.IGNORECASE)),
    ("duality:role-slash-lead", re.compile(r"\brole\s*/\s*`?\$?lead\b", re.IGNORECASE)),
    # (b) the retired duality-encoding frontmatter field
    ("field:orchestrator-value", re.compile(r"orchestrator:\s*(?:main|lead)\b", re.IGNORECASE)),
    ("field:template-orchestrator", re.compile(r"template,\s*orchestrator\b", re.IGNORECASE)),
]

# --- ALLOWLIST ----------------------------------------------------------------
# A line matching ANY of these is a legitimate FINE form and is exempt. Kept
# deliberately SPECIFIC (never a bare `\blead\b`) so an allow-list phrase cannot
# smuggle a real split past on the same line.
ALLOWLIST = [
    # unified-owner: $lead is the ROLE the main conversation holds (never two owners)
    re.compile(r"main conversation \(as lead\)", re.IGNORECASE),
    re.compile(r"main conversation,? as lead", re.IGNORECASE),
    re.compile(r"main conv \(as lead\)", re.IGNORECASE),
    re.compile(r"main session \(as lead\)", re.IGNORECASE),
    re.compile(r"main (?:codex )?session is the lead", re.IGNORECASE),
    re.compile(r"the main conversation holds", re.IGNORECASE),
    re.compile(r"main conversation'?s? orchestration role", re.IGNORECASE),
    re.compile(r"orchestration role the main conversation holds", re.IGNORECASE),
    re.compile(r"hold(?:ing|s)?\s+(?:the\s+)?(?:lead\s+role|`?\$?lead`?)", re.IGNORECASE),
    # explicitly LABELED legacy / rename notes with a read-mapping
    re.compile(r"\blegacy\b", re.IGNORECASE),
    re.compile(r"\brenamed\b", re.IGNORECASE),
    re.compile(r"\bretired\b", re.IGNORECASE),
    re.compile(r"older\s+`?status\.md", re.IGNORECASE),
    # fail-closed refusal stub / canonical-skill negation lines
    re.compile(r"never\s+(?:itself\s+)?(?:be\s+)?spawn", re.IGNORECASE),
    re.compile(r"never\s+spawns\s+a\s+separate", re.IGNORECASE),
    re.compile(r"is never spawned", re.IGNORECASE),
    re.compile(r"\bnot\s+spawn", re.IGNORECASE),  # "do not spawn `$lead`" is the correct instruction
    re.compile(r"not\s+(?:a\s+)?(?:dispatch|subagent)", re.IGNORECASE),
    re.compile(r"never\s+(?:be\s+)?a\s+dispatch", re.IGNORECASE),
    re.compile(r"not a subagent you spawn", re.IGNORECASE),
    re.compile(r"fail-?closed", re.IGNORECASE),
    re.compile(r"fails\s+closed", re.IGNORECASE),
    re.compile(r"refus(?:e|es|al|ed)", re.IGNORECASE),
    re.compile(r"stale route", re.IGNORECASE),
    re.compile(r"throwaway lead", re.IGNORECASE),
]


def _iter_files():
    for d in SCAN_DIRS:
        base = ROOT / d
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if _is_excluded(path):
                continue
            yield path


def _scan():
    violations = []
    for path in _iter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            if any(allow.search(line) for allow in ALLOWLIST):
                continue
            for name, pat in FORBIDDEN:
                if pat.search(line):
                    rel = path.relative_to(ROOT).as_posix()
                    violations.append((rel, lineno, name, line.strip()))
    return violations


def _line_verdict(line: str):
    """Return the forbidden-pattern name a line would trip, or None if clean/allow-listed."""
    if any(allow.search(line) for allow in ALLOWLIST):
        return None
    for name, pat in FORBIDDEN:
        if pat.search(line):
            return name
    return None


def test_no_lead_vs_main_conversation_split():
    violations = _scan()
    if violations:
        lines = "\n".join(
            f"  {rel}:{lineno}  [{name}]  {snippet}" for rel, lineno, name, snippet in violations
        )
        raise AssertionError(
            "lead-vs-main-conversation split residue detected "
            f"({len(violations)} line(s)). $lead is the orchestration role the MAIN "
            "CONVERSATION holds; it is never a second owner and never a dispatch target. "
            "Fix the residue, or (only for a genuine FINE form) extend the allow-list in "
            f"tests/test_lead_invariant.py:\n{lines}"
        )


# --- self-verifying teeth: the guard must fail on a reintroduced split -------
# These strings are the exact WRONG forms two REVISE cycles removed, plus the
# dispatch reintroductions the guard exists to block. (tests/ is out of scan
# scope, so these literals never self-trip the scan above.)
_KNOWN_SPLIT_FORMS = [
    "not straight to Active; `$lead`/main-conv move it Backlog -> Active when work starts.",
    "the lead or main session must prove which roles ran",
    "owned by the closing role / `$lead`, so the archivist does NOT decide",
    "YAML frontmatter (template, orchestrator, started, updated) and sections",
    "includes template, orchestrator role, active/completed agents, next action",
    "orchestrator: lead",
    "route it via `subagent_type: lead` to spin up the orchestrator",
    "You are the `lead` subagent; orchestrate the pipeline",
    "spawn a `$lead` subagent to coordinate the work",
    "run either the main session or `$lead` for this chain",
    "pick main-conv / `$lead` as the closing owner",
]

# These FINE forms must stay clean — the allow-list must not be so tight that it
# flags a legitimate "$lead is the role the main conversation holds" statement.
_KNOWN_FINE_FORMS = [
    "the main conversation (as Lead) moves it Backlog -> Active when work starts.",
    "the main session (as Lead) must prove which roles ran",
    "owned by the closing role (the main conversation as Lead, or the capturing reviewer)",
    "YAML frontmatter (template, orchestration, started, updated) and sections",
    "includes template, orchestration weight, active/completed agents, next action",
    "`$lead` is the main conversation's orchestration role, never a spawned subagent",
    "Hold `$lead` as the orchestration role in the main Codex session; the main session IS the lead.",
    "You hold the Lead role AS the main conversation. `subagent_type: lead` is not a dispatch target.",
    "Legacy handling: older `status.md` files may carry `orchestrator: main | lead`; it is renamed.",
    "the main conversation holds the Lead role (activate the `/lead` skill); do not spawn `$lead`",
    "`$lead` / `$product-manager` consult open lessons when admitting similar work",
]


def test_guard_flags_known_split_forms():
    misses = [s for s in _KNOWN_SPLIT_FORMS if _line_verdict(s) is None]
    assert not misses, f"guard failed to flag reintroduced split form(s): {misses}"


def test_guard_allows_known_fine_forms():
    false_positives = [(s, _line_verdict(s)) for s in _KNOWN_FINE_FORMS if _line_verdict(s) is not None]
    assert not false_positives, f"guard false-flagged legitimate FINE form(s): {false_positives}"
