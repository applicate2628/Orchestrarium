"""Real index capture for trusted Root; no model or live policy authority."""
import base64
import unittest
from unittest.mock import patch
from tests import test_review_receiving_finalizer as receiving


class StagedReviewCaptureTests(unittest.TestCase):
    setUp=receiving.ReceivingFinalizerTests.setUp
    git=receiving.ReceivingFinalizerTests.git
    in_root=receiving.ReceivingFinalizerTests.in_root
    finalize=receiving.ReceivingFinalizerTests.finalize
    object_format="sha1"
    def test_index_capture_evidence_finalize_and_rescan(self):
        raw=(b'C:/Users/'+b'Synthetic/new\n')
        self.root.joinpath('selected.txt').write_bytes(raw)
        self.git('add','selected.txt')
        self.root.joinpath('selected.txt').write_bytes(b'not staged\n')
        with self.in_root(): capture=self.module.capture_staged_review()
        self.assertEqual(capture['status'],'reviewable')
        self.assertEqual(capture['unsupported'],[])
        packet=capture['packet']; self.assertEqual(len(packet['occurrences']),1)
        evidence=capture['content'][packet['occurrences'][0]['blobOid']]
        self.assertEqual(base64.b64decode(evidence['rawBase64']),raw)
        p=self.module._load_review_policy_module()
        self.origin=self.root.parent/'isolated-origin';(self.origin/'.agents/publication').mkdir(parents=True)
        review=dict(packetId=packet['packetId'],decisions=[dict(id=o['id'],verdict='approve',reason='Synthetic fixture') for o in packet['occurrences']],removalCondition='Withdraw on change')
        self.assertEqual(self.finalize(p,packet,review,apply=True)['kind'],'committed')
        with self.in_root(),patch.object(p.Path,'home',return_value=self.origin):
            self.assertEqual(self.module.main([]),0)

    def test_unchanged_path_lines_not_added_to_review(self):
        self.root.joinpath('selected.txt').write_bytes(b'C:/Users/'+b'Synthetic/old\nsafe\n')
        self.git('add','selected.txt');self.git('commit','-qm','old synthetic content')
        self.root.joinpath('selected.txt').write_bytes(b'C:/Users/'+b'Synthetic/old\nnew safe\n')
        self.git('add','selected.txt')
        with self.in_root(): capture=self.module.capture_staged_review()
        self.assertIsNone(capture['packet']);self.assertEqual(capture['content'],{})

    def test_index_drift_refuses_capture(self):
        self.root.joinpath('selected.txt').write_bytes(b'C:/Users/'+b'Synthetic/new\n');self.git('add','selected.txt')
        original=self.module._tracked_files
        calls=0
        def changed(**kw):
            nonlocal calls
            calls+=1
            if calls==2:
                self.root.joinpath('selected.txt').write_bytes(b'changed\n');self.git('add','selected.txt')
            return original(**kw)
        with self.in_root(),patch.object(self.module,'_tracked_files',side_effect=changed),self.assertRaisesRegex(ValueError,'staged-review-drift'):
            self.module.capture_staged_review()

    def test_binary_is_explicit_unsupported(self):
        self.root.joinpath('binary.dat').write_bytes(b'\0data');self.git('add','binary.dat')
        with self.in_root(): capture=self.module.capture_staged_review()
        self.assertEqual(capture['status'],'unsupported')
        self.assertIsNone(capture['packet'])
        self.assertEqual(capture['unsupported'][0]['reason'],'unsupported-review-subject')
