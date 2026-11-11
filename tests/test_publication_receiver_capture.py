"""Actual captured-child/pending lifecycle regression tests, synthetic repo only."""
import dataclasses,importlib.util,json,pathlib,shutil,subprocess,sys,tempfile,unittest
from unittest import mock
ROOT=pathlib.Path(__file__).resolve().parents[1]
SCRIPTS=ROOT/'scripts/universal-hooks/scripts'
class CapturedReceiverTests(unittest.TestCase):
 def setUp(self):
  self.enterContext(mock.patch.dict(sys.modules));self.enterContext(mock.patch.object(sys,'path',[str(SCRIPTS),*sys.path]))
  spec=importlib.util.spec_from_file_location('captured_receiver_gate',SCRIPTS/'check-git-push-gate.py');self.gate=importlib.util.module_from_spec(spec);sys.modules[spec.name]=self.gate;spec.loader.exec_module(self.gate)
  self.root=pathlib.Path(self.enterContext(tempfile.TemporaryDirectory()))
  self.git('init','-q');self.git('config','user.name','Fixture');self.git('config','user.email','fixture@example.invalid')
  (self.root/'a').write_text('safe');self.git('add','.');self.git('commit','-qm','first');old=self.git('rev-parse','HEAD')
  (self.root/'a').write_text('safe next');self.git('commit','-qam','next');tip=self.git('rev-parse','HEAD')
  endpoint='https://example.invalid/fixture.git';wire=(tip+' '+tip+' refs/heads/new '+'0'*40+'\n').encode()
  self.native=self.gate.NativePushInput('target',endpoint,wire)
  from transfer_binding import ScopeBinding
  self.scope=ScopeBinding('test-invocation',self.gate._native_endpoint_identity(endpoint),'sha1','2'*64,(old,),'isolated-captured-test')
 def git(self,*args):return subprocess.check_output(['git','-C',str(self.root),*args],stderr=subprocess.PIPE).decode().strip()
 def scan(self,scope=True):return self.gate._run_authoritative_scan(self.native,str(self.root),shutil.which('git'),receiver_scope=self.scope if scope else None)
 def test_actual_captured_v5_consumed_once(self):
  evidence=self.scan();self.assertEqual(evidence.parsed_outcome.kind,'valid-v5');execution=evidence.execution;pending=execution.pending
  self.assertEqual(pending.state,self.gate.PendingState.CONSUMED)
  self.assertIn('receiver_scope',[node.role for node in execution.closure_after.nodes])
  self.assertEqual(evidence.binding.receiver_scope_sha256,self.scope.digest())
  with self.assertRaisesRegex(self.gate.PrRouteDenied,'RECEIPT-USED'):
   pending.correlate_and_consume_once(execution.launched,(execution,),execution.closure_after,execution.interpreter_identity_after,evidence.binding,self.gate.time.monotonic())
 def test_v4_fullgraph_still_works(self):
  evidence=self.scan(False);self.assertEqual(evidence.parsed_outcome.kind,'valid-v4');self.assertEqual(evidence.parsed_outcome.receipt.commits,2)
 def corrupt(self,change):
  original=self.gate._run_snapshot_child
  def wrapped(*args,**kwargs):
   launched,records=original(*args,**kwargs);record,=records
   self.assertEqual(record.exit_code,0)
   frame=json.loads(record.stdout);change(frame)
   return launched,(dataclasses.replace(record,stdout=json.dumps(frame).encode()),)
  with mock.patch.object(self.gate,'_run_snapshot_child',side_effect=wrapped):
   with self.assertRaises(self.gate.PrRouteDenied):self.scan()
 def test_changed_scope_receipt_refused(self):self.corrupt(lambda frame:frame.update(receiverScopeSha256='f'*64))
 def test_changed_selection_receipt_refused(self):self.corrupt(lambda frame:frame.update(selectionSha256='f'*64))
 def test_scope_receipt_downgrade_refused(self):
  def change(frame):frame.pop('receiverScopeSha256');frame['version']=4
  self.corrupt(change)
 def test_missing_scope_receipt_refused(self):self.corrupt(lambda frame:frame.pop('receiverScopeSha256'))
if __name__=='__main__':unittest.main(verbosity=2)
