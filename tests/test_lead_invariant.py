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
  - the same split with an and/both/vs joiner: "`$lead` and main-conv",
    "both the lead and the main session", "lead vs main conversation"
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
    ("is never spawned", "is not a dispatch target", "fail-closed", ...)

The allow-list is CATEGORY-SCOPED (see _ALLOW_GROUP_EXCUSES): a generic label word
("legacy", "retired", "refuses", ...) may excuse a duality/field hit on its line but
can NEVER neutralize a dispatch:* hit — "spawn a `$lead` subagent to migrate the
legacy status files" is a real dispatch reintroduction, not a labeled legacy note.

Scope: src.claude, src.codex, src.gemini, src.qwen, shared, docs. NOT work-items /
.scratch / changelogs / dated-plan snapshots (those legitimately record superseded
relations).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Shipped-pack trees only. work-items/, .scratch/, changelogs, and dated-plan
# snapshots are excluded (see _is_excluded) because recording a superseded
# relation there is legitimate provenance, not a live split.
SCAN_DIRS = ("src.claude", "src.codex", "src.gemini", "src.qwen", "shared", "docs")

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
        # "both"/"either" cover the joiner form "spawn both `$lead` and X" (F26):
        # dispatching $lead alongside a real subagent is still a dispatch of $lead.
        re.compile(
            r"\b(?:dispatch|spawn|launch|invoke)(?:ed|s|ing)?\s+(?:(?:both|either)\s+)?(?:a\s+|an\s+|the\s+)?`?\$lead\b",
            re.IGNORECASE,
        ),
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
    # (b) the same split with an and/both/vs joiner ("/" and "or" rephrased). The
    # "both the lead and the main session" form is covered by lead-and-main (the
    # "lead and (the) main" core is a substring of the both-form). Joiners are
    # matched with \s+ only — a HYPHENATED "lead-vs-main" is meta-prose ABOUT the
    # retired split (e.g. a doc describing this very guard), not a split assertion.
    ("duality:lead-and-main", re.compile(r"\blead`?\s+and\s+(?:the\s+)?`?\*?main\b", re.IGNORECASE)),
    ("duality:main-and-lead", re.compile(r"\bmain[- ]?(?:conv\w*|session)\s+and\s+(?:the\s+)?`?\$?lead\b", re.IGNORECASE)),
    ("duality:lead-vs-main", re.compile(r"\blead`?\s+vs\.?\s+(?:the\s+)?`?\$?main\b", re.IGNORECASE)),
    ("duality:main-vs-lead", re.compile(r"\bmain[- ]?(?:conv\w*|session)?\s+vs\.?\s+(?:the\s+)?`?\$?lead\b", re.IGNORECASE)),
    # (b) the retired duality-encoding frontmatter field
    ("field:orchestrator-value", re.compile(r"orchestrator:\s*(?:main|lead)\b", re.IGNORECASE)),
    ("field:template-orchestrator", re.compile(r"template,\s*orchestrator\b", re.IGNORECASE)),
]

# --- ALLOWLIST ----------------------------------------------------------------
# Each entry is (group, regex). A match no longer skips ALL forbidden checks on the
# line: it only excuses the forbidden CATEGORIES its group maps to in
# _ALLOW_GROUP_EXCUSES below. This is the F27 fix — the previous flat any-match let
# one incidental generic word ("legacy", "retired", "refuses") neutralize a REAL
# dispatch-of-lead reintroduction on the same line, contradicting this list's own
# stated design property. Entries stay SPECIFIC where they excuse dispatch hits
# (never a bare `\blead\b`, never a bare generic label word).
ALLOWLIST = [
    # unified-owner: $lead is the ROLE the main conversation holds (never two owners)
    ("unified-owner", re.compile(r"main conversation \(as lead\)", re.IGNORECASE)),
    ("unified-owner", re.compile(r"main conversation,? as lead", re.IGNORECASE)),
    ("unified-owner", re.compile(r"main conv \(as lead\)", re.IGNORECASE)),
    ("unified-owner", re.compile(r"main session \(as lead\)", re.IGNORECASE)),
    ("unified-owner", re.compile(r"main (?:codex )?session is the lead", re.IGNORECASE)),
    ("unified-owner", re.compile(r"the main conversation holds", re.IGNORECASE)),
    ("unified-owner", re.compile(r"main conversation'?s? orchestration role", re.IGNORECASE)),
    ("unified-owner", re.compile(r"orchestration role the main conversation holds", re.IGNORECASE)),
    ("unified-owner", re.compile(r"hold(?:ing|s)?\s+(?:the\s+)?(?:lead\s+role|`?\$?lead`?)", re.IGNORECASE)),
    # explicitly LABELED legacy / rename notes with a read-mapping. GENERIC words:
    # they may excuse a duality/field mention on the labeled line, NEVER a dispatch.
    ("legacy-label", re.compile(r"\blegacy\b", re.IGNORECASE)),
    ("legacy-label", re.compile(r"\brenamed\b", re.IGNORECASE)),
    ("legacy-label", re.compile(r"\bretired\b", re.IGNORECASE)),
    ("legacy-label", re.compile(r"older\s+`?status\.md", re.IGNORECASE)),
    ("legacy-label", re.compile(r"refus(?:e|es|al|ed)", re.IGNORECASE)),
    # fail-closed refusal stub / canonical-skill negation lines: SPECIFIC phrases
    # (a negated dispatch is the correct instruction, so these may excuse dispatch)
    ("refusal-negation", re.compile(r"never\s+(?:itself\s+)?(?:be\s+)?spawn", re.IGNORECASE)),
    ("refusal-negation", re.compile(r"never\s+spawns\s+a\s+separate", re.IGNORECASE)),
    ("refusal-negation", re.compile(r"is never spawned", re.IGNORECASE)),
    ("refusal-negation", re.compile(r"\bnot\s+spawn", re.IGNORECASE)),  # "do not spawn `$lead`" is the correct instruction
    ("refusal-negation", re.compile(r"not\s+(?:a\s+)?(?:dispatch|subagent)", re.IGNORECASE)),
    ("refusal-negation", re.compile(r"never\s+(?:be\s+)?a\s+dispatch", re.IGNORECASE)),
    ("refusal-negation", re.compile(r"not a subagent you spawn", re.IGNORECASE)),
    ("refusal-negation", re.compile(r"fail-?closed", re.IGNORECASE)),
    ("refusal-negation", re.compile(r"fails\s+closed", re.IGNORECASE)),
    ("refusal-negation", re.compile(r"stale route", re.IGNORECASE)),
    ("refusal-negation", re.compile(r"throwaway lead", re.IGNORECASE)),
]

