#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,subprocess,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; SCRIPT=ROOT/'scripts'/'baseline'/'build_target_effect_baseline.py'
def canonical_json(v): return json.dumps(v,ensure_ascii=False,indent=2,sort_keys=True)+'\n'
def inventory_payload():
    entries=[
      {'path':'AGENTS.md','sizeBytes':10,'contentSha256':'a'*64,'surfaces':['documentation','governance']},
      {'path':'shared/AGENTS.shared.md','sizeBytes':15,'contentSha256':'f'*64,'surfaces':['documentation','governance','shared-source']},
      {'path':'src.codex/AGENTS.codex.md','sizeBytes':35,'contentSha256':'7'*64,'surfaces':['documentation','provider-pack','provider:codex']},
      {'path':'shared/agents-mode.schema.json','sizeBytes':20,'contentSha256':'b'*64,'surfaces':['configuration','shared-source']},
      {'path':'shared/references/cross-pack-reconciliation.md','sizeBytes':30,'contentSha256':'c'*64,'surfaces':['documentation','shared-source']},
      {'path':'src.codex/skills/architect/SKILL.md','sizeBytes':40,'contentSha256':'d'*64,'surfaces':['provider-pack','provider:codex','skill']},
      {'path':'src.claude/skills/architect/SKILL.md','sizeBytes':40,'contentSha256':'d'*64,'surfaces':['provider-pack','provider:claude','skill']},
      {'path':'src.qwen/QWEN.md','sizeBytes':25,'contentSha256':'8'*64,'surfaces':['documentation','provider-pack','provider:qwen']},
      {'path':'tests/test_alpha.py','sizeBytes':50,'contentSha256':'e'*64,'surfaces':['script','test']},
      {'path':'tests/test_registry_governance_reconciliation_contract.py','sizeBytes':60,'contentSha256':'9'*64,'surfaces':['script','test']},]
    p={'schemaVersion':1,'baseline':{'commitSha':'1'*40,'repository':'example/orche','requestedRef':'baseline','treeSha':'2'*40},'entries':entries,'summary':{'trackedLeafEntries':len(entries),'surfaceCounts':{}}}
    p['inventorySha256']=hashlib.sha256(canonical_json(p).encode()).hexdigest(); return p
class Tests(unittest.TestCase):
    def run_script(self,inv,out,*extra):
        return subprocess.run([sys.executable,str(SCRIPT),'--inventory',str(inv),'--output',str(out),*extra],text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
    def test_metrics_include_all_runtime_instruction_entrypoints(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d); inv=r/'i.json'; out=r/'o.json'; inv.write_text(canonical_json(inventory_payload()))
            p=self.run_script(inv,out); self.assertEqual(p.returncode,0,p.stderr); data=json.loads(out.read_text())
            self.assertEqual(data['repositoryShape']['trackedLeafEntries'],10); self.assertEqual(data['repositoryShape']['trackedBytes'],325)
            self.assertEqual([x['path'] for x in data['repositoryShape']['instructionEntrypoints']],['AGENTS.md','shared/AGENTS.shared.md','src.codex/AGENTS.codex.md','src.qwen/QWEN.md'])
            self.assertEqual(data['repositoryShape']['manualReconciliationArtifacts']['paths'],['shared/references/cross-pack-reconciliation.md'])
    def test_rejects_digest_tamper(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d); inv=r/'i'; out=r/'o'; p=inventory_payload(); p['entries'][0]['sizeBytes']=11; inv.write_text(canonical_json(p)); x=self.run_script(inv,out)
            self.assertEqual(x.returncode,2); self.assertIn('inventorySha256 mismatch',x.stderr)
    def test_rejects_non_object(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d); inv=r/'i'; out=r/'o'; inv.write_text('[]\n'); x=self.run_script(inv,out)
            self.assertEqual(x.returncode,2); self.assertNotIn('Traceback',x.stderr)
    def test_deterministic_and_check(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d); inv=r/'i'; out=r/'o'; inv.write_text(canonical_json(inventory_payload()))
            self.assertEqual(self.run_script(inv,out).returncode,0); first=out.read_bytes(); self.assertEqual(self.run_script(inv,out).returncode,0); self.assertEqual(first,out.read_bytes()); self.assertEqual(self.run_script(inv,out,'--check').returncode,0)
if __name__=='__main__': unittest.main()
