from pathlib import Path
import sys,runpy,importlib.util,hashlib,json,copy,argparse
from unittest.mock import patch
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description='Opt-in authenticated provider preview test; synthetic decision, no policy writes')
parser.add_argument('--expected-repository-id',required=True)
args=parser.parse_args()
with patch.dict(sys.modules):
 f=runpy.run_path(str(root/'tests/test_publication_review_policy.py'))
 body=f['_record']();body.pop('recordSha256');body.pop('repository')
 decision={'schema':'orchestrarium.portable-review.v1','scope':'native-repository-content','project':{'provider':'github','authority':'github.com','repositoryId':args.expected_repository_id},'record':body}
 digest=hashlib.sha256(f['policy'].C(decision)).hexdigest()
scripts=root/'scripts/universal-hooks/scripts';sys.path.insert(0,str(scripts))
spec=importlib.util.spec_from_file_location('portable_probe_gate',scripts/'check-git-push-gate.py');gate=importlib.util.module_from_spec(spec);sys.modules[spec.name]=gate;spec.loader.exec_module(gate)
import receiver_transport
result=receiver_transport.prepare_portable_batch(gate,root,'origin',decision,digest)
assert result['preview']['effect']=='not-applied'
assert result['preview']['before']==result['preview']['observed']
print(json.dumps({'effect':result['preview']['effect'],'project':result['project'],'sourceCaptured':True,'policyUnchanged':True,'syntheticDecisionOnly':True}))
def canonical_digest(value):
 return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=True,separators=(',',':')).encode('ascii')).hexdigest()
negative=[]
for name,change,old_digest in [('wrong-project',lambda d:d['project'].update(repositoryId='1'),False),('content-drift',lambda d:d['record']['occurrences'][0].update(blobOid='f'*40),True),('legacy',lambda d:d.pop('project'),False)]:
 altered=copy.deepcopy(decision);change(altered)
 try:receiver_transport.prepare_portable_batch(gate,root,'origin',altered,digest if old_digest else canonical_digest(altered))
 except (ValueError,RuntimeError):negative.append(name)
 else:raise AssertionError(name+' accepted')
assert negative==['wrong-project','content-drift','legacy']
print(json.dumps({'negativeRefusals':negative,'policyWrites':0}))
