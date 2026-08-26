#!/usr/bin/env python3
from __future__ import annotations
import json, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; SCRIPT=ROOT/'scripts'/'baseline'/'compare_pytest_baseline.py'

def junit(cases):
    nodes=[]
    for cls,name,status in cases:
        child={'failure':'<failure message="failed">trace</failure>','error':'<error message="errored">trace</error>','skipped':'<skipped message="skip" />'}.get(status,'')
        nodes.append(f'<testcase classname="{cls}" name="{name}" file="tests/test_x.py">{child}</testcase>')
    return f'<testsuites><testsuite tests="{len(cases)}">{"".join(nodes)}</testsuite></testsuites>'

class PytestBaselineComparatorTests(unittest.TestCase):
    def run_compare(self,b,c,*,baseline_exit=0,candidate_exit=0,output_as_directory=False):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); bp=root/'b.xml'; cp=root/'c.xml'; out=root/'r.json'
            bp.write_text(junit(b)); cp.write_text(junit(c))
            if output_as_directory: out.mkdir()
            r=subprocess.run([sys.executable,str(SCRIPT),'--baseline-junit',str(bp),'--candidate-junit',str(cp),
                '--baseline-exit',str(baseline_exit),'--candidate-exit',str(candidate_exit),
                '--baseline-ref','baseline','--candidate-ref','candidate','--output',str(out)],
                text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
            return r,json.loads(out.read_text()) if out.is_file() else None

    def test_allows_known_failure_resolution_and_new_pass(self):
        r,p=self.run_compare([('S','p','passed'),('S','k','failure'),('S','r','error')],
            [('S','p','passed'),('S','k','failure'),('S','r','passed'),('S','n','passed')],baseline_exit=1,candidate_exit=1)
        self.assertEqual(r.returncode,0,r.stderr); self.assertEqual(p['verdict'],'PASS')

    def test_blocks_new_failure(self):
        r,p=self.run_compare([('S','p','passed')],[('S','p','failure')],candidate_exit=1)
        self.assertEqual(r.returncode,1); self.assertTrue(p['blockers']['newFailures'])

    def test_blocks_operational_exits_even_with_junit_failures(self):
        for code in (2,3,4,5):
            with self.subTest(code=code):
                r,p=self.run_compare([('S','k','failure')],[('S','k','failure')],baseline_exit=code,candidate_exit=code)
                self.assertEqual(r.returncode,1)
                self.assertEqual(p['blockers']['baselineExitContradiction'][0]['reason'],'operational-pytest-exit')
                self.assertEqual(p['blockers']['candidateExitContradiction'][0]['reason'],'operational-pytest-exit')

    def test_blocks_nonzero_without_junit_failure(self):
        r,p=self.run_compare([('S','k','failure')],[('S','k','passed')],baseline_exit=1,candidate_exit=1)
        self.assertEqual(r.returncode,1); self.assertTrue(p['blockers']['candidateExitContradiction'])

    def test_blocks_zero_with_junit_failure(self):
        r,p=self.run_compare([('S','k','failure')],[('S','k','failure')],baseline_exit=1,candidate_exit=0)
        self.assertEqual(r.returncode,1); self.assertTrue(p['blockers']['candidateExitContradiction'])

    def test_blocks_failure_to_error(self):
        r,p=self.run_compare([('S','k','failure')],[('S','k','error')],baseline_exit=1,candidate_exit=1)
        self.assertEqual(r.returncode,1); self.assertTrue(p['blockers']['changedKnownFailureKind'])

    def test_report_write_failure_returns_two(self):
        r,p=self.run_compare([('S','p','passed')],[('S','p','passed')],output_as_directory=True)
        self.assertIsNone(p); self.assertEqual(r.returncode,2); self.assertNotIn('Traceback',r.stderr)

if __name__=='__main__': unittest.main()