# Which forbidden CATEGORIES (the prefix before ':' in a FORBIDDEN name) each
# allow-list group may excuse. No group except the specific refusal/negation
# phrases may excuse a dispatch:* hit — that category is the guard's primary
# target and a bare label word must never smuggle a spawn-$lead past it (F27).
_ALLOW_GROUP_EXCUSES = {
    "unified-owner": frozenset({"duality", "field"}),
    "legacy-label": frozenset({"duality", "field"}),
    "refusal-negation": frozenset({"dispatch", "duality", "field"}),
}


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


def _line_verdict(line: str):
    """Return the forbidden-pattern name a line would trip, or None if clean/excused.

    Single owner of the verdict logic (the scan and the teeth tests both call it).
    An allow-list match excuses only the categories its group maps to in
    _ALLOW_GROUP_EXCUSES — a dispatch:* hit survives every generic label word.
    """
    excused: set[str] = set()
    for group, allow in ALLOWLIST:
        if allow.search(line):
            excused |= _ALLOW_GROUP_EXCUSES[group]
    for name, pat in FORBIDDEN:
        if name.split(":", 1)[0] in excused:
            continue
        if pat.search(line):
            return name
    return None


def _scan():
    violations = []
    for path in _iter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            text = path.read_text(encoding="utf-8", errors="replace")
        for lineno, line in enumerate(text.splitlines(), start=1):
            name = _line_verdict(line)
            if name is not None:
                rel = path.relative_to(ROOT).as_posix()
                violations.append((rel, lineno, name, line.strip()))
    return violations


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
    # F26: the same split with the '/'-or-'or' joiner rephrased as and/both/vs —
    # a trivially rephrased reintroduction must not slip past the joiner list
    "`$lead` and main-conv move it Backlog -> Active when work starts.",
    "both the lead and the main session must prove which roles ran",
    "the main session and `$lead` co-own the closure step",
    "lead vs main conversation ownership is decided per item",
    # F27: real dispatch reintroductions carrying an incidental generic allow-list
    # word — the word may label a legacy note, it must never excuse a dispatch
    "spawn a `$lead` subagent to migrate the legacy status files",
    "dispatch `$lead` when the retired flow is requested",
    "invoke `$lead` if the user refuses the quick-fix template",
    # F26: dispatch of $lead ALONGSIDE a real subagent (both/either joiner)
    "spawn both $lead and the analyst",
    "spawn either `$lead` or the analyst for this chain",
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
    # a refusal-stub line: the SPECIFIC negation phrase ("fails closed") may still
    # excuse the dispatch mention even though the generic "refused" alone may not
    "spawning `$lead` is refused: the stub fails closed and points to `/lead`",
]


def test_guard_flags_known_split_forms():
    misses = [s for s in _KNOWN_SPLIT_FORMS if _line_verdict(s) is None]
    assert not misses, f"guard failed to flag reintroduced split form(s): {misses}"


def test_guard_allows_known_fine_forms():
    false_positives = [(s, _line_verdict(s)) for s in _KNOWN_FINE_FORMS if _line_verdict(s) is not None]
    assert not false_positives, f"guard false-flagged legitimate FINE form(s): {false_positives}"
