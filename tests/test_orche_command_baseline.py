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
               output_parent_is_file:bool=False, semantic_failure_exits:tuple[int,...]=(1,)):
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
                 '--output',str(report_path),
                 *[item for code in semantic_failure_exits for item in ('--semantic-failure-exit',str(code))],
                 *extra_args]
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

    def test_resolved_failure_requires_declared_success_pattern(self):
        r,p=self.invoke(baseline_exit=1,candidate_exit=0,baseline_log='ERROR\n',candidate_log='RESULT: PASS\n')
        self.assertEqual(r.returncode,1); self.assertEqual(p['classification'],'unverified-resolution')

    def test_resolved_failure_passes_with_declared_success_pattern(self):
        r,p=self.invoke(baseline_exit=1,candidate_exit=0,baseline_log='ERROR\n',candidate_log='RESULT: PASS\n',
            extra_args=('--success-pattern',r'(?m)^RESULT: PASS$'))
        self.assertEqual(r.returncode,0,r.stderr); self.assertEqual(p['classification'],'resolved-failure')

    def test_success_pattern_must_match_terminal_diagnostics(self):
        r,p=self.invoke(baseline_exit=1,candidate_exit=0,baseline_log='ERROR\n',
            candidate_log='RESULT: PASS\nWARNING: validation was bypassed\n',
            extra_args=('--success-pattern',r'(?m)^RESULT: PASS$'))
        self.assertEqual(r.returncode,1); self.assertEqual(p['classification'],'unverified-resolution')

    def test_success_pattern_must_match_candidate_diagnostics(self):
        r,p=self.invoke(baseline_exit=1,candidate_exit=0,baseline_log='ERROR\n',candidate_log='validator exited silently\n',
            extra_args=('--success-pattern',r'(?m)^RESULT: PASS$'))
        self.assertEqual(r.returncode,1); self.assertEqual(p['classification'],'unverified-resolution')

    def test_changed_failure_is_rejected(self):
        r,p=self.invoke(baseline_exit=1,candidate_exit=1,baseline_log='ERROR A\n',candidate_log='ERROR B\n')
        self.assertEqual(r.returncode,1); self.assertEqual(p['classification'],'drifted-failure')

    def test_undeclared_exit_code_is_operational(self):
        r,p=self.invoke(baseline_exit=1,candidate_exit=2,baseline_log='ERROR\n',candidate_log='ERROR\n')
        self.assertEqual(r.returncode,1); self.assertEqual(p['classification'],'operational-exit')
        self.assertEqual(p['operationalExit'],{'candidate':2})


    def test_equal_operational_exits_are_rejected(self):
        r,p=self.invoke(baseline_exit=127,candidate_exit=127,baseline_log='',candidate_log='')
        self.assertEqual(r.returncode,1,r.stderr)
        self.assertEqual(p['classification'],'operational-exit')
        self.assertEqual(p['operationalExit']['baseline'],127)
        self.assertEqual(p['operationalExit']['candidate'],127)

    def test_explicit_secondary_semantic_failure_exit_can_be_preserved(self):
        r,p=self.invoke(baseline_exit=2,candidate_exit=2,baseline_log='VALIDATION FAILED\n',candidate_log='VALIDATION FAILED\n',semantic_failure_exits=(1,2))
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(p['classification'],'preserved-failure')
        self.assertEqual(p['policy']['semanticFailureExits'],[1,2])

    def test_invalid_semantic_failure_exit_is_invalid_input(self):
        r,p=self.invoke(baseline_exit=1,candidate_exit=1,baseline_log='ERROR\n',candidate_log='ERROR\n',semantic_failure_exits=(124,))
        self.assertEqual(p,{})
        self.assertEqual(r.returncode,2)
        self.assertIn('semantic failure exit must be between 1 and 123',r.stderr)

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

    def test_invalid_success_pattern_uses_invalid_input_exit(self):
        r,p=self.invoke(baseline_exit=1,candidate_exit=0,baseline_log='ERROR\n',candidate_log='PASS\n',
            extra_args=('--success-pattern','('))
        self.assertEqual(p,{}); self.assertEqual(r.returncode,2); self.assertIn('invalid success pattern',r.stderr)

    def test_report_write_failure_uses_invalid_input_exit(self):
        r,p=self.invoke(baseline_exit=0,candidate_exit=0,baseline_log='PASS\n',candidate_log='PASS\n',output_parent_is_file=True)
        self.assertEqual(p,{}); self.assertEqual(r.returncode,2); self.assertNotIn('Traceback',r.stderr)

if __name__=='__main__': unittest.main()
