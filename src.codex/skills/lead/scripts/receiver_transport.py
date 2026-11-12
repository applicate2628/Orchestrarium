"""Qualified target-local receiver owner. Existing native hooks are not edited.

Trusted owner/runtime model. Unknown route returns None BEFORE Git launch;
errors after admission refuse rather than replay the transfer.
"""
import hashlib,json,os,pathlib,subprocess,sys,tempfile,time,shlex
from urllib.parse import urlsplit
from bounded_pipe import Broker
from windows_identity import PinnedFile,ProcessWitness,SameHelperLifecycle,pipe_process,canonical
from transfer_binding import ScopeBinding,TransferBinding
from receiver_scope import Invocation,ReceiverScope
from qualifier import qualify
GIT=r'C:\Program Files\Git\ucrt64\bin\git.exe'
HELPER=r'C:\Program Files\Git\ucrt64\libexec\git-core\git-remote-https.exe'
NATIVE_CALLBACK = r'''import ctypes,json,os,sys,shlex
from multiprocessing.connection import Client
from pathlib import Path
sys.path.insert(0,os.environ['ORCHE_TRANSPORT_SOURCE'])
from windows_identity import ProcessWitness,signature,K,W,checked,canonical
server_pid=signature(K,'GetNamedPipeServerProcessId',[W.HANDLE,ctypes.POINTER(W.ULONG)],W.BOOL)
held=[]
try:
 me=ProcessWitness(os.getpid());held.append(me)
 shell=ProcessWitness(me.parent);held.append(shell)
 git=ProcessWitness(shell.parent);held.append(git)
 owner=ProcessWitness(git.parent);held.append(owner)
 if owner.pid!=int(os.environ['ORCHE_OWNER_PID']):raise ValueError('owner parent')
 if not (me.child_of(shell) and shell.child_of(git) and git.child_of(owner)):raise ValueError('owner chain')
 if canonical(git.image)!=canonical(r'C:\Program Files\Git\ucrt64\bin\git.exe') or canonical(owner.image)!=canonical(sys.executable):raise ValueError('owner images')
 if len(owner.argv)<3 or owner.argv[2]!='--target-local-push':raise ValueError('owner entry')
 if canonical(owner.argv[1])!=canonical(os.environ['ORCHE_GATE_ENTRY']):raise ValueError('owner source')
 c=Client(os.environ['ORCHE_RECEIVER_PIPE'],family='AF_PIPE',authkey=None)
 pid=W.ULONG();checked(server_pid(c.fileno(),ctypes.byref(pid)))
 if pid.value!=owner.pid or not owner.live():raise ValueError('pipe owner')
 wire=sys.stdin.buffer.read(4*1024*1024+1)
 if len(wire)>4*1024*1024:raise ValueError('wire cap')
 c.send_bytes(json.dumps({'role':'hook','wire':wire.decode('ascii')}).encode())
 if not c.poll(3660):raise TimeoutError('owner response')
 answer=json.loads(c.recv_bytes(4*1024*1024));c.close()
 if not owner.live() or answer!={'ok':True}:raise ValueError('owner refused')
finally:
 for witness in reversed(held):witness.close()
'''

