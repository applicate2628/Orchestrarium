#!/usr/bin/env python3
"""Tests for the generic Stage 0 command differential gate."""
from __future__ import annotations
import json, subprocess, sys, tempfile, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'scripts'/'baseline'/'compare_command_baseline.py'

class CommandBaselineTests(unittest.TestCase):
    def invoke(self, *, baseline_exit:int, candidate_exit:int, baseline_log:str|bytes,
               candidate_log:str|bytes, baseline_root:str='/tmp/baseline',
               candidate_root:str='/tmp/candidate', extra_args:tuple[str,...]=(),
               output_parent_is_file:bool=False):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); baseline_path=root/'baseline.log'; candidate_path=root/'candidate.log'
            if output_parent_is_file:
                blocker=root/'not-a-directory'; blocker.write_text('blocked\n'); report_path=blocker/'report.json'
            else: report_path=root/'report.json'
            baseline_path.write_bytes(baseline_log if isinstance(baseline_log,bytes) else baseline_log.encode())
            candidate_path.write_bytes(candidate_log if isinstance(candidate_log,bytes) else candidate_log.encode())
            cmd=[sys.executable,str(SCRIPT),'--name','validator','--baseline-exit',str(baseline_exit),
                 '--candidate-exit',str(candidate_exit),'--baseline-log',str(baseline_path),
                 '--candidate-log',str(candidate_path),'--baseline-root',baseline_root,
                 '--candidate-root',candidate_root,'--baseline-ref','a'*40,'--candidate-ref','b'*40,
                 '--output',str(report_path),*extra_args]
            result=subprocess.run(cmd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
            report=json.loads(report_path.read_text()) if report_path.is_file() else {}
            return result,report

    def test_two_identical_successes_pass(self):
        r,p=self.invoke(baseline_exit=0,candidate_exit=0,baseline_log='RESULT: PASS\n',candidate_log='RESULT: PASS\n')
        self.assertEqual(r.returncode,0,r.stderr); self.assertEqual(p['classification'],'preserved-success')

    def test_changed_success_diagnostics_are_rejected(self):
        r,p=self.invoke(baseline_exit=0,candidate_exit=0,baseline_log='RESULT: PASS checks=8\n',candidate_log='RESULT: PASS checks=7\nWARNING: skipped check\n')
        self.assertEqual(r.returncode,1); self.assertEqual(p['classification'],'drifted-success')
        self.assertNotEqual(p['baseline']['normalizedSha256'],p['candidate']['normalizedSha256'])

    def test_new_candidate_failure_is_rejected(self):
        r,p=self.invoke(baseline_exit=0,candidate_exit=1,baseline_log='RESULT: PASS\n',candidate_log='ERROR\n')
        self.assertEqual(r.returncode,1); self.assertEqual(p['classification'],'new-failure')

    def test_identical_normalized_failure_is_characterized(self):
        r,p=self.invoke(baseline_exit=1,candidate_exit=1,
            baseline_log='/tmp/baseline/failure '+ 'a'*40+'\r\n',candidate_log='/tmp/candidate/failure '+'b'*40+'\n')
        self.assertEqual(r.returncode,0,r.stderr); self.assertEqual(p['classification'],'preserved-failure')

    def test_resolved_failure_passes(self):
        r,p=self.invoke(baseline_exit=1,candidate_exit=0,baseline_log='ERROR\n',candidate_log='RESULT: PASS\n')
        self.assertEqual(r.returncode,0); self.assertEqual(p['classification'],'resolved-failure')

    def test_changed_failure_is_rejected(self):
        r,p=self.invoke(baseline_exit=1,candidate_exit=1,baseline_log='ERROR A\n',candidate_log='ERROR B\n')
        self.assertEqual(r.returncode,1); self.assertEqual(p['classification'],'drifted-failure')

    def test_exit_code_drift_is_rejected(self):
        r,p=self.invoke(baseline_exit=1,candidate_exit=2,baseline_log='ERROR\n',candidate_log='ERROR\n')
        self.assertEqual(r.returncode,1); self.assertEqual(p['classification'],'drifted-failure')

    def test_distinct_invalid_utf8_is_not_collapsed(self):
        r,p=self.invoke(baseline_exit=1,candidate_exit=1,baseline_log=b'X\xff\n',candidate_log=b'X\xfe\n')
        self.assertEqual(r.returncode,1); self.assertEqual(p['classification'],'drifted-failure')

    def test_declared_uuid_path_is_normalized(self):
        pattern=r'agents-mode-installer-regression[/\\][0-9a-f]{32}'
        r,p=self.invoke(baseline_exit=1,candidate_exit=1,
            baseline_log='/tmp/baseline/agents-mode-installer-regression/'+'a'*32+'/x\n',
            candidate_log='/tmp/candidate/agents-mode-installer-regression/'+'b'*32+'/x\n',
            extra_args=('--volatile-pattern',pattern))
        self.assertEqual(r.returncode,0,r.stderr); self.assertEqual(p['classification'],'preserved-failure')

    def test_report_write_failure_uses_invalid_input_exit(self):
        r,p=self.invoke(baseline_exit=0,candidate_exit=0,baseline_log='PASS\n',candidate_log='PASS\n',output_parent_is_file=True)
        self.assertEqual(p,{}); self.assertEqual(r.returncode,2); self.assertNotIn('Traceback',r.stderr)

if __name__=='__main__': unittest.main()
