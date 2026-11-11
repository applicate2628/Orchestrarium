import os,pathlib,shutil,subprocess,tempfile,unittest
import importlib.util
_path=pathlib.Path(__file__).resolve().parents[1]/'scripts/universal-hooks/scripts/qualifier.py'
_spec=importlib.util.spec_from_file_location('_receiver_qualifier_test',_path)
_module=importlib.util.module_from_spec(_spec)
import sys
from unittest.mock import patch
with patch.dict(sys.modules):
 sys.modules[_spec.name]=_module
 _spec.loader.exec_module(_module)
qualify=_module.qualify
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=pathlib.Path(self.tmp.name);self.git=shutil.which('git')
  self.env={k:v for k,v in os.environ.items() if not k.upper().startswith('GIT_') and k.upper() not in {'HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','CURL_CA_BUNDLE','SSL_CERT_FILE','SSL_CERT_DIR'}}
  self.env.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull)
  self.run_git('init','-q');self.config('remote.origin.url','https://github.com/example/project.git')
 def run_git(self,*a):return subprocess.run([self.git,'-C',str(self.root),*a],env=self.env,check=True,capture_output=True)
 def config(self,k,v):self.run_git('config',k,v)
 def check(self):return qualify(self.git,self.root,'origin',env=self.env,config_args=('-c','http.followRedirects=false'))
 def test_safe(self):
  r=self.check();self.assertTrue(r.eligible,r);self.assertIn(str(self.root/'.git/config'),r.origins)
 def test_redirect_url_override(self):self.config('http.https://github.com/.followRedirects','true');self.assertFalse(self.check().eligible)
 def test_no_disabled_redirect(self):self.assertFalse(qualify(self.git,self.root,'origin',env=self.env).eligible)
 def test_unsupported(self):
  for key,value in [('remote.origin.receivepack','custom'),('remote.origin.vcs','custom'),('remote.origin.proxy','http://proxy'),('http.proxy','http://proxy'),('http.sslVerify','false'),('http.extraHeader','Authorization: SECRET'),('url.https://github.com/.insteadOf','x:'),('extensions.worktreeConfig','true')]:
   with self.subTest(key=key):
    self.config(key,value);r=self.check();self.assertFalse(r.eligible);self.assertNotIn('SECRET',repr(r));self.run_git('config','--unset',key)
 def test_include(self):
  f=self.root/'included';f.write_text('[core]\n bare = false\n');self.config('include.path',str(f));self.assertFalse(self.check().eligible)
 def test_helper_not_executed(self):
  marker=self.root/'EXECUTED';self.config('credential.helper','!touch '+str(marker));self.assertFalse(self.check().eligible);self.assertFalse(marker.exists())
 def test_proxy_and_env(self):
  for key in ('https_proxy','GIT_CONFIG_COUNT','GIT_SSL_NO_VERIFY','GIT_EXEC_PATH'):
   with self.subTest(key=key):
    self.env[key]='1';self.assertFalse(self.check().eligible);del self.env[key]
 def test_bad_endpoint(self):
  for url in ('https://user:SECRET@github.com/a/b','https://github.com:443/a/b','https://github.com/a/b?q=x','https://evil.invalid/a/b'):
   self.config('remote.origin.url',url);r=self.check();self.assertFalse(r.eligible);self.assertNotIn('SECRET',repr(r))
 def test_no_config_mutation(self):
  p=self.root/'.git/config';before=p.read_bytes();self.check();self.assertEqual(before,p.read_bytes())
 def test_multi_url(self):self.run_git('config','--add','remote.origin.url','https://github.com/a/b');self.assertFalse(self.check().eligible)
 def test_recognized_auth(self):
  exe=self.root/'gh.exe';exe.write_bytes(b'fixture-not-executable')
  self.config('http.sslBackend','schannel');self.config('credential.helper','manager')
  self.config('credential.https://github.com.helper','')
  self.run_git('config','--add','credential.https://github.com.helper','!"'+str(exe).replace('\\','/')+'" auth git-credential')
  self.config('credential.https://gist.github.com.helper','!untrusted other')
  r=qualify(self.git,self.root,'origin',env=self.env,config_args=('-c','http.followRedirects=false'),approved_gh=str(exe))
  self.assertTrue(r.eligible,r);self.assertEqual(r.executables,(str(exe),))
 def test_matching_unknown_auth(self):
  self.config('credential.https://github.com.helper','!unknown executable')
  self.assertFalse(self.check().eligible)
if __name__=='__main__':unittest.main()
