"""Joint Bootstrap/shared source obligations, not runtime or arbitrary semantic proof.

Checks are scoped to real owner units, with bounded Markdown normalization and
selected deletion/inversion counterexamples. Exact identifiers stay exact.
"""
from pathlib import Path
import re
import unittest

from policy_text_contract import identifier_present, lexical, selected_section, selected_unit

ROOT = Path(__file__).resolve().parents[1]
CODEX = "src.codex/AGENTS.codex.md"
SHARED = "shared/AGENTS.shared.md"
TITLE = "Bootstrap — verified premises plus edit/commit checkpoints"


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def bootstrap(text):
    return selected_section(text, TITLE).split("\n### Codex hook requirements", 1)[0]


def unit(body, prefix):
    paragraphs = re.split(r"\n\s*\n|\n(?=\d+(?:\.\d+)?\. |[-*] )", body)
    found = [p for p in paragraphs if lexical(p).startswith(lexical(prefix) + " ")]
    if len(found) != 1:
        raise AssertionError(f"Bootstrap unit {prefix!r}: expected one, got {len(found)}")
    return found[0]


def contains(text, *phrases):
    return all(lexical(phrase) in lexical(text) for phrase in phrases)


def codex_duties(text):
    """Keep relational clauses together; the tests do not infer general semantics."""
    body = bootstrap(text)
    checks = {
        "universal": ("**STOP.", "Every decision, plan, verdict, root-cause claim, fix, implementation action or behavior-changing commit requires verified premises", "Checkpoints supplement, never limit, that rule", "direct, nested, non-Lead and skill-only callers", "another routing flow does not waive it"),
        "orientation-trigger": ("- **(a0)", "before the first repository-local runner/build or mutation in an unfamiliar repo/subtree, complete step 0", "even outside a bug fix"),
        "pre-fix": ("- **(a)", "before the first code mutation for a bug report, runtime failure, error trace, regression", '"does not work", "не работает", "broken" or any reported behavioral defect', "steps 1-3 must complete before the first edit lands", "before changing working behavior for speed, cleanup or refactoring", "runtime diagnosis or profiling before editing is mandatory", "Steps 4 and 4.5 apply while drafting the edit", "step 5 does not apply at this moment"),
        "pre-commit": ("- **(b)", "before a bug-fix, behavior, contract or feature commit", "all 5 steps (1-5), including the 4.5 no-kostyl check", "step 0 retains its (a0) trigger", "Step 5 is pre-commit-specific"),
        "orientation-referral": ("0.", "Apply shared Repository orientation; Mechanism inventory before new paths", "including its exact `REPOSITORY ORIENTATION:` record and `file:line` evidence", "Missing/conflicting authority is `status=conflict`: no run/build/edit until the owner or user resolves it"),
        "historical-scope": ("0.", "Names/counts/recency/layout prove no liveness", "archived/deprecated/superseded/frozen targets need explicit user-approved historical scope", "Prove status and inventory the existing owner before copying/forking a runner or scorer"),
        "session-evidence": ("1.", "concrete observed decision-driving data captured in this session's conversation", "`file:line`, this-session command output, log, verbatim user statement or reproduction", "If none, investigate before editing/committing", "Apply the shared Pre-fix diagnostic gate independently of `/agents-bugfix`"),
        "decomposed-hypotheses": ("2.", "List every interpretive leap separately", "including user-intent interpretation, mechanism/flag behavior and the reason for the affected scope", "Each remains a hypothesis until verified; do not collapse the chain"),
        "assumption-exception": ("3.", "verify every hypothesis empirically, from authoritative documentation, or directly with the user before committing", "Only when asking/verifying genuinely costs more than being wrong may the commit instead disclose", "plus its resolving verification step", "No silent unverified premise"),
        "proportional-scope": ("4.", "Limit the change to what the verified hypothesis requires", "A wider refactor, multi-file/contract change or extraction must be justified by that hypothesis and stated in the commit", "unrelated opportunistic cleanup is forbidden"),
        "no-kostyl": ("4.5.", "Apply shared Fix means correct logic, not workaround or hiding (no kostyl)", "name/correct the producing root cause, not symptom suppression", "Only an explicit `WORKAROUND` commit may retain a workaround", "with separate root cause, scope/lifetime and disclosure that the defect remains unfixed"),
        "rollback": ("5.", "State the rollback path", "Shared Hypothesis disclosure discipline governs destructive history rewrite", "explicit user authority, fresh dirty/index census", "preservation of every unrelated working-tree byte and staged change", "local commits and no other work depends on them", "otherwise use a nondestructive reversible route and re-verify from the contradicted node", "Under those preconditions prefer `git reset --hard HEAD~N` to `git revert`"),
        "first-push": ("5.", "Before first push, also clean your own introduced-then-fixed local commit churn under the same conditions, by squash/reset", "never `git push --force` already-published history to hide it", "Do not push hypothesis-bearing commits before user review", "it is the final hypothesis verification step, separate from required publication/leak gates"),
        "violations": ("**Violation triggers.", "invokes these checkpoints before the dependent action", 'editing from "I see the bug"/"add Y" without captured diagnostic evidence and a verified causal hypothesis', "every banned reasoning phrase in shared Hypothesis disclosure discipline", '"I\'ll just commit this and we can fix it if wrong"', "Shared Indirect-regression discipline requires reverting and reproducing the REAL symptom before clearing non-involvement", "allowed in open exploration/hypothesis formation, never as the load-bearing justification for an edit or commit", "apply steps 1-3 before the fix and all steps before the commit"),
        "recovery": ("Apply shared **Context handoff economy**", "at handoff/interruption/compaction/resume", "restore missing applicable obligations and current authority before the next dependent decision or action", "including interpreting/accepting outstanding results", "reuse unchanged actual context", "A catalog entry, path, prior-read marker or summary alone is not proof that the required rules are present", "a trusted handoff may carry their actual content"),
        "selected-context": ("Apply shared **Context handoff economy**", "governing text in the already selected Source/project/global context", "not an uninstalled reference or a guessed global substitute for missing project rules", "Restore missing selected content before reliance", "no new lookup when it is already present and no permission reset", "neither activate Lead nor admit a new workflow, Goal, scope or authority"),
    }
    result = {name: contains(unit(body, prefix), *phrases)
              for name, (prefix, *phrases) in checks.items()}
    result["assumption-label"] = identifier_present(unit(body, "3."), "ASSUMPTION (UNVERIFIED)")
    return result


