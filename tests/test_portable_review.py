"""Offline contracts for the owner-side portable batch materializer."""
import copy
import hashlib
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch


class PortableReviewTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(sys.modules))
        fixture = runpy.run_path(str(Path(__file__).with_name('test_publication_review_policy.py')))
        self.io_fixture = fixture['PolicyIOContractTests']
        self.p = fixture['policy']
        record = fixture['_record']()
        self.repository = record.pop('repository')
        record.pop('recordSha256')
        self.project = {'provider': 'test-provider', 'authority': 'example.invalid', 'repositoryId': '42'}
        self.decision = {'schema': 'orchestrarium.portable-review.v1', 'scope': 'native-repository-content', 'project': self.project, 'record': record}

    def received(self):
        return hashlib.sha256(self.p.C(self.decision)).hexdigest()

    def materialize(self, **extra):
        args = dict(received_decision_sha256=self.received(), observed_project=self.project,
                    selected_repository=self.repository)
        args.update(extra)
        return self.p.materialize_portable_review(self.decision, **args)

    def test_thousand_occurrences_one_record(self):
        entry = self.decision['record']['occurrences'][0]
        self.decision['record']['occurrences'] = [dict(copy.deepcopy(entry), id=f'occ-{i:06d}') for i in range(1000)]
        record = self.materialize()
        self.assertEqual(len(record['occurrences']), 1000)
        self.p.canonical_document(1, [record])

    def test_materialization_does_not_mutate_received_decision(self):
        before = copy.deepcopy(self.decision)
        prepared = self.materialize()
        self.assertEqual(before, self.decision)
        self.assertIn({'reference': 'portable-review:DEC-1', 'sha256': self.received()},
                      prepared['authorization']['supportingArtifacts'])

    def test_wrong_project(self):
        for key in self.project:
            with self.subTest(key=key), self.assertRaises(self.p.PolicyInputError):
                self.materialize(observed_project=dict(self.project, **{key: 'different'}))

    def test_destination_scoped_decision_not_broadened_to_native_content(self):
        self.decision['scope'] = 'only-this-destination'
        with self.assertRaises(self.p.PolicyInputError):
            self.materialize()

    def test_changed_content_not_received(self):
        accepted = self.received()
        self.decision['record']['occurrences'][0]['blobOid'] = 'f' * 40
        with self.assertRaises(self.p.PolicyInputError):
            self.materialize(received_decision_sha256=accepted)

    def test_revoked_decision(self):
        self.decision['record']['state'] = 'revoked'
        with self.assertRaises(self.p.PolicyInputError):
            self.materialize()

    def test_duplicate_occurrence_rejected(self):
        self.decision['record']['occurrences'] *= 2
        with self.assertRaises(self.p.PolicyInputError):
            self.materialize()

    def test_replay_idempotent_but_conflict_not_overwritten(self):
        existing = self.materialize()
        self.assertEqual(self.materialize(current_record=existing), existing)
        self.decision['record']['reason'] = 'changed decision'
        self.assertEqual(self.materialize()['id'], existing['id'])
        with self.assertRaises(self.p.PolicyInputError):
            self.materialize(current_record=existing)

    def test_native_copy_gets_distinct_binding(self):
        first = self.materialize()
        self.repository['worktreeRoot']['inode'] = '99'
        second = self.materialize()
        self.assertNotEqual(first['id'], second['id'])
        self.assertNotEqual(first['repository'], second['repository'])

    def test_revoked_local_record_cannot_be_replayed(self):
        active = self.materialize()
        revoked = copy.deepcopy(active)
        revoked.update(revision=2, previousRecordSha256=active['recordSha256'], state='revoked',
                       revocation={'reason': 'withdrawn', 'rootReceivingReference': 'owner-revocation'})
        revoked.pop('recordSha256')
        revoked = self.p.seal_record(revoked)
        with self.assertRaises(self.p.PolicyInputError):
            self.materialize(current_record=revoked)

    def test_legacy_report_missing_project_refused(self):
        del self.decision['project']
        with self.assertRaises(self.p.PolicyInputError):
            self.materialize()

    def test_materialized_batch_uses_existing_atomic_promotion_and_revocation(self):
        fixture = self.io_fixture()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.repository = fixture.repository
        record = self.materialize()
        with patch.object(self.p.Path, 'home', return_value=fixture.home):
            origin = self.p.resolve_trusted_origin()
            result = self.p.promote_decision(origin, self.repository, record,
                expected_document_sha256=None, expected_record_sha256=None, apply=True)
            self.assertEqual(result['effect'], 'applied')
            unchanged = fixture.policy_leaf.read_bytes()
            replay = self.p.promote_decision(origin, self.repository, self.materialize(current_record=record),
                expected_document_sha256=result['observed']['documentSha256'],
                expected_record_sha256=record['recordSha256'], apply=True)
            self.assertEqual(replay['kind'], 'idempotent')
            self.assertEqual(fixture.policy_leaf.read_bytes(), unchanged)
            self.p.revoke_decision(origin, self.repository, record['id'], 'withdrawn', 'owner',
                expected_document_sha256=result['observed']['documentSha256'],
                expected_record_sha256=record['recordSha256'], apply=True)
            revoked = fixture.policy_leaf.read_bytes()
            with self.assertRaises(self.p.PolicyError):
                self.p.promote_decision(origin, self.repository, record,
                    expected_document_sha256=result['observed']['documentSha256'],
                    expected_record_sha256=None, apply=True)
            self.assertEqual(fixture.policy_leaf.read_bytes(), revoked)


if __name__ == '__main__':
    unittest.main()
