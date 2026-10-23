#!/usr/bin/env python3
"""Validate spine integrity and report size, with an optional local budget.

Size is informational unless a selected local budget is supplied through
--size-cap or validate(size_cap). That budget compares the larger of decoded
code points and re-encoded UTF-8 bytes; it is not a loader or model-quality
limit. Required protections remain in the canonical shared governance spine.

This validator fails closed if:
  (a) the spine exceeds an explicitly selected local size budget, OR
  (b) any required protection token is missing from the spine -- i.e. a cut
      silently dropped a rule's operational teeth (banned-phrase list, trigger,
      gate name, required probe, safety clause, status label), OR
  (c) a named reference pointer is dead or a present extract card is orphaned.
Missing files and read/decode failures retain their failed/nonzero outcomes.

"A reference link is not enforcement" (Codex design pass): the manifest pins the
TEACHABLE TEETH that must remain in the always-loaded spine, not merely exist in
some reference. Run before AND after every cut; build the baseline from the
uncut file so the manifest is captured while everything is still present.

The manifest is intentionally conservative: it pins exact substrings that the
governance file currently contains. If a future edit legitimately rewords a
pinned phrase, update the manifest in the SAME change and say why -- the failure
is the signal that an enforceable rule's wording moved.

Exit 0 = PASS, 1 = FAIL. Pure stdlib; no deps.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# The extract lists only current spine cards, so parity needs no compatibility
# exception for retired or folded names.
MERGED_INTO_SPINE: frozenset[str] = frozenset()

# --- lose-nothing manifest -------------------------------------------------
# Each entry is an exact substring that MUST remain in the spine. Grouped by
# protection class for diagnosis. Keep groups in sync with the disciplines whose
# "prose is the teeth" (Codex design pass SPLIT_LINE table).

BANNED_REASONING_PHRASES = [
    "most likely means",
    "presumably",
    "I believe it refers to",
    "this should map to",
    "based on training data",
    "extrapolating from",
    "in general X means Y",
    "while I'm here let me also",
    "since we're touching this anyway",
]

BANNED_CORRECTNESS_DRIVERS = [
    "should be fine",
    "I think",
    "this pattern usually works",
    # Backtick-delimited on purpose: the bare forms "likely", "in general",
    # "probably", and "should work" also occur in OTHER spine cards ("most
    # likely means" / "in general X means Y" in the banned-reasoning list;
    # "other modes probably do not hit it" in the General-case card;
    # '"should work" and stale results' in Evidence-based completion), so a
    # bare-token pin is satisfied by those and does NOT protect the standalone
    # correctness-driver occurrence in the Evidence-citation card. The
    # backtick form is unique to that card.
    "`likely`",
    "`in general`",
    "`probably`",
    "`should work`",
]

BUG_TRIGGER_SIGNALS = [
    "does not work",
    "не работает",
    # Anchored on the Pre-fix diagnostic gate's own trigger enumeration: bare
    # "regression" occurs in 4 other spine lines (Regression hygiene,
    # Indirect-regression discipline, Guard precondition discipline,
    # Race-window assertion discipline), so a bare pin cannot protect the
    # gate's trigger list. This exact phrase is unique to the Pre-fix card.
    'error, regression, "does not work"',
    "runtime failure",
]

REQUIRED_STATUS_LABELS = [
    "ASSUMPTION (UNVERIFIED)",
    "WORKAROUND",
    "PASS",
    "REVISE",
    "BLOCKED",
]

GATE_AND_DISCIPLINE_NAMES = [
    "Pre-fix diagnostic gate",
    "Hypothesis disclosure discipline",
    "Evidence-citation discipline",
    "Active-availability probe discipline",
    "Ambiguity resolution discipline",
    "Visual artifact verification discipline",
    "Completion reconciliation discipline",
    "Wire-shape verification",
    "State-synchronization ownership",
    "Mechanism inventory before new paths",
    "General-case over local symptoms",
    "Reuse before hand-rolling",
    "All-return-paths discipline",
    "Guard precondition discipline",
    "End-to-end channel verification",
    "Polling anchor discipline",
    "Race-window assertion discipline",
    "Destructive-default polarity discipline",
    "Directory-level entity separation",
]

NO_KOSTYL_TEETH = [
    "kostyl",
    "root-cause naming",
    "symptom-only suppression",
    "Fix means correct logic",
]

REQUIRED_PROBES = [
    "command -v",
    "Get-Command",
    "Test-Path",
    "curl -I",
    "netstat",
    "Test-NetConnection",
]

SAFETY_CLAUSES = [
    "human review before",          # ... git push / release / publication
    "security-reviewer",            # publication-safety exception owner
    "internal relay",               # external provider must launch directly, not via internal relay
    "file-based prompt",            # external dispatch prompt delivery
    "smallest safe reversible",     # engineering-hygiene ordering
]

# Fine-grained enforceable specifics that the review loop (2026-05-29) caught
# missing from the spine after the first cut — pinned so the same teeth can
# never silently leave the spine into an on-demand extract again.
REVIEW_RESTORED_TEETH = [
    "external-brigade",                                               # bounded parallel helper fan-out permission
    "AskUserQuestion",                                               # pre-fix gate verification mechanism
    "no other work depends on them",                                 # git reset --hard recovery guard (destructive)
    "do not let UI animation or reconciliation depend on mutations", # state-sync observability teeth
    "they are not roles and do not own delivery",                    # common-skills scope clause
    "any role or the main conversation",                             # common-skills caller scope
    "also invocable inline",                                         # delegate-style common-skill fallback
]

GENERAL_CASE_TEETH = [
    "General-case over local symptoms",
    "correct concept/abstraction level",
    "owner-level general case",
    "explicit user-approved boundary",
    "broader cases left untouched",
    "preserved/generalized invariant",
    "correctness over development speed",
    "other modes probably do not hit it",
    "generalize later",
]

TEXTUAL_REVISION_TEETH = [
    "one coherent current truth",
    "clarification that changes a live textual artifact's meaning supersedes its prior wording",
    "genuinely cumulative and non-conflicting",
]

REUSE_BEFORE_HAND_ROLLING_TEETH = [
    "Reuse before hand-rolling",
    "from scratch",
    "repo-standard mechanism",
    "mature optimized library/tool",
    "current viable packages",
    "stack choice",
    "development speed/convenience",
    "runtime speed",
    "user explicitly asks",
    "record rejected options",
]

# Per-card teeth for high-value disciplines whose only manifest pin was the
# bold card NAME (the discipline-parity check requires just "**{name}"), so a
# card could be reduced to its name plus one vague sentence with all checks
# green. Same pattern as GENERAL_CASE_TEETH: exact substrings of the card body.
WIRE_SHAPE_TEETH = [
    "read the producer's actual serialization rules",
    "inspect one real sample",
    "Go structs without tags serialize PascalCase",
    "Read the producer once, then write the consumer",
]

DESTRUCTIVE_POLARITY_TEETH = [
    "encode destructive intent as the positive case",
    "zero/absent value is the safe path",
    "Inverted-polarity names",
]

GUARD_PRECONDITION_TEETH = [
    "check input assumptions",
    "missing, zero, empty, parse-fallback and both-sides-equal-by-default inputs",
    "Accept observed contract-valid input",
    "otherwise fail closed",
    "synthetically-degraded inputs",
    "never silently weaken the invariant",
]

EVIDENCE_COMPLETION_TEETH = [
    "no done-claim without fresh execution evidence",
    "implemented, not yet verified",
    "exit-code-zero from async work is not success evidence",
    "weaker-than-requested verification is a defect",
    "NOT-clean (fail-closed)",
]

REPOSITORY_ORIENTATION_TEETH = [
    "Repository orientation",
    "Names, counts, recency, and layout are not liveness evidence",
    "missing/conflicting status blocks side effects",
]

PERFORMANCE_PROFILE_TEETH = [
    "For a reported runtime-performance symptom, the FIRST mandatory action is to live-profile its reported scenario (not a proxy)",
    "Unprofiled code/stale-report findings, even hedged, are advisory hypotheses",
    "Usage redesign needs that profile plus domain/usage evidence code alone lacks",
]

MANIFEST: dict[str, list[str]] = {
    "banned reasoning phrases": BANNED_REASONING_PHRASES,
    "banned correctness drivers": BANNED_CORRECTNESS_DRIVERS,
    "bug-trigger signals": BUG_TRIGGER_SIGNALS,
    "required status labels": REQUIRED_STATUS_LABELS,
    "gate / discipline names": GATE_AND_DISCIPLINE_NAMES,
    "no-kostyl teeth": NO_KOSTYL_TEETH,
    "required availability probes": REQUIRED_PROBES,
    "safety clauses": SAFETY_CLAUSES,
    "review-restored teeth": REVIEW_RESTORED_TEETH,
    "general-case teeth": GENERAL_CASE_TEETH,
    "textual-revision teeth": TEXTUAL_REVISION_TEETH,
    "reuse-before-hand-rolling teeth": REUSE_BEFORE_HAND_ROLLING_TEETH,
    "wire-shape teeth": WIRE_SHAPE_TEETH,
    "destructive-polarity teeth": DESTRUCTIVE_POLARITY_TEETH,
    "guard-precondition teeth": GUARD_PRECONDITION_TEETH,
    "evidence-completion teeth": EVIDENCE_COMPLETION_TEETH,
    "repository-orientation teeth": REPOSITORY_ORIENTATION_TEETH,
    "performance-profile teeth": PERFORMANCE_PROFILE_TEETH,
}


def validate(spine_path: Path, size_cap: int | None = None) -> tuple[bool, list[str]]:
    """Return integrity verdict/messages, also enforcing any selected budget."""
    messages: list[str] = []
    ok = True

    if not spine_path.is_file():
        return False, [f"FAIL: spine file not found: {spine_path}"]

    text = spine_path.read_text(encoding="utf-8")
    chars = len(text)
    utf8_bytes = len(text.encode("utf-8"))
    # Retain the existing explicit-budget metric; this is not loader raw bytes.
    size = max(chars, utf8_bytes)

    if size_cap is None:
        messages.append(
            f"INFO: spine size {size} (code points {chars}, UTF-8 bytes {utf8_bytes}; no local size budget selected)"
        )
    elif size <= size_cap:
        messages.append(
            f"PASS: spine size {size} <= {size_cap} (code points {chars}, UTF-8 bytes {utf8_bytes})"
        )
    else:
        ok = False
        messages.append(
            f"FAIL: spine size {size} > {size_cap} (code points {chars}, UTF-8 bytes {utf8_bytes}; shed {size - size_cap} more)"
        )

    total_missing = 0
    for group, tokens in MANIFEST.items():
        missing = [t for t in tokens if t not in text]
        if missing:
            ok = False
            total_missing += len(missing)
            messages.append(f"FAIL: missing {len(missing)}/{len(tokens)} [{group}]:")
            for t in missing:
                messages.append(f"         - {t!r}")
        else:
            messages.append(f"PASS: all {len(tokens)} present [{group}]")

    # Pointer-resolution check: every shared/references/...md path named in the
    # spine must exist on disk (catches a moved/renamed extract leaving a dead
    # pointer). repo_root is the directory that contains shared/. NOTE: this
    # resolves against the SOURCE repo only — installed targets ship no
    # shared/references/, which is why the spine's line-4 disclaimer must
    # honestly cover every such pointer as maintainer-reference-only.
    repo_root = spine_path.resolve().parent.parent
    pointers = sorted(set(re.findall(r"shared/references/[A-Za-z0-9_./-]+\.md", text)))
    dead = [p for p in pointers if not (repo_root / p).is_file()]
    if dead:
        ok = False
        messages.append(f"FAIL: {len(dead)}/{len(pointers)} spine reference pointer(s) resolve to no file:")
        for p in dead:
            messages.append(f"         - {p}")
    elif pointers:
        messages.append(f"PASS: all {len(pointers)} spine reference pointers resolve")

    # Discipline-parity check: every bold rule-lead in the verification extract
    # must still have a card (its bold name) in the spine, so an edit cannot drop
    # a rule from the always-loaded spine while leaving it in the on-demand
    # extract. Deliberate merges are listed in MERGED_INTO_SPINE.
    extract = spine_path.parent / "references" / "spine" / "verification-and-decision-discipline.md"
    if extract.is_file():
        ext_text = extract.read_text(encoding="utf-8")
        names = re.findall(r"(?m)^- \*\*([^*]+?):\*\*", ext_text)
        orphaned = [n for n in names if n not in MERGED_INTO_SPINE and f"**{n}" not in text]
        if orphaned:
            ok = False
            messages.append(f"FAIL: {len(orphaned)} extract discipline(s) have no spine card:")
            for n in orphaned:
                messages.append(f"         - {n}")
        elif names:
            messages.append(
                f"PASS: all {len(names)} verification disciplines have a spine card"
                f" ({len(MERGED_INTO_SPINE)} folded)"
            )

    pinned = sum(len(v) for v in MANIFEST.values())
    messages.append(
        f"\nManifest: {pinned - total_missing}/{pinned} protection tokens present in spine."
    )
    return ok, messages


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    repo_root = Path(__file__).resolve().parent.parent
    parser.add_argument(
        "--spine",
        type=Path,
        default=repo_root / "shared" / "AGENTS.shared.md",
        help="Path to the spine file (default: shared/AGENTS.shared.md).",
    )
    parser.add_argument(
        "--size-cap",
        type=int,
        default=None,
        help="Selected local size budget for max(code points, UTF-8 bytes); omitted: informational size only.",
    )
    args = parser.parse_args(argv)

    ok, messages = validate(args.spine, args.size_cap)
    print(f"=== AGENTS.md spine validation ({args.spine}) ===")
    for m in messages:
        print(m)
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
