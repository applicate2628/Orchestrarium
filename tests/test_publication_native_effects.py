"""Public scanner checks for actual Git pre-push selections."""
from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import io
import runpy
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import pytest


SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "universal-hooks" / "scripts" / "check-publication-safety.py"


def load_scanner():
    name = "_publication_native_effects"
    spec = importlib.util.spec_from_file_location(name, SOURCE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.mark.usefixtures("isolated_standalone_review_modules")
class TestNativePublicationEffects(unittest.TestCase):
    object_format = "sha1"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="publication-native-")
        temporary_root = Path(self.temp.name)
        def cleanup():
            self.temp.cleanup()
            self.assertFalse(temporary_root.exists())
        self.addCleanup(cleanup)
        self.root = Path(self.temp.name) / "source"
        self.remote = Path(self.temp.name) / "remote.git"
        self.root.mkdir()
        self.git("init", "-q", "--initial-branch=main", "--object-format=" + self.object_format)
        self.git("config", "user.name", "Synthetic Author")
        self.git("config", "user.email", "author@example.invalid")
        self.git("init", "--bare", "-q", "--object-format=" + self.object_format, str(self.remote))
        self.git("remote", "add", "origin", str(self.remote))
        (self.root / "safe.txt").write_text("safe public content\n", encoding="utf-8")
        self.git("add", "safe.txt")
        self.git("commit", "-qm", "initial public fixture")
        self.commit = self.git("rev-parse", "HEAD").strip().decode()
        self.git("push", "-q", "origin", "HEAD:refs/heads/main")
        self.module = load_scanner()

    def git(self, *args, raw=None):
        result = subprocess.run([shutil.which("git"), "-C", str(self.root), *args], input=raw,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        return result.stdout

    @contextlib.contextmanager
    def in_root(self):
        before = Path.cwd()
        os.chdir(self.root)
        try:
            yield
        finally:
            os.chdir(before)

    def payload(self, rows):
        with self.in_root():
            policy = self.module._load_review_policy_module()
            observation, _exchanges = self.module._capture_review_repository(
                policy, self.root, self.module.time.monotonic() + 30)
            fmt = self.module._detect_git_object_format(30)
        self.assertEqual(observation["status"], "captured")
        endpoint = str(self.remote)
        encoded_endpoint = json.dumps(endpoint, ensure_ascii=True, separators=(",", ":")).encode("ascii")
        raw = b"".join(b" ".join((a, b.encode("ascii"), c, d.encode("ascii"))) + b"\n" for a, b, c, d in rows)
        return {"version": 1, "objectFormat": fmt.name, "repositoryObservation": observation,
                "endpoint": endpoint, "endpointIdentity": "sha256:" + hashlib.sha256(encoded_endpoint).hexdigest(),
                "inputSha256": hashlib.sha256(raw).hexdigest(), "wireBase64": base64.b64encode(raw).decode("ascii")}

    def scan(self, payload):
        with self.in_root():
            return self.module._scan_native_push(payload, lambda _line: ())

    def zero(self):
        return "0" * len(self.commit)

    def test_native_post_scan_currentness_does_not_replace_prior_refusal(self):
        mod = self.module
        payload = self.payload([(b"refs/heads/main", self.commit, b"refs/heads/alias", self.zero())])
        captured = payload["repositoryObservation"]
        unavailable = {"status": "unavailable", "repository": None, "diagnostic": "metadata-unavailable"}
        timeout = mod._refusal("PS-MSG-READ-TIMEOUT", "deadline")
        for kind, after, expected, captures in (
            ("refusal", unavailable, timeout, 1),
            ("clean", unavailable, mod._refusal("PS-INPUT-REFUSAL", "native-repository-currentness"), 2),
            ("clean", captured, None, 2),
        ):
            with self.subTest(kind=kind, status=after["status"]):
                history = mod.ScanOutcome(kind, "native-push", refusal=timeout if kind == "refusal" else None)
                with mock.patch.object(mod, "_capture_review_repository", side_effect=[(captured, ()), (after, ())]) as observation, \
                        mock.patch.object(mod, "_scan_selected_history_async", return_value=history):
                    actual = self.scan(payload)
                self.assertEqual(actual.refusal, expected)
                self.assertEqual(actual.kind, "refusal" if expected else "clean")
                self.assertEqual(observation.call_count, captures)


    def test_object_ids_stream_through_shared_git_reader(self):
        mod = self.module
        with self.in_root():
            fmt = mod._detect_git_object_format(15)
        oid = "a" * fmt.hex_length

        async def shared_reader(_argv, *, on_line=None, **options):
            self.assertIsNotNone(on_line)
            self.assertEqual(options["line_cap"], fmt.hex_length)
            self.assertIsNone(on_line(oid.upper().encode("ascii")))
            return 0, ()

        with mock.patch.object(mod, "_read_git_lines_bounded", side_effect=shared_reader):
            async def exercise():
                return await mod._read_git_oid_lines_bounded(
                    (sys.executable, "-c", "raise SystemExit(1)"),
                    object_format=fmt, count_cap=2, byte_cap=fmt.list_byte_cap(2),
                    deadline=asyncio.get_running_loop().time() + 3,
                )
            self.assertEqual(asyncio.run(exercise()), (oid,))


    def test_parent_graph_validated_rows_arrive_without_collecting_raw_output(self):
        mod = self.module
        fmt = mod._detect_git_object_format(15)
        first, second = "1" * fmt.hex_length, "2" * fmt.hex_length
        streamed = []

        async def read_with_sink(_argv, *, on_line=None, **_options):
            self.assertIsNotNone(on_line)
            for raw in (f"{first} {second}".encode("ascii"), second.encode("ascii")):
                streamed.append(raw)
                self.assertIsNone(on_line(raw))
            return 0, ()

        with mock.patch.object(mod, "_read_git_lines_bounded", side_effect=read_with_sink):
            async def exercise():
                return await mod._read_parent_graph_bounded(
                    ("unused",), object_format=fmt, deadline=asyncio.get_running_loop().time() + 20,
                )
            graph = asyncio.run(exercise())
        self.assertEqual(len(streamed), 2)
        self.assertEqual(graph, ((first, (second,)), (second, ())))


    def test_graph_budget_preserves_indexed_scope_and_rejects_duplicate_rows(self):
        mod = self.module
        fmt = mod._SUPPORTED_OBJECT_FORMATS[self.object_format]
        oids = [str(side) * fmt.hex_length for side in (1, 2, 3)]
        seen = set()

        def admit(oid, _parents):
            if oid in seen:
                return False
            seen.add(oid)
            return True

        async def attempt(rows, store=None):
            async def read(_argv, *, on_line, **_options):
                for oid in rows:
                    problem = on_line(oid.encode("ascii"))
                    if problem is not None:
                        return problem
                return 0, ()
            with mock.patch.object(mod, "_read_git_lines_bounded", side_effect=read), \
                    mock.patch.object(mod, "_MAX_COMMITS", 2):
                return await mod._read_parent_graph_bounded(
                    ("unused",), deadline=asyncio.get_running_loop().time() + 5,
                    object_format=fmt, store_row=store,
                )

        self.assertEqual(asyncio.run(attempt(oids)).reason, "count")
        self.assertEqual(asyncio.run(attempt(oids, admit)), ())
        self.assertEqual(seen, set(oids))
        seen.clear()
        self.assertEqual(asyncio.run(attempt(oids + [oids[2]], admit)).reason, "parent-graph")


    def test_compact_graph_spools_total_bytes_but_still_checks_each_frame(self):
        mod = self.module
        fmt = mod._SUPPORTED_OBJECT_FORMATS[self.object_format]
        oid = "1" * fmt.hex_length
        output = (oid + "\n").encode("ascii")
        argv = (sys.executable, "-B", "-c", "import sys; sys.stdout.buffer.write(" + repr(output) + ")")

        async def read(indexed, frame_limit=1_048_576):
            accepted = []
            def store(commit, parents):
                accepted.append((commit, parents))
                return True
            with mock.patch.object(mod, "_MAX_PARENT_GRAPH_BYTES", fmt.hex_length), mock.patch.object(
                mod, "_MAX_COMMIT_TREE_BYTES", frame_limit,
            ):
                result = await mod._read_parent_graph_bounded(
                    argv, deadline=asyncio.get_running_loop().time() + 10, object_format=fmt,
                    store_row=store, indexed_only=indexed,
                )
                return result, accepted

        legacy, seen = asyncio.run(read(False))
        self.assertEqual(legacy.reason, "selection-bytes")
        self.assertEqual(seen, [])
        compact, seen = asyncio.run(read(True))
        self.assertEqual(compact, ())
        self.assertEqual(seen, [(oid, ())])
        malformed, seen = asyncio.run(read(True, fmt.hex_length - 1))
        self.assertEqual(malformed.failure_id, "PS-MSG-FRAME")
        self.assertEqual(seen, [])


    def test_native_quiet_budget_tracks_only_fresh_decoded_work(self):
        mod = self.module
        tick = [10.0]
        fake = mod._ScanInactivity(11.0, 1.0, clock=lambda: tick[0])
        tick[0] = 10.6
        fake.observe_unit()
        self.assertAlmostEqual(fake.remaining(), 1.0)
        tick[0] = 11.8
        fake.observe_unit()
        self.assertLess(fake.remaining(), 0)

        program = ("import sys,time;[(sys.stdout.buffer.write(bytes((48+i,10))),"
                   "sys.stdout.buffer.flush(),time.sleep(.13)) for i in range(8)]")
        argv = (sys.executable, "-B", "-c", program)

        async def scan(advancing):
            budget = mod._ScanInactivity(mod.time.monotonic() + .55, .55)
            observed = []
            def admit(row):
                self.assertEqual(row, str(len(observed)).encode("ascii"))
                observed.append(row)
                if advancing:
                    budget.observe_unit()
            outcome = await mod._read_git_lines_bounded(
                argv, byte_cap=128, line_cap=8, deadline=budget,
                accepted_codes=frozenset({0}), on_line=admit,
            )
            return outcome, observed
        outcome, observed = asyncio.run(scan(True))
        self.assertEqual(outcome, (0, ()))
        self.assertEqual(len(observed), 8)
        outcome, observed = asyncio.run(scan(False))
        self.assertEqual(outcome.failure_id, "PS-MSG-READ-TIMEOUT")
        self.assertLess(len(observed), 8)


    def test_native_quiet_budget_does_not_emit_clean_after_formatting(self):
        mod = self.module
        tick = [10.0]
        budget = mod._ScanInactivity(11.0, 1.0, clock=lambda: tick[0])
        kind_log = []
        refusal_log = []

        def formatting(outcome):
            kind_log.append(outcome.kind)
            if outcome.kind == "clean":
                tick[0] = 11.0
                return "clean proof", "", 0
            refusal_log.append(outcome.refusal.failure_id)
            return "", "refused proof", 2

        out, err = io.StringIO(), io.StringIO()
        with (mock.patch.object(mod, "_format_outcome", side_effect=formatting),
              contextlib.redirect_stdout(out), contextlib.redirect_stderr(err)):
            result = mod._emit_outcome(mod.ScanOutcome("clean", "native-push"), work_budget=budget)
        self.assertEqual(result, 2)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue(), "refused proof\n")
        self.assertEqual(kind_log, ["clean", "refusal"])
        self.assertEqual(refusal_log, ["PS-MSG-READ-TIMEOUT"])

        earlier = mod.ScanOutcome("refusal", "native-push", refusal=mod._refusal("PS-MSG-READ", "reader"))
        self.assertIs(mod._inactivity_checked_outcome(earlier, budget), earlier)


    def import_large_history(self):
        stream = bytearray()
        for number in range(1, 10_002):
            stream.extend(
                (f"commit refs/heads/local-first\nmark :{number}\n"
                 f"committer Synthetic Author <author@example.invalid> {1_700_000_000 + number} +0000\n"
                 "data 15\nsynthetic input\n").encode("ascii")
            )
            if number > 1:
                stream.extend(f"from :{number - 1}\n".encode("ascii"))
            stream.extend(b"\n")
        self.git("fast-import", "--quiet", raw=stream)

    def test_large_first_publication_of_valid_history_is_not_refused_for_count(self):
        # Use real unique Git commits and an empty receiver. No production
        # tuning, altered limits, synthetic findings, or published refs.
        import_root = self.root / "first-publication.git"
        self.git("init", "--bare", "-q", "--object-format=" + self.object_format, str(import_root))
        self.remote = import_root
        self.git("remote", "set-url", "origin", str(import_root))
        self.import_large_history()
        tip = self.git("rev-parse", "refs/heads/local-first").strip().decode("ascii")
        count = self.git("rev-list", "--count", tip).strip()
        self.assertEqual(count, b"10001")
        payload = self.payload([
            (b"refs/heads/local-first", tip, b"refs/heads/main", self.zero()),
        ])
        outcome = self.scan(payload)
        self.assertEqual(outcome.kind, "clean", outcome.refusal)
        self.assertEqual(len(outcome.history.commit_ids), 10_001)
        mod = self.module
        with self.in_root(), mock.patch.object(mod, "__injected_native_push__", payload, create=True):
            ranged = mod._scan_range(
                "origin", "refs/heads/main", lambda _line: (), source_revision=tip, receipt_coverage=True,
            )
        self.assertEqual(ranged.kind, "clean", ranged.refusal)
        self.assertEqual(len(ranged.history.commit_ids), 10_001)
        self.assertEqual(mod._format_outcome(ranged)[2], 0)
        self.assertEqual(self.git("--git-dir", str(import_root), "for-each-ref"), b"")


    def test_small_publication_does_not_rescan_large_receiver_history(self):
        self.import_large_history()
        base = self.git("rev-parse", "refs/heads/local-first").strip().decode("ascii")
        self.git("push", "-q", "origin", base + ":refs/heads/large")
        tree = self.git("rev-parse", base + "^{tree}").strip().decode("ascii")
        tip = self.git("commit-tree", tree, "-p", base, "-m", "one new commit").strip().decode("ascii")
        self.git("update-ref", "refs/heads/local-first", tip)
        payload = self.payload([(b"refs/heads/local-first", tip, b"refs/heads/large", base)])
        outcome = self.scan(payload)
        self.assertEqual(outcome.kind, "clean", outcome.refusal)
        self.assertEqual(outcome.history.commit_ids, (tip,))
        self.assertEqual(outcome.history.object_ids, (tip,))
        self.assertEqual(self.git("--git-dir", str(self.remote), "rev-parse", "refs/heads/large").strip(),
                         base.encode("ascii"))


    def test_tag_annotation_is_scanned_even_when_target_commit_is_remote(self):
        annotation = "TOKEN=" + "aB9" * 16
        self.git("tag", "-a", "extra", "-m", annotation)
        tag = self.git("rev-parse", "refs/tags/extra").strip().decode()
        outcome = self.scan(self.payload([(b"refs/heads/main", self.commit, b"refs/heads/alias", self.zero()),
                                         (b"refs/tags/extra", tag, b"refs/tags/extra", self.zero())]))
        self.assertEqual(outcome.kind, "findings", outcome)
        self.assertTrue(any(item.subject_kind == "tag-object" for item in outcome.findings))
        self.assertNotIn(annotation, self.module._format_outcome(outcome)[1])

    def test_native_commit_header_is_scanned_separately_from_message(self):
        marker = "TOKEN=" + "aB9" * 16
        tree = self.git("rev-parse", "HEAD^{tree}").strip().decode()
        raw = (f"tree {tree}\nparent {self.commit}\nauthor {marker} <author@example.invalid> 1 +0000\n"
               "committer Synthetic <author@example.invalid> 1 +0000\n\npublic message\n").encode()
        commit = self.git("hash-object", "-t", "commit", "-w", "--stdin", raw=raw).strip().decode()
        payload = self.payload([(commit.encode(), commit, b"refs/heads/main", self.commit)])
        outcome = self.scan(payload)
        self.assertEqual(outcome.kind, "findings")
        self.assertTrue(any(row.subject_kind == "commit-header" for row in outcome.findings))
        self.assertFalse(any(row.subject_kind == "commit-message" for row in outcome.findings))
        with self.in_root():
            legacy = self.module._scan_range("origin", "refs/heads/main", lambda _line: (), source_revision=commit)
        self.assertEqual(legacy.kind, "clean")

    def test_new_tree_names_are_scanned_when_blob_is_already_remote(self):
        blob = self.git("rev-parse", "HEAD:safe.txt").strip()
        marker = ("TOKEN=" + "aB9" * 16).encode()
        for filename in (marker, b".env"):
            with self.subTest(filename_kind="assignment" if filename == marker else "env"):
                raw_tree = b"100644 blob " + blob + b"\t" + filename + b"\n"
                tree = self.git("mktree", raw=raw_tree).strip().decode()
                commit = self.git("commit-tree", tree, "-p", self.commit, raw=b"public tree metadata fixture\n").strip().decode()
                payload = self.payload([(commit.encode(), commit, b"refs/heads/main", self.commit)])
                outcome = self.scan(payload)
                self.assertEqual(outcome.kind, "findings")
                self.assertEqual(outcome.history.blob_ids, ())
                self.assertTrue(any(row.subject_kind == "tree-path" for row in outcome.findings))
                published_ref = "refs/heads/public-metadata-" + ("assignment" if filename == marker else "env")
                self.git("push", "-q", "origin", commit + ":" + published_ref)
                next_commit = self.git("commit-tree", tree, "-p", commit, raw=b"new public metadata-only commit\n").strip().decode()
                next_payload = self.payload([(next_commit.encode(), next_commit, b"refs/heads/new-public", self.zero())])
                # A different advertised ref cannot exclude this new destination.
                self.assertEqual(self.scan(next_payload).kind, "findings")
                known_old = self.payload([(next_commit.encode(), next_commit, published_ref.encode(), commit)])
                self.assertEqual(self.scan(known_old).kind, "clean")

    def test_tag_chain_and_direct_roots_have_real_object_coverage(self):
        self.git("tag", "-a", "inner", "-m", "public inner annotation")
        inner = self.git("rev-parse", "refs/tags/inner").strip().decode()
        raw = f"object {inner}\ntype tag\ntag outer\ntagger Synthetic <author@example.invalid> 1 +0000\n\npublic outer annotation\n".encode()
        outer = self.git("hash-object", "-t", "tag", "-w", "--stdin", raw=raw).strip().decode()
        tree = self.git("rev-parse", "HEAD^{tree}").strip().decode()
        blob = self.git("hash-object", "-w", "--stdin", raw=b"other public blob\n").strip().decode()
        payload = self.payload([(b"refs/tags/outer", outer, b"refs/tags/outer", self.zero()),
                                (b"refs/object/tree", tree, b"refs/object/tree", self.zero()),
                                (b"refs/object/blob", blob, b"refs/object/blob", self.zero())])
        outcome = self.scan(payload)
        self.assertEqual(outcome.kind, "clean", outcome)
        receipt = json.loads(self.module._format_outcome(outcome)[0])
        self.assertEqual(receipt["version"], 4)
        self.assertNotIn("effectKind", receipt)
        self.assertEqual(receipt["tags"], 2)
        self.assertEqual(receipt["commits"], 1)
        self.assertGreaterEqual(receipt["objects"], 3)
        self.assertEqual(outcome.coverage.expected_count, receipt["objects"])
        self.assertEqual(outcome.coverage.scanned_count, receipt["objects"])
        self.assertNotIn(str(self.remote), self.module._format_outcome(outcome)[0])

    def test_zero_object_coverage_reports_observed_rows_without_claiming_ref_effects(self):
        rows = [(b"(delete)", self.zero(), b"refs/heads/main", self.commit)]
        for name, updates in (("observed-deletion-row", rows), ("empty-observed-wire", []),
                              ("native-known-old-root", [(b"refs/heads/main", self.commit, b"refs/heads/main", self.commit)])):
            with self.subTest(name=name):
                payload = self.payload(updates)
                outcome = self.scan(payload)
                self.assertEqual(outcome.kind, "clean", outcome)
                value = json.loads(self.module._format_outcome(outcome)[0])
                self.assertNotIn("effectKind", value)
                self.assertEqual(value["updates"], len(updates))
                self.assertEqual(value["coverageKind"], "objects")
                self.assertEqual(value["objects"], 0)
                self.assertEqual(value["commits"], 0)
                self.assertEqual(value["inputSha256"], payload["inputSha256"])
                self.assertIsNone(outcome.reap_certificate)

    def test_deletion_and_empty_wire_do_not_require_scanner_storage(self):
        deletion = [(b"(delete)", self.zero(), b"refs/heads/main", self.commit)]
        for updates in ([], deletion):
            with self.subTest(updates=len(updates)):
                payload = self.payload(updates)
                with mock.patch.object(self.module, "_HistoryIndex",
                                       side_effect=AssertionError("no scanner storage needed")):
                    outcome = self.scan(payload)
                self.assertEqual(outcome.kind, "clean", outcome)
                self.assertEqual(outcome.coverage.scanned_count, 0)

    def test_malformed_or_rebound_selection_does_not_become_noop(self):
        for field, value in (("inputSha256", "0" * 64), ("endpointIdentity", "sha256:" + "0" * 64),
                             ("objectFormat", "unknown"), ("wireBase64", None)):
            with self.subTest(field=field):
                payload = self.payload([])
                payload[field] = value
                self.assertEqual(self.scan(payload).kind, "refusal")
        self.assertEqual(self.scan(None).kind, "refusal")
        payload = self.payload([])
        payload["repositoryObservation"]["repository"] = {}
        self.assertEqual(self.scan(payload).kind, "refusal")

    def test_single_commit_v3_api_stays_separate(self):
        (self.root / "next.txt").write_text("next safe public content\n", encoding="utf-8")
        self.git("add", "next.txt")
        self.git("commit", "-qm", "next public commit\n\nTOKEN=" + "aB9" * 16 + " (deployment note)")
        with self.in_root():
            outcome = self.module._scan_range("origin", "refs/heads/main", lambda _line: (), source_revision="HEAD")
        self.assertEqual(outcome.kind, "clean", outcome)
        self.assertIn("receipt=v3", self.module._format_outcome(outcome)[0])

    def test_native_v3_union_uses_each_destinations_actual_old_commit(self):
        (self.root / "safe.txt").write_text("first branch update\n", encoding="utf-8")
        self.git("add", "safe.txt")
        self.git("commit", "-qm", "first branch update")
        first = self.git("rev-parse", "HEAD").strip().decode()
        marker = ("AK" + "IA" + "A" * 16).encode()
        old_blob = self.git("hash-object", "-w", "--stdin", raw=marker).strip()
        old_tree = self.git("mktree", raw=b"100644 blob " + old_blob + b"\tsecond.txt\n").strip().decode()
        second_old = self.git("commit-tree", old_tree, raw=b"separate old root\n").strip().decode()
        safe_blob = self.git("hash-object", "-w", "--stdin", raw=b"second safe update\n").strip()
        safe_tree = self.git("mktree", raw=b"100644 blob " + safe_blob + b"\tsecond.txt\n").strip().decode()
        second = self.git("commit-tree", safe_tree, "-p", second_old, raw=b"second branch update\n").strip().decode()
        payload = self.payload([(first.encode(), first, b"refs/heads/first", self.commit),
                                (second.encode(), second, b"refs/heads/second", second_old)])
        with self.in_root(), mock.patch.dict(self.module.__dict__, {"__injected_native_push__": payload}):
            outcome = self.module._scan_range("origin", "refs/heads/first", lambda _line: (), source_revision=first)
        self.assertEqual(outcome.kind, "clean", outcome)
        self.assertEqual(set(outcome.history.commit_ids), {first, second})
        self.assertNotIn(old_blob.decode(), outcome.history.blob_ids)
        self.assertIn("receipt=v3", self.module._format_outcome(outcome)[0])

    def test_native_commit_and_blob_coverage_and_receipt_binding(self):
        (self.root / "next.txt").write_text("next safe public content\n", encoding="utf-8")
        self.git("add", "next.txt")
        self.git("commit", "-qm", "next public commit")
        new = self.git("rev-parse", "HEAD").strip().decode()
        payload = self.payload([(b"refs/heads/main", new, b"refs/heads/main", self.commit)])
        outcome = self.scan(payload)
        self.assertEqual(outcome.kind, "clean", outcome)
        value = json.loads(self.module._format_outcome(outcome)[0])
        self.assertEqual(value["commits"], 1)
        self.assertGreater(value["blobs"], 0)
        self.assertEqual(value["selectionSha256"], hashlib.sha256(self.module._native_json_bytes(payload)).hexdigest())
        request = self.module._native_push_request(payload)
        documents = self.module._native_update_documents(request.updates)
        self.assertEqual(value["updateSetSha256"], hashlib.sha256(self.module._native_json_bytes(documents)).hexdigest())
        broken = self.module.replace(outcome, history=self.module.replace(outcome.history, object_set="0" * 64))
        self.assertEqual(self.module._format_outcome(broken)[2], 2)

    def test_compact_native_tree_frontier_preserves_exact_receipt(self):
        mod = self.module
        for outer in range(5):
            for inner in range(3):
                folder = self.root / f"group-{outer}" / f"part-{inner}"
                folder.mkdir(parents=True)
                (folder / "public.txt").write_text(f"synthetic record {outer}:{inner}\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "synthetic wide nested tree")
        tip = self.git("rev-parse", "HEAD").strip().decode()
        payload = self.payload([(b"refs/heads/main", tip, b"refs/heads/main", self.commit)])
        reference_order, compact_order = [], []

        def observe(rows):
            def detector(line):
                rows.append(line)
                return ()
            return detector

        with self.in_root():
            reference = mod._scan_native_push(payload, observe(reference_order), receipt_coverage=True)
            with (mock.patch.object(mod, "_MAX_TREE_FRONTIER", 2),
                  mock.patch.object(mod, "_TREE_FRONTIER_PAGE", 2)):
                compact = mod._scan_native_push(payload, observe(compact_order), receipt_coverage=True)
                legacy = self.scan(payload)
        self.assertEqual(reference.kind, "clean")
        self.assertGreater(len(reference_order), 15)
        self.assertEqual(compact_order, reference_order)
        self.assertEqual(compact.kind, "clean", compact.refusal)
        self.assertEqual(len(compact.history.blob_ids), 15)
        self.assertEqual(mod._format_outcome(compact), mod._format_outcome(reference))
        self.assertEqual(legacy.refusal, mod._refusal("PS-MSG-LIMIT", "tree-frontier"))

        pop = mod._PendingTrees.pop

        def lose_spilled_row(stack):
            if not stack._page and stack._stored:
                stack._db.execute("DELETE FROM tree_frontier WHERE ordinal = ?", (stack._stored - 1,))
            return pop(stack)

        with (self.in_root(), mock.patch.object(mod, "_TREE_FRONTIER_PAGE", 2),
              mock.patch.object(mod._PendingTrees, "pop", lose_spilled_row)):
            refused = mod._scan_native_push(payload, lambda _line: (), receipt_coverage=True)
        self.assertEqual(refused.kind, "refusal")
        self.assertEqual(refused.refusal, mod._refusal("PS-MSG-READ", "coverage-storage"))
        self.assertEqual(mod._format_outcome(refused)[2], 2)


    def test_compact_native_blob_count_preserves_exact_receipt_and_late_findings(self):
        mod = self.module
        for index in range(3):
            name = f"part-{index}.txt"
            (self.root / name).write_text(f"safe public fixture {index}\n", encoding="utf-8")
            self.git("add", name)
        self.git("commit", "-qm", "multiple synthetic public blobs")
        tip = self.git("rev-parse", "HEAD").strip().decode()
        rows = [(b"refs/heads/main", tip, b"refs/heads/main", self.commit)]
        payload = self.payload(rows)
        with self.in_root():
            compact = lambda: mod._scan_native_push(payload, lambda _line: (), receipt_coverage=True)
            reference = compact()
            with mock.patch.object(mod, "_MAX_BLOBS", 1):
                clean = compact()
                legacy = self.scan(payload)
        self.assertEqual(reference.kind, "clean", reference)
        self.assertEqual(clean.kind, "clean", clean)
        self.assertEqual(len(clean.history.blob_ids), 3)
        self.assertEqual(mod._format_outcome(clean), mod._format_outcome(reference))
        self.assertEqual((legacy.refusal.failure_id, legacy.refusal.reason), ("PS-MSG-LIMIT", "blob-count"))

        (self.root / "z-last.txt").write_text("TOKEN=" + "aB9" * 16 + "\n", encoding="utf-8")
        self.git("add", "z-last.txt")
        self.git("commit", "-qm", "synthetic detector fixture")
        head = self.git("rev-parse", "HEAD").strip().decode()
        payload = self.payload([(b"refs/heads/main", head, b"refs/heads/main", self.commit)])
        with self.in_root():
            found = compact()
            with mock.patch.object(mod, "_MAX_BLOBS", 1):
                unsafe = compact()
        self.assertEqual(unsafe.kind, "findings", unsafe)
        self.assertTrue(any(f.failure_id == "PS-FINDING-CONTENT" for f in unsafe.findings), unsafe.findings)
        self.assertEqual(mod._format_outcome(unsafe), mod._format_outcome(found))
        self.assertEqual(mod._format_outcome(unsafe)[2], 1)


    def test_blob_review_is_preserved_and_cannot_approve_tag_annotation(self):
        from tests.test_publication_review_policy import _record
        raw = ("TOKEN=" + "aB9" * 16 + "\n").encode()
        path = b"reviewed.txt"
        (self.root / path.decode()).write_bytes(raw)
        self.git("add", path.decode())
        self.git("commit", "-qm", "reviewed synthetic fixture")
        new = self.git("rev-parse", "HEAD").strip().decode()
        blob = self.git("rev-parse", "HEAD:reviewed.txt").strip().decode()
        payload = self.payload([(b"refs/heads/main", new, b"refs/heads/main", self.commit)])
        policy = self.module._load_review_policy_module()
        analysis = self.module.analyze_review_candidates(raw, path, subject_kind="history-blob", policy_module=policy)
        self.assertTrue(analysis["complete"])
        self.assertEqual(len(analysis["candidates"]), 1)
        candidate = analysis["candidates"][0]
        record = _record()
        record.pop("recordSha256")
        record["repository"] = payload["repositoryObservation"]["repository"]
        record["modes"] = ["range-blob-text"]
        record["rangeScope"] = {"kind": "exact-commits", "commits": [new]}
        occurrence = record["occurrences"][0]
        occurrence.update(rawPathBase64=base64.b64encode(path).decode(), blobOid=blob,
                          blobSha256=hashlib.sha256(raw).hexdigest(), blobByteCount=len(raw),
                          gitMode="100644", detector=candidate["detector"], candidate=candidate["candidate"],
                          reviewRegion=self.module._byte_region(raw, 0, len(raw)),
                          contexts=[{"id": "fixture", "region": self.module._byte_region(raw, 0, len(raw))}])
        record = policy.seal_record(record)
        synthetic_home = Path(self.temp.name) / "policy-home"
        origin = synthetic_home / ".agents" / "publication"
        origin.mkdir(parents=True)
        (origin / "reviewed-exceptions.json").write_bytes(policy.canonical_document(1, [record]))
        with mock.patch.object(policy.Path, "home", return_value=synthetic_home):
            read = policy.read_policy_snapshot(policy.resolve_trusted_origin(), self.root)
        self.assertEqual(len(read.usable_records), 1)
        def evaluation():
            return self.module.ReviewEvaluation(policy_module=policy, policy_read=read,
                    repository_observation=payload["repositoryObservation"], execution="gate-captured-v1")
        accepted = evaluation()
        with self.in_root():
            outcome = self.module._scan_native_push(payload, lambda _line: (), review_evaluation=accepted)
        self.assertEqual(outcome.kind, "clean", outcome)
        outcome = self.module.replace(outcome, review=accepted.evidence())
        value = json.loads(self.module._format_outcome(outcome)[0])
        self.assertEqual(value["status"], "qualified")
        self.assertEqual(value["review"]["applied"], 1)
        self.git("tag", "-a", "unreviewed", "-m", raw.decode().strip())
        tag = self.git("rev-parse", "refs/tags/unreviewed").strip().decode()
        payload = self.payload([(b"refs/heads/main", new, b"refs/heads/main", self.commit),
                                (b"refs/tags/unreviewed", tag, b"refs/tags/unreviewed", self.zero())])
        with self.in_root():
            outcome = self.module._scan_native_push(payload, lambda _line: (), review_evaluation=evaluation())
        self.assertEqual(outcome.kind, "findings", outcome)
        self.assertTrue(any(row.subject_kind == "tag-object" for row in outcome.findings))

    def test_public_native_cli_consumes_captured_payload_without_transcript(self):
        payload = self.payload([(b"(delete)", self.zero(), b"refs/heads/main", self.commit)])
        policy = self.module._load_review_policy_module()
        synthetic_home = Path(self.temp.name) / "empty-policy-home"
        synthetic_home.mkdir()
        with mock.patch.object(policy.Path, "home", return_value=synthetic_home):
            absent = policy.read_policy_snapshot(policy.resolve_trusted_origin(), self.root)
        output, errors = io.StringIO(), io.StringIO()
        with self.in_root(), mock.patch.object(sys, "argv", [str(SOURCE), "--native-push"]), \
                mock.patch.object(policy.Path, "home", return_value=synthetic_home), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            with self.assertRaises(SystemExit) as terminal:
                runpy.run_path(str(SOURCE), run_name="__main__", init_globals={
                    "__injected_native_push__": payload,
                })
        self.assertEqual(terminal.exception.code, 0, errors.getvalue())
        result = json.loads(output.getvalue())
        self.assertEqual(result["version"], 4)
        self.assertNotIn("effectKind", result)
        self.assertEqual(result["updates"], 1)
        self.assertEqual(result["objects"], 0)
        self.assertEqual(errors.getvalue(), "")

    def test_single_wire_owner_accepts_only_actual_normal_form_sources(self):
        for source in (self.commit.encode(), b"refs/heads/main", "refs/tags/public-α".encode(), b":/initial public fixture", b":/tab\tword", b":/line\rbreak"):
            with self.subTest(source=source):
                payload = self.payload([(source, self.commit, b"refs/heads/alias", self.zero())])
                parsed = self.module._native_push_request(payload)
                self.assertIsInstance(parsed, self.module.NativePushRequest)
                self.assertEqual(parsed.updates[0].local_ref, source)
                self.assertEqual(parsed.input_sha256, payload["inputSha256"])
        for source in (b":/line\nbreak", b"invalid\0ref"):
            with self.subTest(source=source):
                payload = self.payload([(source, self.commit, b"refs/heads/alias", self.zero())])
                self.assertIsInstance(self.module._native_push_request(payload), self.module.Refusal)

    def test_remote_peel_is_verified_for_noncommit_tag_target(self):
        blob = self.git("hash-object", "-w", "--stdin", raw=b"safe tag blob\n").strip().decode()
        raw = f"object {blob}\ntype blob\ntag blob-tag\ntagger Synthetic <author@example.invalid> 1 +0000\n\nsafe blob annotation\n".encode()
        tag = self.git("hash-object", "-t", "tag", "-w", "--stdin", raw=raw).strip().decode()
        async def check(peeled):
            return await self.module._local_remote_commit_tip_oids(
                (self.module.RemoteRefTip(b"refs/tags/blob-tag", tag, peeled),),
                deadline=asyncio.get_running_loop().time() + 30,
                object_format=self.module._SUPPORTED_OBJECT_FORMATS[self.object_format], include_object_roots=True)
        with self.in_root():
            self.assertEqual(asyncio.run(check(blob)), (tag,))
            rejected = asyncio.run(check(self.commit))
        self.assertIsInstance(rejected, self.module.Refusal)
        self.assertEqual(rejected.reason, "remote-ref-type")


class TestNativePublicationEffectsSHA256(TestNativePublicationEffects):
    object_format = "sha256"


class TestSourceAnnotationBoundary(unittest.TestCase):
    def test_inline_source_annotation_has_no_authority_for_metadata(self):
        module = load_scanner()
        text = 'TOKEN="' + "aB9" * 16 + '" # orchestrarium:public-token'
        for kind in ("commit-message", "commit-header", "tree-path", "tag-object", "future-metadata"):
            with self.subTest(metadata=kind):
                self.assertTrue(module._content_hits(text, "object", lambda _line: (), subject_kind=kind))
        for kind in ("tracked-blob", "path-blob", "history-blob", "git-object-blob"):
            with self.subTest(source=kind):
                self.assertEqual(module._content_hits(text, "source.txt", lambda _line: (), subject_kind=kind), [])

    def test_callable_source_lexicon_does_not_hide_native_metadata(self):
        module = load_scanner()
        text = "TOKEN=" + "aB9" * 16 + " (deployment note)"
        for kind in ("commit-header", "tree-path", "tag-object", "future-metadata"):
            with self.subTest(metadata=kind):
                self.assertTrue(module._content_hits(text, "object", lambda _line: (), subject_kind=kind))
        for kind in ("tracked-blob", "path-blob", "history-blob", "git-object-blob", "commit-message"):
            with self.subTest(compatible_context=kind):
                self.assertEqual(module._content_hits(text, "source.txt", lambda _line: (), subject_kind=kind), [])
        self.assertEqual(module._binary_content_hits(b"\0" + text.encode() + b"\0", "image.bin", lambda _line: ()), [])


@unittest.skipUnless(os.name == "nt", "native Windows owned-pipe lifecycle")
class TestNativeSelectionInputLifecycle(unittest.TestCase):
    def test_backpressure_timeout_settles_owned_job_before_joining_input(self):
        module = load_scanner()
        inner = '''import asyncio,importlib.util,json,sys
s=importlib.util.spec_from_file_location("_input_lifecycle",SCANNER)
m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m)
owner=m._WINDOWS_JOB.WindowsJobProcessV1
original=owner.settle
closures=[]
def observed(self,*a,**kw):
 c=original(self,*a,**kw);closures.append(c.complete);return c
owner.settle=observed
async def probe():
 results=[]
 for kind in ("lines","oids"):
  kwargs={"input_bytes":b"x"*(4*1024*1024),"byte_cap":1024,"deadline":asyncio.get_running_loop().time()+.2}
  argv=(sys.executable,"-B","-c","import time;time.sleep(30)")
  if kind=="lines":
   value=await m._read_git_lines_bounded(argv,line_cap=80,accepted_codes=frozenset({0}),**kwargs)
  else:
   value=await m._read_git_oid_lines_bounded(argv,count_cap=10,**kwargs)
  results.append({"kind":kind,"id":value.failure_id,"phase":value.phase,"reason":value.reason})
 print(json.dumps({"results":results,"closures":closures}),flush=True)
asyncio.run(probe())
'''.replace("SCANNER", repr(str(SOURCE)))
        owner = module._WINDOWS_JOB.WindowsJobProcessV1
        original = owner.settle
        closures = []
        def observed(self, *args, **kwargs):
            result = original(self, *args, **kwargs)
            closures.append(result)
            return result
        with mock.patch.object(owner, "settle", observed):
            result = module._run_windows_owned_process([sys.executable, "-I", "-B", "-c", inner],
                                                       text=True, timeout=4.0, env=None)
        self.assertEqual(result.returncode, 0, result.stderr)
        values = json.loads(result.stdout)
        self.assertEqual(values["closures"], [True, True])
        for row in values["results"]:
            self.assertIn(row["id"], {"PS-MSG-READ-TIMEOUT", "PS-MSG-REAP"})
            if row["id"] == "PS-MSG-READ-TIMEOUT":
                self.assertEqual(row["reason"], "deadline")
            else:
                self.assertIn("after-PS-MSG-READ-TIMEOUT-reader-deadline", row["reason"])
        self.assertTrue(closures and all(row.complete for row in closures))


if __name__ == "__main__":
    unittest.main()
