import unittest
from dataclasses import replace
from unittest.mock import patch
import importlib.util, pathlib, sys
from unittest.mock import patch as _module_patch
with _module_patch.dict(sys.modules):
    _path = pathlib.Path(__file__).resolve().parents[1] / 'scripts/universal-hooks/scripts/receiver_scope.py'
    _spec = importlib.util.spec_from_file_location('_test_receiver_scope', _path)
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = _module
    _spec.loader.exec_module(_module)
Invocation = _module.Invocation
ReceiverScope = _module.ReceiverScope

A='a'*40;B='b'*40
class Scope(unittest.TestCase):
 def setUp(self):
  self.channel=object();self.inv=Invocation(b'nonce','https://github.com/owner/repo.git',b'helper-sha256',(17,234))
 def scope(self,qualified=True):return ReceiverScope(self.inv,owned_channel=self.channel,qualified_route=qualified)
 def capture(self,s,lines=None,**kw):return s.capture(lines or [(A+' refs/heads/main\n').encode(),b'\n'],channel=kw.get('channel',self.channel),invocation=kw.get('invocation',self.inv))
 def consume(self,s,**kw):return s.consume(channel=kw.get('channel',self.channel),invocation=kw.get('invocation',self.inv),local_object_exists=kw.get('exists',lambda x:True))
 def test_complete_owned_capture(self):
  s=self.scope();self.assertTrue(self.capture(s));self.assertEqual(self.consume(s),frozenset([A]));self.assertIsNone(self.consume(s))
 def test_custom_receiver_route_falls_back(self):
  s=self.scope(False);self.assertFalse(self.capture(s));self.assertIsNone(self.consume(s))
 def test_hook_trace_or_other_channel_cannot_supply_roots(self):
  s=self.scope();self.assertFalse(self.capture(s,channel=object()));self.assertIsNone(self.consume(s))
 def test_invocation_binding(self):
  for field,value in [('nonce',b'other'),('endpoint','https://github.com/other/repo.git'),('helper_identity',b'other'),('git_process_identity',(17,235))]:
   with self.subTest(field=field):
    s=self.scope();self.assertFalse(self.capture(s,invocation=replace(self.inv,**{field:value})));self.assertIsNone(self.consume(s))
 def test_changed_or_replayed_advertisement_falls_back(self):
  s=self.scope();self.assertTrue(self.capture(s));self.assertFalse(self.capture(s,[(B+' refs/heads/main\n').encode(),b'\n']));self.assertIsNone(self.consume(s))
 def test_remote_ref_deletion_after_snapshot_does_not_mutate_capture(self):
  rows=[(A+' refs/heads/main\n').encode(),b'\n'];s=self.scope();self.assertTrue(self.capture(s,rows));rows[:]=[b'\n'];self.assertEqual(self.consume(s),frozenset([A]))
 def test_missing_local_root_not_guessed(self):
  s=self.scope();self.capture(s);self.assertEqual(self.consume(s,exists=lambda _:False),frozenset())
 def test_incomplete_malformed_duplicate_or_mixed_width(self):
  bad=[[(A+' refs/heads/main\n').encode()],[(A+' refs/heads/main\n').encode()]*2+[b'\n'],[b'@refs/heads/main HEAD\n',b'\n'],[(A+' refs/heads/main\n').encode(),('b'*64+' refs/heads/other\n').encode(),b'\n'],[b'\n',b'garbage\n'],[(A+' refs/heads/../main\n').encode(),b'\n']]
  for lines in bad:
   with self.subTest(lines=lines):
    s=self.scope();self.assertFalse(self.capture(s,lines));self.assertIsNone(self.consume(s))
 def test_exact_lf_framing_and_git_component_rules(self):
  for suffix in ('refs/heads/main\n\n','refs/.hidden/main\n','refs/heads/a.lock/x\n','refs/heads//main\n'):
   s=self.scope();self.assertFalse(self.capture(s,[(A+' '+suffix).encode(),b'\n']));self.assertIsNone(self.consume(s))
 def test_bounded_row_count_line_bytes_and_total_bytes(self):
  cases=[('MAX_ROWS',1,[(A+' refs/heads/main\n').encode(),b'\n']),('MAX_LINE_BYTES',10,[(A+' refs/heads/main\n').encode(),b'\n']),('MAX_TOTAL_BYTES',60,[(A+' refs/heads/main\n').encode(),(B+' refs/heads/other\n').encode(),b'\n'])]
  for key,value,rows in cases:
   with self.subTest(key=key),patch.object(_module,key,value):
    s=self.scope();self.assertFalse(self.capture(s,rows));self.assertIsNone(self.consume(s))
 def test_official_helper_object_format_header(self):
  s=self.scope();self.assertTrue(self.capture(s,[b':object-format sha1\n',(A+' refs/heads/main\n').encode(),b'\n']));self.assertEqual(self.consume(s),frozenset([A]))
  for rows in [[b':object-format sha256\n',(A+' refs/heads/main\n').encode(),b'\n'],[b':object-format sha1\n',b':object-format sha1\n',b'\n'],[(A+' refs/heads/main\n').encode(),b':object-format sha1\n',b'\n']]:
   s=self.scope();self.assertFalse(self.capture(s,rows));self.assertIsNone(self.consume(s))
if __name__=='__main__':unittest.main()
