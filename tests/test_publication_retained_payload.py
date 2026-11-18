"""Bounded retained payload and reread identity regression tests."""
from __future__ import annotations

import asyncio
import collections
import hashlib
import importlib.util
from pathlib import Path
import sys
import tracemalloc
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "_publication_payload_scanner",
    ROOT / "scripts/universal-hooks/scripts/check-publication-safety.py",
)
scanner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = scanner
SPEC.loader.exec_module(scanner)


def oid(kind, raw):
    digest = hashlib.sha1()
    digest.update(f"{kind} {len(raw)}\0".encode("ascii"))
    digest.update(raw)
    return digest.hexdigest()


class Reader:
    def __init__(self, objects, fault=None):
        self.objects = objects
        self.calls = collections.Counter()
        self.sequence = []
        self.bytes_read = 0
        self.retained_before_read = []
        self.fault = fault

    async def read(self, object_id, expected_type=None, *, scan_deadline):
        if tracemalloc.is_tracing():
            self.retained_before_read.append(tracemalloc.get_traced_memory()[0])
        self.calls[object_id] += 1
        self.sequence.append(object_id)
        kind, original = self.objects[object_id]
        raw = bytes(bytearray(original))
        self.bytes_read += len(raw)
        returned_oid = object_id
        if self.fault and self.calls[object_id] > 1 and kind == "blob":
            if self.fault == "read":
                return scanner._refusal("PS-MSG-READ", "fixture")
            if self.fault == "timeout":
                return scanner._refusal("PS-MSG-READ-TIMEOUT", "deadline")
            if self.fault == "type":
                kind = "tree"
            elif self.fault == "oid":
                returned_oid = "f" * 40
            elif self.fault == "size":
                raw += b"x"
            elif self.fault == "content":
                raw = b"z" + raw[1:]
        return scanner.ObjectReadSuccess(object_id, returned_oid, kind, raw)


def fixture(count=3, size=1024, repeated=False):
    objects = {}
    blobs = []
    for index in range(count):
        raw = b"\0" + bytes([65 + index]) * (size - 1)
        object_id = oid("blob", raw)
        blobs.append(object_id)
        objects[object_id] = ("blob", raw)
    pairs = [(f"file{index}".encode(), value) for index, value in enumerate(blobs)]
    if repeated:
        pairs.append((b"fileZ", blobs[0]))
    tree = b"".join(b"100644 " + name + b"\0" + bytes.fromhex(value)
                    for name, value in pairs)
    tree_id = oid("tree", tree)
    objects[tree_id] = ("tree", tree)
    order = (tree_id, *blobs)
    selection = scanner.NativePushSelection(
        None, (), order, scanner._SHA1_OBJECT_FORMAT, (tree_id,),
    )
    return selection, objects, blobs


def acquire(selection, reader, review=None):
    async def run():
        recorder = scanner.CoverageRecorder(
            selection.object_oids if isinstance(selection, scanner.NativePushSelection)
            else selection.expected_oids)
        return await scanner._acquire_history(
            selection, reader, lambda _line: [], recorder,
            asyncio.get_running_loop().time() + 30, review_evaluation=review,
        )
    return asyncio.run(run())


