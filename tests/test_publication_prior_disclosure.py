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


class TestAnnotationOnlyProof(native.TestNativePublicationEffects):
    def tag_payload(self, *, target="HEAD", receiver_inventory=True):
        self.git("tag", "-a", "release-boundary", "-m", "synthetic annotation", target)
        name = b"refs/tags/release-boundary"
        oid = self.git("rev-parse", name.decode()).strip().decode()
        payload = self.payload([(name, oid, name, self.zero())])
        payload["receiverInventory"] = receiver_inventory
        return name, oid, payload

    def test_known_target_produces_positive_bound_tag_proof(self):
        _, oid, payload = self.tag_payload()
        outcome = self.scan(payload)
        self.assertEqual(outcome.kind, "clean", outcome)
        self.assertEqual(outcome.history.object_ids, (oid,))
        self.assertEqual(outcome.history.direct_tag_commit, self.commit)
        import json
        proof = json.loads(self.module._serialize_native_receipt_v4(outcome))["tagOnly"]
        self.assertEqual((proof["tag"], proof["commit"]), (oid, self.commit))

    def test_new_graph_and_unqualified_receiver_do_not_produce_tag_only_proof(self):
        _, _, payload = self.tag_payload(receiver_inventory=False)
        outcome = self.scan(payload)
        self.assertEqual(outcome.kind, "clean", outcome)
        self.assertIsNone(outcome.history.direct_tag_commit)
        self.assertEqual(outcome.history.commit_ids, (self.commit,))
        self.git("tag", "-d", "release-boundary")
        self.git("commit", "--allow-empty", "-qm", "not yet transmitted")
        _, _, payload = self.tag_payload()
        outcome = self.scan(payload)
        self.assertEqual(outcome.kind, "clean", outcome)
        self.assertTrue(outcome.history.commit_ids)
        self.assertIsNone(outcome.history.direct_tag_commit)

    def test_nested_tag_target_does_not_produce_proof_even_if_already_disclosed(self):
        self.git("tag", "-a", "inner-tag", "-m", "synthetic prior annotation")
        self.git("push", "-q", "origin", "refs/tags/inner-tag")
        _, oid, payload = self.tag_payload(target="refs/tags/inner-tag")
        outcome = self.scan(payload)
        self.assertEqual(outcome.kind, "clean", outcome)
        self.assertEqual(outcome.history.object_ids, (oid,))
        self.assertIsNone(outcome.history.direct_tag_commit)

    def test_existing_destination_or_concurrent_creation_refuses(self):
        name, oid, payload = self.tag_payload()
        row = self.module.RemoteRefTip(b"refs/heads/main", self.commit)
        appeared = self.module.RemoteRefTip(name, oid, self.commit)
        for advertisements in [((row, appeared),), ((row,), (row, appeared))]:
            with mock.patch.object(self.module, "_remote_ref_tip_oids", side_effect=advertisements):
                outcome = self.scan(payload)
            self.assertEqual(outcome.kind, "refusal", outcome)

    def test_mixed_push_does_not_read_prior_disclosed_large_tag_target(self):
        (self.root / "old-large.txt").write_bytes(b"x" * 128)
        self.git("add", "old-large.txt")
        self.git("commit", "-qm", "publish synthetic blob")
        self.git("push", "-q", "origin", "HEAD:refs/heads/main")
        self.git("tag", "-a", "old-blob", "-m", "synthetic annotation", "HEAD:old-large.txt")
        tag = self.git("rev-parse", "refs/tags/old-blob").strip().decode()
        target = self.git("rev-parse", "HEAD:old-large.txt").strip().decode()
        self.git("commit", "--allow-empty", "-qm", "new history")
        tip = self.git("rev-parse", "HEAD").strip().decode()
        payload = self.payload([
            (b"HEAD", tip, b"refs/heads/new", self.zero()),
            (b"refs/tags/old-blob", tag, b"refs/tags/old-blob", self.zero()),
        ])
        payload["receiverInventory"] = True
        with mock.patch.object(self.module, "_MAX_BLOB_BYTES", 64):
            outcome = self.scan(payload)
        self.assertEqual(outcome.kind, "clean", outcome)
        self.assertIn(tip, outcome.history.commit_ids)
        self.assertIn(tag, outcome.history.object_ids)
        self.assertNotIn(target, outcome.history.object_ids)
        self.assertIsNone(outcome.history.direct_tag_commit)
