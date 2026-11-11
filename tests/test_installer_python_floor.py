from pathlib import Path
import importlib.util, types, unittest, io
from unittest.mock import Mock
ROOT=Path(__file__).resolve().parents[1]
def load():
 spec=importlib.util.spec_from_file_location("floor",ROOT/"scripts/python_installer_bootstrap.py")
 module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 module.sys=types.SimpleNamespace(version_info=(3,12),executable="current",argv=["entry","two words"],stderr=io.StringIO())
 module.shutil=types.SimpleNamespace(which=Mock(return_value=None))
 module.subprocess=types.SimpleNamespace(run=Mock(side_effect=AssertionError("real subprocess forbidden")),DEVNULL=-3)
 module.os=types.SimpleNamespace(execv=Mock(side_effect=AssertionError("real exec forbidden")))
 module._is_current_executable=lambda value:value=="current"
 return module
class FloorTests(unittest.TestCase):
 def test_unsupported_refuses(self):
  for version in [(3,10),(3,11),(3,12)]:
   with self.subTest(version=version):
    m=load();m.sys.version_info=version
    with self.assertRaises(SystemExit) as e:m.ensure_supported_python("entry")
    self.assertEqual(e.exception.code,2);m.subprocess.run.assert_not_called()
 def test_supported_no_probe(self):
  for version in [(3,13),(3,14),(3,15)]:
   with self.subTest(version=version):
    m=load();m.sys.version_info=version;m.ensure_supported_python("entry")
    m.shutil.which.assert_not_called();m.subprocess.run.assert_not_called()
 def test_probe_matches_floor(self):
  m=load()
  for version in [(3,10),(3,11),(3,12),(3,13),(3,15)]:
   with self.subTest(version=version):
    fake=types.SimpleNamespace(version_info=version)
    with self.assertRaises(SystemExit) as e:exec(m._VERSION_PROBE,{"__builtins__":{"__import__":lambda *args,**kwargs:fake,"SystemExit":SystemExit}})
    self.assertEqual(e.exception.code,0 if version>=(3,13) else 1)
 def test_fallback_preserves_args(self):
  m=load();m.shutil.which.side_effect=["old","new"]
  m.subprocess.run.side_effect=[types.SimpleNamespace(returncode=1),types.SimpleNamespace(returncode=0)]
  class Reexec(Exception):pass
  m.os.execv.side_effect=Reexec
  with self.assertRaises(Reexec):m.ensure_supported_python("entry")
  m.os.execv.assert_called_once_with("new",["new","entry","two words"])
 def test_messages_match(self):
  for path in ["install.sh","scripts/install-codex.sh","scripts/install-claude.sh"]:
   self.assertIn(load().VERSION_FAILURE,(ROOT/path).read_text())
if __name__=="__main__":unittest.main()