class RetainedPayloadTests(unittest.TestCase):
    def test_machine_path_detection_reused_but_subject_findings_remain_independent(self):
        from types import SimpleNamespace
        evaluation = scanner.ReviewEvaluation.__new__(scanner.ReviewEvaluation)
        evaluation.policy = scanner._load_review_policy_module()
        evaluation.read = SimpleNamespace(usable_records=(object(),))
        evaluation.repository_observation = {"status": "captured", "repository": {}, "diagnostic": "none"}
        evaluation.unresolved = 0
        evaluation._analysis = {}
        evaluation._machine_path_analysis = None
        evaluation._clean_line_analysis = scanner._CleanLineAnalysis()
        finder = mock.Mock(side_effect=lambda line: "marked" in line)
        arguments = dict(subject_kind="history-blob", mode="range-blob-text",
                         raw_path=b"sample.txt", blob_oid="1" * 40, git_mode="100644")
        for index in range(3):
            findings = evaluation.scan_text_subject(
                b"ordinary\nmarked\n", "sample.txt", finder,
                commit_oid=f"{index:040x}", display_locator=str(index), **arguments,
            )
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0].display_locator, str(index))
        self.assertEqual(finder.call_count, 2)
        self.assertEqual(evaluation.unresolved, 3)
        self.assertEqual(evaluation.scan_text_subject(
            b"ordinary\nmarked\n", "sample.txt", finder, commit_oid="3" * 40,
            machine_path_lines=frozenset(), **arguments), [])
        self.assertEqual(finder.call_count, 2)
        other = mock.Mock(return_value=False)
        self.assertEqual(evaluation.scan_text_subject(
            b"ordinary\nmarked\n", "sample.txt", other, commit_oid="4" * 40, **arguments), [])
        self.assertEqual(other.call_count, 2)

    def test_clean_review_text_does_not_materialize_byte_map(self):
        policy = scanner._load_review_policy_module()
        for raw in (b"ordinary prose\n", bytes.fromhex("6f7264696e61727920d09fd180d0b8d0b2d0b5d18220f09f98802070726f73650a")):
            with self.subTest(raw=raw), mock.patch.object(
                scanner, "_original_byte_boundaries",
                side_effect=AssertionError("clean text needs no candidate byte map"),
            ):
                result = scanner.analyze_review_candidates(
                    raw, b"sample.txt", subject_kind="history-blob", policy_module=policy,
                )
                self.assertTrue(result["complete"])
                self.assertEqual(result["candidates"], ())
                self.assertEqual(result["unresolved"], ())
                self.assertIsNone(result["refusal"])

    def test_retained_payload_does_not_grow_with_unique_blobs(self):
        selection, objects, _ = fixture(count=8, size=256 * 1024)
        reader = Reader(objects)
        tracemalloc.start()
        try:
            result = acquire(selection, reader)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        self.assertIsInstance(result, tuple)
        # Before the next read, the old payload must already be released.
        # Metadata for this tiny fixture is much smaller than one payload.
        self.assertLess(max(reader.retained_before_read), 256 * 1024)
        print("payload measurement:", {"peak_traced_bytes": peak,
              "max_retained_before_read": max(reader.retained_before_read),
              "reads": sum(reader.calls.values()), "read_bytes": reader.bytes_read})

    def test_reread_mutation_or_failure_never_returns_proof(self):
        for fault in ("type", "oid", "size", "content", "read", "timeout"):
            with self.subTest(fault=fault):
                selection, objects, _ = fixture()
                result = acquire(selection, Reader(objects, fault))
                self.assertIsInstance(result, scanner.Refusal)

    def test_path_order_and_complete_unique_coverage_are_preserved(self):
        selection, objects, blobs = fixture(repeated=True)
        reader = Reader(objects)
        result = acquire(selection, reader)
        self.assertIsInstance(result, tuple)
        history, coverage, findings = result
        self.assertEqual(history.blob_bytes, 3 * 1024)
        self.assertEqual(history.binary_blobs, 3)
        self.assertEqual(history.text_blobs, 0)
        self.assertEqual(coverage.expected_count, 4)
        self.assertEqual(coverage.requested_count, 4)
        self.assertEqual(coverage.acquired_count, 4)
        self.assertEqual(coverage.scanned_count, 4)
        self.assertEqual(findings, ())
        self.assertEqual(reader.sequence[4:], [*blobs, blobs[0]])

    def test_text_findings_and_review_context_order_native_and_range(self):
        for native in (True, False):
            with self.subTest(native=native):
                objects = {}
                blobs = []
                for index in range(3):
                    raw = f"Public documentation section {index}\n".encode()
                    value = oid("blob", raw)
                    objects[value] = ("blob", raw)
                    blobs.append(value)
                pairs = [(b"file0", blobs[0]), (b"file1", blobs[1]),
                         (b"file2", blobs[2]), (b"fileZ", blobs[0])]
                tree = b"".join(b"100644 " + path + b"\0" + bytes.fromhex(value)
                                for path, value in pairs)
                tree_id = oid("tree", tree)
                objects[tree_id] = ("tree", tree)
                commit = (f"tree {tree_id}\nauthor Fixture <fixture@example.test> 1 +0000\n"
                          "committer Fixture <fixture@example.test> 1 +0000\n\nPublic change\n").encode()
                commit_id = oid("commit", commit)
                objects[commit_id] = ("commit", commit)
                order = (commit_id, tree_id, *blobs)
                selection = (scanner.NativePushSelection(
                    None, (commit_id,), order, scanner._SHA1_OBJECT_FORMAT, (commit_id,),
                ) if native else scanner.RangeSelection(
                    "origin", "topic", "topic", commit_id, (commit_id,), order,
                ))
                calls = []

                class Review:
                    def scan_text_subject(self, raw, path, classifier, **context):
                        calls.append((path, raw, context))
                        return [scanner.Finding(
                            "PS-FINDING-CONTENT", "history-blob", path, 1, "fixture",
                        )]

                result = acquire(selection, Reader(objects), Review())
                self.assertIsInstance(result, tuple)
                history, coverage, findings = result
                self.assertEqual([row.locator for row in findings],
                                 ["file0", "file1", "file2", "fileZ"])
                self.assertEqual([row[0] for row in calls],
                                 ["file0", "file1", "file2", "fileZ"])
                for (path, value), (_, raw, context) in zip(pairs, calls):
                    self.assertEqual(raw, objects[value][1])
                    self.assertEqual(context["commit_oid"], commit_id)
                    self.assertEqual(context["raw_path"], path)
                    self.assertEqual(context["blob_oid"], value)
                    self.assertEqual(context["git_mode"], "100644")
                expected_subjects = tuple(sorted((commit_id, path, value)
                                                 for path, value in pairs))
                self.assertEqual(history.subjects, expected_subjects)
                self.assertEqual(history.subject_set,
                                 scanner._subject_set_digest(expected_subjects))
                self.assertEqual(history.text_blobs, 3)
                self.assertEqual(history.binary_blobs, 0)
                self.assertEqual(history.blob_bytes,
                                 sum(len(objects[value][1]) for value in blobs))
                expected_count = 5 if native else 1
                self.assertEqual(coverage.expected_count, expected_count)
                self.assertEqual(coverage.scanned_count, expected_count)
                failed = acquire(selection, Reader(objects, "content"), Review())
                self.assertIsInstance(failed, scanner.Refusal)

    def test_final_detector_and_proof_must_finish_before_deadline(self):
        from types import SimpleNamespace
        for phase in ("detector", "proof"):
            for completed_at in (0.999, 1.0, 1.001):
                with self.subTest(phase=phase, completed_at=completed_at):
                    selection, objects, _ = fixture(count=1)
                    clock = [0.0]
                    target = ("_binary_content_hits" if phase == "detector"
                              else "_path_set_digest")
                    original = getattr(scanner, target)
                    def finish(*args, **kwargs):
                        result = original(*args, **kwargs)
                        clock[0] = completed_at
                        return result
                    async def run():
                        with mock.patch.object(
                            scanner.asyncio, "get_running_loop",
                            return_value=SimpleNamespace(time=lambda: clock[0]),
                        ), mock.patch.object(scanner, target, side_effect=finish):
                            return await scanner._acquire_history(
                                selection, Reader(objects), lambda _line: [],
                                scanner.CoverageRecorder(selection.object_oids), 1.0,
                            )
                    result = asyncio.run(run())
                    if completed_at < 1.0:
                        self.assertIsInstance(result, tuple)
                    else:
                        self.assertIsInstance(result, scanner.Refusal)
                        self.assertEqual(result.failure_id, "PS-MSG-READ-TIMEOUT")

    def test_blob_count_boundary_remains_enforced(self):
        selection, objects, _ = fixture()
        for cap, accepted in ((3, True), (2, False)):
            with self.subTest(cap=cap), mock.patch.object(
                scanner, "_MAX_BLOBS", cap
            ):
                result = acquire(selection, Reader(objects))
                self.assertEqual(isinstance(result, tuple), accepted)
                if not accepted:
                    self.assertEqual(result.failure_id, "PS-MSG-LIMIT")

    def test_history_volume_is_not_a_retained_payload_budget(self):
        # Exceed the former 512 MiB cache cap without holding that history.
        # Run real acquisition, identity, line and content checks; the reader
        # generates immutable objects lazily instead of retaining the corpus.
        size = 16 * 1024 * 1024
        count = 33
        specs = {}
        for index in range(count):
            chunk = bytes([index]) + b"\0" * 1022 + b"\n"
            digest = hashlib.sha1()
            digest.update(f"blob {size}\0".encode())
            for _ in range(size // len(chunk)):
                digest.update(chunk)
            specs[digest.hexdigest()] = chunk
        tree = b"".join(b"100644 " + f"file{i:03}".encode() + b"\0"
                        + bytes.fromhex(value) for i, value in enumerate(specs))
        tree_id = oid("tree", tree)
        selection = scanner.NativePushSelection(
            None, (), (tree_id, *specs), scanner._SHA1_OBJECT_FORMAT, (tree_id,),
        )

        class LazyReader:
            reads = 0
            async def read(self, value, expected_type=None, *, scan_deadline):
                self.reads += 1
                kind = "tree" if value == tree_id else "blob"
                raw = tree if kind == "tree" else specs[value] * (size // 1024)
                return scanner.ObjectReadSuccess(value, value, kind, raw)

        reader = LazyReader()
        result = acquire(selection, reader)
        self.assertIsInstance(result, tuple)
        self.assertEqual(result[0].blob_bytes, count * size)
        self.assertEqual(result[0].binary_blobs, count)
        self.assertEqual(result[1].scanned_count, count + 1)
        self.assertEqual(reader.reads, count * 2 + 1)


if __name__ == "__main__":
    unittest.main()
