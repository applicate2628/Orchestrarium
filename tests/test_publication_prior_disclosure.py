"""Native prior-disclosure scope, using real synthetic Git object graphs."""
from __future__ import annotations

import asyncio
from unittest import mock

import test_publication_native_effects as native


class TestPriorDisclosure(native.TestNativePublicationEffects):
    def publish_marker(self):
        # Synthetic detector fixture, not credential material.
        (self.root / "old.txt").write_text("TOKEN=" + "aB9" * 16 + "\n", encoding="utf-8")
        self.git("add", "old.txt")
        self.git("commit", "-qm", "published synthetic marker")
        published = self.git("rev-parse", "HEAD").strip().decode()
        self.git("push", "-q", "origin", "HEAD:refs/heads/main")
        (self.root / "old.txt").unlink()
        self.git("add", "-u")
        self.git("commit", "-qm", "remove synthetic fixture")
        return published, self.git("rev-parse", "HEAD").strip().decode()

    def test_prior_receiver_history_is_not_new_disclosure(self):
        published, tip = self.publish_marker()
        payload = self.payload([(tip.encode(), tip, b"refs/heads/new", self.zero())])
        self.assertEqual(self.scan(payload).kind, "findings")
        # This flag is normally captured by the gate, not user scan input.
        payload["receiverInventory"] = True
        outcome = self.scan(payload)
        self.assertEqual(outcome.kind, "clean", outcome)
        self.assertNotIn(published, outcome.history.commit_ids)

    def test_new_disclosure_still_fails_after_prior_inventory(self):
        _published, tip = self.publish_marker()
        (self.root / "new.txt").write_text("TOKEN=" + "xY8" * 16 + "\n", encoding="utf-8")
        self.git("add", "new.txt")
        self.git("commit", "-qm", "new synthetic fixture")
        tip = self.git("rev-parse", "HEAD").strip().decode()
        payload = self.payload([(tip.encode(), tip, b"refs/heads/new", self.zero())])
        payload["receiverInventory"] = True
        self.assertEqual(self.scan(payload).kind, "findings")

    def test_callback_old_roots_are_shared_across_actual_updates(self):
        published, tip = self.publish_marker()
        payload = self.payload([
            (tip.encode(), tip, b"refs/heads/new", self.zero()),
            (b"(delete)", self.zero(), b"refs/heads/main", published),
        ])
        self.assertEqual(self.scan(payload).kind, "clean")
        with self.in_root():
            request = self.module._native_push_request(payload)
            selected = asyncio.run(self.module._native_commit_range_selection(
                self.module.RangeRequest("origin", "refs/heads/new", tip),
                request, self.module.time.monotonic() + 30))
        self.assertNotIsInstance(selected, self.module.Refusal)
        self.assertNotIn(published, selected.expected_oids)
        self.assertIn(tip, selected.expected_oids)

    def test_unknown_advertised_object_never_excludes_new_history(self):
        _published, tip = self.publish_marker()
        payload = self.payload([(tip.encode(), tip, b"refs/heads/new", self.zero())])
        payload["receiverInventory"] = True
        async def absent(*args, **kwargs):
            return (self.module.RemoteRefTip(b"refs/heads/unknown", "1" * len(tip)),)
        with mock.patch.object(self.module, "_remote_ref_tip_oids", absent):
            self.assertEqual(self.scan(payload).kind, "findings")

    def test_unqualified_receiver_does_not_probe_nominal_inventory(self):
        _published, tip = self.publish_marker()
        payload = self.payload([(tip.encode(), tip, b"refs/heads/new", self.zero())])
        with mock.patch.object(self.module, "_remote_ref_tip_oids", side_effect=AssertionError("unqualified probe")):
            self.assertEqual(self.scan(payload).kind, "findings")

    def test_receiver_qualification_shape_is_strict(self):
        payload = self.payload([(b"refs/heads/main", self.commit, b"refs/heads/new", self.zero())])
        payload["receiverInventory"] = "true"
        self.assertIsInstance(self.module._native_push_request(payload), self.module.Refusal)

    def test_inventory_preserves_new_tree_path_context(self):
        blob = self.git("rev-parse", "HEAD:safe.txt").strip()
        tree = self.git("mktree", raw=b"100644 blob " + blob + b"\t.env\n").strip().decode()
        tip = self.git("commit-tree", tree, "-p", self.commit, raw=b"new context\n").strip().decode()
        payload = self.payload([(tip.encode(), tip, b"refs/heads/new", self.zero())])
        payload["receiverInventory"] = True
        outcome = self.scan(payload)
        self.assertEqual(outcome.kind, "findings")
        self.assertTrue(any(row.subject_kind == "tree-path" for row in outcome.findings))

    def test_inventory_preserves_new_tag_annotation(self):
        self.git("tag", "-a", "new-tag", "-m", "TOKEN=" + "aB9" * 16)
        tag = self.git("rev-parse", "refs/tags/new-tag").strip().decode()
        payload = self.payload([(b"refs/tags/new-tag", tag, b"refs/tags/new-tag", self.zero())])
        payload["receiverInventory"] = True
        outcome = self.scan(payload)
        self.assertEqual(outcome.kind, "findings")
        self.assertTrue(any(row.subject_kind == "tag-object" for row in outcome.findings))

    def test_probe_pins_no_redirect_without_exposing_endpoint_in_arguments(self):
        endpoint = "https://example.invalid/project.git"
        alias, env = self.module._remote_probe_binding(endpoint, no_redirect=True)
        count = int(env["GIT_CONFIG_COUNT"])
        self.assertNotIn(endpoint, alias)
        self.assertEqual(env[f"GIT_CONFIG_KEY_{count - 1}"], f"http.{endpoint}.followRedirects")
        self.assertEqual(env[f"GIT_CONFIG_VALUE_{count - 1}"], "false")

    def test_mode_only_change_retains_new_tree_metadata(self):
        blob = self.git("rev-parse", "HEAD:safe.txt").strip()
        tree = self.git("mktree", raw=b"100755 blob " + blob + b"\tsafe.txt\n").strip().decode()
        tip = self.git("commit-tree", tree, "-p", self.commit, raw=b"mode metadata\n").strip().decode()
        payload = self.payload([(tip.encode(), tip, b"refs/heads/new", self.zero())])
        payload["receiverInventory"] = True
        with self.in_root():
            selected = asyncio.run(self.module._native_push_selection(
                self.module._native_push_request(payload), self.module.time.monotonic() + 30))
        self.assertNotIsInstance(selected, self.module.Refusal)
        self.assertIn(tree, selected.object_oids)
        self.assertNotIn(blob.decode(), selected.object_oids)
        self.assertEqual(self.scan(payload).kind, "clean")
