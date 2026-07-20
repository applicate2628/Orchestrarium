"""Contract + spec-guard tests for the `/agents-status` reserved-PM-admission flag.

Work-item: 2026-07-19-pm-admission-trigger-status-flag (candidate b).
Design: .scratch/reviews/pm-trigger-fix-plan.md (architect PASS).

Two layers, matching the design's §9:

  Layer 1 (structural) — pin the prose contract into the INSTALLED-owner source
  `src.claude/commands/agents-status.md`: the "Reserved PM admissions" step, both
  predicate halves (PM co-location + a frontmatter `status:` gate), the read-only
  dispatch OFFER wording, and the surviving `## Rules` read-only line. This proves
  the step was not silently dropped or loosened on a future edit (guards I1/I4).

  Layer 2 (spec-guard) — encode the detection predicate (A)+(B) as a reference
  function and run it over an 8-file fixture that is the 1:1 regression encoding of
  the real live tree found during design (§9 table). Asserts the flagged set is
  exactly {proposed-pm decision, active-parked-pm epic, open-pm bug} — 3 true
  positives fire, 5 negatives stay silent — exercising I2, I3, F1, F3 directly.

  This reference function guards the predicate SPEC's decidability and the expected
  set against drift. It deliberately does NOT (and cannot) execute the model-run
  prose command; that remains Layer-2 QA, consistent with how the pack verifies
  every other model-executed command (no test runs `/agents-status` today).
"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
STATUS_CMD = REPO_ROOT / "src.claude" / "commands" / "agents-status.md"

# --- reference predicate (SPEC-GUARD; NOT the model executor) ----------------

_PM_RE = re.compile(r"\$?product-manager", re.IGNORECASE)
# Decidable stem set from the design (§2): admit/admitted/admitting, admission,
# accept/accepted/acceptance, intake, re-intake, pending, call. Matched as lowercase
# substrings via these stems ("admiss" catches "admission"; "accept" catches
# "accepted"/"acceptance"; "intake" subsumes "re-intake").
_STEMS = ("admit", "admiss", "accept", "intake", "pending", "call")
# Non-terminal (not-yet-admitted) frontmatter status per live registry.
_NONTERMINAL = {"decisions": {"proposed"}, "epics": {"active"}, "bugs": {"open"}}


def _frontmatter_region(text: str) -> list[str]:
    """Return the leading frontmatter lines only.

    Two shapes exist in the real tree: a `---`-delimited YAML block, or a leading
    run of list-item `- key: value` lines (older decisions). Body lines after the
    frontmatter are never returned, so a stale body `status:` cannot be read (I3).
    """
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        out: list[str] = []
        for ln in lines[1:]:
            if ln.strip() == "---":
                break
            out.append(ln)
        return out
    out = []
    for ln in lines:
        s = ln.strip()
        if s.startswith("- ") and ":" in s:
            out.append(ln)
            continue
        if s == "" and not out:
            continue  # skip leading blank lines before a list-item block
        break
    return out


def _frontmatter_status(text: str) -> str | None:
    for ln in _frontmatter_region(text):
        m = re.match(r"\s*-?\s*status:\s*([A-Za-z-]+)", ln)
        if m:
            return m.group(1).lower()
    return None


def _pm_colocated(text: str) -> bool:
    """Signal (A): a PM token co-located with an admission stem on the same or an
    adjacent line."""
    lines = [ln.lower() for ln in text.splitlines()]
    for i in range(len(lines)):
        window = lines[i]
        if i + 1 < len(lines):
            window = window + "\n" + lines[i + 1]
        if _PM_RE.search(window) and any(stem in window for stem in _STEMS):
            return True
    return False


def reserved_pm_flag(text: str, registry: str) -> bool:
    """Full predicate: (A) PM co-location AND (B) non-terminal frontmatter status."""
    return _pm_colocated(text) and (_frontmatter_status(text) in _NONTERMINAL[registry])


# --- Layer 2 fixture: 1:1 encoding of the §9 table ---------------------------

# (registry, filename, content, expected_flag)
_FIXTURE = [
    # decision, list-item frontmatter, PM + admit stem, proposed -> FLAG
    ("decisions", "proposed-pm.md",
     "- id: proposed-pm\n- status: proposed\n- decided-by: lead\n\n"
     "## Decision\nCross-cutting; admit/accept via `$product-manager` then gate.\n",
     True),
    # decision, proposed but no PM (names operator) -> no (I2 subset check)
    ("decisions", "proposed-no-pm.md",
     "- id: proposed-no-pm\n- status: proposed\n\n"
     "## Decision\nAdmit via the operator directly; no roadmap owner needed.\n",
     False),
    # decision, accepted frontmatter but STALE body says proposed+PM -> no (I3)
    ("decisions", "accepted-stale-body.md",
     "---\nstatus: accepted\ndate: 2026-07-18\n---\n\n"
     "## Admission\n`status: proposed`; accept via `$product-manager` + a gate.\n",
     False),
    # decision, proposed + role-noun mention only, no action stem -> no (F1)
    ("decisions", "proposed-role-noun.md",
     "- id: proposed-role-noun\n- status: proposed\n\n"
     "## Decision\n`product-manager` is a dual role exposed as a skill.\n",
     False),
    # epic, active + parked + PM admission -> FLAG
    ("epics", "active-parked-pm.md",
     "---\nstatus: active\n---\n\n# Epic\n\n## Parked\n\n"
     "## Children\n(to be admitted by `$product-manager` when the epic unparks)\n",
     True),
    # epic, closed + PM mention -> no (terminal state gate)
    ("epics", "closed-pm.md",
     "---\nstatus: closed\n---\n\n# Epic\n\nRecommendation pending `$product-manager`.\n",
     False),
    # bug, open + PM admission -> FLAG
    ("bugs", "open-pm.md",
     "---\nstatus: open\ndate: 2026-07-19\nseverity: medium\n---\n\n"
     "Needs adversarial review. Admit via `$product-manager`.\n",
     True),
    # bug, fixed + PM follow-up admission -> no (F3 stale-terminal escape, accepted limit)
    ("bugs", "fixed-pm.md",
     "---\nstatus: fixed\ndate: 2026-07-18\nseverity: high\n---\n\n"
     "Follow-up control. Admit via `$product-manager`. Until then, unfixed.\n",
     False),
]

_EXPECTED_FLAGGED = {"proposed-pm.md", "active-parked-pm.md", "open-pm.md"}


class TestReservedPMFlagStructure(unittest.TestCase):
    """Layer 1 — the prose contract is present in the installed-owner source."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = STATUS_CMD.read_text(encoding="utf-8")

    def test_step_present(self) -> None:
        self.assertIn("Reserved PM admissions", self.text,
                      "the reserved-PM-admission step/section was dropped from agents-status.md")

    def test_predicate_signal_a_pm_colocation(self) -> None:
        self.assertIn("PM-admission-owner signal", self.text)
        self.assertIn("product-manager", self.text)
        # the fixed admission stem set must be spelled out (decidability)
        for stem in ("admit", "accept", "intake", "pending", "call"):
            self.assertIn(stem, self.text, f"admission stem '{stem}' missing from predicate (A)")

    def test_predicate_signal_b_frontmatter_gate(self) -> None:
        self.assertIn("not-yet-admitted state", self.text)
        self.assertIn("frontmatter", self.text)
        self.assertIn("status:", self.text)
        # per-registry non-terminal states named
        for state in ("proposed", "active", "open"):
            self.assertIn(state, self.text)

    def test_offer_is_read_only(self) -> None:
        self.assertIn("I will not dispatch or modify", self.text,
                      "the read-only dispatch-offer wording (I1/F4 guard) is missing")

    def test_rules_still_read_only(self) -> None:
        rules = self.text.split("## Rules", 1)
        self.assertEqual(len(rules), 2, "## Rules section missing")
        self.assertIn("Read-only", rules[1],
                      "the read-only contract line was removed from ## Rules")


class TestReservedPMFlagPredicate(unittest.TestCase):
    """Layer 2 — the reference predicate yields exactly the expected 3/8 on the fixture."""

    def test_fixture_flagged_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for registry, name, content, _ in _FIXTURE:
                d = root / registry
                d.mkdir(parents=True, exist_ok=True)
                (d / name).write_text(content, encoding="utf-8")

            flagged = set()
            for registry, name, _content, _ in _FIXTURE:
                text = (root / registry / name).read_text(encoding="utf-8")
                if reserved_pm_flag(text, registry):
                    flagged.add(name)

        self.assertEqual(
            flagged, _EXPECTED_FLAGGED,
            f"reserved-PM predicate drifted: flagged={sorted(flagged)} "
            f"expected={sorted(_EXPECTED_FLAGGED)}",
        )

    def test_each_fixture_row_matches_expectation(self) -> None:
        """Per-row assertion so a failure names the exact archetype that drifted."""
        for registry, name, content, expected in _FIXTURE:
            with self.subTest(file=f"{registry}/{name}"):
                self.assertEqual(
                    reserved_pm_flag(content, registry), expected,
                    f"{registry}/{name}: expected flag={expected}",
                )


if __name__ == "__main__":
    unittest.main()
