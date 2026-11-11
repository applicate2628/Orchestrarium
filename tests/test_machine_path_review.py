"""Exact path-review records through the real trusted policy data owner."""
import base64,copy,hashlib,sys,unittest
from pathlib import Path
from unittest import mock
from tests.test_publication_native_effects import TestNativePublicationEffects as Base
class ExactMachinePathReview(unittest.TestCase):
 object_format='sha1'
 setUp=Base.setUp;git=Base.git;in_root=Base.in_root;payload=Base.payload
 def test_canonical_spans_preserve_legacy_classification(self):
  import itertools
  f=self.module._path_finder(Path(self.module.__file__))
  for prefix,user,delimiter in itertools.product(('C:/Users/','C:\\Users\\','/c/Users/','/home/','/Users/','D:/dev/','/d/projects/','\\\\host\\Users\\'),('Fixture','you','<repo>','...','Демо','%USERPROFILE%'),('', ' ', '\"', "'",'(', '=', ',')):
   text=delimiter+prefix+user+'/a'
   self.assertEqual(set(f(text)),{text[a:b] for a,b in f._review_occurrences(text)})
  text='C:/Users/'+'Fixture';text=text+' '+text
  self.assertEqual(len(f(text)),1);self.assertEqual(len(f._review_occurrences(text)),2)
 def fixture(self, suffix=b''):
  from tests.test_publication_review_policy import _record
  m=self.module; p=m._load_review_policy_module(); path=b'fixture.txt'
  raw=('C:/Users/'+'Fixture/a C:/Users/'+'Other/b\n').encode()+suffix
  (self.root/path.decode()).write_bytes(raw);self.git('add',path.decode());self.git('commit','-qm','synthetic fixture')
  oid=self.git('rev-parse','HEAD:fixture.txt').strip().decode();head=self.git('rev-parse','HEAD').strip().decode()
  payload=self.payload([(b'refs/heads/main',head,b'refs/heads/main',self.commit)])
  finder=m._path_finder(Path(m.__file__))
  analysis=m.analyze_review_candidates(raw,path,subject_kind='tracked-blob',policy_module=p,find_machine_paths=finder)
  self.assertTrue(analysis['complete'],analysis);rows=[x for x in analysis['candidates'] if x['detectorClass']=='machine-path'];self.assertEqual(len(rows),2)
  record=_record();record.pop('recordSha256');record['repository']=payload['repositoryObservation']['repository']
  occ=record['occurrences'][0];row=rows[0];occ.update(rawPathBase64=base64.b64encode(path).decode(),blobOid=oid,blobSha256=hashlib.sha256(raw).hexdigest(),blobByteCount=len(raw),detector=row['detector'],candidate=row['candidate'],reviewRegion=m._byte_region(raw,row['candidate']['startByte'],row['candidate']['endByteExclusive']),contexts=[{'id':'fixture','region':m._byte_region(raw,0,len(raw))}])
  self.origin=Path(self.temp.name)/'home';origin=self.origin/'.agents/publication';origin.mkdir(parents=True)
  def evaluation(records):
   (origin/'reviewed-exceptions.json').write_bytes(p.canonical_document(1,records))
   with mock.patch.object(p.Path,'home',return_value=self.origin):read=p.read_policy_snapshot(p.resolve_trusted_origin(),self.root)
   self.assertEqual(len(read.usable_records),sum(r['state']=='active' for r in records))
   return m.ReviewEvaluation(policy_module=p,policy_read=read,repository_observation=payload['repositoryObservation'],execution='gate-captured-v1')
  def scan(e,body=raw,pathname=path,blob=oid):
   return e.scan_text_subject(body,pathname.decode(),finder,subject_kind='tracked-blob',mode='staged-blob-text',commit_oid=None,raw_path=pathname,blob_oid=blob,git_mode='100644')
  return m,p,raw,rows,record,evaluation,scan,finder
 def test_exact_occurrence_does_not_hide_second_path(self):
  m,p,raw,rows,r,ev,scan,f=self.fixture();e=ev([p.seal_record(r)]);hits=scan(e)
  self.assertEqual([h.detector_class for h in hits],['machine-path'])
 def test_changed_blob_and_location_rejected(self):
  m,p,raw,rows,r,ev,scan,f=self.fixture();record=p.seal_record(r)
  self.assertEqual(len(scan(ev([record]),body=raw+b'x')),2)
  self.assertEqual(len(scan(ev([record]),pathname=b'other.txt')),2)
  self.assertEqual(len(scan(ev([record]),blob='f'*40)),2)
 def test_full_exact_review_keeps_evidence(self):
  m,p,raw,rows,r,ev,scan,f=self.fixture();o=copy.deepcopy(r['occurrences'][0]);o.update(id='occ-2',detector=rows[1]['detector'],candidate=rows[1]['candidate'],reviewRegion=m._byte_region(raw,rows[1]['candidate']['startByte'],rows[1]['candidate']['endByteExclusive']));r['occurrences'].append(o)
  e=ev([p.seal_record(r)]);self.assertEqual(scan(e),[]);self.assertIsNotNone(e.evidence())
 def test_changed_detector_rejected(self):
  m,p,raw,rows,r,ev,scan,f=self.fixture();record=p.seal_record(r);f._review_source_sha256='0'*64
  self.assertEqual(len(scan(ev([record]))),2)
 def test_revocation_removes_credit(self):
  m,p,raw,rows,r,ev,scan,f=self.fixture();active=p.seal_record(r)
  r.update(revision=2,previousRecordSha256=active['recordSha256'],state='revoked',revocation={'reason':'withdrawn','rootReceivingReference':'root-revoke'})
  revoked=p.seal_record(r);self.assertEqual(p.validate_record_transition(active,revoked),'revoke')
  hits=scan(ev([revoked]));self.assertTrue(hits);self.assertTrue(all(h.detector_class=='machine-path' for h in hits))
 def test_context_change_and_other_secret_still_block(self):
  m,p,raw,rows,r,ev,scan,f=self.fixture()
  r['occurrences'][0]['contexts'][0]['region']['sha256']='0'*64
  self.assertEqual(len(scan(ev([p.seal_record(r)]))),2)
 def test_missing_review_does_not_grant(self):
  m,p,raw,rows,r,ev,scan,f=self.fixture();self.assertTrue(scan(ev([])))
 def test_secret_is_not_covered_by_path_review(self):
  secret=('TOKEN='+ 'aB9'*16+'\n').encode()
  m,p,raw,rows,r,ev,scan,f=self.fixture(secret)
  o=copy.deepcopy(r['occurrences'][0]);o.update(id='occ-2',detector=rows[1]['detector'],candidate=rows[1]['candidate'],reviewRegion=m._byte_region(raw,rows[1]['candidate']['startByte'],rows[1]['candidate']['endByteExclusive']));r['occurrences'].append(o)
  hits=scan(ev([p.seal_record(r)]));self.assertTrue(hits);self.assertTrue(any(h.detector_class!='machine-path' for h in hits))
 def test_independent_decisions_compose_without_blanket_credit(self):
  m,p,raw,rows,r,ev,scan,f=self.fixture()
  second=copy.deepcopy(r);second['id']='DEC-2';o=second['occurrences'][0]
  o.update(detector=rows[1]['detector'],candidate=rows[1]['candidate'],reviewRegion=m._byte_region(raw,rows[1]['candidate']['startByte'],rows[1]['candidate']['endByteExclusive']))
  first=p.seal_record(r);other=p.seal_record(second)
  e=ev([first,other]);self.assertEqual(scan(e),[]);self.assertEqual(len(e.evidence().used_decisions),2)
  second.update(revision=2,previousRecordSha256=other['recordSha256'],state='revoked',revocation={'reason':'withdrawn','rootReceivingReference':'root-revoke'})
  self.assertEqual(len(scan(ev([first,p.seal_record(second)]))),1)
 def test_public_candidate_projection_for_machine_path(self):
  m,p,raw,rows,r,ev,scan,f=self.fixture()
  detector=m.resolve_review_detector('machine-path',policy_module=p)
  self.assertEqual(detector,rows[0]['detector'])
  projected=m.project_review_candidate(raw,b'fixture.txt',detector,r['occurrences'][0]['reviewRegion'],policy_module=p)
  self.assertEqual(projected['status'],'bound');self.assertEqual(projected['candidate'],rows[0]['candidate'])
  ambiguous=m.project_review_candidate(raw,b'fixture.txt',detector,m._byte_region(raw,0,len(raw)),policy_module=p)
  self.assertEqual(ambiguous['status'],'ambiguous')
 def captured_case(self, tamper=None, actual_push=False):
  import importlib.util,shutil,json,dataclasses,subprocess,os
  m,p,raw,rows,r,ev,scan,f=self.fixture()
  r['modes']=['range-blob-text'];r['rangeScope']={'kind':'object-content'}
  o=copy.deepcopy(r['occurrences'][0]);o.update(id='occ-2',detector=rows[1]['detector'],candidate=rows[1]['candidate'],reviewRegion=m._byte_region(raw,rows[1]['candidate']['startByte'],rows[1]['candidate']['endByteExclusive']));r['occurrences'].append(o)
  active=p.seal_record(r)
  with mock.patch.object(p.Path,'home',return_value=self.origin):
   selection=p.resolve_trusted_origin()
   promoted=p.promote_decision(selection,r['repository'],active,expected_document_sha256=None,expected_record_sha256=None,apply=True)
  self.assertEqual(promoted['kind'],'committed')
  self.assertTrue(promoted['resourcesSettled'])
  scripts=Path(m.__file__).parent
  self.enterContext(mock.patch.object(sys,'path',[str(scripts),*sys.path]))
  spec=importlib.util.spec_from_file_location('path_review_gate',scripts/'check-git-push-gate.py');gate=importlib.util.module_from_spec(spec);sys.modules[spec.name]=gate;spec.loader.exec_module(gate)
  from transfer_binding import ScopeBinding
  tip=self.git('rev-parse','HEAD').strip().decode();endpoint=str(self.remote)
  wire=(tip+' '+tip+' refs/heads/new '+'0'*40+'\n').encode()
  native=gate.NativePushInput('target',endpoint,wire)
  scope=ScopeBinding('path-review-test',gate._native_endpoint_identity(endpoint),'sha1','2'*64,(self.commit,),'isolated-captured-test')
  # Release fixture imports; the real gate must load its own captured modules.
  sys.modules.pop('_orchestrarium_publication_review_policy_v1',None)
  sys.modules.pop('_orchestrarium_linked_runtime_subroots_v1',None)
  original=gate._run_snapshot_child
  def wrapped(*args,**kwargs):
   launched,records=original(*args,**kwargs);record,=records
   self.assertEqual(record.exit_code,0)
   frame=json.loads(record.stdout)
   if tamper=='snapshot':frame['review']['snapshotId']='f'*64
   if tamper=='applied':frame['review']['appliedSet']='f'*64
   if tamper=='scope':frame['receiverScopeSha256']='f'*64
   if tamper=='revoke':
    revoked=p.revoke_decision(selection,r['repository'],active['id'],'withdrawn','root-revoke',expected_document_sha256=promoted['observed']['documentSha256'],expected_record_sha256=active['recordSha256'],apply=True)
    self.assertEqual(revoked['kind'],'committed')
   return launched,(dataclasses.replace(record,stdout=json.dumps(frame).encode()),)
  if actual_push:
   if tamper=='missing':
    with mock.patch.object(p.Path,'home',return_value=self.origin):
     p.revoke_decision(selection,r['repository'],active['id'],'withdrawn','root-revoke',expected_document_sha256=promoted['observed']['documentSha256'],expected_record_sha256=active['recordSha256'],apply=True)
   env=dict(os.environ,HOME=str(self.origin),USERPROFILE=str(self.origin))
   result=subprocess.run([sys.executable,str(scripts/'check-git-push-gate.py'),'--target-local-push',str(self.root),'origin',tip,'refs/heads/reviewed'],env=env,capture_output=True,text=True)
   if tamper=='missing':
    self.assertNotEqual(result.returncode,0)
    absent=subprocess.run([shutil.which('git'),'--git-dir',str(self.remote),'rev-parse','--verify','refs/heads/reviewed'],capture_output=True)
    self.assertNotEqual(absent.returncode,0)
    return
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
   observed=subprocess.check_output([shutil.which('git'),'--git-dir',str(self.remote),'rev-parse','refs/heads/reviewed']).decode().strip()
   self.assertEqual(observed,tip)
   return
  with mock.patch.object(p.Path,'home',return_value=self.origin),mock.patch.object(gate,'_run_snapshot_child',side_effect=wrapped):
   if tamper:
    with self.assertRaises(gate.PrRouteDenied):gate._run_authoritative_scan(native,str(self.root),shutil.which('git'),receiver_scope=scope)
    return
   evidence=gate._run_authoritative_scan(native,str(self.root),shutil.which('git'),receiver_scope=scope)
  self.assertEqual(evidence.parsed_outcome.kind,'qualified-v5')
  self.assertIsNotNone(evidence.parsed_outcome.qualification)
  self.assertEqual(evidence.execution.pending.state,gate.PendingState.CONSUMED)
 def test_captured_v5_review_is_finalized_and_consumed(self):self.captured_case()
 def test_captured_wrong_snapshot_refused(self):self.captured_case('snapshot')
 def test_captured_wrong_scope_refused(self):self.captured_case('scope')
 def test_captured_revoked_during_scan_refused(self):self.captured_case('revoke')
 def test_actual_local_push_through_native_hook(self):self.captured_case(actual_push=True)
 def test_actual_local_push_without_live_grant_refused(self):self.captured_case('missing',actual_push=True)
if __name__=='__main__':unittest.main()
