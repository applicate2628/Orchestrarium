import base64,dataclasses,importlib.util,json,pathlib,sys,unittest
from unittest import mock
ROOT=pathlib.Path(__file__).resolve().parents[1]
with mock.patch.dict(sys.modules), mock.patch.object(sys,'path',list(sys.path)):
 sys.path.insert(0,str(ROOT/'scripts/universal-hooks/scripts'))
 spec=importlib.util.spec_from_file_location('receiver_gate_candidate',ROOT/'scripts/universal-hooks/scripts/check-git-push-gate.py');gate=importlib.util.module_from_spec(spec);sys.modules[spec.name]=gate;spec.loader.exec_module(gate)


class ReceiptTests(unittest.TestCase):
 def setUp(self):
  self.binding=gate.NativePushScanBinding('sha1','sha256:'+'1'*64,'2'*64,'3'*64,'4'*64)
  self.frame={'kind':'publication-safety-native','version':5,'status':'clean','coverageKind':'objects','objectFormat':'sha1','endpointIdentity':self.binding.endpoint_identity,'inputSha256':self.binding.input_sha256,'updateSetSha256':'5'*64,'selectionSha256':self.binding.selection_sha256,'repositoryObservationSha256':self.binding.repository_observation_sha256,'updates':1,'commits':0,'objects':1,'tags':1,'blobs':0,'blobBytes':0,'text':0,'binary':0,'subjects':1,'paths':0,'review':None,'receiverScopeSha256':'6'*64}
  for key in ('commitSetSha256','objectSetSha256','coverageSha256','blobSetSha256','subjectSetSha256','pathSetSha256'):self.frame[key]='7'*64
 def parse(self):return gate._parse_receiver_scoped_receipt_v5(json.dumps(self.frame))
 def test_valid_explicit(self):
  parsed=self.parse();self.assertIsNotNone(parsed);gate._verify_receiver_scoped_receipt_v5(parsed,self.binding,'6'*64)
 def test_existing_v4_dispatch_refuses_v5(self):self.assertEqual(gate._parse_native_publication_observation(json.dumps(self.frame)).kind,'malformed')
 def test_no_scope(self):
  del self.frame['receiverScopeSha256'];self.assertIsNone(self.parse())
 def test_unknown_field(self):self.frame['allowed']=True;self.assertIsNone(self.parse())
 def test_v4_cannot_downgrade(self):self.frame['version']=4;self.assertIsNone(self.parse())
 def test_bad_coverage(self):self.frame['tags']=2;self.assertIsNone(self.parse())
 def test_changed_scope(self):
  with self.assertRaises(gate.PrRouteDenied):gate._verify_receiver_scoped_receipt_v5(self.parse(),self.binding,'8'*64)
 def test_changed_selection(self):
  wrong=dataclasses.replace(self.binding,selection_sha256='8'*64)
  with self.assertRaises(gate.PrRouteDenied):gate._verify_receiver_scoped_receipt_v5(self.parse(),wrong,'6'*64)
 def test_duplicate_json(self):
  text=json.dumps(self.frame)[:-1]+',"receiverScopeSha256":"'+'6'*64+'"}'
  self.assertIsNone(gate._parse_receiver_scoped_receipt_v5(text))
 def test_empty_expectation(self):
  with self.assertRaises(gate.PrRouteDenied):gate._verify_receiver_scoped_receipt_v5(self.parse(),self.binding,'')

 def test_qualified_review_not_discarded(self):
  used=[['decision','9'*64]]
  self.frame.update(status='qualified',tags=0,blobs=1,text=1,blobBytes=1,paths=1,
   review={'snapshotId':'8'*64,'usedDecisions':used,'applied':1,'appliedSet':'9'*64,'usedToken':base64.b64encode(gate._native_canonical_bytes(used)).decode()})
  native=dict(self.frame);native.pop('receiverScopeSha256');native['version']=4
  self.assertEqual(gate._parse_native_publication_observation(json.dumps(native)).kind,'qualified-v4')
  observed=self.parse()
  self.assertIsNotNone(observed)
  self.assertEqual(observed.qualification,gate._parse_native_publication_observation(json.dumps(native)).qualification)

if __name__=='__main__':unittest.main()
