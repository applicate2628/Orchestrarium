"""Native prior-disclosure scope, using real synthetic Git object graphs."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
import runpy
import sys
from unittest import mock, skipUnless

import test_publication_native_effects as native


@contextmanager
def serial_process_owners(module):
    """Make a forbidden nested Linux acquisition fail before its blocking lock."""
    if not sys.platform.startswith("linux"):
        yield
        return
    acquire = module.PosixProcessGroupOwnerV1.acquire
    lock = acquire.__func__.__globals__["_LINUX_SUBREAPER_LOCK"]
    nested = []

    def guarded_acquire():
        if lock.locked():
            nested.append("owned process requested while another owner is active")
            raise RuntimeError(nested[-1])
        return acquire()

    with mock.patch.object(module.PosixProcessGroupOwnerV1, "acquire", guarded_acquire):
        yield
    assert not nested, nested
    assert not lock.locked(), "scan retained its Linux process owner"


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

    def test_indexed_and_legacy_native_receipts_are_byte_identical(self):
        (self.root / "second.txt").write_bytes(b"Public second fixture\n")
        self.git("add", "second.txt")
        self.git("commit", "-qm", "public follow-up")
        tip = self.git("rev-parse", "HEAD").strip().decode()
        payload = self.payload([(tip.encode(), tip, b"refs/heads/main", self.commit)])
        mod = self.module
        with self.in_root(), mock.patch.object(sys, "path", [str(native.SOURCE.parent), *sys.path]):
            from transfer_binding import ScopeBinding
            scope = ScopeBinding(
                "synthetic-scope", payload["endpointIdentity"], self.object_format,
                "f" * 64, (self.commit,), "synthetic-local-receiver",
            )
            for receiver, serialize in (
                (None, mod._serialize_native_receipt_v4),
                (scope, mod._serialize_receiver_scoped_receipt_v5),
            ):
                with self.subTest(scoped=receiver is not None):
                    old = mod._scan_native_push(payload, lambda _line: (), receiver_scope=receiver)
                    new = mod._scan_native_push(
                        payload, lambda _line: (), receiver_scope=receiver, receipt_coverage=True,
                    )
                    self.assertEqual(old.kind, "clean", old.refusal)
                    self.assertEqual(new.kind, "clean", new.refusal)
                    self.assertIsInstance(new.coverage, mod._ReceiptCoverage)
                    self.assertTrue(old.native_selection.expected_parents)
                    self.assertTrue(new.native_selection.indexed_parent_graph)
                    self.assertEqual(new.native_selection.expected_parents, ())
                    for field in ("object_ids", "blob_ids", "tag_ids"):
                        sealed = getattr(new.history, field)
                        self.assertIsInstance(sealed, mod._SealedOids)
                        self.assertEqual(len(sealed), len(getattr(old.history, field)))
                    self.assertEqual(serialize(old), serialize(new))
                    invalid = mod.replace(new.coverage, selection_set="0" * 64)
                    with self.assertRaisesRegex(ValueError, "native coverage"):
                        serialize(mod.replace(new, coverage=invalid))
                    with self.assertRaisesRegex(ValueError, "native coverage"):
                        serialize(mod.replace(new, reap_certificate=None))
                    wrong_order = mod.replace(new.coverage, selection_order="0" * 64)
                    with self.assertRaisesRegex(ValueError, "native coverage"):
                        serialize(mod.replace(new, coverage=wrong_order))
                    impossible_tags = mod.replace(new.history.tag_ids, count=len(new.history.object_ids) + 1)
                    with self.assertRaisesRegex(ValueError, "native coverage"):
                        serialize(mod.replace(new, history=mod.replace(new.history, tag_ids=impossible_tags)))

    def test_indexed_and_legacy_guarded_range_receipts_are_byte_identical(self):
        self.git("commit", "--allow-empty", "-qm", "public guarded-range follow-up")
        tip = self.git("rev-parse", "HEAD").strip().decode()
        payload = self.payload([(tip.encode(), tip, b"refs/heads/main", self.commit)])
        mod = self.module
        with self.in_root(), mock.patch.object(mod, "__injected_native_push__", payload, create=True):
            old = mod._scan_range("origin", "refs/heads/main", lambda _line: (), source_revision=tip)
            indexed = mod._scan_range(
                "origin", "refs/heads/main", lambda _line: (), source_revision=tip, receipt_coverage=True,
            )
        self.assertEqual(old.kind, "clean", old.refusal)
        self.assertEqual(indexed.kind, "clean", indexed.refusal)
        self.assertIsInstance(indexed.coverage, mod._ReceiptCoverage)
        self.assertTrue(old.selection.expected_parents)
        self.assertTrue(indexed.selection.indexed_parent_graph)
        self.assertEqual(indexed.selection.expected_parents, ())
        self.assertEqual(mod._format_outcome(indexed), mod._format_outcome(old))
        self.assertEqual(mod._format_outcome(indexed)[2], 0)
        for mismatch in (
            {"coverage": mod.replace(indexed.coverage, selection_order="0" * 64)},
            {"coverage": mod.replace(indexed.coverage, expected_count=indexed.coverage.expected_count + 1)},
            {"reap_certificate": None},
        ):
            with self.subTest(field=next(iter(mismatch))):
                self.assertNotEqual(mod._format_outcome(mod.replace(indexed, **mismatch))[2], 0)

    def test_prior_receiver_history_is_not_new_disclosure(self):
        published, tip = self.publish_marker()
        payload = self.payload([(tip.encode(), tip, b"refs/heads/new", self.zero())])
        self.assertEqual(self.scan(payload).kind, "findings")
        # This flag is normally captured by the gate, not user scan input.
        payload["receiverInventory"] = True
        outcome = self.scan(payload)
        self.assertEqual(outcome.kind, "clean", outcome)
        self.assertNotIn(published, outcome.history.commit_ids)

    def test_edited_blob_distinguishes_inherited_and_new_machine_paths(self):
        path = self.root / "trace.txt"
        old = "retained=" + chr(68) + chr(58) + "/dev/synthetic-published/" + "\n"
        fresh = "fresh=" + chr(69) + chr(58) + "/dev/synthetic-new/" + "\n"
        path.write_text(old + "status=old\n", encoding="utf-8")
        self.git("add", "trace.txt")
        self.git("commit", "-qm", "synthetic baseline path")
        published = self.git("rev-parse", "HEAD").strip().decode()
        self.git("push", "-q", "origin", "HEAD:refs/heads/main")

        def scan_edit(data, moved=False):
            target = self.root / "other.txt" if moved else path
            target.write_text(data, encoding="utf-8")
            self.git("add", target.name)
            tree = self.git("write-tree").strip().decode()
            tip = self.git("commit-tree", tree, "-p", published, raw=b"synthetic transition\n").strip().decode()
            payload = self.payload([(tip.encode(), tip, b"refs/heads/main", published)])
            finder = self.module._path_finder(native.SOURCE)
            with serial_process_owners(self.module), self.in_root(), mock.patch.object(
                self.module, "__injected_native_push__", payload, create=True,
            ):
                return (
                    self.module._scan_native_push(payload, finder),
                    self.module._scan_range("origin", "refs/heads/main", finder, source_revision=tip),
                )

        for outcome in scan_edit(old + "status=updated\n"):
            self.assertEqual(outcome.kind, "clean", [
                (row.subject_kind, row.detector_class) for row in outcome.findings])

        run_git = self.module._run_range_git
        def unavailable_baseline(args, **kwargs):
            if "log" in args and "--raw" in args:
                raise self.module.subprocess.TimeoutExpired("optional baseline", 0)
            return run_git(args, **kwargs)
        with mock.patch.object(self.module, "_run_range_git", unavailable_baseline):
            for outcome in scan_edit(old + "status=updated\n"):
                self.assertEqual(outcome.kind, "findings")
                self.assertTrue(any(row.detector_class == "machine-path" for row in outcome.findings))

        for data in (old + "status=updated\n" + fresh, old + "status=updated\n" + old):
            for outcome in scan_edit(data):
                self.assertEqual(outcome.kind, "findings")
                self.assertTrue(any(row.detector_class == "machine-path" for row in outcome.findings))
        for outcome in scan_edit(old + "TOKEN=" + "aB9" * 16 + "\n"):
            self.assertEqual(outcome.kind, "findings")
            self.assertTrue(any(row.detector_class != "machine-path" for row in outcome.findings))
        for outcome in scan_edit(old, moved=True):
            self.assertEqual(outcome.kind, "findings")
            self.assertTrue(any(row.detector_class == "machine-path" for row in outcome.findings))

    def test_retained_matcher_serializes_with_reader_and_prior_disclosure(self):
        peer = self.root.parent / "synthetic-matcher.py"
        peer.write_text(
            "import json, re, sys\n"
            "sys.stdout.reconfigure(newline=chr(10))\n"
            "rules = [(row['binary'], re.compile(row['regex'])) "
            "for row in json.loads(sys.stdin.buffer.readline())]\n"
            "sys.stdout.write('orche-match-spans-v1\\n'); sys.stdout.flush()\n"
            "for frame in sys.stdin.buffer:\n"
            "    result = []\n"
            "    for row in json.loads(frame):\n"
            "        text = row['text']; hits = []\n"
            "        for index, (binary, pattern) in enumerate(rules):\n"
            "            if row['binary'] and not binary: continue\n"
            "            for match in pattern.finditer(text):\n"
            "                spans = [None if start < 0 else "
            "[len(text[:start].encode('utf-8')), len(text[:end].encode('utf-8'))] "
            "for start, end in match.regs]\n"
            "                hits.append([index, spans])\n"
            "        result.append(hits)\n"
            "    sys.stdout.write(json.dumps(result) + '\\n'); sys.stdout.flush()\n",
            encoding="utf-8",
        )
        wire = runpy.run_path(str(native.SOURCE.parent / "publication_match_wire.py"))
        wire["retained_matcher"] = lambda _python: peer
        create = self.module._create_owned_async_process

        async def create_peer(argv, **kwargs):
            if tuple(argv) == (str(peer),):
                argv = (sys.executable, "-B", str(peer))
            return await create(argv, **kwargs)

        with mock.patch.object(self.module, "__injected_matcher_wire__", wire, create=True), \
                mock.patch.object(self.module, "_create_owned_async_process", create_peer):
            self.test_edited_blob_distinguishes_inherited_and_new_machine_paths()

    def _edited_prior_path_with_later_blobs(self):
        old = "retained=" + chr(68) + chr(58) + "/dev/synthetic-published/\n"
        path = self.root / "a-retained.txt"
        path.write_text(old + "status=old\n", encoding="utf-8")
        self.git("add", path.name)
        self.git("commit", "-qm", "synthetic published path")
        published = self.git("rev-parse", "HEAD").strip().decode()
        self.git("push", "-q", "origin", "HEAD:refs/heads/main")
        path.write_text(old + "status=updated\n", encoding="utf-8")
        for index in range(8):
            (self.root / f"b-{index}.txt").write_text(f"public value {index}\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "synthetic edited path and public blobs")
        tip = self.git("rev-parse", "HEAD").strip().decode()
        return self.payload([(tip.encode(), tip, b"refs/heads/main", published)])

    def test_reader_reopens_lazily_after_prior_disclosure_proof(self):
        payload = self._edited_prior_path_with_later_blobs()
        readers = []

        def reader_factory():
            reader = self.module._AsyncGitObjectReader()
            readers.append(reader)
            return reader

        with serial_process_owners(self.module), self.in_root():
            outcome = asyncio.run(self.module._scan_native_push_async(
                payload, self.module._path_finder(native.SOURCE), reader_factory=reader_factory,
            ))
        self.assertEqual(outcome.kind, "clean", outcome.refusal)
        self.assertEqual(len(readers), 2 if sys.platform.startswith("linux") else 1,
                         "ordinary later blobs must reuse the reopened reader")
        self.assertTrue(all(reader.reap_certificate.complete for reader in readers))

    @skipUnless(sys.platform.startswith("linux"), "serialized Linux subreaper ownership")
    def test_prior_disclosure_requires_every_reader_reap_certificate(self):
        payload = self._edited_prior_path_with_later_blobs()
        module = self.module
        run_git = module._run_range_git
        for failed_reader in (1, 2):
            with self.subTest(failed_reader=failed_reader):
                readers = []
                proofs = []

                def reader_factory():
                    reader = module._AsyncGitObjectReader()
                    readers.append(reader)
                    if len(readers) == failed_reader:
                        finalize = reader.finalize
                        calls = 0

                        async def refuse_once():
                            nonlocal calls
                            result = await finalize()
                            calls += 1
                            if calls == 1 and result is None:
                                return module._refusal("PS-MSG-REAP", "synthetic-uncertified-reader")
                            return result

                        reader.finalize = refuse_once
                    return reader

                def observe_proof(args, **kwargs):
                    if "log" in args and "--raw" in args:
                        proofs.append(tuple(args))
                    return run_git(args, **kwargs)

                with serial_process_owners(module), self.in_root(), \
                        mock.patch.object(module, "_run_range_git", observe_proof):
                    outcome = asyncio.run(module._scan_native_push_async(
                        payload, module._path_finder(native.SOURCE), reader_factory=reader_factory,
                    ))
                self.assertEqual(outcome.kind, "refusal")
                self.assertEqual(outcome.refusal.failure_id, "PS-MSG-REAP")
                self.assertEqual(len(readers), failed_reader)
                self.assertEqual(bool(proofs), failed_reader == 2)
                self.assertTrue(all(reader.reap_certificate.complete for reader in readers))

    @skipUnless(sys.platform.startswith("linux"), "serialized Linux subreaper ownership")
    def test_failed_successor_spawn_preserves_spawn_refusal(self):
        payload = self._edited_prior_path_with_later_blobs()
        readers = []

        def reader_factory():
            arguments = {} if not readers else {"argv": (str(self.root / "absent-git"),)}
            reader = self.module._AsyncGitObjectReader(**arguments)
            readers.append(reader)
            return reader

        with serial_process_owners(self.module), self.in_root():
            outcome = asyncio.run(self.module._scan_native_push_async(
                payload, self.module._path_finder(native.SOURCE), reader_factory=reader_factory,
            ))
        self.assertEqual(outcome.kind, "refusal")
        self.assertEqual(outcome.refusal.failure_id, "PS-MSG-SPAWN")
        self.assertEqual(len(readers), 2)
        self.assertTrue(readers[0].reap_certificate.complete)
        self.assertIs(readers[1].state, self.module.ReaderState.SPAWN_FAILED)

    def test_older_published_machine_path_is_not_new_disclosure(self):
        file = self.root / "history.txt"
        prior = "trace=" + chr(68) + chr(58) + "/dev/synthetic-older/" + "\n"
        file.write_text(prior, encoding="utf-8")
        self.git("add", file.name)
        self.git("commit", "-qm", "synthetic path in published history")
        file.write_text("current public snapshot\n", encoding="utf-8")
        self.git("add", file.name)
        self.git("commit", "-qm", "synthetic ref no longer contains path")
        published_tip = self.git("rev-parse", "HEAD").strip().decode()
        self.git("push", "-q", "origin", "HEAD:refs/heads/main")

        def scan_text(value):
            file.write_text(value, encoding="utf-8")
            self.git("add", file.name)
            tree = self.git("write-tree").strip().decode()
            tip = self.git("commit-tree", tree, "-p", published_tip, raw=b"synthetic history test\n").strip().decode()
            payload = self.payload([(tip.encode(), tip, b"refs/heads/main", published_tip)])
            finder = self.module._path_finder(native.SOURCE)
            with self.in_root(), mock.patch.object(self.module, "__injected_native_push__", payload, create=True):
                return (self.module._scan_native_push(payload, finder),
                        self.module._scan_range("origin", "refs/heads/main", finder, source_revision=tip))

        for outcome in scan_text(prior + "new unrelated line\n"):
            self.assertEqual(outcome.kind, "clean")
        for value in (prior + prior, prior.replace("older", "novel")):
            for outcome in scan_text(value):
                self.assertEqual(outcome.kind, "findings")
                self.assertTrue(any(row.detector_class == "machine-path" for row in outcome.findings))

    def test_qualified_receiver_object_difference_excludes_shared_older_blobs(self):
        old = self.root / "already-published.txt"
        published_text = "published=" + chr(68) + chr(58) + "/dev/synthetic-shared/" + "\n"
        old.write_text(published_text, encoding="utf-8")
        self.git("add", old.name)
        self.git("commit", "-qm", "publish an ordinary object")
        shared = self.git("rev-parse", "HEAD:" + old.name).strip().decode()
        old.unlink()
        self.git("add", "-u")
        self.git("commit", "-qm", "delete the published object in final tree")
        previous = self.git("rev-parse", "HEAD").strip().decode()
        self.git("push", "-q", "origin", "HEAD:refs/heads/main")
        (self.root / "new-location.txt").write_text(published_text, encoding="utf-8")
        (self.root / "new-data.txt").write_text("Genuinely new synthetic object\n", encoding="utf-8")
        self.git("add", "new-location.txt", "new-data.txt")
        self.git("commit", "-qm", "publish new commit and reuse old object")
        tip = self.git("rev-parse", "HEAD").strip().decode()
        expected = (set(self.git("rev-list", "--objects", "--no-object-names", tip).decode().splitlines())
                    - set(self.git("rev-list", "--objects", "--no-object-names", previous).decode().splitlines()))
        self.assertNotIn(shared, expected)
        payload = self.payload([(tip.encode(), tip, b"refs/heads/main", previous)])
        mod = self.module

        async def select():
            request = mod._native_push_request(payload)
            deadline = mod.time.monotonic() + 30
            with mod._open_history_index(deadline) as index:
                range_selection = await mod._native_commit_range_selection(
                    mod.RangeRequest("origin", "refs/heads/main", tip), request, deadline, index,
                )
            with mod._open_history_index(deadline) as index:
                native_selection = await mod._native_push_selection(request, deadline, (tip,), index)
            return range_selection, native_selection

        finder = mod._path_finder(native.SOURCE)
        with self.in_root():
            for selection in asyncio.run(select()):
                self.assertNotIsInstance(selection, mod.Refusal)
                self.assertEqual(set(selection.object_oids), expected)
            outcome = mod._scan_native_push(payload, finder)
            self.assertEqual(outcome.kind, "clean", outcome.refusal)

        (self.root / "new-data.txt").write_text("TOKEN=" + "aB9" * 16 + "\n", encoding="utf-8")
        self.git("add", "new-data.txt")
        self.git("commit", "-qm", "exercise genuinely new content")
        novel = self.git("rev-parse", "HEAD").strip().decode()
        with self.in_root():
            outcome = mod._scan_native_push(
                self.payload([(novel.encode(), novel, b"refs/heads/main", previous)]), finder,
            )
        self.assertEqual(outcome.kind, "findings")
        self.assertTrue(any(row.detector_class != "machine-path" for row in outcome.findings))

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
        async def select():
            request = self.module._native_push_request(payload)
            deadline = self.module.time.monotonic() + 30
            with self.module._open_history_index(deadline) as index:
                return await self.module._native_commit_range_selection(
                    self.module.RangeRequest("origin", "refs/heads/new", tip),
                    request, deadline, index,
                )

        with self.in_root():
            selected = asyncio.run(select())
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

        async def select():
            request = self.module._native_push_request(payload)
            deadline = self.module.time.monotonic() + 30
            with self.module._open_history_index(deadline) as index:
                return await self.module._native_push_selection(request, deadline, (tip,), index)

        with self.in_root():
            selected = asyncio.run(select())
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
        serialize = self.module._serialize_native_receipt_v4
        proof = json.loads(serialize(outcome))["tagOnly"]
        self.assertEqual((proof["tag"], proof["commit"]), (oid, self.commit))
        with self.in_root():
            compact = self.module._scan_native_push(payload, lambda _line: (), receipt_coverage=True)
        self.assertIsInstance(compact.coverage, self.module._ReceiptCoverage)
        self.assertEqual(serialize(compact), serialize(outcome))
        wrong_tag = self.module.replace(compact.history.tag_ids, digest="0" * 64)
        wrong_history = self.module.replace(compact.history, tag_ids=wrong_tag)
        with self.assertRaisesRegex(ValueError, "native tag-only coverage"):
            serialize(self.module.replace(compact, history=wrong_history))

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

        mod = self.module
        checked = []
        verify = mod._verify_excluded_tag_targets

        async def observe(targets, *args):
            self.assertNotIsInstance(targets, dict)
            checked.extend(targets.items())
            return await verify(targets, *args)

        with (self.in_root(), mock.patch.object(mod, "_MAX_BLOB_BYTES", 64),
              mock.patch.object(mod, "_verify_excluded_tag_targets", observe)):
            compact = mod._scan_native_push(payload, lambda _line: (), receipt_coverage=True)
        self.assertEqual(compact.kind, "clean", compact.refusal)
        self.assertEqual(checked, [(target, "blob")])
        self.assertEqual(mod._format_outcome(compact), mod._format_outcome(outcome))

        async def drop_row(targets, *args):
            targets._db.execute("DELETE FROM excluded_tag_target WHERE oid=?", (target,))
            return await verify(targets, *args)

        with (self.in_root(), mock.patch.object(mod, "_MAX_BLOB_BYTES", 64),
              mock.patch.object(mod, "_verify_excluded_tag_targets", drop_row)):
            missing = mod._scan_native_push(payload, lambda _line: (), receipt_coverage=True)
        self.assertEqual(missing.refusal, mod._refusal("PS-MSG-READ", "coverage-storage"))
        self.assertEqual(mod._format_outcome(missing)[2], 2)
