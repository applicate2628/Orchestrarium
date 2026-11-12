"""Isolated tests of Root-owned finalization, not authentication of callers."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_review_candidate_workflow as candidate_tests


class ReceivingFinalizerTests(unittest.TestCase):
    setUp=candidate_tests.CandidateWorkflowTests.setUp
    git=candidate_tests.CandidateWorkflowTests.git
    in_root=candidate_tests.CandidateWorkflowTests.in_root
    payload=candidate_tests.CandidateWorkflowTests.payload
    fixture=candidate_tests.CandidateWorkflowTests.fixture
    generated=candidate_tests.CandidateWorkflowTests.generated
    object_format='sha1'

    def case(self,count=6):
        m,p,raw,r,_=self.generated(count)
        packet=m.build_review_packet([(raw,b'arbitrary-fixture.txt','100644')],
            repository=r['repository'],modes=['staged-blob-text'],range_scope=None,policy_module=p)
        decisions=[dict(id=o['id'],verdict='approve',reason='Public synthetic fixture') for o in packet['occurrences'][::2]]
        review={'packetId':packet['packetId'],'decisions':decisions,'removalCondition':'Revoke when superseded'}
        return m,p,raw,packet,review

    def finalize(self,p,packet,review,**kw):
        with patch.object(p.Path,'home',return_value=self.origin):
            return p.finalize_received_review(p.resolve_trusted_origin(),packet,
                json.dumps(review).encode() if isinstance(review,dict) else review,
                receiving_reference=kw.pop('receiving_reference','native-result:synthetic-review'),
                review_artifact_reference='synthetic-review-result',**kw)

    def fresh_scan(self,m,p,raw,packet):
        with patch.object(p.Path,'home',return_value=self.origin):
            read=p.read_policy_snapshot(p.resolve_trusted_origin(),self.root)
        evaluation=m.ReviewEvaluation(policy_module=p,policy_read=read,
            repository_observation=self.payload([])['repositoryObservation'],execution='gate-captured-v1')
        return evaluation.scan_text_subject(raw,'arbitrary-fixture.txt',m._path_finder(Path(m.__file__)),
            subject_kind='tracked-blob',mode='staged-blob-text',commit_oid=None,
            raw_path=b'arbitrary-fixture.txt',blob_oid=packet['occurrences'][0]['blobOid'],git_mode='100644')

    def test_preview_apply_replay_and_fresh_partial_scan_counts(self):
        for count in (1,6,1000):
            with self.subTest(count=count):
                m,p,raw,packet,review=self.case(count)
                before=self.origin.joinpath('.agents/publication/reviewed-exceptions.json')
                previous=before.read_bytes() if before.exists() else None
                preview=self.finalize(p,packet,review)
                self.assertEqual(preview['kind'],'preview')
                self.assertEqual(before.read_bytes() if before.exists() else None,previous)
                applied=self.finalize(p,packet,review,apply=True)
                self.assertEqual((applied['kind'],applied['effect']),('committed','applied'))
                self.assertTrue(applied['resourcesSettled'])
                self.assertEqual(applied['proposed'],applied['observed'])
                persisted=before.read_bytes()
                replay=self.finalize(p,packet,review,apply=True)
                self.assertEqual(replay['kind'],'idempotent')
                self.assertEqual(before.read_bytes(),persisted)
                self.assertEqual(len(self.fresh_scan(m,p,raw,packet)),count-len(review['decisions']))

    def test_revoked_decision_cannot_be_replayed(self):
        m,p,raw,packet,review=self.case()
        result=self.finalize(p,packet,review,apply=True)
        with patch.object(p.Path,'home',return_value=self.origin):
            revoked=p.revoke_decision(p.resolve_trusted_origin(),packet['repository'],result['decisionId'],
                'Withdrawn','synthetic-native-revocation',
                expected_document_sha256=result['observed']['documentSha256'],
                expected_record_sha256=result['observed']['recordSha256'],apply=True)
        self.assertEqual(revoked['kind'],'committed')
        with self.assertRaises(p.PolicyError):self.finalize(p,packet,review,apply=True)
        reformatted=json.dumps(dict(review,decisions=list(reversed(review['decisions']))),indent=2).encode()
        with self.assertRaises(p.PolicyError):self.finalize(p,packet,reformatted,apply=True)
        self.assertEqual(len(self.fresh_scan(m,p,raw,packet)),6)

    def test_packet_and_scope_drift_never_rebind_received_review(self):
        m,p,raw,packet,review=self.case()
        changed=copy.deepcopy(packet);changed['modes']=['range-blob-text'];changed['rangeScope']={'kind':'object-content'}
        with self.assertRaisesRegex(p.PolicyInputError,'packet-drift'):self.finalize(p,changed,review,apply=True)
        changed['packetId']=p.candidate_packet_id({k:v for k,v in changed.items() if k!='packetId'})
        with self.assertRaisesRegex(p.PolicyInputError,'packet-mismatch'):self.finalize(p,changed,review,apply=True)
        self.assertFalse(self.origin.joinpath('.agents/publication/reviewed-exceptions.json').exists())

    def test_labels_file_references_and_duplicate_json_do_not_replace_result(self):
        m,p,raw,packet,review=self.case()
        invalid=[dict(review,role='security-reviewer',approved=True),
                 {'report':'untrusted.md','role':'security-reviewer','gate':'PASS'},
                 b'{"packetId":"x","packetId":"x","decisions":[],"removalCondition":"x"}',
                 b'@untrusted-review.json']
        for submitted in invalid:
            with self.subTest(submitted=submitted),self.assertRaises(p.PolicyInputError):
                self.finalize(p,packet,submitted,apply=True)
        self.assertFalse(self.origin.joinpath('.agents/publication/reviewed-exceptions.json').exists())

    def test_preimage_change_between_capture_and_promotion_is_not_retried(self):
        m,p,raw,packet,review=self.case()
        real=p.promote_decision
        def drift(*args,**kwargs):
            self.origin.joinpath('.agents/publication/reviewed-exceptions.json').write_bytes(p.canonical_document(7,[]))
            return real(*args,**kwargs)
        with patch.object(p,'promote_decision',side_effect=drift) as promote:
            with self.assertRaises(p.PolicyError):self.finalize(p,packet,review,apply=True)
            self.assertEqual(promote.call_count,1)
        self.assertEqual(self.origin.joinpath('.agents/publication/reviewed-exceptions.json').read_bytes(),p.canonical_document(7,[]))

    def test_transaction_failure_remains_owner_failure_without_success_claim(self):
        m,p,raw,packet,review=self.case()
        with patch.object(p.os,'link',side_effect=OSError('synthetic creation failure')):
            with self.assertRaises(p.PolicyError):self.finalize(p,packet,review,apply=True)
        self.assertFalse(self.origin.joinpath('.agents/publication/reviewed-exceptions.json').exists())
        self.assertFalse(list(self.origin.rglob('*.tmp')))

    def test_packet_is_detached_from_callers_mutable_input(self):
        m,p,raw,r,_=self.generated(1)
        repository=copy.deepcopy(r['repository']);modes=['staged-blob-text']
        packet=m.build_review_packet([(raw,b'arbitrary-fixture.txt','100644')],repository=repository,
            modes=modes,range_scope=None,policy_module=p)
        original=copy.deepcopy(packet)
        modes.append('range-blob-text');repository['objectFormat']='sha256'
        self.assertEqual(packet,original)

    def test_post_replace_failure_retains_actual_applied_state(self):
        m,p,raw,packet,review=self.case()
        with patch.object(p,'_sync_policy_directory',side_effect=OSError('synthetic durability failure')):
            with self.assertRaises(p.PolicyError) as raised:
                self.finalize(p,packet,review,apply=True)
        self.assertEqual(raised.exception.outcome['kind'],'recovery-required')
        self.assertEqual(raised.exception.outcome['effect'],'applied')
        self.assertTrue(self.origin.joinpath('.agents/publication/reviewed-exceptions.json').exists())
        self.assertEqual(len(self.fresh_scan(m,p,raw,packet)),3)

    def test_fresh_scan_retains_new_content_findings_after_promotion(self):
        m,p,raw,packet,review=self.case()
        self.finalize(p,packet,review,apply=True)
        self.assertEqual(len(self.fresh_scan(m,p,raw+b'# changed\n',packet)),6)

    def test_repository_controlled_policy_origin_cannot_receive_grant(self):
        m,p,raw,packet,review=self.case()
        with patch.object(p.Path,'home',return_value=self.root):
            selection=p.resolve_trusted_origin()
            with self.assertRaises(p.PolicyError):
                p.finalize_received_review(selection,packet,json.dumps(review).encode(),
                    receiving_reference='native-result:synthetic-review',
                    review_artifact_reference='synthetic-review-result',apply=True)
        self.assertFalse(self.root.joinpath('.agents/publication/reviewed-exceptions.json').exists())

    def test_new_host_result_can_reapprove_without_reactivating_old_decision(self):
        m,p,raw,packet,review=self.case()
        first=self.finalize(p,packet,review,apply=True)
        with patch.object(p.Path,'home',return_value=self.origin):
            p.revoke_decision(p.resolve_trusted_origin(),packet['repository'],first['decisionId'],
                'Withdrawn','synthetic-native-revocation',
                expected_document_sha256=first['observed']['documentSha256'],
                expected_record_sha256=first['observed']['recordSha256'],apply=True)
        # A different actual result supplied by the trusted Root, not parsed auth.
        second=self.finalize(p,packet,review,receiving_reference='native-result:synthetic-new-review',apply=True)
        self.assertNotEqual(first['decisionId'],second['decisionId'])
        persisted=json.loads(self.origin.joinpath('.agents/publication/reviewed-exceptions.json').read_bytes())
        by_id={record['id']:record for record in persisted['decisions']}
        self.assertEqual(by_id[first['decisionId']]['state'],'revoked')
        self.assertEqual(by_id[second['decisionId']]['state'],'active')
        self.assertEqual(by_id[first['decisionId']]['occurrences'],by_id[second['decisionId']]['occurrences'])
        with self.assertRaises(p.PolicyError):self.finalize(p,packet,review,apply=True)
        self.assertEqual(len(self.fresh_scan(m,p,raw,packet)),3)
