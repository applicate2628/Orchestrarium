"""Pure selected file replacement proposals; no physical owner or provider."""
from dataclasses import FrozenInstanceError, replace
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from installation import ownership
from installation.receipt_plan import Outcome, plan_changes, apply_delta, serialize_delta


def sha(value):
    return hashlib.sha256(value).hexdigest()


class SelectedFileReceiptPlanTests(unittest.TestCase):
    def setUp(self):
        self.path = ".claude/agents/lead.md"
        self.before, self.after = b"current user bytes\r\n", b"selected replacement\n"
        self.item = Outcome(self.path, "file", self.before, self.after,
                            "replace", sha(self.before))
        self.record = {
            "schema": ownership.SCHEMA, "provider": "claude", "scope": "global",
            "files": {self.path: sha(b"historical"),
                      ".claude/skills/other/SKILL.md": sha(b"unrelated")},
            "configs": {
                ".claude/CLAUDE.md": {"kind": "block", "blockKind": "claude",
                                     "sha256": sha(b"block")},
                ".claude/.agents-mode.yaml": {"kind": "file", "sha256": sha(b"mode")},
            },
            "directories": [".claude/agents/retained"],
        }
        self.raw = json.dumps(self.record).encode()

    def plan(self, raw, *items):
        return plan_changes(raw, "claude", "global", items or (self.item,), None)

    def assert_preserved(self, raw, item):
        plan = self.plan(raw, item)
        self.assertEqual(plan.artifacts[0].route, "preserve")
        self.assertEqual(plan.changes, ())
        self.assertEqual(serialize_delta(raw, plan), raw)

    def test_selected_replacement_of_drifted_claim_has_only_selected_requirements(self):
        plan = self.plan(self.raw)
        artifact = plan.artifacts[0]
        self.assertEqual(artifact.route, "selected-replacement-proposal")
        self.assertEqual(artifact.requirements, (
            "artifact-and-receipt-currentness", "atomic-owner-commit-and-rollback",
            "exact-current-replacement-approval", "selected-storage-acquisition"))
        self.assertEqual((artifact.before_sha256, artifact.after_sha256),
                         (sha(self.before), sha(self.after)))
        self.assertEqual(plan.changes[0].expected_json, json.dumps(sha(b"historical")))

    def test_matching_claim_still_requires_explicit_selected_authority(self):
        self.record["files"][self.path] = sha(self.before)
        raw = json.dumps(self.record).encode()
        plan = self.plan(raw)
        self.assertIn("exact-current-replacement-approval", plan.artifacts[0].requirements)
        self.assertNotIn("historical-storage-authority", plan.artifacts[0].requirements)
        self.assertEqual(apply_delta(raw, plan)["files"][self.path], sha(self.after))

    def test_absent_receipt_acquires_only_selected_entry_without_layout(self):
        result = json.loads(serialize_delta(None, self.plan(None)))
        self.assertEqual(result, dict(schema=ownership.SCHEMA, provider="claude",
                                      scope="global", files={self.path: sha(self.after)}))

    def test_absent_claim_in_existing_receipt_is_acquired(self):
        del self.record["files"][self.path]
        raw = json.dumps(self.record).encode()
        self.assertIsNone(self.plan(raw).changes[0].expected_json)
        self.assertEqual(apply_delta(raw, self.plan(raw))["files"][self.path], sha(self.after))

    def test_missing_or_wrong_grant_never_proposes(self):
        for digest in (None, "", "0" * 64, sha(b"historical")):
            with self.subTest(digest=digest):
                self.assert_preserved(self.raw, replace(self.item, adoption_sha256=digest))

    def test_missing_before_or_after_never_proposes(self):
        for item in (replace(self.item, before=None, adoption_sha256=None),
                     replace(self.item, after=None)):
            with self.subTest(item=item):
                self.assert_preserved(self.raw, item)

    def test_empty_existing_and_replacement_bytes_are_valid(self):
        item = replace(self.item, before=b"", after=b"", adoption_sha256=sha(b""))
        self.assertEqual(apply_delta(None, self.plan(None, item))["files"][self.path], sha(b""))

    def test_block_replacement_is_rejected_even_with_matching_preimage(self):
        item = replace(self.item, path=".claude/CLAUDE.md", kind="block")
        self.assert_preserved(self.raw, item)
        self.assert_preserved(None, item)

    def test_any_file_span_is_rejected(self):
        for span in ((0, len(self.before)), (0, 0), "all"):
            with self.subTest(span=span):
                self.assert_preserved(self.raw, replace(self.item, adoption_span=span))

    def test_exact_claim_case_alias_is_rejected(self):
        item = replace(self.item, path=".claude/agents/LEAD.md")
        with self.assertRaisesRegex(ValueError, "E_RECEIPT_PLAN_ALIAS"):
            self.plan(self.raw, item)

    def test_duplicate_selected_target_alias_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "E_RECEIPT_PLAN_ALIAS"):
            self.plan(None, self.item, replace(self.item, path=".claude/agents/LEAD.md"))

    def test_directory_category_overlap_is_rejected(self):
        del self.record["files"][self.path]
        self.record["directories"].append(self.path)
        with self.assertRaisesRegex(ValueError, "E_RECEIPT_PLAN_ALIAS"):
            self.plan(json.dumps(self.record).encode())

    def test_unrelated_claims_and_layout_presence_are_preserved(self):
        for with_layout in (False, True):
            with self.subTest(with_layout=with_layout):
                record = copy.deepcopy(self.record)
                if with_layout:
                    record["layout"] = ownership.LAYOUT
                raw = json.dumps(record).encode()
                expected = copy.deepcopy(record)
                expected["files"][self.path] = sha(self.after)
                self.assertEqual(json.loads(serialize_delta(raw, self.plan(raw))), expected)

    def test_changed_receipt_fingerprint_rejects_apply_and_serialization(self):
        plan = self.plan(self.raw)
        changed = self.raw + b"\n"
        for apply in (apply_delta, serialize_delta):
            with self.subTest(apply=apply.__name__):
                with self.assertRaisesRegex(ValueError, "E_RECEIPT_PLAN_STALE"):
                    apply(changed, plan)

    def test_mixed_selected_and_recreated_claim_does_not_refresh_old_claim(self):
        fresh_path = ".claude/skills/other/SKILL.md"
        fresh = Outcome(fresh_path, "file", None, b"newly recreated", "create")
        plan = self.plan(self.raw, self.item, fresh)
        self.assertEqual(tuple(artifact.route for artifact in plan.artifacts),
                         ("selected-replacement-proposal", "preserve"))
        self.assertEqual(tuple(change.path for change in plan.changes), (self.path,))
        expected = copy.deepcopy(self.record)
        expected["files"][self.path] = sha(self.after)
        self.assertEqual(apply_delta(self.raw, plan), expected)
        self.assertEqual(json.loads(serialize_delta(self.raw, plan)), expected)
        self.assertNotEqual(expected["files"][fresh_path], sha(fresh.after))

    def test_inputs_and_frozen_outcome_are_immutable(self):
        original, raw = copy.deepcopy(self.record), bytes(self.raw)
        plan = self.plan(raw)
        projected = apply_delta(raw, plan)
        projected["files"].clear()
        self.assertEqual(self.record, original)
        self.assertEqual(self.raw, raw)
        self.assertEqual(apply_delta(raw, plan)["files"][self.path], sha(self.after))
        with self.assertRaises(FrozenInstanceError):
            self.item.intent = "update"

    def test_legacy_intents_do_not_inherit_selected_replacement_authority(self):
        for intent in ("update", "create", "adopt", "remove"):
            with self.subTest(intent=intent):
                item = replace(self.item, intent=intent,
                               adoption_sha256=sha(self.before) if intent == "adopt" else None,
                               after=None if intent == "remove" else self.after)
                self.assert_preserved(self.raw, item)
        update = replace(self.item, intent="update", adoption_sha256=None)
        self.assertEqual(self.plan(None, update).artifacts[0].route, "legacy")
        self.record["files"][self.path] = sha(self.before)
        raw = json.dumps(self.record).encode()
        self.assertIn("historical-storage-authority",
                      self.plan(raw, update).artifacts[0].requirements)
        with self.assertRaisesRegex(ValueError, "E_RECEIPT_PLAN_UNUSED_SELECTION"):
            self.plan(raw, replace(self.item, intent="update"))


if __name__ == "__main__":
    unittest.main()
