import dataclasses
import unittest
import importlib.util, pathlib, sys
from unittest.mock import patch as _module_patch
with _module_patch.dict(sys.modules):
    _path = pathlib.Path(__file__).resolve().parents[1] / 'scripts/universal-hooks/scripts/transfer_binding.py'
    _spec = importlib.util.spec_from_file_location('_test_transfer_binding', _path)
    _module = importlib.util.module_from_spec(_spec)
    sys.modules[_spec.name] = _module
    _spec.loader.exec_module(_module)
ScopeBinding = _module.ScopeBinding
TransferBinding = _module.TransferBinding


class TransferTests(unittest.TestCase):
 def setUp(self):
  self.scope=ScopeBinding('invocation','sha256:'+'1'*64,'sha1','2'*64,('3'*40,),'fixture-v1')
  self.channel=object();self.binding=TransferBinding(self.scope,channel=self.channel)
  self.wire=('a'*40+' '+'a'*40+' refs/heads/new '+'0'*40+'\n').encode()
  self.commands=[('push '+'a'*40+':refs/heads/new\n').encode()]
 def bind(self):self.binding.bind_hook(self.wire,channel=self.channel,scope_digest=self.scope.digest())
 def consume(self,**kwargs):
  args=dict(channel=self.channel,scope_digest=self.scope.digest(),same_helper_live=True);args.update(kwargs)
  return self.binding.consume_transfer(self.commands,**args)
 def test_exact_one_use(self):
  self.bind();self.assertEqual(self.consume(),self.scope.digest())
  with self.assertRaises(ValueError):self.consume()
 def test_scope_changes_selection_identity(self):
  for name,value in [('invocation','other'),('endpoint_identity','sha256:'+'4'*64),('advertisement_sha256','5'*64),('excluded_roots',()),('route_contract','other')]:
   other=dataclasses.replace(self.scope,**{name:value})
   self.assertNotEqual(other.digest(),self.scope.digest())
   self.assertNotEqual(other.selection_digest({'wire':'same'}),self.scope.selection_digest({'wire':'same'}))
 def test_request_changes_selection(self):
  self.assertNotEqual(self.scope.selection_digest({'wire':'a'}),self.scope.selection_digest({'wire':'b'}))
 def test_changed_oid(self):
  self.bind();self.commands=[self.commands[0].replace(b'a'*40,b'b'*40)]
  with self.assertRaises(ValueError):self.consume()
 def test_changed_ref(self):
  self.bind();self.commands=[self.commands[0].replace(b'/new',b'/other')]
  with self.assertRaises(ValueError):self.consume()
 def test_dead_helper(self):
  self.bind()
  with self.assertRaises(ValueError):self.consume(same_helper_live=False)
 def test_changed_channel(self):
  self.bind()
  with self.assertRaises(ValueError):self.consume(channel=object())
 def test_missing_scope(self):
  self.bind()
  with self.assertRaises(ValueError):self.consume(scope_digest='')
 def test_symbolic_source_refused(self):
  self.wire=self.wire.replace(b'a'*40,b'refs/heads/local',1)
  with self.assertRaises(ValueError):self.bind()
 def test_transfer_before_hook(self):
  with self.assertRaises(ValueError):self.consume()
 def test_second_hook_poison(self):
  self.bind()
  with self.assertRaises(ValueError):self.bind()
  with self.assertRaises(ValueError):self.consume()
 def test_failed_transfer_not_retryable(self):
  self.bind()
  with self.assertRaises(ValueError):self.consume(same_helper_live=False)
  with self.assertRaises(ValueError):self.consume()

 def test_duplicate_destination(self):
  self.wire+=self.wire.replace(b'a'*40,b'b'*40)
  with self.assertRaises(ValueError):self.bind()
 def test_invalid_ref_component(self):
  self.wire=self.wire.replace(b'refs/heads/new',b'refs/heads/.hidden')
  with self.assertRaises(ValueError):self.bind()

 def test_mutable_scope_fields_refused(self):
  for field in ('invocation','route_contract'):
   with self.subTest(field=field),self.assertRaises(ValueError):dataclasses.replace(self.scope,**{field:['mutable']})

if __name__=='__main__':unittest.main()
