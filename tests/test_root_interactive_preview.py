"""Interactive preview policy, with inert provider runners."""
import argparse
import ast
import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
ROOT=Path(__file__).resolve().parents[1]
class InteractivePreviewTests(unittest.TestCase):
    def run_case(self, answers, exits=(), args=()):
        tree=ast.parse((ROOT/'install.py').read_bytes())
        nodes=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('main','_run_selected')]
        run=Mock(side_effect=exits); reader=Mock(side_effect=answers)
        scope={'sys':sys,'argparse':argparse,'CLIENTS':{'codex':{},'claude':{}},'input':reader,'_run_production':run}
        exec(compile(ast.Module(body=nodes,type_ignores=[]),'install.py','exec'),scope)
        out,err=io.StringIO(),io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            try:rc=scope['main'](list(args))
            except BaseException as e:rc=e
        return rc,[c.args for c in run.call_args_list],out.getvalue()+err.getvalue(),reader.call_count
    def test_empty_and_quit_do_nothing(self):
        for answer in ('','q',' Q '):
            with self.subTest(answer=answer):
                rc,calls,_,_=self.run_case([answer])
                self.assertEqual((rc,calls),(0,[]))
    def test_preview_both_before_confirmed_apply(self):
        rc,calls,_,reads=self.run_case(['3','yes'],(0,0,0,0),('--target','project space'))
        self.assertEqual(rc,0);self.assertEqual(reads,2)
        self.assertEqual(calls,[(p,['--target','project space','--dry-run']) for p in ('codex','claude')]+[(p,['--target','project space']) for p in ('codex','claude')])
    def test_declined_apply_is_not_started(self):
        for answer in ('','n','maybe'):
            rc,calls,_,_=self.run_case(['1',answer],(0,))
            self.assertEqual((rc,calls),(0,[('codex',['--dry-run'])]))
    def test_preview_failure_never_prompts_apply(self):
        rc,calls,_,reads=self.run_case(['3'],(0,9))
        self.assertEqual((rc,reads),(9,1));self.assertEqual(len(calls),2)
        self.assertTrue(all('--dry-run' in c[1] for c in calls))
    def test_preview_only_and_help_never_apply(self):
        for flag in ('--dry-run','-DryRun','--help','-h'):
            rc,calls,_,reads=self.run_case(['2'],(0,),(flag,))
            self.assertEqual((rc,reads,calls),(0,1,[('claude',[flag])]))
    def test_confirmation_eof_or_interrupt_cancels(self):
        for e in (EOFError(),KeyboardInterrupt()):
            rc,calls,_,_=self.run_case(['1',e],(0,))
            self.assertEqual(rc,130);self.assertEqual(len(calls),1)
    def test_apply_failure_keeps_partial_outcome(self):
        rc,calls,out,_=self.run_case(['3','y'],(0,0,0,7))
        self.assertEqual(rc,7);self.assertEqual(len(calls),4)
        self.assertIn('Earlier completed calls were not rolled back',out)
    def test_installer_interrupt_not_misreported_as_cancel(self):
        error=KeyboardInterrupt()
        rc,calls,out,_=self.run_case(['1'],(error,))
        self.assertIs(rc,error);self.assertIn('outcome unavailable',out)
        self.assertNotIn('Cancelled',out)
if __name__=='__main__':unittest.main()
