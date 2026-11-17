"""Pure extracted mode/writer ordering tests; no installer import or OS effects."""
import ast
import dataclasses
import hashlib
from pathlib import Path
import stat
import types
import unittest
SOURCE = Path(__file__).resolve().parents[1] / 'scripts/production_installer.py'
@dataclasses.dataclass(frozen=True)
class Node:
    python_identity: tuple
    data: str
    native_proof: object = 'proof'
def fixture(before_mode=0o644, requested=0o600, failure=None, platform='posix'):
    tree = ast.parse(SOURCE.read_text(encoding='utf-8-sig'))
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == '_InstallTransaction')
    owner.body = [n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name in {'_write_owned_file','_chmod_owned','_chmod_identity'}]
    owner.bases, owner.decorator_list = [], []
    module = ast.Module(body=[ast.ImportFrom(module='__future__', names=[ast.alias(name='annotations')], level=0), owner], type_ignores=[])
    trace, records = [], []
    primary = OSError('injected mode boundary')
    initial = Node((1,2,stat.S_IFREG | before_mode,0), hashlib.sha256(b'old').hexdigest())
    state = {'identity': initial.python_identity}
    def identity(path):
        trace.append('identity')
        if failure == 'readback' and 'setter' in trace:
            raise primary
        return state['identity']
    def setter(fd, mode):
        trace.append('setter')
        if failure == 'setter':
            raise primary
        state['identity'] = (1,2,stat.S_IFREG | mode,0)
    fake_os = types.SimpleNamespace(name=platform, SEEK_SET=0, ftruncate=lambda *a: trace.append('truncate'), lseek=lambda *a: 0, write=lambda fd,data: len(data), fchmod=setter)
    fake_stat = types.SimpleNamespace(**{n:getattr(stat,n) for n in dir(stat) if not n.startswith('__')})
    fake_stat.FILE_ATTRIBUTE_READONLY = 1
    class Bound:
        def __init__(self, path):
            self.proof = 'proof'
        def python_metadata(self):
            dev,ino,mode,attributes = state['identity']
            return types.SimpleNamespace(st_dev=dev,st_ino=ino,st_mode=mode,st_file_attributes=attributes)
        def set_readonly(self, value):
            trace.append('setter')
            state['identity'] = tx._chmod_identity(initial.python_identity, requested)
    ns = dict(os=fake_os, stat=fake_stat, hashlib=hashlib, replace=dataclasses.replace, _CreateOnlyMutablePath=types.SimpleNamespace(_identity=identity), _WindowsBoundNode=Bound)
    exec(compile(ast.fix_missing_locations(module),'<owned-mode-only>','exec'),ns)
    tx = ns['_InstallTransaction']()
    def record(path,node):
        trace.append('record')
        records.append(node)
    def invoke():
        return tx._write_owned_file(Path('owned'),19,(b'new',),record,hashlib.sha256(b'new').hexdigest(),initial_state=initial,mode=requested,fsync='none')
    return tx,initial,state,trace,records,primary,invoke
class OwnedFileModeTests(unittest.TestCase):
    def test_successful_setter_is_recorded_before_failed_readback(self):
        tx,initial,state,trace,records,primary,invoke = fixture(failure='readback')
        with self.assertRaises(OSError) as caught:
            invoke()
        self.assertIs(caught.exception,primary)
        self.assertEqual(records[-1].python_identity,state['identity'])
        self.assertEqual(records[-1].data,hashlib.sha256(b'new').hexdigest())
        self.assertEqual(records[-1].native_proof,initial.native_proof)
        self.assertEqual(trace[trace.index('setter'):],['setter','record','identity'])
    def test_failed_setter_does_not_record_projected_mode(self):
        tx,initial,state,trace,records,primary,invoke = fixture(failure='setter')
        with self.assertRaises(OSError) as caught:
            invoke()
        self.assertIs(caught.exception,primary)
        self.assertEqual(records[-1].python_identity,initial.python_identity)
        self.assertEqual(state['identity'],initial.python_identity)
        self.assertEqual(trace[trace.index('setter'):],['setter'])
    def test_success_preserves_final_verification_and_record(self):
        tx,initial,state,trace,records,primary,invoke = fixture()
        result = invoke()
        self.assertEqual(result,records[-1])
        self.assertEqual(result.python_identity,state['identity'])
        self.assertEqual(trace[trace.index('setter'):],['setter','record','identity','record'])
    def test_special_bits_are_not_projected_before_readback(self):
        for before,requested in ((0o2644,0o600),(0o644,0o2600)):
            with self.subTest(before=before,requested=requested):
                tx,initial,state,trace,records,primary,invoke = fixture(before_mode=before,requested=requested,failure='readback')
                with self.assertRaises(OSError) as caught:
                    invoke()
                self.assertIs(caught.exception,primary)
                self.assertEqual(records[-1].python_identity,initial.python_identity)
                self.assertEqual(trace[trace.index('setter'):],['setter','identity'])
    def test_default_helper_call_keeps_existing_contract(self):
        tx,initial,state,trace,records,primary,invoke = fixture()
        result = tx._chmod_owned(Path('owned'),initial.python_identity,0o600,descriptor=19)
        self.assertEqual(result,state['identity'])
        self.assertEqual(trace,['identity','setter','identity'])
        self.assertEqual(records,[])
    def test_windows_helper_does_not_invoke_posix_callback(self):
        tx,initial,state,trace,records,primary,invoke = fixture(platform='nt')
        callbacks = []
        result = tx._chmod_owned(Path('owned'),initial.python_identity,0o600,descriptor=19,native_proof='proof',on_mode_set=callbacks.append)
        self.assertEqual(result,state['identity'])
        self.assertEqual(callbacks,[])
        self.assertEqual(trace,['identity','setter','identity'])
if __name__ == '__main__':
    unittest.main()
