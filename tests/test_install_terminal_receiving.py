"""Actual public try/except/finally tail with inert transaction/cleanup participants."""
import ast
import contextlib
import dataclasses
import errno
import hashlib
import re
import types
import io
import os
from pathlib import Path
import sys
import traceback
from types import SimpleNamespace
import unittest
ROOT=Path(__file__).resolve().parents[1]
SOURCE=Path(os.environ.get('TERMINAL_TEST_SOURCE',ROOT/'scripts/production_installer.py'))

class TerminalTests(unittest.TestCase):
    def run_tail(self, *, primary=None, cleanup=None, compatibility=None, dry=False, global_install=False, exit_error=None, real_formatter=False, stderr=None):
        tree=ast.parse(SOURCE.read_bytes())
        install=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='install')
        outer=next(n for n in install.body if isinstance(n,ast.Try))
        at=next(i for i,n in enumerate(outer.body) if isinstance(n,ast.If) and
                '_install_codex_legacy_skill_compatibility' in ast.unparse(n))
        if at and isinstance(outer.body[at-1],ast.Assign) and ast.unparse(outer.body[at-1]).startswith('applied ='):
            at-=1
        outer.body=ast.parse('with transaction:\n    transaction_body()\n    transaction.commit()').body+outer.body[at:]
        final=install.body[install.body.index(outer)+1:]
        init=ast.parse('primary = cleanup_error = None\napplied = False').body
        fn=ast.FunctionDef(name='tail',args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),body=init+[outer]+final,decorator_list=[])
        helpers=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('_finish_install_result','_passive_owner_storage')]
        self.events=[]
        def tx():
            self.events.append('transaction-exit')
            if primary is not None:raise primary
        def compat(*a,**kw):
            self.events.append('compatibility')
            if compatibility is not None:raise compatibility
        def discard(*a,**kw):
            self.events.append('cleanup')
            if cleanup is not None:raise cleanup
        tx_class=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='_InstallTransaction')
        methods=[n for n in tx_class.body if isinstance(n,ast.FunctionDef) and n.name in ('commit','__exit__')]
        txscope={}
        exec(compile(ast.Module(body=methods,type_ignores=[]),'actual-transaction-methods','exec'),txscope)
        class Tx:
            committed=False
            enabled=True
            _temporary=object()
            commit=txscope['commit']
            def __enter__(self):return self
            def __exit__(self,*args):
                if self.committed and exit_error is not None:
                    return txscope['__exit__'](self,*args)
                return False
            def _commit_migrated(self):raise exit_error
        scope={'transaction':Tx(),'sys':sys,'args':SimpleNamespace(dry_run=dry),'provider':'codex',
               'mode':'global' if global_install else 'project','target':'target','home':'home','root':'root',
               'canonical_plan':object(),'canonical_skills_target':'skills','legacy_codex_skill_migrations':(),
               'transaction_body':tx,'_install_codex_legacy_skill_compatibility':compat,
               '_discard_canonical_skills_plan':discard,'_installer_failure_text':lambda e:type(e).__name__}
        if real_formatter:
            names={'_InstallFailure','_RollbackFailureMember','_CopySetterDiagnostic',
                   '_passive_owner_storage','_store_copy_setter_detail','_copy_setter_detail',
                   '_copy_setter_operation_errors','_merge_copy_setter_operation_errors',
                   '_retain_copy_setter_operation_errors','_installer_failure_text'}
            declarations=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name in names]
            self.assertEqual({n.name for n in declarations},names)
            declarations += [n for n in tree.body if isinstance(n,ast.Assign) and any(
                isinstance(t,ast.Name) and t.id=='SLICE_A_FAILURE_IDS' for t in n.targets)]
            module=types.ModuleType('_terminal_real_diagnostics')
            module.__dict__.update(dataclass=dataclasses.dataclass,field=dataclasses.field,
                                   errno=errno,hashlib=hashlib,Path=Path,re=re)
            sys.modules[module.__name__]=module
            future=ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0)
            try:
                exec(compile(ast.fix_missing_locations(ast.Module(body=[future]+declarations,type_ignores=[])),
                             'real-diagnostics','exec'),module.__dict__)
                scope['_installer_failure_text']=module._installer_failure_text
            finally:
                del sys.modules[module.__name__]
        exec(compile(ast.fix_missing_locations(ast.Module(body=helpers+[fn],type_ignores=[])),'public-tail','exec'),scope)
        self.out=io.StringIO();self.err=stderr if stderr is not None else io.StringIO()
        with contextlib.redirect_stdout(self.out),contextlib.redirect_stderr(self.err):return scope['tail']()
    def test_real_sanitizer_primary_cleanup_private_text(self):
        primary=ValueError('PRIVATE_PRIMARY_SENTINEL');cleanup=OSError(13,'PRIVATE_CLEANUP_SENTINEL')
        self.assertEqual(self.run_tail(global_install=True,compatibility=primary,cleanup=cleanup,real_formatter=True),1)
        text=self.out.getvalue()+self.err.getvalue()
        self.assertNotIn('PRIVATE_',text)
        self.assertIn('installation applied',text)
        self.assertIn('failure-id=',text)
        self.assertIn('staging cleanup:',text)
    def test_zero_systemexit_preserved_with_postcommit_warning(self):
        error=SystemExit(0)
        with self.assertRaises(SystemExit) as got:self.run_tail(cleanup=error,real_formatter=True)
        self.assertIs(got.exception,error);self.assertEqual(got.exception.code,0)
        self.assertEqual(self.out.getvalue(),'')
        self.assertIn('installation applied',self.err.getvalue())
        self.assertIn('Do not retry blindly.',self.err.getvalue())
    def test_primary_postcommit_interrupt_reports_applied_without_private_text(self):
        for factory in (KeyboardInterrupt, SystemExit, AssertionError):
            with self.subTest(exception=factory.__name__):
                primary=factory('PRIVATE_INTERRUPT_SENTINEL')
                with self.assertRaises(factory) as got:
                    self.run_tail(global_install=True,compatibility=primary,real_formatter=True)
                self.assertIs(got.exception,primary)
                self.assertIn('installation applied',self.err.getvalue())
                self.assertIn('Do not retry blindly.',self.err.getvalue())
                self.assertNotIn('PRIVATE_',self.out.getvalue()+self.err.getvalue())
                self.assertEqual(self.out.getvalue(),'')
    def test_committed_exit_interrupt_reports_potentially_applied(self):
        primary=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt) as got:self.run_tail(exit_error=primary)
        self.assertIs(got.exception,primary)
        self.assertIn('transaction commit requested',self.err.getvalue())
        self.assertIn('Installation may be applied',self.err.getvalue())
        self.assertNotIn('installation applied;',self.err.getvalue())
        self.assertEqual(self.out.getvalue(),'')
    def test_precommit_and_dry_run_interrupt_do_not_claim_applied(self):
        for kwargs in ({'primary':SystemExit(0)}, {'dry':True,'cleanup':SystemExit(0)}):
            with self.subTest(kwargs=tuple(kwargs)):
                with self.assertRaises(SystemExit):self.run_tail(**kwargs)
                self.assertEqual(self.out.getvalue(),'')
                self.assertEqual(self.err.getvalue(),'')
    def test_postcommit_warning_failure_retains_original_interrupt_and_errors(self):
        class BrokenStderr:
            def __init__(self,error):self.error=error;self.calls=0
            def write(self,text):self.calls+=1;raise self.error
        for write_error in (OSError('PRIVATE_WRITE'),KeyboardInterrupt(),SystemExit(0)):
            with self.subTest(write_error=type(write_error).__name__):
                original=RuntimeError('PRIVATE_CAUSE')
                primary=KeyboardInterrupt();primary.__cause__=original
                secondary=ValueError('PRIVATE_SECONDARY')
                stream=BrokenStderr(write_error)
                with self.assertRaises(KeyboardInterrupt) as got:
                    self.run_tail(global_install=True,compatibility=primary,cleanup=secondary,stderr=stream)
                self.assertIs(got.exception,primary)
                self.assertIs(primary.__cause__,original)
                self.assertEqual(primary._installer_terminal_errors,(secondary,write_error))
                self.assertEqual(stream.calls,1)
                self.assertEqual(self.out.getvalue(),'')
    def test_cleanup_interrupt_warning_failure_does_not_expose_handled_primary(self):
        primary=ValueError('PRIVATE_PRIMARY')
        interruption=SystemExit(0)
        write_error=OSError('PRIVATE_WRITE')
        class BrokenStderr:
            def write(self,text):raise write_error
        with self.assertRaises(SystemExit) as got:
            self.run_tail(global_install=True,compatibility=primary,cleanup=interruption,stderr=BrokenStderr())
        self.assertIs(got.exception,interruption)
        self.assertEqual(interruption.code,0)
        self.assertEqual(interruption._installer_terminal_errors,(primary,write_error))
        self.assertNotIn('PRIVATE_', ''.join(traceback.format_exception(interruption)))
        self.assertEqual(self.out.getvalue(),'')
    def test_cleanup_failure_has_no_false_success(self):
        self.assertEqual(self.run_tail(cleanup=OSError('secret')),1)
        self.assertEqual(self.out.getvalue(),'');self.assertIn('installation applied',self.err.getvalue())
        self.assertNotIn('secret',self.err.getvalue())
    def test_ordinary_success_unchanged(self):
        self.assertEqual(self.run_tail(),0);self.assertEqual(self.out.getvalue(),'RESULT: OK - Codex pack installed to target\n')
        self.assertEqual(self.events,['transaction-exit','cleanup'])
    def test_dry_run(self):
        self.assertEqual(self.run_tail(dry=True),0);self.assertIn('DRY-RUN complete',self.out.getvalue())
        self.assertEqual(self.run_tail(dry=True,cleanup=OSError()),1);self.assertNotIn('installation applied',self.err.getvalue())
    def test_transaction_failure_not_claimed_applied(self):
        self.assertEqual(self.run_tail(primary=ValueError(),cleanup=OSError()),1)
        self.assertNotIn('installation applied',self.err.getvalue());self.assertIn('ValueError',self.err.getvalue());self.assertIn('OSError',self.err.getvalue())
    def test_global_failure_after_commit(self):
        self.assertEqual(self.run_tail(global_install=True,compatibility=ValueError(),cleanup=OSError()),1)
        self.assertIn('installation applied',self.err.getvalue());self.assertEqual(self.events,['transaction-exit','compatibility','cleanup'])
    def test_primary_interrupt_preserved(self):
        primary=KeyboardInterrupt();secondary=OSError()
        with self.assertRaises(KeyboardInterrupt) as got:self.run_tail(primary=primary,cleanup=secondary)
        self.assertIs(got.exception,primary);self.assertIsNone(primary.__cause__)
        self.assertIs(primary._installer_terminal_errors[0],secondary)
        self.assertEqual(self.out.getvalue(),'')
    def test_existing_primary_cause_survives(self):
        original=RuntimeError('original');primary=KeyboardInterrupt();primary.__cause__=original
        secondary=OSError('secondary')
        with self.assertRaises(KeyboardInterrupt) as got:self.run_tail(primary=primary,cleanup=secondary)
        self.assertIs(got.exception.__cause__,original)
        self.assertIs(got.exception._installer_terminal_errors[0],secondary)
    def test_handled_primary_cleanup_interrupt_privacy(self):
        for error in (KeyboardInterrupt(),SystemExit(4)):
            primary=ValueError('PRIVATE_SENTINEL')
            with self.assertRaises(type(error)) as got:self.run_tail(primary=primary,cleanup=error)
            self.assertIs(got.exception,error)
            self.assertIs(error._installer_terminal_errors[0],primary)
            text=''.join(traceback.format_exception(error))
            self.assertNotIn('PRIVATE_SENTINEL',text)
            self.assertEqual(self.out.getvalue(),'')
    def test_real_committed_exit_failure_not_precommit(self):
        self.assertEqual(self.run_tail(exit_error=OSError('settlement')),1)
        self.assertIn('transaction commit requested',self.err.getvalue())
        self.assertIn('Installation may be applied',self.err.getvalue())
        self.assertEqual(self.out.getvalue(),'')
    def test_cleanup_interrupt_never_success(self):
        e=SystemExit(3)
        with self.assertRaises(SystemExit) as got:self.run_tail(cleanup=e)
        self.assertIs(got.exception,e);self.assertEqual(self.out.getvalue(),'')
    def test_strict_cleanup_same_call_no_extra_effects(self):
        tree=ast.parse(SOURCE.read_bytes())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef)and n.name=='_discard_canonical_skills_plan')
        calls=[];scope={'_CanonicalSkillsPlan':object,'shutil':SimpleNamespace(rmtree=lambda *a,**kw:calls.append((a,kw)))}
        exec(compile(ast.Module(body=[fn],type_ignores=[]),'cleanup','exec'),scope)
        plan=SimpleNamespace(stage=SimpleNamespace(path='stage'))
        scope[fn.name](plan);scope[fn.name](plan,strict=True)
        self.assertEqual(calls,[(('stage',),{'ignore_errors':True}),(('stage',),{'ignore_errors':False})])

if __name__=='__main__':unittest.main()
