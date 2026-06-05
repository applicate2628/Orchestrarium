#!/usr/bin/env python3
"""Validate the AGENTS.md spine: size budget + lose-nothing protection manifest.

Task 6 safety net. `shared/AGENTS.shared.md` is installed VERBATIM as the target
`AGENTS.md` (install-claude.sh:829-830) and is always-loaded by the main
conversation. Claude Code warns when a context file exceeds 40,000 chars, so we
shed weight by moving non-enforcing ELABORATION to on-demand `shared/references/`
files (read via the Read tool, NOT @import -- imports load at launch and save
nothing). But every enforceable PROTECTION must stay in the spine, or main-conv
loses it. Reference docs confirm: @import does not reduce context; on-demand
reference files do.

This validator fails closed if:
  (a) the spine exceeds SIZE_CAP chars (the size goal), OR
  (b) any required protection token is missing from the spine -- i.e. a cut
      silently dropped a rule's operational teeth (banned-phrase list, trigger,
      gate name, required probe, safety clause, status label).

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

# Disciplines whose standalone bold card was intentionally folded into another
# spine card during the Task-6 cut (so the discipline-parity check below does
# not false-positive on a deliberate merge). "Results-table provenance
# discipline" is folded into the "Formula scope and assumptions discipline"
# card, which carries its teeth (the `provenance triad`, pinned in the manifest).
MERGED_INTO_SPINE = {"Results-table provenance discipline"}

# Claude Code warns when an always-loaded context file exceeds 40,000 chars.
# SIZE_CAP is the spine ceiling the validator enforces: 39,900 keeps a 100-char
# guard band below the warning for char-count measurement differences between
# this len()-based check and Claude's own measure. The guard band is thin
# because lose-nothing restores (the review loop required several enforceable
# specifics to stay in the spine, not just in extracts) raised the floor to
# ~39,800; the dense operational content cannot drop further without removing
# rules. Real headroom is architectural (new DETAIL -> extracts); a genuinely
# new always-on RULE is the trigger to recompress a card or escalate structure.
#
# Why not lower: the spine is dense operational governance. The Task-6 cut moved
# all genuine ELABORATION (rationale, examples, recovery procedures, the
# glossary, common-skill layout, delegation prose) to on-demand
# shared/references/spine/*.md extracts, taking AGENTS.shared.md from
# 61,905 -> ~39,815 chars while keeping all manifest protection tokens in the
# spine. The floor near 39,815 is also set by the pack validators
# (validate-skill-pack.sh), which require specific formula/terminology/
# verification phrases to be present in the installed AGENTS.md itself, not only
# in a reference. What remains is irreducible enforcement teeth (banned-phrase
# lists, gate triggers, kostyl tests, probe commands, the required formula
# rules); compressing further would drop actual rules, which the "lose no
# protection" constraint forbids. Real headroom is architectural, not numeric:
# new governance DETAIL now lands in references, so the spine stops growing. If a
# genuinely new always-on RULE must enter the spine and would trip this cap, that
# is the signal to move its elaboration to a reference (keeping only the
# operational card in the spine) rather than to raise the cap.
SIZE_CAP = 39_900

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
    "should work",
    "should be fine",
    "probably",
    "I think",
    "this pattern usually works",
    # Backtick-delimited on purpose: the bare forms "likely" and "in general" are
    # substrings of the pinned reasoning phrases "most likely means" and
    # "in general X means Y", so a bare-token pin would already be satisfied by
    # those and would NOT protect the standalone correctness-driver occurrence in
    # the Evidence-citation card. The backtick form is unique to that card.
    "`likely`",
    "`in general`",
]

BUG_TRIGGER_SIGNALS = [
    "does not work",
    "не работает",
    "regression",
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
    "Provider-contract evidence discipline",
    "Canonical-source maintenance discipline",
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
    "provenance triad",                                              # results-table provenance requirement
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
    "reuse-before-hand-rolling teeth": REUSE_BEFORE_HAND_ROLLING_TEETH,
}


def validate(spine_path: Path, size_cap: int = SIZE_CAP) -> tuple[bool, list[str]]:
    """Return (ok, messages). ok is False if size or any manifest token fails."""
    messages: list[str] = []
    ok = True

    if not spine_path.is_file():
        return False, [f"FAIL: spine file not found: {spine_path}"]

    text = spine_path.read_text(encoding="utf-8")
    size = len(text)

    if size <= size_cap:
        messages.append(f"PASS: spine size {size} <= {size_cap} chars")
    else:
        ok = False
        messages.append(
            f"FAIL: spine size {size} > {size_cap} chars (shed {size - size_cap} more)"
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
    # pointer). repo_root is the directory that contains shared/.
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
        default=SIZE_CAP,
        help=f"Max chars for the spine (default: {SIZE_CAP}).",
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
