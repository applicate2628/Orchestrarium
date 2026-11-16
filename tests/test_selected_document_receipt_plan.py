"""Pure selected-document rendering and receipt proposals, without installation.

Fixtures are deterministic strings: clock, locale, random state, filesystem
ordering and scheduling do not participate in these pure contracts.
"""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from installation import configuration as config, ownership
from installation.document_outcomes import render_document
from installation.receipt_plan import Outcome, plan_changes, apply_delta, serialize_delta
from installer_markdown import document_context


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class SelectedDocumentReceiptPlanTests(unittest.TestCase):
    payload = "# Shared Governance\nFresh selected rules\n"
    prefix = "\ufeffUser caf\u00e9 \U0001f600\r\n"
    suffix = "\r\n## Project policies\r\nKeep exact user tail\rLast"

    def fixture(self, marked=True):
        begin, end = config.MARKERS["codex"]
        if marked:
            # A closed literal example must not truncate the real managed pair.
            body = (begin + "\nExample:\n\x60\x60\x60markdown\n" + end
                    + "\n\x60\x60\x60\nOld selected rules\n" + end)
        else:
            body = "# Shared Governance\r\nOld selected rules\r\n"
        before = self.prefix + body + self.suffix
        return before, (len(self.prefix), len(self.prefix + body))

    def render(self, before, span, digest=None):
        return config.render_selected_document(
            before, "codex", self.payload, document_context,
            document_digest=sha(before.encode()) if digest is None else digest,
            span=span)

    def outcome(self, before, after, span):
        return Outcome("AGENTS.md", "block", before.encode(), after.encode(),
                       "adopt", sha(before.encode()), span)

    def plan(self, item, raw=None):
        return plan_changes(raw, "codex", "project", (item,), document_context)

    def assert_preserved(self, item, raw=None):
        plan = self.plan(item, raw)
        self.assertEqual(plan.artifacts[0].route, "preserve")
        self.assertEqual(plan.changes, ())
        self.assertEqual(serialize_delta(raw, plan), raw)
        self.assertEqual(apply_delta(raw, plan),
                         None if raw is None else json.loads(raw))

    def assert_proposal(self, before, after, span):
        plan = self.plan(self.outcome(before, after, span))
        self.assertEqual(plan.artifacts[0].route, "adoption-proposal")
        self.assertEqual(plan.artifacts[0].requirements, (
            "artifact-and-receipt-currentness", "atomic-owner-commit-and-rollback",
            "exact-user-adoption-approval", "selected-storage-acquisition"))
        self.assertEqual((plan.artifacts[0].before_sha256,
                          plan.artifacts[0].after_sha256),
                         (sha(before.encode()), sha(after.encode())))
        self.assertEqual(len(plan.changes), 1)
        self.assertEqual(plan.changes[0].category, "configs")
        self.assertIsNone(plan.changes[0].expected_json)
        self.assertEqual(apply_delta(None, plan), {
            "schema": ownership.SCHEMA, "provider": "codex",
            "scope": "project", "files": {},
            "configs": {"AGENTS.md": {
                "kind": "block", "blockKind": "codex",
                "sha256": config.block_digest(after, "codex", document_context)}}})
        self.assertEqual(json.loads(serialize_delta(None, plan)), apply_delta(None, plan))

    def test_marked_closed_literal_end_uses_real_pair_and_exact_outside(self):
        before, span = self.fixture()
        self.assertEqual(config.owned_block(before, "codex", document_context), span)
        self.assertEqual(config.validate_selected_document(
            before, "codex", document_context,
            document_digest=sha(before.encode()), span=span), span)
        after = self.render(before, span)
        fresh = config.merge_owned_block(None, "codex", self.payload, document_context)
        self.assertEqual(after, self.prefix + fresh[:-1] + self.suffix)
        new = config.owned_block(after, "codex", document_context)
        self.assertEqual(after[:new[0]].encode(), before[:span[0]].encode())
        self.assertEqual(after[new[1]:].encode(), before[span[1]:].encode())
        self.assert_proposal(before, after, span)

    def test_unmarked_codex_exact_legacy_span_keeps_fresh_final_lf(self):
        before, span = self.fixture(marked=False)
        self.assertIsNone(config.owned_block(before, "codex", document_context))
        after = self.render(before, span)
        fresh = config.merge_owned_block(None, "codex", self.payload, document_context)
        self.assertEqual(after.encode(), (self.prefix + fresh + self.suffix).encode())
        self.assert_proposal(before, after, span)

    def test_stale_full_hash_after_only_outside_edit_preserves(self):
        for marked in (True, False):
            with self.subTest(marked=marked):
                before, span = self.fixture(marked)
                after = self.render(before, span)
                changed = before + "outside edit"
                with self.assertRaises(ValueError):
                    self.render(changed, span, sha(before.encode()))
                item = self.outcome(before, after, span)
                self.assert_preserved(replace(item, before=changed.encode()))

    def test_manually_changed_outside_output_preserves(self):
        for marked in (True, False):
            before, span = self.fixture(marked)
            after = self.render(before, span)
            for changed in ("changed prefix\n" + after, after + "changed suffix"):
                with self.subTest(marked=marked, changed=changed):
                    self.assert_preserved(self.outcome(before, changed, span))

    def test_invalid_explicit_spans_preserve_without_receipt_delta(self):
        for marked in (True, False):
            before, span = self.fixture(marked)
            after = self.render(before, span)
            start, end = span
            invalid = ((start - 1, end), (start, end - 1), (end, start),
                       (start, len(before) + 1), (True, end), [start, end],
                       (start,), (float(start), end))
            for selected in invalid:
                with self.subTest(marked=marked, selected=selected):
                    with self.assertRaises(ValueError):
                        self.render(before, selected)
                    self.assert_preserved(self.outcome(before, after, selected))

    def test_ambiguous_markers_do_not_fall_back_to_legacy_selection(self):
        before, span = self.fixture(marked=False)
        after = self.render(before, span)
        ambiguous = before + "\n" + config.MARKERS["codex"][1] + "\n"
        with self.assertRaises(ValueError):
            self.render(ambiguous, span)
        self.assert_preserved(self.outcome(ambiguous, after, span))

    def test_existing_claim_rejects_adoption_even_when_selected_current(self):
        before, span = self.fixture()
        after = self.render(before, span)
        current = config.block_digest(before, "codex", document_context)
        for digest in (current, sha(b"historical different block")):
            with self.subTest(digest=digest):
                raw = json.dumps({
                    "schema": ownership.SCHEMA, "provider": "codex",
                    "scope": "project", "files": {},
                    "configs": {"AGENTS.md": {
                        "kind": "block", "blockKind": "codex", "sha256": digest}}
                }, indent=2).encode()
                self.assert_preserved(self.outcome(before, after, span), raw)

    def test_update_default_and_document_adapter_never_auto_adopt(self):
        for marked in (True, False):
            with self.subTest(marked=marked):
                before, span = self.fixture(marked)
                digest = sha(before.encode())

                def selected_renderer(kind, existing):
                    return config.render_selected_document(
                        existing, kind, self.payload, document_context,
                        document_digest=digest, span=span)

                result = render_document("codex", "project", "AGENTS.md",
                                         before.encode(), selected_renderer)
                outcome = result.as_outcome()
                self.assertEqual(result.after, self.render(before, span).encode())
                self.assertEqual(outcome, Outcome("AGENTS.md", "block",
                                                 before.encode(), result.after))
                self.assertEqual(outcome.intent, "update")
                self.assertIsNone(outcome.adoption_sha256)
                self.assertIsNone(outcome.adoption_span)
                plan = self.plan(outcome)
                self.assertEqual(plan.artifacts[0].route, "legacy")
                self.assertEqual(plan.changes, ())
                self.assertIsNone(serialize_delta(None, plan))


if __name__ == "__main__":
    unittest.main()
