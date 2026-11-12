"""Offline producer/receiving projection; input is never policy authority."""
import copy
from pathlib import Path
import unittest
from unittest.mock import patch
from tests import test_machine_path_review as fixtures


class CandidateWorkflowTests(unittest.TestCase):
    setUp=fixtures.ExactMachinePathReview.setUp
    git=fixtures.ExactMachinePathReview.git
    in_root=fixtures.ExactMachinePathReview.in_root
    payload=fixtures.ExactMachinePathReview.payload
    fixture=fixtures.ExactMachinePathReview.fixture
    object_format="sha1"
    def generated(self, count):
        if not hasattr(self, "_case"): self._case=self.fixture()
        m,p,raw,rows,original,ev,scan,f=self._case
        record=copy.deepcopy(original)
        # Public synthetic fixture, assembled as path components rather than a real host path.
        raw=(b'/'.join((b'C:',b'Users',b'Fixture',b'a'))+b'\n') * count
        self.assertEqual(raw,(b'C:/Users/' + b'Fixture/a\n') * count)
        occurrences=m.build_review_occurrences(raw,b'arbitrary-fixture.txt',
            object_format='sha1',git_mode='100644',policy_module=p)
        record['occurrences']=list(occurrences)
        return m,p,raw,record,ev

    def test_generated_counts_and_partial_review(self):
        for count in (1,6,1000):
            with self.subTest(count=count):
                m,p,raw,r,ev=self.generated(count)
                self.assertEqual(len(r['occurrences']),count)
                self.assertEqual(len({o['id'] for o in r['occurrences']}),count)
                approved=r['occurrences'][::2]
                rows=[dict(id=o['id'],verdict='approve',reason='Synthetic test fixture') for o in approved]
                prepared=p.prepare_candidate_review(r,rows)
                self.assertEqual(prepared['occurrences'],approved)
                self.assertEqual(len(prepared['occurrences']),(count+1)//2)
                remaining=ev([prepared]).scan_text_subject(raw,'arbitrary-fixture.txt',
                    m._path_finder(Path(m.__file__)),subject_kind='tracked-blob',
                    mode='staged-blob-text',commit_oid=None,raw_path=b'arbitrary-fixture.txt',
                    blob_oid=r['occurrences'][0]['blobOid'],git_mode='100644')
                self.assertEqual(len(remaining),count-len(approved))

    def test_changed_content_changes_generated_ids(self):
        m,p,raw,r,ev=self.generated(6)
        changed=m.build_review_occurrences(raw+b'changed',b'arbitrary-fixture.txt',
            object_format='sha1',git_mode='100644',policy_module=p)
        r['occurrences']=list(changed)
        with self.assertRaises(p.PolicyInputError):
            p.prepare_candidate_review(r,[dict(id='not-generated',verdict='approve',reason='x')])
        original=m.build_review_occurrences(raw,b'arbitrary-fixture.txt',
            object_format='sha1',git_mode='100644',policy_module=p)
        self.assertTrue(set(o['id'] for o in original).isdisjoint(o['id'] for o in changed))

    def test_duplicate_unknown_and_injected_occurrence_rejected(self):
        m,p,raw,r,ev=self.generated(1)
        row=dict(id=r['occurrences'][0]['id'],verdict='approve',reason='Synthetic')
        for verdicts in ([row,row],[dict(row,id='unknown')],[dict(row,blobOid='a'*40)],
                         [dict(row,verdict='PASS')],[dict(row,reason='')]):
            with self.subTest(verdicts=verdicts),self.assertRaises(p.PolicyInputError):
                p.prepare_candidate_review(r,verdicts)

    def test_projection_does_not_apply_or_authorize(self):
        m,p,raw,r,ev=self.generated(1)
        before=copy.deepcopy(r)
        row=dict(id=r['occurrences'][0]['id'],verdict='approve',reason='Synthetic')
        with patch.object(p, "promote_decision") as promote:
            prepared=p.prepare_candidate_review(r,[row])
            promote.assert_not_called()
        self.assertEqual(r,before)
        # A prepared value alone is not found in the trusted policy snapshot.
        self.assertEqual(len(list(self.origin.rglob("reviewed-exceptions.json"))), 0)
        self.assertEqual(prepared['state'],'active')

    def test_explicit_rejection_or_empty_never_grants(self):
        m,p,raw,r,ev=self.generated(1)
        for rows in ([],[dict(id=r['occurrences'][0]['id'],verdict='reject',reason='Unsafe')]):
            with self.assertRaises(p.PolicyInputError):p.prepare_candidate_review(r,rows)

    def test_prepared_record_and_revocation_through_existing_scanner(self):
        m,p,raw,r,ev=self.generated(6)
        active=p.prepare_candidate_review(r,[dict(id=o['id'],verdict='approve',reason='Synthetic') for o in r['occurrences']])
        def scan(record):
            evaluation=ev([record])
            return evaluation.scan_text_subject(raw,'arbitrary-fixture.txt',m._path_finder(Path(m.__file__)),subject_kind='tracked-blob',mode='staged-blob-text',commit_oid=None,raw_path=b'arbitrary-fixture.txt',blob_oid=r['occurrences'][0]['blobOid'],git_mode='100644')
        self.assertEqual(scan(active),[])
        revoked=copy.deepcopy(active)
        revoked.pop('recordSha256')
        revoked.update(revision=2,previousRecordSha256=active['recordSha256'],state='revoked',revocation={'reason':'withdrawn','rootReceivingReference':'synthetic-revocation'})
        self.assertTrue(scan(p.seal_record(revoked)))

    def test_retained_id_cannot_approve_mutated_occurrence_fields(self):
        import base64
        m,p,raw,r,ev=self.generated(1)
        original=r['occurrences'][0]
        row=dict(id=original['id'],verdict='approve',reason='Synthetic')
        changes={
            'rawPathBase64': base64.b64encode(b'different-reviewed-path.txt').decode(),
            'blobOid': 'a' * 40,
            'blobSha256': 'a' * 64,
            'blobByteCount': original['blobByteCount'] + 1,
            'gitMode': '100755',
            'reviewRegion': m._byte_region(raw,0,len(raw)),
            'contexts': [dict(id='different-context',region=original['contexts'][0]['region'])],
        }
        for field,replacement in changes.items():
            changed=copy.deepcopy(r)
            changed['occurrences'][0][field]=replacement
            # The old schema accepts these values: rejection must be ID binding.
            p.seal_record(changed)
            with self.subTest(field=field),self.assertRaisesRegex(p.PolicyInputError,'content-id-mismatch'):
                p.prepare_candidate_review(changed,[row])
        # A valid alternate detector/candidate pair also cannot retain old ID.
        alternate=m.build_review_occurrences(b'TOKEN='+b'aB9'*16+b'\n',b'arbitrary-fixture.txt',
            object_format='sha1',git_mode='100644',policy_module=p)
        self.assertTrue(alternate)
        changed=copy.deepcopy(r)
        changed['occurrences']=[dict(copy.deepcopy(alternate[0]),id=original['id'])]
        p.seal_record(changed)
        with self.assertRaisesRegex(p.PolicyInputError,'content-id-mismatch'):
            p.prepare_candidate_review(changed,[row])

    def test_duplicate_generated_ids_rejected_before_selection(self):
        m,p,raw,r,ev=self.generated(1)
        r['occurrences']*=2
        with self.assertRaises(p.PolicyInputError):
            p.prepare_candidate_review(r,[dict(id=r['occurrences'][0]['id'],verdict='approve',reason='Synthetic')])
