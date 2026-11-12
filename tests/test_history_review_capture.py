"""History capture reuses real traversal; synthetic Root authority only."""
import base64
import unittest
from unittest.mock import patch
from tests import test_review_receiving_finalizer as receiving


class HistoryReviewCaptureTests(unittest.TestCase):
    setUp=receiving.ReceivingFinalizerTests.setUp
    git=receiving.ReceivingFinalizerTests.git
    in_root=receiving.ReceivingFinalizerTests.in_root
    payload=receiving.ReceivingFinalizerTests.payload
    finalize=receiving.ReceivingFinalizerTests.finalize
    object_format='sha1'

    def history_case(self):
        raw=b'C:/Users/'+b'Synthetic/history\n'
        self.root.joinpath('review.txt').write_bytes(raw);self.git('add','review.txt');self.git('commit','-qm','new synthetic content')
        tip=self.git('rev-parse','HEAD').strip().decode()
        return raw,tip,self.payload([(b'refs/heads/main',tip,b'refs/heads/main',self.commit)])

    def test_real_range_and_native_capture_share_exact_evidence(self):
        raw,tip,payload=self.history_case()
        with self.in_root():
            ranged=self.module.capture_history_review('origin','refs/heads/main')
            native=self.module.capture_history_review(native_payload=payload)
        for capture in (ranged,native):
            self.assertEqual(capture['status'],'reviewable')
            packet=capture['packet'];self.assertEqual(packet['rangeScope'],{'kind':'exact-commits','commits':[tip]})
            self.assertEqual(len(packet['occurrences']),1)
            self.assertEqual(base64.b64decode(capture['content'][packet['occurrences'][0]['blobOid']]['rawBase64']),raw)
        self.assertEqual(ranged['packet'],native['packet'])
        p=self.module._load_review_policy_module();self.origin=self.root.parent/'origin';(self.origin/'.agents/publication').mkdir(parents=True)
        packet=native['packet'];review=dict(packetId=packet['packetId'],decisions=[dict(id=o['id'],verdict='approve',reason='Synthetic evidence') for o in packet['occurrences']],removalCondition='Withdraw')
        self.assertEqual(self.finalize(p,packet,review,apply=True)['kind'],'committed')
        with self.in_root(),patch.object(p.Path,'home',return_value=self.origin):
            self.assertEqual(self.module.main(['--range','origin','refs/heads/main']),0)
            with patch.object(self.module,'__injected_native_push__',payload,create=True):
                self.assertEqual(self.module.main(['--native-push']),0)

    def test_capture_budget_refuses_without_partial_packet(self):
        self.history_case()
        with self.in_root(),patch.object(self.module,'_MAX_REVIEW_CAPTURE_BYTES',1):
            result=self.module.capture_history_review('origin','refs/heads/main')
        self.assertEqual(result['status'],'refused');self.assertIsNone(result['packet']);self.assertEqual(result['content'],{})

    def test_commit_message_findings_are_not_hidden(self):
        self.history_case();self.git('commit','--allow-empty','-qm','TOKEN='+('aB9'*16))
        with self.in_root():result=self.module.capture_history_review('origin','refs/heads/main')
        self.assertEqual(result['status'],'unsupported');self.assertTrue(result['unsupported'])

    def test_shared_blob_preserves_path_and_mode_aliases(self):
        raw,tip,payload=self.history_case()
        self.root.joinpath('alias.txt').write_bytes(raw);self.git('add','alias.txt')
        self.git('update-index','--chmod=+x','alias.txt');self.git('commit','-qm','alias')
        with self.in_root():result=self.module.capture_history_review('origin','refs/heads/main')
        self.assertEqual(result['status'],'reviewable')
        self.assertEqual(len(result['content']),1)
        occurrences=result['packet']['occurrences']
        self.assertEqual({o['gitMode'] for o in occurrences},{'100644','100755'})
        self.assertEqual({base64.b64decode(o['rawPathBase64']) for o in occurrences},{b'review.txt',b'alias.txt'})
        self.assertEqual(len(occurrences),2)

    def test_repository_recheck_failure_discards_partial_evidence(self):
        self.history_case();original=self.module._capture_review_repository;calls=0
        def drift(*args,**kwargs):
            nonlocal calls
            calls+=1
            observed,rows=original(*args,**kwargs)
            if calls==2: observed={'status':'unavailable','repository':None}
            return observed,rows
        with self.in_root(),patch.object(self.module,'_capture_review_repository',side_effect=drift):
            result=self.module.capture_history_review('origin','refs/heads/main')
        self.assertEqual(result['status'],'refused');self.assertEqual(result['content'],{});self.assertIsNone(result['packet'])

    def test_native_path_content_findings_are_explicitly_unsupported(self):
        path=self.root/('C:/Users/'+'Synthetic/file.txt')
        path.parent.mkdir(parents=True);path.write_text('safe content\n')
        self.git('add','.');self.git('commit','-qm','synthetic metadata')
        tip=self.git('rev-parse','HEAD').strip().decode()
        payload=self.payload([(b'refs/heads/main',tip,b'refs/heads/main',self.commit)])
        with self.in_root():result=self.module.capture_history_review(native_payload=payload)
        self.assertEqual(result['status'],'unsupported')
        self.assertIn('tree-path',result['unsupported'])
        self.assertIsNone(result['packet'])
