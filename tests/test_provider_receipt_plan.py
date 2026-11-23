"""Semantic receipt planning only: no installer, filesystem owner or provider."""
from dataclasses import FrozenInstanceError
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from installation import configuration as config, ownership
from installation.receipt_plan import Outcome, plan_changes, apply_delta, serialize_delta
from installer_markdown import document_context

sha = lambda data: hashlib.sha256(data).hexdigest()


class ReceiptPlanTests(unittest.TestCase):
    def setUp(self):
        self.prefix = "Русский 😀\r\nUSER PREFIX\r"
        self.suffix = "\r\nUSER TAIL\rLast\n"
        self.body = config.merge_owned_block(None, "codex", "old rule\n", document_context).rstrip("\n")
        self.before = (self.prefix + self.body + self.suffix).encode()
        self.claim = config.block_digest(self.before.decode(), "codex", document_context)
        self.after = config.merge_owned_block(
            self.before.decode(), "codex", "new rule\n", document_context,
            expected_digest=self.claim).encode()
        self.record = {
            "schema": ownership.SCHEMA, "provider": "codex", "scope": "project",
            "files": {".codex/agents/other.toml": sha(b"other")},
            "directories": [".codex/agents/retained"],
            "configs": {
                "AGENTS.md": {"kind": "block", "blockKind": "codex", "sha256": self.claim},
                ".agents/.agents-mode.yaml": {"kind": "file", "sha256": sha(b"mode")},
            },
        }

    def receipt(self, record=None, **kwargs):
        return json.dumps(self.record if record is None else record, **kwargs).encode()

    def plan(self, receipt, *outcomes, provider="codex", scope="project"):
        return plan_changes(receipt, provider, scope, tuple(outcomes), document_context)

    def document(self, **kwargs):
        values = dict(path="AGENTS.md", kind="block", before=self.before, after=self.after)
        values.update(kwargs)
        return Outcome(**values)

    def assert_preserved(self, plan, receipt):
        self.assertEqual(plan.artifacts[0].route, "preserve")
        self.assertEqual(plan.changes, ())
        self.assertEqual(apply_delta(receipt, plan), json.loads(receipt) if receipt is not None else None)

    def test_absent_receipt_legacy_update_never_acquires(self):
        plan = self.plan(None, self.document())
        self.assertEqual(plan.artifacts[0].route, "legacy")
        self.assertEqual(plan.changes, ())
        self.assertIsNone(apply_delta(None, plan))

    def test_absent_entry_is_legacy_even_when_receipt_exists(self):
        del self.record["configs"]["AGENTS.md"]
        raw = self.receipt()
        plan = self.plan(raw, self.document())
        self.assertEqual(plan.artifacts[0].route, "legacy")
        self.assertEqual(apply_delta(raw, plan), self.record)

    def test_matching_claim_changes_one_entry_and_preserves_others(self):
        raw = self.receipt()
        original = json.loads(raw)
        plan = self.plan(raw, self.document())
        self.assertEqual(len(plan.changes), 1)
        projected = apply_delta(raw, plan)
        expected = json.loads(raw)
        expected["configs"]["AGENTS.md"]["sha256"] = config.block_digest(
            self.after.decode(), "codex", document_context)
        self.assertEqual(projected, expected)
        self.assertEqual(self.record, original)
        self.assertIn("historical-storage-authority", plan.artifacts[0].requirements)
        self.assertEqual(plan.artifacts[0].before_sha256, sha(self.before))
        self.assertEqual(plan.artifacts[0].after_sha256, sha(self.after))

    def test_modified_missing_or_ambiguous_claim_never_falls_back(self):
        raw = self.receipt()
        for before in (None, self.before.replace(b"old rule", b"user edit"),
                       self.before + self.body.encode(), b"\xff"):
            with self.subTest(before=before):
                self.assert_preserved(self.plan(raw, self.document(before=before)), raw)

    def test_changed_outside_slice_is_preserved(self):
        raw = self.receipt()
        for after in (self.after.replace(b"USER TAIL", b"deleted"),
                      self.after.replace(b"\r\n", b"\n"), b"no block"):
            with self.subTest(after=after):
                self.assert_preserved(self.plan(raw, self.document(after=after)), raw)

    def test_creation_requires_a_positive_event(self):
        after = config.merge_owned_block(None, "codex", "fresh\n", document_context).encode()
        unqualified = self.plan(None, self.document(before=None, after=after))
        self.assertEqual(unqualified.artifacts[0].route, "legacy")
        plan = self.plan(None, self.document(before=None, after=after, intent="create"))
        self.assertEqual(plan.artifacts[0].route, "creation-proposal")
        self.assertIn("fresh-creation-acquisition", plan.artifacts[0].requirements)
        projected = apply_delta(None, plan)
        self.assertNotIn("layout", projected)
        self.assertEqual(projected["files"], {})
        self.assertEqual(set(projected["configs"]), {"AGENTS.md"})

    def test_inserted_block_preserves_entire_foreign_document(self):
        original = "User\r\nРусский\rLast\n".encode()
        after = config.merge_owned_block(original.decode(), "codex", "fresh\n", document_context).encode()
        plan = self.plan(None, self.document(before=original, after=after, intent="create"))
        self.assertEqual(plan.artifacts[0].route, "creation-proposal")
        changed = self.plan(None, self.document(before=original, after=after.replace(b"User", b"Other"),
                                               intent="create"))
        self.assert_preserved(changed, None)

    def test_creation_never_adopts_existing_marked_block(self):
        self.assert_preserved(self.plan(None, self.document(intent="create")), None)

    def test_marked_adoption_is_conditional_on_exact_raw_preimage(self):
        plan = self.plan(None, self.document(intent="adopt", adoption_sha256=sha(self.before)))
        self.assertEqual(plan.artifacts[0].route, "adoption-proposal")
        self.assertIn("exact-user-adoption-approval", plan.artifacts[0].requirements)
        self.assertIn("selected-storage-acquisition", plan.artifacts[0].requirements)
        self.assertNotIn("layout", apply_delta(None, plan))
        wrong = self.plan(None, self.document(intent="adopt", adoption_sha256="0" * 64))
        self.assert_preserved(wrong, None)

    def test_adoption_cannot_override_claim(self):
        raw = self.receipt()
        self.assert_preserved(self.plan(raw, self.document(intent="adopt",
                             adoption_sha256=sha(self.before))), raw)

    def test_legacy_selection_preserves_exact_prefix_and_suffix(self):
        prefix, legacy, suffix = "😀\r\n", "# Shared Governance\rOld\r\n", "## Project policies\rUSER TAIL"
        before = prefix + legacy + suffix
        replacement = config.merge_owned_block(None, "codex", "fresh\n", document_context)
        after = prefix + replacement + suffix
        selection = (len(prefix), len(prefix + legacy))
        plan = self.plan(None, self.document(before=before.encode(), after=after.encode(),
                         intent="adopt", adoption_sha256=sha(before.encode()), adoption_span=selection))
        self.assertEqual(plan.artifacts[0].route, "adoption-proposal")
        self.assertEqual(len(plan.changes), 1)

    def test_bad_legacy_selections_preserve(self):
        before = "User\r\n# Shared Governance\r\nOld\r\n## Project policies\r\nTAIL"
        start, end = before.index("# Shared"), before.index("## Project")
        replacement = config.merge_owned_block(None, "codex", "fresh\n", document_context)
        after = before[:start] + replacement + before[end:]
        for span in (None, (start - 1, end), (start, end - 1), (True, end), (end, start)):
            with self.subTest(span=span):
                plan = self.plan(None, self.document(before=before.encode(), after=after.encode(),
                                 intent="adopt", adoption_sha256=sha(before.encode()), adoption_span=span))
                self.assert_preserved(plan, None)

    def test_legacy_selection_inside_code_is_preserved(self):
        before = "```markdown\n# Shared Governance\nExample\n```\nTAIL"
        start, end = before.index("# Shared"), before.index("TAIL")
        replacement = config.merge_owned_block(None, "codex", "fresh\n", document_context)
        after = before[:start] + replacement + before[end:]
        plan = self.plan(None, self.document(before=before.encode(), after=after.encode(),
                         intent="adopt", adoption_sha256=sha(before.encode()), adoption_span=(start, end)))
        self.assert_preserved(plan, None)

    def test_raw_end_without_ownership_remains_legacy(self):
        begin, end = config.MARKERS["codex"]
        before = (begin + "\nExample `" + end + "`\nUSER TEXT\n" + end).encode()
        plan = self.plan(None, self.document(before=before, after=self.after))
        self.assertEqual(plan.artifacts[0].route, "legacy")
        self.assertEqual(plan.changes, ())

    def test_raw_end_with_known_semantic_digest_preserves_outside(self):
        # Payload rejection prevents inserting reserved markers through that
        # renderer. This fixture represents a separately recorded old body.
        begin, end = config.MARKERS["codex"]
        before = (self.prefix + begin + "\nExample `" + end + "`\nOld\n"
                  + end + self.suffix)
        claim = config.block_digest(before, "codex", document_context)
        self.record["configs"]["AGENTS.md"]["sha256"] = claim
        after = config.merge_owned_block(before, "codex", "new\n", document_context,
                                         expected_digest=claim)
        plan = self.plan(self.receipt(), self.document(before=before.encode(), after=after.encode()))
        self.assertEqual(plan.artifacts[0].route, "recorded-proposal")
        self.assertIn("historical-storage-authority", plan.artifacts[0].requirements)

    def test_document_removal_requires_exact_outside_preservation(self):
        raw = self.receipt()
        after = config.remove_owned_block(self.before.decode(), "codex", self.claim,
                                           document_context).encode()
        plan = self.plan(raw, self.document(after=after, intent="remove"))
        self.assertEqual(plan.artifacts[0].route, "removal-proposal")
        self.assertNotIn("AGENTS.md", apply_delta(raw, plan)["configs"])
        self.assert_preserved(self.plan(raw, self.document(after=b"", intent="remove")), raw)

    def test_unrecorded_removal_is_not_planned(self):
        self.assert_preserved(self.plan(None, self.document(after=b"", intent="remove")), None)

    def test_file_update_create_adopt_and_remove_share_codec(self):
        path = ".codex/agents/other.toml"
        raw = self.receipt()
        update = Outcome(path, "file", b"other", b"new")
        plan = self.plan(raw, update)
        self.assertEqual(apply_delta(raw, plan)["files"][path], sha(b"new"))
        self.assert_preserved(self.plan(raw, Outcome(path, "file", b"edited", b"new")), raw)
        remove = self.plan(raw, Outcome(path, "file", b"other", None, "remove"))
        self.assertNotIn(path, apply_delta(raw, remove)["files"])
        fresh = Outcome(".codex/agents/new.toml", "file", None, b"new", "create")
        self.assertEqual(self.plan(None, fresh).artifacts[0].route, "creation-proposal")
        adopt = Outcome(path, "file", b"other", b"new", "adopt", sha(b"other"))
        self.assertEqual(self.plan(None, adopt).artifacts[0].route, "adoption-proposal")

    def test_partial_planning_does_not_gate_other_legacy_artifacts(self):
        raw = self.receipt()
        plan = self.plan(raw, self.document(before=b"edited"),
                         Outcome(".codex/agents/unrecorded.toml", "file", b"legacy", b"update"),
                         Outcome(".codex/agents/new.toml", "file", None, b"new", "create"))
        self.assertEqual([x.route for x in plan.artifacts],
                         ["preserve", "legacy", "creation-proposal"])
        projected = apply_delta(raw, plan)
        self.assertEqual(projected["configs"], self.record["configs"])
        self.assertEqual(projected["directories"], self.record["directories"])
        self.assertEqual(len(plan.changes), 1)

    def test_exact_receipt_bytes_are_precondition_not_reencoded_json(self):
        raw = self.receipt(separators=(",", ":"))
        plan = self.plan(raw, self.document())
        same_value = self.receipt(indent=2)
        self.assertEqual(json.loads(raw), json.loads(same_value))
        with self.assertRaisesRegex(ValueError, "STALE"):
            apply_delta(same_value, plan)
        with self.assertRaisesRegex(ValueError, "STALE"):
            apply_delta(None, plan)

    def test_layout_presence_and_value_are_preserved(self):
        for present in (False, True):
            if present:
                self.record["layout"] = ownership.LAYOUT
            raw = self.receipt()
            projected = apply_delta(raw, self.plan(raw, self.document()))
            self.assertEqual("layout" in projected, present)
            if present:
                self.assertEqual(projected["layout"], ownership.LAYOUT)

    def test_encoder_is_never_called(self):
        with patch.object(ownership, "encode_record", side_effect=AssertionError("no encoder")):
            raw = self.receipt()
            apply_delta(raw, self.plan(raw, self.document()))
            fresh = Outcome(".codex/agents/new.toml", "file", None, b"new", "create")
            self.assertNotIn("layout", apply_delta(None, self.plan(None, fresh)))

    def test_duplicate_json_and_wrong_identity_are_invalid_inputs(self):
        duplicate = b'{"schema":"orche.provider-install.v1","provider":"codex","scope":"project","files":{},"files":{}}'
        for raw in (duplicate, b"", self.receipt().replace(b'"project"', b'"global"')):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    self.plan(raw, self.document())
        with self.assertRaises(ValueError):
            self.plan(self.receipt(), self.document(), provider="claude")

    def test_aliases_and_cross_category_collisions_are_rejected(self):
        raw = self.receipt()
        cases = [
            (self.document(), self.document()),
            (Outcome(".codex/agents/OTHER.toml", "file", None, b"new", "create"),),
            (Outcome(".codex/agents/retained", "file", None, b"new", "create"),),
        ]
        for outcomes in cases:
            with self.subTest(outcomes=outcomes):
                with self.assertRaises(ValueError):
                    self.plan(raw, *outcomes)

    def test_unqualified_paths_and_unused_selection_are_rejected(self):
        for outcome in (Outcome("../escape", "file", None, b"x", "create"),
                        Outcome(".codex/config.toml", "file", None, b"x", "create"),
                        self.document(adoption_sha256=sha(self.before))):
            with self.subTest(outcome=outcome):
                with self.assertRaises(ValueError):
                    self.plan(None, outcome)

    def test_claude_payload_uses_same_plan_without_global_v1_blanket_hold(self):
        record = {"schema": ownership.SCHEMA, "provider": "claude", "scope": "global",
                  "files": {".claude/agents/role.md": sha(b"old")}}
        raw = self.receipt(record)
        plan = self.plan(raw, Outcome(".claude/agents/role.md", "file", b"old", b"new"),
                         provider="claude", scope="global")
        self.assertEqual(plan.artifacts[0].route, "recorded-proposal")
        self.assertIn("historical-storage-authority", plan.artifacts[0].requirements)
        self.assertEqual(apply_delta(raw, plan)["files"][".claude/agents/role.md"], sha(b"new"))

    def test_plan_is_immutable_and_not_an_acquisition_receipt(self):
        plan = self.plan(self.receipt(), self.document())
        with self.assertRaises(FrozenInstanceError):
            plan.provider = "claude"
        self.assertIsInstance(plan.changes, tuple)
        self.assertIsInstance(plan.artifacts[0].requirements, tuple)
        self.assertIn("atomic-owner-commit-and-rollback", plan.artifacts[0].requirements)

    def test_repeat_semantic_update_is_idempotent(self):
        raw = self.receipt()
        projected = apply_delta(raw, self.plan(raw, self.document()))
        repeated_raw = self.receipt(projected)
        repeated = self.plan(repeated_raw, self.document(before=self.after, after=self.after))
        self.assertEqual(apply_delta(repeated_raw, repeated), projected)

    def test_unknown_v1_binding_fields_are_not_accepted(self):
        self.record["binding"] = {"id": "not-authority"}
        with self.assertRaises(ValueError):
            self.plan(self.receipt(), self.document())

    def test_receipt_size_and_wrong_byte_types_are_invalid(self):
        with self.assertRaises(ValueError):
            self.plan(b" " * (ownership.MAX_BYTES + 1), self.document())
        raw = self.receipt()
        plan = self.plan(raw, self.document())
        for invalid in ("text", bytearray(raw), False):
            with self.subTest(invalid=type(invalid)):
                with self.assertRaises(ValueError):
                    self.plan(invalid, self.document())
                with self.assertRaises(ValueError):
                    apply_delta(invalid, plan)

    def test_existing_casefold_aliases_are_invalid_receipt(self):
        self.record["files"][".CODEX/agents/OTHER.toml"] = sha(b"other")
        with self.assertRaises(ValueError):
            self.plan(self.receipt(), self.document())

    def test_file_adoption_requires_complete_exact_preimage(self):
        path = ".codex/agents/role.toml"
        for before, digest, span in ((None, sha(b"old"), None),
                                     (b"old", sha(b"wrong"), None),
                                     (b"old", sha(b"old"), (0, 3))):
            plan = self.plan(None, Outcome(path, "file", before, b"new", "adopt", digest, span))
            self.assert_preserved(plan, None)

    def test_file_creation_with_existing_bytes_is_not_acquired(self):
        item = Outcome(".codex/agents/role.toml", "file", b"same", b"same", "create")
        self.assert_preserved(self.plan(None, item), None)

    def test_missing_proposed_result_does_not_replace_claim(self):
        raw = self.receipt()
        self.assert_preserved(self.plan(raw, self.document(after=None)), raw)

    def test_immutable_change_contains_only_serialized_entry_not_receipt(self):
        plan = self.plan(self.receipt(), self.document())
        change = plan.changes[0]
        self.assertEqual(set(json.loads(change.proposed_json)), {"kind", "blockKind", "sha256"})
        with self.assertRaises(FrozenInstanceError):
            change.path = "other"

    def test_no_entry_does_not_manufacture_layout_or_empty_receipt(self):
        record = {"schema": ownership.SCHEMA, "provider": "codex",
                  "scope": "project", "files": {}}
        raw = self.receipt(record)
        projected = apply_delta(raw, self.plan(raw, self.document()))
        self.assertEqual(projected, record)
        self.assertNotIn("configs", projected)
        self.assertNotIn("layout", projected)

    def test_marked_adoption_offsets_require_exact_integers(self):
        before = b"\n" + self.body.encode()
        after = b"\n" + config.merge_owned_block(None, "codex", "new\n", document_context).rstrip("\n").encode()
        valid = self.plan(None, self.document(before=before, after=after, intent="adopt",
                          adoption_sha256=sha(before), adoption_span=(1, len(before))))
        self.assertEqual(valid.artifacts[0].route, "adoption-proposal")
        for span in ((True, len(before)), (1.0, float(len(before)))):
            with self.subTest(span=span):
                plan = self.plan(None, self.document(before=before, after=after, intent="adopt",
                                 adoption_sha256=sha(before), adoption_span=span))
                self.assert_preserved(plan, None)

    def test_selection_validator_never_extends_new_owned_frame_into_suffix(self):
        from installation.receipt_plan import _legacy_selection
        begin, end = config.MARKERS["codex"]
        legacy = "# Shared Governance\nOld\n"
        suffix = "USER SUFFIX\n```markdown\n" + end + "\n```\nKEEP"
        before, after = legacy + suffix, begin + "\nNew\n" + suffix
        bounds = (0, after.index(end) + len(end))
        # The old END is a fenced example, so the selected preimage is valid.
        # Even supplied oversized new bounds cannot acquire its user suffix.
        # The complete planner also rejects this malformed rendered frame.
        with self.assertRaisesRegex(ValueError, "outside reviewed span changed"):
            _legacy_selection(before, after, bounds, (0, len(legacy)),
                              document_context, sha(before.encode()))

    def test_serialization_preserves_layout_presence_and_input(self):
        for layout in (False, True):
            record = json.loads(self.receipt())
            if layout:
                record["layout"] = ownership.LAYOUT
            unchanged = json.loads(json.dumps(record))
            payload = ownership.serialize_record(record, "codex", "project")
            self.assertEqual(ownership.decode_record(payload, "codex", "project"), record)
            self.assertEqual(record, unchanged)
            self.assertEqual("layout" in json.loads(payload), layout)

    def test_sdk_encoder_keeps_exact_existing_layout_contract(self):
        expected = dict(self.record, layout=ownership.LAYOUT)
        actual = ownership.encode_record(self.record["files"], "codex", "project",
                                         configs=self.record["configs"],
                                         directories=self.record["directories"])
        self.assertEqual(actual, (json.dumps(expected, sort_keys=True,
                         separators=(",", ":")) + "\n").encode())

    def test_serialization_validates_identity_schema_and_layout(self):
        for change in ({"provider": "claude"}, {"scope": "global"},
                       {"layout": "invented"}, {"binding": "unproved"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                ownership.serialize_record(dict(self.record, **change), "codex", "project")

    def test_encoded_size_limit_applies_to_both_codec_entry_points(self):
        record = dict(self.record, layout=ownership.LAYOUT)
        record["files"] = {".codex/agents/русский.toml": sha(b"other")}
        expected = ownership.serialize_record(record, "codex", "project")
        self.assertEqual(ownership.MAX_BYTES, 4 * 1024 * 1024)
        def old_encoder():
            return ownership.encode_record(record["files"], "codex", "project",
                configs=record["configs"], directories=record["directories"])
        with patch.object(ownership, "MAX_BYTES", len(expected)):
            self.assertEqual(ownership.serialize_record(record, "codex", "project"), expected)
            self.assertEqual(old_encoder(), expected)
        with patch.object(ownership, "MAX_BYTES", len(expected) - 1):
            with self.assertRaises(ValueError):
                ownership.serialize_record(record, "codex", "project")
            with self.assertRaises(ValueError):
                old_encoder()

    def test_serialize_delta_preserves_absence_and_exact_noop_bytes(self):
        self.assertIsNone(serialize_delta(None, self.plan(None, self.document())))
        raw = self.receipt(indent=4)
        self.assertEqual(serialize_delta(raw, self.plan(raw)), raw)

    def test_serialize_delta_projects_without_layout_or_unrelated_changes(self):
        raw = self.receipt()
        plan = self.plan(raw, self.document())
        with patch.object(ownership, "encode_record", side_effect=AssertionError("false layout")):
            result = serialize_delta(raw, plan)
        self.assertEqual(ownership.decode_record(result, "codex", "project"), apply_delta(raw, plan))
        self.assertNotIn("layout", json.loads(result))
        self.assertEqual(plan.artifacts[0].requirements[-1], "historical-storage-authority")

    def test_serialize_delta_checks_currentness_and_capacity(self):
        raw = self.receipt()
        plan = self.plan(raw, self.document())
        with self.assertRaises(ValueError):
            serialize_delta(raw + b" ", plan)
        expected = serialize_delta(raw, plan)
        with patch.object(ownership, "MAX_BYTES", max(len(raw), len(expected))):
            self.assertEqual(serialize_delta(raw, plan), expected)
        # The receipt must fit the decoder; an expanding file map exceeds the output cap.
        empty = ownership.serialize_record({"schema": ownership.SCHEMA, "provider": "codex",
                                           "scope": "project", "files": {}}, "codex", "project")
        created = self.plan(empty, Outcome(".codex/agents/new.toml", "file", None, b"new", "create"))
        with patch.object(ownership, "MAX_BYTES", len(empty)):
            with self.assertRaises(ValueError):
                serialize_delta(empty, created)


if __name__ == "__main__":
    unittest.main()
