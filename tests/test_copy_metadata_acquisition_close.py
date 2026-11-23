"""Pure acquisition-close contract tests; no installer import or native effects."""
import ast
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/production_installer.py'

class Failure(RuntimeError):
    def __init__(self, stable_id, context, cause, *, members, recovery_path=None, unresolved_paths=()):
        super().__init__(stable_id)
        self.stable_id, self.context, self.cause, self.members = stable_id, context, cause, members
        self.recovery_path, self.unresolved_paths = recovery_path, unresolved_paths

def member(phase, ordinal, path, stable_id, cause, **kw):
    return NS(phase=phase, ordinal=ordinal, path=path, stable_id=stable_id, cause=cause, **kw)

class AcquisitionCloseTests(unittest.TestCase):
    def fixture(self, stage=None, cleanup=None):
        tree = ast.parse(SOURCE.read_text(encoding='utf-8-sig'))
        owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == '_InstallTransaction')
        method = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == '_acquire_copy_metadata')
        path, prior, image = Path('declared-copy'), object(), object()
        p = NS(before=prior, current=prior)
        tx = NS(_copy_metadata={path: p}, _copy_current={path: prior})
        primary = OSError(5, 'acquisition failed')
        metadata = NS(st_dev=1, st_ino=2, st_mode=3)
        actual = NS(st_dev=1, st_ino=9 if stage == 'identity' else 2, st_mode=3)
        close = Mock(side_effect=cleanup)
        os_stub = NS(O_RDONLY=0, O_NOFOLLOW=1, open=Mock(return_value=19), close=close,
            fstat=Mock(side_effect=primary if stage == 'fstat' else None, return_value=actual))
        tx._read_copy_metadata = Mock(side_effect=primary if stage == 'metadata' else None, return_value=image)
        ns = dict(os=os_stub, _InstallFailure=Failure, _RollbackFailureMember=member)
        helper = next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == '_copy_close_failure')
        helper.decorator_list = []
        exec(compile(ast.fix_missing_locations(ast.Module(body=[helper, method], type_ignores=[])), '<acquire-only>', 'exec'), ns)
        ns['_InstallTransaction'] = NS(_copy_close_failure=ns['_copy_close_failure'])
        invoke = lambda: ns[method.name](tx, path, metadata, None, None)
        return invoke, tx, p, path, prior, image, primary, close

    def unchanged(self, tx, p, path, prior):
        self.assertIs(p.before, prior)
        self.assertIs(p.current, prior)
        self.assertEqual(tx._copy_current, {path: prior})

    def test_acquisition_failure_successful_close(self):
        for stage in ('fstat', 'metadata', 'identity'):
            with self.subTest(stage=stage):
                invoke, tx, p, path, prior, image, primary, close = self.fixture(stage)
                with self.assertRaises(ValueError if stage == 'identity' else OSError) as caught:
                    invoke()
                if stage != 'identity':
                    self.assertIs(caught.exception, primary)
                else:
                    self.assertIn('copy metadata acquisition', str(caught.exception))
                close.assert_called_once_with(19)
                self.unchanged(tx, p, path, prior)

    def test_acquisition_failure_failed_close(self):
        for stage in ('fstat', 'metadata', 'identity'):
            with self.subTest(stage=stage):
                cleanup = OSError(5, 'close failed')
                invoke, tx, p, path, prior, image, primary, close = self.fixture(stage, cleanup)
                with self.assertRaises(Failure) as caught:
                    invoke()
                failure = caught.exception
                if stage != 'identity':
                    self.assertIs(failure.cause, primary)
                else:
                    self.assertIsInstance(failure.cause, ValueError)
                    self.assertIn('copy metadata acquisition', str(failure.cause))
                self.assertIs(failure.__cause__, failure.cause)
                self.assertEqual((failure.stable_id, failure.context), ('E_ROLLBACK_SETTLEMENT_FAILED', 'copy-metadata-close'))
                self.assertEqual(len(failure.members), 1)
                detail = failure.members[0]
                self.assertEqual((detail.phase, detail.ordinal, detail.path, detail.participant), ('backup', -1, str(path), 'backup'))
                self.assertEqual(detail.stable_id, 'E_ROLLBACK_BACKUP_CLEANUP_FAILED')
                self.assertIs(detail.cause_exception, cleanup)
                close.assert_called_once_with(19)
                self.unchanged(tx, p, path, prior)

    def test_successful_acquisition_failed_close(self):
        cleanup = OSError(5, 'close failed')
        invoke, tx, p, path, prior, image, primary, close = self.fixture(cleanup=cleanup)
        with self.assertRaises(Failure) as caught:
            invoke()
        self.assertIs(caught.exception.cause, cleanup)
        self.assertIs(caught.exception.members[0].cause_exception, cleanup)
        self.assertIsNone(caught.exception.__cause__)
        close.assert_called_once_with(19)
        self.unchanged(tx, p, path, prior)

    def test_success_publishes_only_after_close(self):
        invoke, tx, p, path, prior, image, primary, close = self.fixture()
        close.side_effect = lambda fd: self.unchanged(tx, p, path, prior)
        invoke()
        close.assert_called_once_with(19)
        self.assertIs(p.before, image)
        self.assertIs(p.current, image)
        self.assertIs(tx._copy_current[path], image)

if __name__ == '__main__':
    unittest.main()