def shared_duties(text):
    """The Codex referral cannot substitute for a missing shared governing duty."""
    section = "Verification and decision discipline"
    checks = {
        "evidence-core": (section, "Verification-and-evidence core.", "requires primary evidence sufficient for its exact claim and plausible alternatives addressed"),
        "orientation-owner": ("Scope and ownership discipline", "Repository orientation; Mechanism inventory before new paths:", "before unfamiliar-repo run/modify/build, read governance", "missing/conflicting status blocks side effects", "Before a new mechanism, identify owner+propagation"),
        "hypothesis-owner": (section, "Hypothesis disclosure discipline:", "verify each or record `ASSUMPTION (UNVERIFIED)` plus resolving step in the body", "Only direct user confirmation verifies intent", "Destructive history rewrite requires explicit user authority, fresh dirty/index census and preservation of all unrelated working-tree bytes/staged changes", "local commits and no other work depends on them", "otherwise use a nondestructive, reversible route"),
        "evidence-owner": (section, "Evidence-citation discipline:", "Banned fix drivers", "based on training data", "Binds every actor"),
        "availability-owner": (section, "Active-availability probe discipline:", "current-session direct probe", "else `ASSUMPTION (UNVERIFIED)`, no substitution", "Indirect inference cannot prove unavailability"),
        "root-cause-owner": (section, "Fix means correct logic, not workaround or hiding (no kostyl):", "correct producing logic/contract/invariant, never hide symptoms", "root-cause naming", "symptom-only suppression detection", "unless separately verified legitimate boundary fallback"),
        "actual-regression-owner": (section, "Indirect-regression discipline (code-untouched ≠ behavior-unchanged):", "clear suspicion only by reverting and reproducing the REAL symptom, not a proxy"),
        "pre-fix-owner": (section, "Pre-fix diagnostic gate:", "before defect edits", "or working-path speed/cleanup edits", "FIRST mandatory action is to live-profile its reported scenario (not a proxy), before design/fix", "advisory hypotheses, not roots/gates", "`/agents-bugfix`-independent"),
        "context-owner": ("Core delegation principles", "Context handoff economy (binding):", "receiver's actual context", "before relying on them", "A file path, skill catalog entry or task-local marker is not proof of inherited content", "After compaction or resume, restore missing obligations", "never reset obligations or permissions"),
    }
    return {name: contains(selected_unit(text, heading, marker), *phrases)
            for name, (heading, marker, *phrases) in checks.items()}


