"""Pure exact-current Codex block replacement proposals; no installation."""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from installation import configuration as config, ownership
from installation.receipt_plan import Outcome, plan_changes, apply_delta, serialize_delta
from installer_markdown import document_context


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


class SelectedBlockReceiptPlanTests(unittest.TestCase):
    def fixture(self, marked=True, scope="project"):
        prefix = "\ufeffUser caf\u00e9 \U0001f600\r\n"
        begin, end = config.MARKERS["codex"]
        body = (begin + "\r\nOld\r\n" + end if marked
                else "# Shared Governance\r\nOld\r\n")
        before = prefix + body + "\r\n## User tail\r\nKeep\rLast"
        span = (len(prefix), len(prefix + body))
        after = config.render_selected_document(
            before, "codex", "# Shared Governance\nNew\n", document_context,
            document_digest=sha(before.encode()), span=span)
        return Outcome("AGENTS.md" if scope == "project" else ".codex/AGENTS.md",
                       "block", before.encode(), after.encode(), "replace",
                       sha(before.encode()), span)

    def raw(self, item, claim="stale", layout=False, scope="project"):
        record = {"schema": ownership.SCHEMA, "provider": "codex", "scope": scope,
                  "files": {}, "configs": {}}
        if claim is not None:
            digest = (config.block_digest(item.before.decode(), "codex", document_context)
                      if claim == "matching" else sha(b"historical"))
            record["configs"][item.path] = {
                "kind": "block", "blockKind": "codex", "sha256": digest}
        if layout:
            record["layout"] = ownership.LAYOUT
        return json.dumps(record, indent=2).encode()

    def plan(self, item, raw=None, scope="project", provider="codex"):
        return plan_changes(raw, provider, scope, (item,), document_context)

    def preserved(self, item, raw=None):
        plan = self.plan(item, raw)
        self.assertEqual(plan.artifacts[0].route, "preserve")
        self.assertEqual(plan.changes, ())
        self.assertEqual(serialize_delta(raw, plan), raw)

    def test_marked_and_legacy_absent_matching_stale_claims(self):
        for scope in ("project", "global"):
            for marked in (True, False):
                item = self.fixture(marked, scope)
                for claim in (None, "stale", "matching") if marked else (None, "stale"):
                    for layout in (False, True):
                        with self.subTest(scope=scope, marked=marked, claim=claim, layout=layout):
                            raw = self.raw(item, claim, layout, scope)
                            plan = self.plan(item, raw, scope)
                            artifact = plan.artifacts[0]
                            self.assertEqual(artifact.route, "selected-replacement-proposal")
                            self.assertEqual(artifact.requirements, (
                                "artifact-and-receipt-currentness", "atomic-owner-commit-and-rollback",
                                "exact-current-replacement-approval", "selected-storage-acquisition"))
                            self.assertEqual((artifact.before_sha256, artifact.after_sha256),
                                             (sha(item.before), sha(item.after)))
                            expected = json.loads(raw)
                            old = expected["configs"].get(item.path)
                            expected["configs"][item.path] = {
                                "kind": "block", "blockKind": "codex",
                                "sha256": config.block_digest(item.after.decode(), "codex", document_context)}
                            self.assertEqual(apply_delta(raw, plan), expected)
                            self.assertEqual(json.loads(serialize_delta(raw, plan)), expected)
                            self.assertEqual(plan.changes[0].expected_json,
                                             None if old is None else json.dumps(old, sort_keys=True, separators=(",", ":")))
                plan = self.plan(item, None, scope)
                self.assertEqual(plan.artifacts[0].route, "selected-replacement-proposal")
                self.assertNotIn("layout", apply_delta(None, plan))

    def test_missing_preimages_hashes_and_spans(self):
        for marked in (True, False):
            item = self.fixture(marked)
            for changed in (replace(item, before=None), replace(item, after=None),
                            replace(item, adoption_sha256=None), replace(item, adoption_sha256="0" * 64),
                            replace(item, adoption_span=None)):
                with self.subTest(marked=marked, changed=changed):
                    self.preserved(changed)

    def test_invalid_character_spans_and_crlf_boundaries(self):
        for marked in (True, False):
            item = self.fixture(marked)
            start, end = item.adoption_span
            spans = ([start, end], (True, end), (float(start), end), (start,),
                     (end, start), (start, len(item.before) + 1), (start - 1, end),
                     (start, end - 1),
                     (len(item.before.decode()[:start].encode()),
                      len(item.before.decode()[:end].encode())))
            for span in spans:
                with self.subTest(marked=marked, span=span):
                    self.preserved(replace(item, adoption_span=span))

    def test_full_raw_hash_rejects_outside_only_edit_and_normalized_hash(self):
        for marked in (True, False):
            item = self.fixture(marked)
            self.preserved(replace(item, before=item.before + b"outside"))
            self.preserved(replace(item, adoption_sha256=sha(item.before.replace(b"\r\n", b"\n"))))

    def test_changed_outside_and_extra_marked_lf_rejected(self):
        for marked in (True, False):
            item = self.fixture(marked)
            after = item.after.decode()
            bounds = config.owned_block(after, "codex", document_context)
            for changed in ("X" + after, after + "X", after[:bounds[1]] + "\n\n" + after[bounds[1]:]):
                self.preserved(replace(item, after=changed.encode()))
            if marked:
                self.preserved(replace(item, after=(after[:bounds[1]] + "\n" + after[bounds[1]:]).encode()))

    def test_closed_literal_end_and_unclosed_or_multiple_frames(self):
        item = self.fixture()
        before = item.before.decode()
        begin, end = config.MARKERS["codex"]
        start, stop = item.adoption_span
        body = begin + "\nExample:\n```markdown\n" + end + "\n```\nOld\n" + end
        before = before[:start] + body + before[stop:]
        span = (start, start + len(body))
        after = config.render_selected_document(before, "codex", "Fresh\n", document_context,
                                                document_digest=sha(before.encode()), span=span)
        valid = replace(item, before=before.encode(), after=after.encode(),
                        adoption_sha256=sha(before.encode()), adoption_span=span)
        self.assertEqual(self.plan(valid).artifacts[0].route, "selected-replacement-proposal")
        for malformed in (begin + "\n```\n" + end, begin + "\nOld",
                          begin + "\n" + end + "\n" + begin + "\n" + end,
                          begin + " malformed\nOld\n" + end):
            bad = before[:start] + malformed + before[span[1]:]
            selected = (start, start + len(malformed))
            self.preserved(replace(valid, before=bad.encode(), adoption_sha256=sha(bad.encode()),
                                   adoption_span=selected))
            bad_after = after[:start] + malformed + after[config.owned_block(after, "codex", document_context)[1]:]
            self.preserved(replace(valid, after=bad_after.encode()))

    def test_malformed_marker_outside_valid_frame_is_rejected(self):
        item = self.fixture()
        for field in ("before", "after"):
            changed = getattr(item, field) + b"\n<!-- BEGIN ORCHESTRARIUM CODEX PACK broken\n"
            values = {field: changed}
            if field == "before":
                values["adoption_sha256"] = sha(changed)
            self.preserved(replace(item, **values))

    def test_wrong_provider_or_document_kind(self):
        item = self.fixture()
        for provider, path in (("claude", ".claude/CLAUDE.md"), ("claude", ".claude/AGENTS.md")):
            changed = replace(item, path=path)
            plan = self.plan(changed, provider=provider)
            self.assertEqual(plan.artifacts[0].route, "preserve")
        with self.assertRaises(ValueError):
            self.plan(replace(item, path=".codex/config.toml"))

    def test_alias_malformed_receipt_and_stale_apply(self):
        item = self.fixture()
        raw = self.raw(item)
        with self.assertRaises(ValueError):
            plan_changes(raw, "codex", "project", (item, item), document_context)
        for invalid in (b"not json", b"{}", raw.replace(b'"blockKind": "codex"', b'"blockKind": "claude"')):
            with self.assertRaises(ValueError):
                self.plan(item, invalid)
        plan = self.plan(item, raw)
        for apply in (apply_delta, serialize_delta):
            with self.assertRaisesRegex(ValueError, "E_RECEIPT_PLAN_STALE"):
                apply(raw + b"\n", plan)
        changed = replace(plan, changes=(replace(plan.changes[0], expected_json=None),))
        with self.assertRaisesRegex(ValueError, "E_RECEIPT_PLAN_STALE"):
            apply_delta(raw, changed)

    def test_unrelated_metadata_and_category_aliases_remain_guarded(self):
        item = self.fixture()
        record = json.loads(self.raw(item, layout=True))
        record["files"][".agents/skills/other/SKILL.md"] = sha(b"other")
        record["configs"][".agents/.agents-mode.yaml"] = {"kind": "file", "sha256": sha(b"mode")}
        record["directories"] = [".agents/skills/retained"]
        raw = json.dumps(record).encode()
        result = apply_delta(raw, self.plan(item, raw))
        self.assertEqual(result["files"], record["files"])
        self.assertEqual(result["directories"], record["directories"])
        self.assertEqual(result["layout"], record["layout"])
        self.assertEqual(result["configs"][".agents/.agents-mode.yaml"],
                         record["configs"][".agents/.agents-mode.yaml"])
        del record["configs"][item.path]
        record["directories"].append(item.path)
        with self.assertRaises(ValueError):
            self.plan(item, json.dumps(record).encode())
        with self.assertRaises(ValueError):
            self.plan(replace(item, path="agents.md"), raw)

    def test_adoption_still_refuses_any_claim_and_update_retains_history(self):
        item = self.fixture()
        for claim in ("matching", "stale"):
            raw = self.raw(item, claim)
            self.preserved(replace(item, intent="adopt"), raw)
            update = replace(item, intent="update", adoption_sha256=None, adoption_span=None)
            if claim == "stale":
                self.preserved(update, raw)
            else:
                self.assertIn("historical-storage-authority", self.plan(update, raw).artifacts[0].requirements)
        update = replace(item, intent="update", adoption_sha256=None, adoption_span=None)
        self.assertEqual(self.plan(update).artifacts[0].route, "legacy")


if __name__ == "__main__":
    unittest.main()
