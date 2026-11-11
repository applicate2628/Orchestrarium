import base64,dataclasses,hashlib,importlib.util,json,os,pathlib,subprocess,sys,tempfile,unittest
from unittest import mock
ROOT=pathlib.Path(__file__).resolve().parents[1]
def _synthetic_machine_path(user, filename):
 # Test-only generated identities, never paths from the user's machine.
 return str(pathlib.PureWindowsPath('C:/') / 'Users' / user / filename)

class ScopedScannerTests(unittest.TestCase):
 def setUp(self):
  self.enterContext(mock.patch.dict(sys.modules));self.enterContext(mock.patch.object(sys,'path',[str(ROOT/'scripts/universal-hooks/scripts'),*sys.path]))
  spec=importlib.util.spec_from_file_location('scoped_scanner',ROOT/'scripts/universal-hooks/scripts/check-publication-safety.py');self.scanner=importlib.util.module_from_spec(spec);sys.modules[spec.name]=self.scanner;spec.loader.exec_module(self.scanner)
  self.tmp=self.enterContext(tempfile.TemporaryDirectory());self.root=pathlib.Path(self.tmp)
  prior=os.getcwd();os.chdir(self.root);self.addCleanup(os.chdir,prior)
  self.git('init','-q');self.git('config','user.name','Fixture');self.git('config','user.email','fixture@example.invalid')
  (self.root/'file.txt').write_text('safe public text\n');self.git('add','.');self.git('commit','-qm','Historical example '+_synthetic_machine_path('Fixture','file.txt'));self.old=self.git('rev-parse','HEAD')
  (self.root/'file.txt').write_text('next safe public text\n');self.git('commit','-qam','next safe');self.tip=self.git('rev-parse','HEAD')
  policy=self.scanner._load_review_policy_module();observation,_=self.scanner._capture_review_repository(policy,self.root,self.scanner.time.monotonic()+30)
  self.assertEqual(observation['status'],'captured')
  endpoint='https://example.invalid/fixture.git';wire=(self.tip+' '+self.tip+' refs/heads/new '+'0'*40+'\n').encode()
  self.payload={'version':1,'objectFormat':'sha1','repositoryObservation':observation,'endpoint':endpoint,'endpointIdentity':'sha256:'+hashlib.sha256(json.dumps(endpoint,separators=(',',':')).encode()).hexdigest(),'inputSha256':hashlib.sha256(wire).hexdigest(),'wireBase64':base64.b64encode(wire).decode()}
  from transfer_binding import ScopeBinding
  self.scope=ScopeBinding('invocation',self.payload['endpointIdentity'],'sha1','2'*64,(self.old,),'local-experiment-only')
  self.finder=self.scanner._path_finder(ROOT/'scripts/universal-hooks/scripts/check-publication-safety.py')
 def git(self,*args):return subprocess.check_output(['git',*args],stderr=subprocess.PIPE).decode().strip()
 def scan(self,scope):return self.scanner._scan_native_push(self.payload,self.finder,receiver_scope=scope,scan_timeout=30)
 def test_fullgraph_retains_historical_finding(self):self.assertEqual(self.scan(None).kind,'findings')
 def test_scoped_actual_scan_and_receipt(self):
  result=self.scan(self.scope);self.assertEqual(result.kind,'clean',result.refusal)
  self.assertEqual(result.history.commit_ids,(self.tip,))
  frame=json.loads(self.scanner._serialize_receiver_scoped_receipt_v5(result));self.assertEqual(frame['receiverScopeSha256'],self.scope.digest());self.assertEqual(frame['selectionSha256'],self.scope.selection_digest(self.payload));self.assertEqual(frame['version'],5)
  with self.assertRaises(ValueError):self.scanner._serialize_native_receipt_v4(result)
 def test_wrong_endpoint_refused(self):self.assertEqual(self.scan(dataclasses.replace(self.scope,endpoint_identity='sha256:'+'8'*64)).kind,'refusal')
 def test_missing_local_root_does_not_exclude_history(self):self.assertEqual(self.scan(dataclasses.replace(self.scope,excluded_roots=('f'*40,))).kind,'findings')
 def test_new_finding_still_blocked(self):
  self.git('commit','--allow-empty','-qm','New private path '+_synthetic_machine_path('Private','secret.txt'));new=self.git('rev-parse','HEAD');wire=(new+' '+new+' refs/heads/new '+'0'*40+'\n').encode();self.payload.update(inputSha256=hashlib.sha256(wire).hexdigest(),wireBase64=base64.b64encode(wire).decode());self.assertEqual(self.scan(self.scope).kind,'findings')
 def reset_wire(self,roots):
  wire=''.join(oid+' '+oid+' '+ref+' '+'0'*40+'\n' for oid,ref in roots).encode()
  self.payload.update(inputSha256=hashlib.sha256(wire).hexdigest(),wireBase64=base64.b64encode(wire).decode())
 def test_disjoint_multi_update(self):
  tree=self.git('rev-parse','HEAD^{tree}');other=self.git('commit-tree',tree,'-m','independent safe root')
  self.reset_wire([(self.tip,'refs/heads/new'),(other,'refs/heads/independent')])
  result=self.scan(self.scope);self.assertEqual(result.kind,'clean',result.refusal)
  self.assertEqual(set(result.history.commit_ids),{self.tip,other})
 def test_tag_and_tree_roots(self):
  self.git('tag','-a','fixture-tag','-m','safe annotated tag');tag=self.git('rev-parse','fixture-tag');tree=self.git('rev-parse','HEAD^{tree}')
  self.reset_wire([(tag,'refs/tags/new-tag'),(tree,'refs/tags/tree-root')])
  result=self.scan(self.scope);self.assertEqual(result.kind,'clean',result.refusal)
  self.assertIn(tag,result.history.tag_ids);self.assertIn(tree,result.history.object_ids)
  self.assertEqual(result.history.commit_ids,(self.tip,))
 def test_wrong_object_format_refused(self):
  wrong=dataclasses.replace(self.scope,object_format='sha256',excluded_roots=())
  self.assertEqual(self.scan(wrong).kind,'refusal')

 def test_external_native_payload_cannot_enable_scope(self):
  payload=dict(self.payload,receiverScope=self.scope.document())
  request=self.scanner._native_push_request(payload)
  self.assertIsInstance(request,self.scanner.Refusal)

if __name__=='__main__':unittest.main()