class CodexBootstrapInstructionKernelTests(unittest.TestCase):
    def test_codex_checkpoint_obligations(self):
        for duty, present in codex_duties(read(CODEX)).items():
            with self.subTest(duty=duty):
                self.assertTrue(present)

    def test_referrals_have_actual_shared_owners(self):
        for duty, present in shared_duties(read(SHARED)).items():
            with self.subTest(duty=duty):
                self.assertTrue(present)
        for label in re.findall(r"\*\*([^*]+)\*\*", bootstrap(read(CODEX))):
            if label.startswith(("Verification-and-evidence", "Evidence-citation", "Hypothesis disclosure", "Repository orientation;", "Pre-fix diagnostic", "Fix means correct", "Indirect-regression", "Context handoff")):
                with self.subTest(shared_owner=label):
                    self.assertIn("**" + label, read(SHARED))

    def test_unique_orientation_record_is_shared_and_normatively_referred(self):
        record = "REPOSITORY ORIENTATION: scope=<repo-relative path>; status=<live|mutable|frozen|archived|deprecated|superseded|conflict>; workflow=<repo-relative entry point(s)>; protected=<repo-relative path(s)|none>; evidence=<path:line[,path:line...]>"
        shared, codex = read(SHARED), read(CODEX)
        self.assertEqual(shared.count(record), 1)
        self.assertEqual(codex.count(record), 0)
        self.assertTrue(codex_duties(codex)["orientation-referral"])
        self.assertTrue(shared_duties(shared)["orientation-owner"])

    def test_selected_deletions_and_inversions_fail_the_owning_duty(self):
        cases = (
            ("pre-fix", "steps 1-3 must complete before the first edit lands", "steps 1-3 may complete after the first edit lands"),
            ("pre-commit", "including the 4.5 no-kostyl check", "excluding the 4.5 no-kostyl check"),
            ("orientation-referral", "no run/build/edit until the owner or user resolves it", "run/build/edit before the owner or user resolves it"),
            ("session-evidence", "captured in this session's conversation", "captured in any historical report"),
            ("assumption-exception", "Only when asking/verifying genuinely costs more than being wrong", "Whenever asking/verifying takes time"),
            ("rollback", "explicit user authority, fresh dirty/index census", ""),
            ("first-push", "never `git push --force` already-published history to hide it", "use `git push --force` already-published history to hide it"),
            ("recovery", "including interpreting/accepting outstanding results", "excluding interpreting/accepting outstanding results"),
            ("selected-context", "not an uninstalled reference or a guessed global substitute for missing project rules", "use an uninstalled reference or a guessed global substitute for missing project rules"),
        )
        original = read(CODEX)
        for duty, old, new in cases:
            with self.subTest(duty=duty):
                self.assertEqual(original.count(old), 1)
                self.assertFalse(codex_duties(original.replace(old, new, 1))[duty])
        shared = read(SHARED)
        old = "Only direct user confirmation verifies intent"
        self.assertFalse(shared_duties(shared.replace(old, "Inferred intent needs no confirmation", 1))["hypothesis-owner"])
        self.assertFalse(shared_duties(shared.replace("based on training data", "", 1))["evidence-owner"])

    def test_scoped_checks_do_not_borrow_from_hooks_or_other_rules(self):
        text = read(CODEX)
        old = "including interpreting/accepting outstanding results"
        changed = text.replace(old, "receiving excluded", 1) + "\n" + old
        self.assertFalse(codex_duties(changed)["recovery"])
        with self.assertRaises(AssertionError):
            codex_duties(text.replace("## " + TITLE, "## Removed Bootstrap", 1))
        with self.assertRaises(AssertionError):
            shared_duties(read(SHARED).replace("**Context handoff economy (binding):**", "**Removed context owner:**", 1))

    def test_prose_formatting_does_not_pin_whole_documents(self):
        text = read(CODEX).replace("restore missing applicable obligations", "RESTORE  missing applicable obligations")
        self.assertTrue(all(codex_duties(text).values()))
        self.assertFalse(codex_duties(text.replace("`ASSUMPTION (UNVERIFIED)`", "`assumption (unverified)`", 1))["assumption-label"])


if __name__ == "__main__":
    unittest.main()