def run_target(gate,source,remote,tip,destination,*,dry_run=False):
 source=pathlib.Path(source)
 env=dict(os.environ)
 preliminary=qualify(GIT,source,remote,env=env,config_args=('-c','http.followRedirects=false'),approved_gh=r'C:\Program Files\GitHub CLI\gh.exe')
 if not preliminary.eligible:return None
 endpoint=subprocess.check_output([GIT,'-C',str(source),'remote','get-url','--push',remote],env=env).decode().strip()
 # All runtime scratch belongs to Orche, never the user's project root.
 root=pathlib.Path(os.environ['LOCALAPPDATA'])/'Orche'/'workspaces'/'receiver-owner';root.mkdir(parents=True,exist_ok=True)
 base=pathlib.Path(tempfile.mkdtemp(prefix='push-',dir=root))
 pipe=r'\\.\pipe\orche-transfer-'+os.urandom(12).hex();broker=Broker(pipe,deadline=time.monotonic()+gate.SCAN_TIMEOUT_SECONDS+120)
 helperdir=base/'helpers';helperdir.mkdir();payload=helperdir/'relay.py';launcher=helperdir/'git-remote-orche-receiver'
 payload.write_text('''import json,os,re,subprocess,sys
from multiprocessing.connection import Client
assert sys.argv[2]==ENDPOINT
def call(obj):
 c=Client(os.environ['ORCHE_RECEIVER_PIPE'],family='AF_PIPE',authkey=None);c.send_bytes(json.dumps(obj).encode());assert c.poll(3660);r=json.loads(c.recv_bytes(4*1024*1024));c.close();assert r=={'ok':True}
p=subprocess.Popen([HELPER,sys.argv[1],sys.argv[2]],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
def send(s):p.stdin.write(s.encode());p.stdin.flush()
def emit(b):sys.stdout.buffer.write(b);sys.stdout.buffer.flush()
try:
 for cmd in sys.stdin:
  if cmd=='\\n':break
  if cmd.startswith('push '):
   batch=[cmd]
   for row in sys.stdin:
    if row=='\\n':break
    if len(row)>4096 or len(batch)>=100000:raise ValueError('push batch bound')
    batch.append(row)
   call({'role':'transfer','commands':batch,'pid':p.pid})
   for row in batch:send(row)
   send('\\n')
  else:
   if cmd not in ('capabilities\\n','list for-push\\n','stateless-connect git-receive-pack\\n') and not re.fullmatch(r'option (?:progress (?:true|false)|verbosity [0-5]|object-format true|dry-run true)\\n',cmd):raise ValueError('unsupported route command: '+repr(cmd))
   send(cmd)
  if cmd.startswith(('option ','stateless-connect ')):
   row=p.stdout.readline()
   if cmd.startswith('stateless-connect ') and row!=b'fallback\\n':raise ValueError('unqualified protocol takeover')
   emit(row);continue
  rows=[];total=0
  while True:
   row=p.stdout.readline(4097)
   total+=len(row)
   if not row or len(row)>4096 or total>32*1024*1024 or len(rows)>=100000:raise ValueError('helper response')
   rows.append(row)
   if row==b'\\n':break
  if cmd=='list for-push\\n':
   call({'role':'advertisement','rows':[r.decode() for r in rows],'pid':p.pid})
  for row in rows:emit(row)
finally:
 p.stdin.close()
 try:p.wait(timeout=5)
 except subprocess.TimeoutExpired:p.kill();p.wait()
'''.replace('HELPER',repr(HELPER)).replace('ENDPOINT',repr(endpoint)),newline='\n')
 def launch(path):return '#!/bin/sh\nexec "'+sys.executable.replace('\\','/')+'" -IS "'+str(path).replace('\\','/')+'" "$@"\n'
 launcher.write_text(launch(payload),newline='\n')
 hookpayload=helperdir/'native_callback.py'
 hookpayload.write_text(NATIVE_CALLBACK,newline='\n')
 hook=helperdir/'native-callback';hook.write_text(launch(hookpayload),newline='\n')
 env=dict(os.environ,ORCHE_TRANSPORT_SOURCE=str(pathlib.Path(__file__).resolve().parent),ORCHE_GATE_ENTRY=str(pathlib.Path(gate.__file__).resolve()))
 env.update(ORCHE_RECEIVER_PIPE=pipe,ORCHE_OWNER_PID=str(os.getpid()))
 p=None;binding=None;channel=object();events=[];upstream=None;held=[];pins=[];lifecycle=None;relay=None;scanned={"allowed":False,"kind":"not-run"}
 try:
  for path in (GIT,sys.executable,HELPER,r'C:\Program Files\Git\usr\bin\sh.exe',payload,launcher,hookpayload,hook,source/'.git/config'):
   pins.append(PinnedFile(path))
  git_pin,python_pin,upstream_pin,shell_pin,relay_pin,launcher_pin,hook_pin,hook_launcher_pin,config_pin=pins
  if git_pin.sha256!='9c75f3f41eb5686bacde4b7c4fdfcd7970e8b699ee05c8d7a0cc9c8a7ddaffe8' or upstream_pin.sha256!='ad461657eca12dfeb50f281d107ac3760ac355a20882e4a3b0d470cb6bab77c6':raise ValueError('unqualified Git build')
  for runtime in pathlib.Path(__file__).resolve().parent.glob('*.py'):pins.append(PinnedFile(runtime))
  cfg=('-c','http.followRedirects=false')
  gh=r'C:\Program Files\GitHub CLI\gh.exe'
  preliminary=qualify(GIT,source,remote,env=env,config_args=cfg,approved_gh=gh)
  if not preliminary.eligible:raise ValueError('HTTPS qualification: '+preliminary.reason)
  expected={canonical(source/'.git/config'),canonical(pathlib.Path.home()/'.gitconfig'),canonical(r'C:\Program Files\Git\etc\gitconfig')}
  if {canonical(p) for p in preliminary.origins}!=expected:raise ValueError('unsupported config origin namespace')
  # Freeze the observed global/system input selection, preserving their contents
  # and credential helper configuration rather than disabling authentication.
  env.update(GIT_CONFIG_GLOBAL=str(pathlib.Path.home()/'.gitconfig'),GIT_CONFIG_SYSTEM=r'C:\Program Files\Git\etc\gitconfig')
  for path in (*preliminary.origins,*preliminary.executables):pins.append(PinnedFile(path))
  qualified=qualify(GIT,source,remote,env=env,config_args=cfg,approved_gh=gh)
  if qualified!=preliminary:raise ValueError('effective config changed before pins')
  # Only this owner-generated helper directory is admitted after raw-env check.
  env['GIT_EXEC_PATH']=str(helperdir)
  if shlex.quote(str(hook).replace('\\','/'))!=str(hook).replace('\\','/'):raise ValueError('unsupported hook launcher path')
  hookcfg=tuple(x for setting in (f'hook.{gate.NATIVE_PUBLICATION_HOOK}.command='+shlex.quote(str(hook).replace('\\','/')),f'hook.{gate.NATIVE_PUBLICATION_HOOK}.event=',f'hook.{gate.NATIVE_PUBLICATION_HOOK}.event=pre-push',f'hook.{gate.NATIVE_PUBLICATION_HOOK}.enabled=true',f'hook.{gate.NATIVE_PUBLICATION_HOOK}.parallel=false') for x in ('-c',setting))
  argv=[GIT,'-C',str(source),*cfg,*hookcfg,'-c',f'remote.{remote}.vcs=orche-receiver','push','--verify','--no-follow-tags','--recurse-submodules=no',*(['--dry-run'] if dry_run else []),'--',remote,tip+':'+destination]
  p=subprocess.Popen(argv,env=env)
  root_witness=ProcessWitness(p.pid);held.append(root_witness);broker.owner=root_witness.handle
  for expected in ('advertisement','hook','transfer'):
   with broker.accept() as connection:
    peer=pipe_process(connection);held.append(peer)
    request=json.loads(connection.recv_bytes());events.append(request.get('role'));ok=True
    if request.get('role')!=expected:
     connection.send_bytes(json.dumps({'ok':False}).encode());break
    if expected=='advertisement':
     if not (peer.uses(python_pin) and len(peer.argv)==5 and peer.argv[1]=='-IS' and canonical(peer.argv[2])==relay_pin.path and peer.argv[3:]==(remote,endpoint)):
      connection.send_bytes(b'{"ok":false}');break
     shell=ProcessWitness(peer.parent);held.append(shell)
     dispatcher=ProcessWitness(shell.parent);held.append(dispatcher)
     if not (shell.uses(shell_pin) and len(shell.argv)==4 and canonical(shell.argv[1])==launcher_pin.path and shell.argv[2:]==(remote,endpoint) and dispatcher.argv==('git','remote-orche-receiver',remote,endpoint)):
      connection.send_bytes(b'{"ok":false}');break
     upstream_witness=ProcessWitness(request['pid']);held.append(upstream_witness)
     lifecycle=SameHelperLifecycle(root=root_witness,dispatcher=dispatcher,relay=peer,upstream=upstream_witness,git_file=git_pin,relay_interpreter=python_pin,upstream_file=upstream_pin,upstream_args=(remote,endpoint),launcher=shell,shell_file=shell_pin)
     if not lifecycle.capture_once():connection.send_bytes(b'{"ok":false}');break
     relay=peer
     raw=''.join(request['rows']).encode()
     invocation=Invocation(os.urandom(32),endpoint,bytes.fromhex(upstream_pin.sha256),(root_witness.pid,root_witness.creation))
     captured=ReceiverScope(invocation,owned_channel=channel,qualified_route=True)
     if not captured.capture([row.encode() for row in request['rows']],channel=channel,invocation=invocation):connection.send_bytes(b'{"ok":false}');break
     roots=captured.consume(channel=channel,invocation=invocation,local_object_exists=lambda oid:subprocess.run([GIT,'-C',str(source),'cat-file','-e',oid],capture_output=True).returncode==0)
     if roots is None:connection.send_bytes(b'{"ok":false}');break
     scope=ScopeBinding(invocation.nonce.hex(),'sha256:'+hashlib.sha256(json.dumps(endpoint,separators=(',',':')).encode()).hexdigest(),'sha1',hashlib.sha256(raw).hexdigest(),tuple(sorted(roots)),'github-https-held-native-v1');binding=TransferBinding(scope,channel=channel);upstream=request['pid']
    elif expected=='hook':
     hook_shell=ProcessWitness(peer.parent);held.append(hook_shell)
     if not (lifecycle.current() and peer.uses(python_pin) and peer.child_of(hook_shell) and hook_shell.uses(shell_pin) and hook_shell.child_of(root_witness) and canonical(hook_shell.argv[1])==hook_launcher_pin.path and hook_shell.argv[2:]==(remote,endpoint) and peer.argv[1:]==('-IS',str(hookpayload).replace('\\','/'),remote,endpoint)):
      connection.send_bytes(b'{"ok":false}');break
     native=gate.NativePushInput(remote,endpoint,request['wire'].encode())
     current=gate._native_callback_currentness(native,str(source),GIT)
     evidence=gate._run_authoritative_scan(native,str(source),GIT,receiver_scope=scope)
     ok=evidence.parsed_outcome.kind in {'valid-v5','qualified-v5'} and evidence.execution is not None
     if gate._native_callback_currentness(native,str(source),GIT)!=current:raise ValueError('native currentness drift')
     scanned={'allowed':ok,'kind':'consumed-v5','commits':evidence.parsed_outcome.receipt.native.commits,'pending_state':evidence.execution.pending.state.value}
     if ok:binding.bind_hook(request['wire'].encode(),channel=channel,scope_digest=scope.digest())
    else:
     commands=[r.encode() for r in request['commands']]
     try:binding.consume_transfer(commands,channel=channel,scope_digest=scope.digest(),same_helper_live=(peer.pid==relay.pid and peer.creation==relay.creation and request['pid']==upstream and lifecycle.consume()))
     except ValueError:ok=False
    connection.send_bytes(json.dumps({'ok':ok}).encode())
   if not ok:break
  p.wait()
  print('Receiver scope: '+json.dumps(scanned,sort_keys=True),file=sys.stderr)
  return p.returncode
 except TimeoutError:
  # A preceding/downstream native hook veto can terminate Git before transfer.
  if p is not None and p.poll() is not None and p.returncode!=0:
   p.wait();return p.returncode
  raise

 finally:
  broker.close()
  if p is not None and p.poll() is None:p.kill();p.wait(timeout=5)
  for witness in reversed(held):witness.close()
  for pin in reversed(pins):pin.close()


