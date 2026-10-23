"""Focused contract tests for the reviewed publication policy data owner."""

from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


_POLICY_KEY = "_orchestrarium_publication_review_policy_v1"
_POLICY_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "universal-hooks"
    / "scripts"
    / "publication_review_policy.py"
)
_SPEC = importlib.util.spec_from_file_location(_POLICY_KEY, _POLICY_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError("policy module cannot be loaded from its declared sibling path")
policy = importlib.util.module_from_spec(_SPEC)
sys.modules[_POLICY_KEY] = policy
_SPEC.loader.exec_module(policy)


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _region(raw: bytes, start: int, end: int) -> dict[str, object]:
    return {"startByte": start, "endByteExclusive": end, "sha256": _sha(raw[start:end])}


def _native_directory(path: str, *, device: str = "1", inode: str = "2") -> dict[str, str]:
    raw = path.encode("utf-16-le", errors="surrogatepass")
    return {
        "pathEncoding": "windows-utf16le",
        "pathBase64": base64.b64encode(raw).decode("ascii"),
        "device": device,
        "inode": inode,
    }


def _native_directory_for_path(path: Path) -> dict[str, str]:
    metadata = path.lstat()
    if os.name == "nt":
        encoding = "windows-utf16le"
        raw = os.fspath(path).encode("utf-16-le", errors="surrogatepass")
    else:
        encoding = "posix-bytes"
        raw = os.fsencode(path)
    return {
        "pathEncoding": encoding,
        "pathBase64": base64.b64encode(raw).decode("ascii"),
        "device": str(metadata.st_dev),
        "inode": str(metadata.st_ino),
    }


def _repository(root: Path) -> dict[str, object]:
    common = root / ".git"
    worktree = common / "worktrees" / "selected"
    worktree.mkdir(parents=True, exist_ok=True)
    return {
        "kind": "native-worktree-v1",
        "objectFormat": "sha1",
        "commonGit": _native_directory_for_path(common),
        "worktreeGit": _native_directory_for_path(worktree),
        "worktreeRoot": _native_directory_for_path(root),
    }


def _record(
    record_id: str = "DEC-1",
    *,
    root_reference: str = "root-review-1",
    repository: dict[str, object] | None = None,
) -> dict[str, object]:
    blob = b"abc"
    review_region = _region(blob, 0, 3)
    candidate_span = _region(blob, 1, 2)
    detector = {"ruleId": "simple-signature-v1", "meaningSha256": "b" * 64}
    contributors = [{"leafId": "leaf-1", "fullMatch": candidate_span}]
    candidate_body = {
        "detector": detector,
        "normalFormId": "nf-simple-match-v1",
        "startByte": candidate_span["startByte"],
        "endByteExclusive": candidate_span["endByteExclusive"],
        "sha256": candidate_span["sha256"],
        "assignment": None,
        "contributors": contributors,
    }
    candidate = {
        "normalFormId": "nf-simple-match-v1",
        "startByte": candidate_span["startByte"],
        "endByteExclusive": candidate_span["endByteExclusive"],
        "sha256": candidate_span["sha256"],
        "assignment": None,
        "contributors": contributors,
        "occurrenceSha256": policy.H(policy.DOMAIN_OCCURRENCE, candidate_body),
    }
    default_repository = {
        "kind": "native-worktree-v1",
        "objectFormat": "sha1",
        "commonGit": _native_directory(r"C:\repo\.git", device="4", inode="5"),
        "worktreeGit": _native_directory(r"C:\repo\.git", device="4", inode="5"),
        "worktreeRoot": _native_directory(r"C:\repo", device="4", inode="6"),
    }
    body = {
        "id": record_id,
        "revision": 1,
        "previousRecordSha256": None,
        "state": "active",
        "repository": repository or default_repository,
        "modes": ["staged-blob-text"],
        "rangeScope": None,
        "occurrences": [
            {
                "id": "occ-1",
                "rawPathBase64": base64.b64encode(b"file.txt").decode("ascii"),
                "blobOid": "a" * 40,
                "blobSha256": _sha(blob),
                "blobByteCount": len(blob),
                "gitMode": "100644",
                "detector": detector,
                "reviewRegion": review_region,
                "candidate": candidate,
                "contexts": [{"id": "context-1", "region": _region(blob, 0, 1)}],
            }
        ],
        "reason": "reviewed content",
        "removalCondition": "remove after replacement",
        "authorization": {
            "reviewArtifact": {"reference": "review-1", "sha256": "c" * 64},
            "rootReceivingReference": root_reference,
            "supportingArtifacts": [],
        },
        "revocation": None,
    }
    return policy.seal_record(body)


def _resign(record: dict[str, object]) -> dict[str, object]:
    body = copy.deepcopy(record)
    body.pop("recordSha256")
    return policy.seal_record(body)


class PublicationReviewPolicyTests(unittest.TestCase):
    def test_canonical_encoding_and_applied_set_match_frozen_vectors(self) -> None:
        self.assertEqual(policy.C({"a": 1, "s": "α"}), b'{"a":1,"s":"\\u03b1"}')
        self.assertEqual(
            policy.applied_set_digest([]),
            "3e3da4309937f6aaf150042c616716950ada90006fda50aeb620e94287e047bc",
        )
        canonical = policy.C({"x": 1})
        expected = hashlib.sha256(
            policy.DOMAIN_RECORD.encode("ascii")
            + b"\0"
            + str(len(canonical)).encode("ascii")
            + b":"
            + canonical
        ).hexdigest()
        self.assertEqual(policy.H(policy.DOMAIN_RECORD, {"x": 1}), expected)

        row = {"x": 1}
        encoded_row = policy.C(row)
        framed_rows = (
            policy.DOMAIN_APPLIED_SET.encode("ascii")
            + b"\0"
            + str(len(encoded_row)).encode("ascii")
            + b":"
            + encoded_row
            + b"!1"
        )
        self.assertEqual(policy.applied_set_digest([row]), hashlib.sha256(framed_rows).hexdigest())

    def test_canonical_encoding_rejects_float_and_lone_surrogate(self) -> None:
        with self.assertRaises(policy.PolicyInputError):
            policy.C({"value": 1.0})
        with self.assertRaises(policy.PolicyInputError):
            policy.C({"value": "\ud800"})
        with self.assertRaises(policy.PolicyInputError):
            policy.H("unowned-domain.v1", {})

    def test_canonical_integer_encoding_has_no_convenience_digit_ceiling(self) -> None:
        digits = b"9" * 5000
        raw = b'{"decisions":[],"revision":' + digits + b',"schemaVersion":1}'
        decoded = policy.decode_document(raw)
        self.assertTrue(decoded.outer_valid)
        self.assertEqual(policy.C({"revision": decoded.revision}), b'{"revision":' + digits + b"}")

    def test_document_writer_sorts_records_and_adds_one_final_lf(self) -> None:
        second = _record("DEC-2")
        first = _record("DEC-1")
        raw = policy.canonical_document(3, [second, first])
        self.assertTrue(raw.endswith(b"\n"))
        self.assertFalse(raw.endswith(b"\n\n"))
        decoded = policy.decode_document(raw)
        self.assertTrue(decoded.mutation_safe)
        self.assertEqual([row["id"] for row in decoded.records], ["DEC-1", "DEC-2"])

    def test_record_local_duplicate_key_does_not_discard_valid_neighbor(self) -> None:
        malformed = policy.C(_record("DEC-BAD")).replace(
            b'"state":"active"', b'"state":"active","state":"active"'
        )
        valid = policy.C(_record("DEC-GOOD"))
        raw = (
            b'{"schemaVersion":1,"revision":1,"decisions":['
            + malformed
            + b"," + valid + b"]}"
        )
        decoded = policy.decode_document(raw)
        self.assertTrue(decoded.outer_valid)
        self.assertFalse(decoded.mutation_safe)
        self.assertEqual(decoded.invalid_record_count, 1)
        self.assertEqual([row["id"] for row in decoded.records], ["DEC-GOOD"])

    def test_duplicate_outer_key_invalidates_entire_document(self) -> None:
        decoded = policy.decode_document(
            b'{"schemaVersion":1,"schemaVersion":1,"revision":0,"decisions":[]}'
        )
        self.assertFalse(decoded.outer_valid)
        self.assertEqual(decoded.records, ())

    def test_duplicate_recoverable_ids_invalidate_every_matching_record(self) -> None:
        record = policy.C(_record("DEC-DUP"))
        raw = b'{"schemaVersion":1,"revision":1,"decisions":[' + record + b"," + record + b"]}"
        decoded = policy.decode_document(raw)
        self.assertTrue(decoded.outer_valid)
        self.assertEqual(decoded.duplicate_ids, ("DEC-DUP",))
        self.assertEqual(decoded.invalid_record_count, 2)
        self.assertEqual(decoded.records, ())

    def test_bad_record_digest_and_wrong_numeric_types_get_no_credit(self) -> None:
        valid_neighbor = policy.C(_record("DEC-GOOD"))
        bad_digest = copy.deepcopy(_record("DEC-BAD"))
        bad_digest["recordSha256"] = "d" * 64
        bad_revision = policy.C(_record("DEC-TYPE")).replace(b'"revision":1', b'"revision":true')
        raw = (
            b'{"schemaVersion":1,"revision":1,"decisions":['
            + policy.C(bad_digest)
            + b"," + bad_revision + b"," + valid_neighbor + b"]}"
        )
        decoded = policy.decode_document(raw)
        self.assertEqual(decoded.invalid_record_count, 2)
        self.assertEqual([row["id"] for row in decoded.records], ["DEC-GOOD"])

    def test_unknown_record_fields_and_json_floats_are_record_local(self) -> None:
        unknown = _record("DEC-UNKNOWN")
        unknown["unowned"] = "value"
        float_record = policy.C(_record("DEC-FLOAT")).replace(
            b'"blobByteCount":3', b'"blobByteCount":3.0'
        )
        neighbor = policy.C(_record("DEC-GOOD"))
        raw = (
            b'{"schemaVersion":1,"revision":1,"decisions":['
            + policy.C(unknown)
            + b"," + float_record + b"," + neighbor + b"]}"
        )
        decoded = policy.decode_document(raw)
        self.assertEqual(decoded.invalid_record_count, 2)
        self.assertEqual([row["id"] for row in decoded.records], ["DEC-GOOD"])

    def test_usable_records_are_independent_plain_copies(self) -> None:
        decoded = policy.decode_document(policy.canonical_document(1, [_record()]))
        first_copy = decoded.usable_records()
        first_copy[0]["reason"] = "caller mutation"
        second_copy = decoded.usable_records()
        self.assertEqual(second_copy[0]["reason"], "reviewed content")

    def test_forward_only_transitions_and_stale_reactivation_are_rejected(self) -> None:
        active = _record()
        self.assertEqual(policy.validate_record_transition(None, active), "create")

        revoked_body = copy.deepcopy(active)
        revoked_body.update(
            {
                "revision": 2,
                "previousRecordSha256": active["recordSha256"],
                "state": "revoked",
                "revocation": {
                    "reason": "review withdrawn",
                    "rootReceivingReference": "root-revoke-1",
                },
            }
        )
        revoked = _resign(revoked_body)
        self.assertEqual(policy.validate_record_transition(active, revoked), "revoke")

        stale_reactivation_body = copy.deepcopy(revoked)
        stale_reactivation_body.update(
            {
                "revision": 3,
                "previousRecordSha256": revoked["recordSha256"],
                "state": "active",
                "revocation": None,
            }
        )
        stale_reactivation = _resign(stale_reactivation_body)
        with self.assertRaises(policy.PolicyInputError):
            policy.validate_record_transition(revoked, stale_reactivation)

        fresh_body = copy.deepcopy(stale_reactivation_body)
        fresh_body["authorization"] = {
            "reviewArtifact": {"reference": "review-2", "sha256": "e" * 64},
            "rootReceivingReference": "root-review-2",
            "supportingArtifacts": [],
        }
        fresh = _resign(fresh_body)
        self.assertEqual(policy.validate_record_transition(revoked, fresh), "reactivate")

    def test_revocation_cannot_rewrite_retained_grant_fields(self) -> None:
        active = _record()
        changed_body = copy.deepcopy(active)
        changed_body.update(
            {
                "revision": 2,
                "previousRecordSha256": active["recordSha256"],
                "state": "revoked",
                "reason": "rewritten grant reason",
                "revocation": {
                    "reason": "withdrawn",
                    "rootReceivingReference": "root-revoke-1",
                },
            }
        )
        revoked = _resign(changed_body)
        with self.assertRaises(policy.PolicyInputError):
            policy.validate_record_transition(active, revoked)

    def test_assignment_identifier_may_precede_review_region_but_contributors_may_not(self) -> None:
        record = _record()
        body = copy.deepcopy(record)
        body.pop("recordSha256")
        occurrence = body["occurrences"][0]
        blob = b"let key=1"
        review_region = _region(blob, 8, 9)
        identifier = _region(blob, 4, 7)
        delimiter = _region(blob, 7, 8)
        rhs = _region(blob, 8, 9)
        detector = occurrence["detector"]
        contributors = [{"leafId": "leaf-1", "fullMatch": rhs}]
        candidate_body = {
            "detector": detector,
            "normalFormId": "nf-value-assignment-v1",
            "startByte": rhs["startByte"],
            "endByteExclusive": rhs["endByteExclusive"],
            "sha256": rhs["sha256"],
            "assignment": {"identifier": identifier, "delimiter": delimiter, "rhs": rhs},
            "contributors": contributors,
        }
        occurrence.update(
            {
                "blobSha256": _sha(blob),
                "blobByteCount": len(blob),
                "reviewRegion": review_region,
                "candidate": {
                    "normalFormId": "nf-value-assignment-v1",
                    "startByte": rhs["startByte"],
                    "endByteExclusive": rhs["endByteExclusive"],
                    "sha256": rhs["sha256"],
                    "assignment": {"identifier": identifier, "delimiter": delimiter, "rhs": rhs},
                    "contributors": contributors,
                    "occurrenceSha256": policy.H(policy.DOMAIN_OCCURRENCE, candidate_body),
                },
            }
        )

        accepted = policy.seal_record(body)
        self.assertEqual(accepted["occurrences"][0]["candidate"]["assignment"]["identifier"], identifier)

        outside_contributor = copy.deepcopy(accepted)
        outside_contributor.pop("recordSha256")
        outside_occurrence = outside_contributor["occurrences"][0]
        outside_candidate = outside_occurrence["candidate"]
        outside_candidate["contributors"][0]["fullMatch"] = _region(blob, 4, 9)
        outside_body = {
            "detector": outside_occurrence["detector"],
            "normalFormId": outside_candidate["normalFormId"],
            "startByte": outside_candidate["startByte"],
            "endByteExclusive": outside_candidate["endByteExclusive"],
            "sha256": outside_candidate["sha256"],
            "assignment": outside_candidate["assignment"],
            "contributors": outside_candidate["contributors"],
        }
        outside_candidate["occurrenceSha256"] = policy.H(policy.DOMAIN_OCCURRENCE, outside_body)
        with self.assertRaisesRegex(policy.PolicyInputError, "candidate-contributor-review-region"):
            policy.seal_record(outside_contributor)


class PolicyIOContractTests(unittest.TestCase):
    def setUp(self) -> None:
        scratch = Path(__file__).resolve().parents[1] / ".scratch"
        self._temporary = tempfile.TemporaryDirectory(
            prefix="publication-review-policy-", dir=scratch
        )
        self.addCleanup(self._temporary.cleanup)
        self.base = Path(self._temporary.name)
        self.home = self.base / "synthetic-home"
        self.policy_root = self.home / ".agents" / "publication"
        self.policy_root.mkdir(parents=True)
        self.policy_leaf = self.policy_root / "reviewed-exceptions.json"
        self.repository_root = self.base / "synthetic-repository"
        self.repository_root.mkdir()
        self.repository = _repository(self.repository_root)

    def _write_document(self, revision: int, records: list[dict[str, object]]) -> bytes:
        raw = policy.canonical_document(revision, records)
        self.policy_leaf.write_bytes(raw)
        return raw

    def _read_policy(self):
        with patch.object(policy.Path, "home", return_value=self.home):
            selection = policy.resolve_trusted_origin()
            result = policy.read_policy_snapshot(selection, self.repository_root)
        return selection, result

    def _query_results(self, plan):
        paths = {
            "topLevel": self.repository_root,
            "commonGit": self.repository_root / ".git",
            "worktreeGit": self.repository_root / ".git" / "worktrees" / "selected",
        }
        results = []
        for query in plan.queries:
            if query.key == "objectFormat":
                stdout = b"sha1\n"
            else:
                stdout = os.fsencode(paths[query.key]) + b"\n"
            results.append(
                policy.RepositoryQueryResultV1(
                    query_key=query.key,
                    git_args=query.git_args,
                    returncode=0,
                    stdout=stdout,
                    stderr=b"",
                    complete=True,
                    resources_settled=True,
                    failure_kind=None,
                )
            )
        return tuple(results)

    def _revoked(self, current: dict[str, object]) -> dict[str, object]:
        body = copy.deepcopy(current)
        body.update(
            {
                "revision": current["revision"] + 1,
                "previousRecordSha256": current["recordSha256"],
                "state": "revoked",
                "revocation": {
                    "reason": "review withdrawn",
                    "rootReceivingReference": "root-revoke-1",
                },
            }
        )
        body.pop("recordSha256")
        return policy.seal_record(body)

    def test_repository_query_plan_and_results_are_exact_and_raw(self) -> None:
        plan = policy.repository_query_plan(self.repository_root)
        self.assertEqual(
            tuple(query.key for query in plan.queries),
            ("topLevel", "commonGit", "worktreeGit", "objectFormat"),
        )
        self.assertEqual(
            plan.queries[0].git_args[:4],
            ("--no-optional-locks", "-C", os.fspath(self.repository_root), "rev-parse"),
        )
        results = self._query_results(plan)
        observation = policy.repository_from_query_results(plan, results)
        self.assertEqual(observation["status"], "captured")
        self.assertEqual(observation["repository"]["worktreeRoot"], self.repository["worktreeRoot"])
        self.assertEqual(
            policy.repository_from_query_results(plan, tuple(reversed(results)))["status"],
            "unavailable",
        )
        incomplete = list(results)
        incomplete[1] = policy.RepositoryQueryResultV1(
            query_key=incomplete[1].query_key,
            git_args=incomplete[1].git_args,
            returncode=0,
            stdout=None,
            stderr=b"partial",
            complete=False,
            resources_settled=False,
            failure_kind="incomplete-capture",
        )
        self.assertEqual(
            policy.repository_from_query_results(plan, tuple(incomplete))["status"],
            "unavailable",
        )

    def test_fixed_origin_read_and_all_repository_roots_are_excluded(self) -> None:
        record = _record(repository=self.repository)
        revoked = self._revoked(_record("DEC-REVOKED", repository=self.repository))
        self._write_document(2, [record, revoked])
        selection, policy_read = self._read_policy()
        self.assertEqual(selection.status, "selected")
        self.assertEqual([row["id"] for row in policy_read.usable_records], ["DEC-1"])
        self.assertEqual(policy_read.issues, ({"decision_id": "DEC-REVOKED", "code": "POLICY-REVOKED"},))
        self.assertTrue(policy.origin_is_outside_repository(policy_read.snapshot, self.repository))

        for root_name in ("commonGit", "worktreeGit", "worktreeRoot"):
            overlapping = copy.deepcopy(self.repository)
            overlapping[root_name] = _native_directory_for_path(self.policy_root)
            self.assertFalse(policy.origin_is_outside_repository(policy_read.snapshot, overlapping))

        linked = copy.deepcopy(policy_read.snapshot)
        fake_link_path = self.base / "logical-link-witness"
        if os.name == "nt":
            link_path_bytes = os.fspath(fake_link_path).encode("utf-16-le", errors="surrogatepass")
            link_encoding = "windows-utf16le"
            target_bytes = os.fspath(self.repository_root).encode("utf-16-le", errors="surrogatepass")
        else:
            link_path_bytes = os.fsencode(fake_link_path)
            link_encoding = "posix-bytes"
            target_bytes = os.fsencode(self.repository_root)
        linked["origin"]["links"].append(
            [
                {"pathEncoding": link_encoding, "pathBase64": base64.b64encode(link_path_bytes).decode("ascii")},
                ["9", "10", "16384", "0"],
                "symlink",
                {"pathEncoding": link_encoding, "pathBase64": base64.b64encode(target_bytes).decode("ascii")},
            ]
        )
        self.assertFalse(policy.origin_is_outside_repository(linked, self.repository))

    def test_unsettled_policy_capture_raises_before_snapshot_projection(self) -> None:
        with patch.object(policy.Path, "home", return_value=self.home):
            selection = policy.resolve_trusted_origin()
            unavailable = policy._snapshot("unavailable", None, None, "unreadable")
            failed_capture = policy.PolicyCapture(unavailable, None, False)
            with patch.object(policy, "_capture_policy_file", return_value=failed_capture):
                with self.assertRaises(policy.PolicyError) as raised:
                    policy.read_policy_snapshot(selection, self.repository_root)
            self.assertEqual(raised.exception.detail, {"code": "POLICY-IO", "phase": "settlement"})

            settled_capture = policy.PolicyCapture(unavailable, None, True)
            with patch.object(policy, "_capture_policy_file", return_value=settled_capture):
                settled = policy.read_policy_snapshot(selection, self.repository_root)
        self.assertEqual(settled.snapshot["status"], "unavailable")

    def test_policy_directory_sync_preserves_close_failure_and_primary_context(self) -> None:
        with patch.object(policy.Path, "home", return_value=self.home):
            selection = policy.resolve_trusted_origin()
        self.assertEqual(selection.status, "selected")
        opened_metadata = self.policy_root.stat()

        def observe(fsync_error=None, close_error=None):
            try:
                with (
                    patch.object(policy.os, "name", "posix"),
                    patch.object(policy.os, "O_DIRECTORY", 0x10000, create=True),
                    patch.object(policy.os, "O_NOFOLLOW", 0x20000, create=True),
                    patch.object(policy.os, "open", return_value=41),
                    patch.object(policy.os, "fstat", return_value=opened_metadata),
                    patch.object(policy.os, "fsync", side_effect=fsync_error),
                    patch.object(policy.os, "close", side_effect=close_error),
                ):
                    policy._sync_policy_directory(selection)
            except OSError as exc:
                return exc
            return None

        primary_error = OSError("fsync failed")
        self.assertIs(observe(fsync_error=primary_error), primary_error)

        close_only = OSError("close failed")
        close_failure = observe(close_error=close_only)
        self.assertIsInstance(close_failure, policy._ResourceUnsettledError)
        self.assertIs(close_failure.__cause__, close_only)

        simultaneous_fsync = OSError("fsync failed")
        simultaneous_close = OSError("close failed")
        combined_failure = observe(fsync_error=simultaneous_fsync, close_error=simultaneous_close)
        self.assertIsInstance(combined_failure, policy._ResourceUnsettledError)
        self.assertIs(combined_failure.__cause__, simultaneous_close)
        reachable: set[int] = set()
        pending = [combined_failure]
        while pending:
            error = pending.pop()
            if error is None or id(error) in reachable:
                continue
            reachable.add(id(error))
            pending.extend((error.__cause__, error.__context__))
        self.assertIn(id(simultaneous_close), reachable)
        self.assertIn(id(simultaneous_fsync), reachable)
        self.assertIsNone(observe())

    def test_absent_home_policy_and_captured_mode_fail_closed_without_fallback(self) -> None:
        with patch.object(policy.Path, "home", return_value=self.home):
            selection = policy.resolve_trusted_origin()
            absent = policy.read_policy_snapshot(selection, self.repository_root)
            self.assertEqual(absent.snapshot["status"], "absent")
            self.assertEqual(absent.issues, ({"decision_id": None, "code": "POLICY-ABSENT"},))
            decoded = policy.decode_policy_snapshot(absent.snapshot)
            self.assertEqual(decoded.snapshot_id, absent.snapshot_id)

        with patch.object(policy.Path, "home", side_effect=OSError("home unavailable")):
            unavailable_selection = policy.resolve_trusted_origin()
            unavailable = policy.read_policy_snapshot(unavailable_selection, self.repository_root)
            self.assertEqual(unavailable.snapshot["status"], "unavailable")

        saved_file = policy.__file__
        saved_link = sys.modules.pop(policy.LINKED_RUNTIME_SUBROOTS_MODULE_KEY, None)
        try:
            policy.__file__ = "<closure>/publication_review_policy.py"
            with patch.object(policy.Path, "home", return_value=self.home):
                captured_without_injection = policy.resolve_trusted_origin()
            self.assertEqual(captured_without_injection.status, "unavailable")
        finally:
            policy.__file__ = saved_file
            if saved_link is not None:
                sys.modules[policy.LINKED_RUNTIME_SUBROOTS_MODULE_KEY] = saved_link

    def test_finalization_ignores_unused_records_but_rejects_revoked_used_record(self) -> None:
        used_record = _record(repository=self.repository)
        self._write_document(1, [used_record])
        with patch.object(policy.Path, "home", return_value=self.home):
            selection = policy.resolve_trusted_origin()
            initial = policy.read_policy_snapshot(selection, self.repository_root)
            used = [[used_record["id"], used_record["recordSha256"]]]
            first = policy.verify_used(initial.snapshot, self.repository, used)
            self.assertEqual((first["status"], first["reason"]), ("valid", "none"))

            unrelated = _record("DEC-UNUSED", repository=self.repository)
            self._write_document(2, [used_record, unrelated])
            unchanged_used = policy.verify_used(initial.snapshot, self.repository, used)
            self.assertEqual((unchanged_used["status"], unchanged_used["reason"]), ("valid", "none"))
            self.assertNotEqual(unchanged_used["currentSnapshotId"], initial.snapshot_id)

            self._write_document(3, [self._revoked(used_record), unrelated])
            revoked_used = policy.verify_used(initial.snapshot, self.repository, used)
            self.assertEqual((revoked_used["status"], revoked_used["reason"]), ("invalid", "used-record-revoked"))
            empty_used = policy.verify_used(initial.snapshot, self.repository, [])
            self.assertEqual((empty_used["status"], empty_used["reason"]), ("invalid", "used-record-missing"))

    def test_positive_apply_preview_idempotence_and_forward_revocation(self) -> None:
        record = _record(repository=self.repository)
        with patch.object(policy.Path, "home", return_value=self.home):
            selection = policy.resolve_trusted_origin()
            preview = policy.promote_decision(
                selection,
                self.repository,
                record,
                expected_document_sha256=None,
                expected_record_sha256=None,
                apply=False,
            )
            self.assertEqual((preview["kind"], preview["effect"]), ("preview", "not-applied"))
            self.assertFalse(self.policy_leaf.exists())

            committed = policy.promote_decision(
                selection,
                self.repository,
                record,
                expected_document_sha256=None,
                expected_record_sha256=None,
                apply=True,
            )
            self.assertEqual((committed["kind"], committed["effect"]), ("committed", "applied"))
            self.assertTrue(committed["resourcesSettled"])
            persisted = self.policy_leaf.read_bytes()
            idempotent = policy.promote_decision(
                selection,
                self.repository,
                record,
                expected_document_sha256="0" * 64,
                expected_record_sha256="0" * 64,
                apply=True,
            )
            self.assertEqual(idempotent["kind"], "idempotent")
            self.assertEqual(self.policy_leaf.read_bytes(), persisted)

            current_document_sha = committed["observed"]["documentSha256"]
            revoke_preview = policy.revoke_decision(
                selection,
                self.repository,
                record["id"],
                "review withdrawn",
                "root-revoke-1",
                expected_document_sha256=current_document_sha,
                expected_record_sha256=record["recordSha256"],
                apply=False,
            )
            self.assertEqual(revoke_preview["kind"], "preview")
            self.assertEqual(self.policy_leaf.read_bytes(), persisted)

            revoked = policy.revoke_decision(
                selection,
                self.repository,
                record["id"],
                "review withdrawn",
                "root-revoke-1",
                expected_document_sha256=current_document_sha,
                expected_record_sha256=record["recordSha256"],
                apply=True,
            )
            self.assertEqual((revoked["kind"], revoked["effect"]), ("committed", "applied"))
            self.assertNotEqual(revoked["observed"]["recordSha256"], record["recordSha256"])
            revoked_bytes = self.policy_leaf.read_bytes()
            stale_idempotent = policy.revoke_decision(
                selection,
                self.repository,
                record["id"],
                "review withdrawn",
                "root-revoke-1",
                expected_document_sha256=current_document_sha,
                expected_record_sha256=record["recordSha256"],
                apply=True,
            )
            self.assertEqual(stale_idempotent["kind"], "idempotent")
            self.assertEqual(self.policy_leaf.read_bytes(), revoked_bytes)

    def test_idempotent_readback_preserves_invalid_neighbor_but_mutation_refuses(self) -> None:
        record = _record(repository=self.repository)
        invalid_neighbor = _record("DEC-INVALID", repository=self.repository)
        invalid_neighbor["unownedField"] = "preserve"
        raw = policy.C(
            {
                "schemaVersion": 1,
                "revision": 2,
                "decisions": [record, invalid_neighbor],
            }
        ) + b"\n"
        self.policy_leaf.write_bytes(raw)
        with patch.object(policy.Path, "home", return_value=self.home):
            selection = policy.resolve_trusted_origin()
            idempotent = policy.promote_decision(
                selection,
                self.repository,
                record,
                expected_document_sha256="0" * 64,
                expected_record_sha256="0" * 64,
                apply=True,
            )
            self.assertEqual(idempotent["kind"], "idempotent")
            self.assertEqual(self.policy_leaf.read_bytes(), raw)
            with self.assertRaises(policy.PolicyError) as raised:
                policy.revoke_decision(
                    selection,
                    self.repository,
                    record["id"],
                    "review withdrawn",
                    "root-revoke-1",
                    expected_document_sha256=hashlib.sha256(raw).hexdigest(),
                    expected_record_sha256=record["recordSha256"],
                    apply=True,
                )
        self.assertEqual(raised.exception.detail["code"], "POLICY-STATE")
        self.assertEqual(self.policy_leaf.read_bytes(), raw)


if __name__ == "__main__":
    unittest.main()