def prepare_portable_batch(gate, source, remote, decision, received_decision_sha256):
 """Qualified GitHub owner preview only; never promotes or launches a push.

 The accepted decision digest is owner authority, not an untrusted CLI input.
 Bind the provider lookup to this repository's pinned effective push route.
 """
 if os.name!='nt':raise ValueError('unsupported portable owner platform')
 if type(decision) is not dict or decision.get('schema')!='orchestrarium.portable-review.v1' or 'project' not in decision:
  raise ValueError('explicit portable decision required')
 source=pathlib.Path(source).resolve()
 env=dict(os.environ);cfg=('-c','http.followRedirects=false');gh=r'C:\Program Files\GitHub CLI\gh.exe'
 gcm=str(pathlib.Path(GIT).parent/'git-credential-manager.exe')
 if any(env.get(k) for k in ('GH_HOST','GH_HTTP_UNIX_SOCKET','GH_CONFIG_DIR','GH_DEBUG')):
  raise ValueError('unsupported provider environment')
 initial=qualify(GIT,source,remote,env=env,config_args=cfg,approved_gh=gh,approved_gcm=gcm)
 if not initial.eligible:raise ValueError('unqualified portable publication route: '+initial.reason)
 expected={canonical(source/'.git/config'),canonical(pathlib.Path.home()/'.gitconfig'),canonical(r'C:\Program Files\Git\etc\gitconfig')}
 if {canonical(p) for p in initial.origins}!=expected:raise ValueError('unsupported config origin namespace')
 pins=[];fds=();modules=None
 try:
  for name in (GIT,gh,*initial.origins,*initial.executables):pins.append(PinnedFile(name))
  env.update(GIT_CONFIG_GLOBAL=str(pathlib.Path.home()/'.gitconfig'),GIT_CONFIG_SYSTEM=r'C:\Program Files\Git\etc\gitconfig')
  if qualify(GIT,source,remote,env=env,config_args=cfg,approved_gh=gh,approved_gcm=gcm)!=initial:raise ValueError('configuration drift')
  endpoints=subprocess.check_output([GIT,'-C',str(source),*cfg,'remote','get-url','--push','--all',remote],env=env,timeout=10).decode('utf-8').splitlines()
  if len(endpoints)!=1:raise ValueError('endpoint count')
  endpoint=endpoints[0];parsed=urlsplit(endpoint);slug=parsed.path.lstrip('/')
  if slug.endswith('.git'):slug=slug[:-4]
  if parsed.scheme!='https' or parsed.netloc!='github.com' or len(slug.split('/'))!=2:raise ValueError('provider endpoint')
  fds,closure=gate._capture_source_closure();modules=gate._load_captured_review_modules(closure);policy=modules.policy_module
  native=gate._capture_repository_observation(policy,source,GIT)
  if native['status']!='captured':raise ValueError('native repository unavailable')
  result=subprocess.run([gh,'api','--hostname','github.com','repos/'+slug],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=30,check=False)
  if result.returncode or len(result.stdout)>1024*1024:raise ValueError('provider identity unavailable')
  response=json.loads(result.stdout)
  if type(response.get('id')) is not int or response['id']<=0 or response.get('full_name','').lower()!=slug.lower() or response.get('html_url','').lower()!='https://github.com/'+slug.lower():
   raise ValueError('provider identity route mismatch')
  observed={'provider':'github','authority':'github.com','repositoryId':str(response['id'])}
  prepared=policy.materialize_portable_review(decision,received_decision_sha256=received_decision_sha256,observed_project=observed,selected_repository=native['repository'])
  origin=policy.resolve_trusted_origin();snapshot=policy.read_policy_snapshot(origin,source)
  existing=next((r for r in snapshot.usable_records if r['id']==prepared['id']),None)
  prepared=policy.materialize_portable_review(decision,received_decision_sha256=received_decision_sha256,observed_project=observed,selected_repository=native['repository'],current_record=existing)
  preview=policy.promote_decision(origin,native['repository'],prepared,expected_document_sha256=snapshot.snapshot['rawSha256'],expected_record_sha256=existing['recordSha256'] if existing else None,apply=False)
  if gate._capture_repository_observation(policy,source,GIT)!=native or qualify(GIT,source,remote,env=env,config_args=cfg,approved_gh=gh,approved_gcm=gcm)!=initial:
   raise ValueError('repository or route drift')
  gate._recheck_source_closure(fds,closure)
  return {'record':prepared,'preview':preview,'project':observed,'repository':native['repository'],'providerResponseSha256':hashlib.sha256(result.stdout).hexdigest()}
 finally:
  failures=[]
  if modules is not None:
   try:gate._release_captured_review_modules(modules)
   except BaseException as e:failures.append(e)
  failures.extend(e for _,e in gate._close_owned_descriptors(list(fds)))
  for pin in reversed(pins):
   try:pin.close()
   except BaseException as e:failures.append(e)
  if failures:raise RuntimeError('portable owner cleanup failed') from failures[0]
