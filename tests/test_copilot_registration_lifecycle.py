from pathlib import Path
import json
import os
import subprocess
import sys
import pytest
from _module_loading_support import load_module
ROOT=Path(__file__).resolve().parents[1]
M=load_module(ROOT/'scripts/installation/copilot_registration.py','copilot_registration_lifecycle')
def payload(name='first'):
    return (json.dumps({'version':1,'hooks':{'preToolUse':[{'type':'command','powershell':name}]}})+'\n').encode()
@pytest.fixture
def project(tmp_path):
    p=tmp_path/'project space';(p/'.github/hooks').mkdir(parents=True)
    (p/'.github/hooks/user.json').write_bytes(b'foreign malformed content\r\n')
    return p
def target(p):return p/M.RELATIVE
@pytest.mark.skipif(os.name!='nt',reason='existing Windows physical owner qualification')
def test_real_preview_create_update_remove_and_trash(project):
    a,b=payload(),payload('second')
    assert M.change(project,a)['action']=='create'
    assert not target(project).exists()
    assert M.change(project,a,apply=True)['action']=='create'
    assert M.change(project,a,apply=True)['action']=='unchanged'
    assert target(project).read_bytes()==a
    preview=M.change(project,b,previous=a)
    assert preview['action']=='update' and target(project).read_bytes()==a
    update=M.change(project,b,previous=a,apply=True)
    assert target(project).read_bytes()==b
    assert Path(update['trash']).read_bytes()==a
    removal=M.change(project,None,previous=b,apply=True)
    assert not target(project).exists() and Path(removal['trash']).read_bytes()==b
    assert (project/'.github/hooks/user.json').read_bytes()==b'foreign malformed content\r\n'
@pytest.mark.skipif(os.name!='nt',reason='existing Windows physical owner qualification')
def test_existing_foreign_or_modified_registration_preserved(project):
    a,b=payload(),payload('second');target(project).write_bytes(a)
    with pytest.raises(ValueError,match='SELECTION-REQUIRED'):M.change(project,b,apply=True)
    with pytest.raises(ValueError,match='STALE-SELECTION'):M.change(project,b,previous=b,apply=True)
    assert target(project).read_bytes()==a
    doc=json.loads(a);doc['hooks']['preToolUse'].append({'type':'command','powershell':'user'})
    mixed=json.dumps(doc).encode();target(project).write_bytes(mixed)
    with pytest.raises(ValueError,match='MIXED-HANDLERS'):M.change(project,b,previous=mixed,apply=True)
    assert target(project).read_bytes()==mixed and not (project/'trash').exists()
@pytest.mark.skipif(os.name!='nt',reason='existing Windows physical owner qualification')
def test_update_failure_restores_registration_and_sibling(project,monkeypatch):
    a,b=payload(),payload('second');M.change(project,a,apply=True)
    original=M.backend._CreateOnlyMutablePath.write_file
    def fail(writer,relative,data,**kw):
        result=original(writer,relative,data,**kw)
        if relative==M.RELATIVE and data==b:raise ValueError('injected after write')
        return result
    monkeypatch.setattr(M.backend._CreateOnlyMutablePath,'write_file',fail)
    with pytest.raises(ValueError,match='injected after write'):M.change(project,b,previous=a,apply=True)
    assert target(project).read_bytes()==a
    assert not list((project/'trash').glob('*.json'))
    assert (project/'.github/hooks/user.json').read_bytes()==b'foreign malformed content\r\n'
@pytest.mark.parametrize('data',[b'{}',b'{"version":1,"version":1,"hooks":{}}',b'[]',b'null',b'x'*65537])
def test_malformed_candidates_refuse(data):
    with pytest.raises(ValueError):M.validate(data)
@pytest.mark.skipif(os.name!="nt",reason="existing POSIX installation hold")
def test_public_cli_preview_is_no_write(project,tmp_path):
    candidate=tmp_path/'candidate.json';candidate.write_bytes(payload())
    p=subprocess.run([sys.executable,'-I','-B',str(ROOT/'scripts/installation/copilot_registration.py'),'--project',str(project),'--desired',str(candidate)],capture_output=True,text=True,timeout=30)
    assert p.returncode==0,p.stderr
    assert json.loads(p.stdout)['applied'] is False
    assert not target(project).exists()

@pytest.mark.skipif(os.name!='nt',reason='native junction refusal')
def test_linked_hook_ancestry_is_not_followed(tmp_path):
    import _winapi
    p=tmp_path/'project';p.mkdir()
    other=tmp_path/'outside';(other/'hooks').mkdir(parents=True)
    sentinel=other/'hooks/user.json';sentinel.write_bytes(b'keep')
    _winapi.CreateJunction(str(other),str(p/'.github'))
    with pytest.raises(ValueError):M.change(p,payload(),apply=True)
    assert sentinel.read_bytes()==b'keep'
    assert not (other/'hooks/orchestrarium.json').exists()

@pytest.mark.skipif(os.name!='nt',reason='existing Windows physical owner qualification')
def test_remove_failure_restores_registration(project,monkeypatch):
    a=payload();M.change(project,a,apply=True)
    original=M.backend._CreateOnlyMutablePath.remove_exact_file
    def fail(writer,relative,digest):
        original(writer,relative,digest)
        raise ValueError('injected after remove')
    monkeypatch.setattr(M.backend._CreateOnlyMutablePath,'remove_exact_file',fail)
    with pytest.raises(ValueError,match='injected after remove'):
        M.change(project,None,previous=a,apply=True)
    assert target(project).read_bytes()==a
    assert not list((project/'trash').glob('*.json'))

@pytest.mark.skipif(os.name!='nt',reason='existing Windows physical owner qualification')
def test_removal_preview_retains_exact_bytes_without_trash(project):
    a=payload();M.change(project,a,apply=True)
    result=M.change(project,None,previous=a)
    assert result['action']=='remove' and not result['applied']
    assert target(project).read_bytes()==a and not (project/'trash').exists()

@pytest.mark.skipif(os.name!='nt',reason='existing Windows physical owner qualification')
def test_fresh_project_creates_missing_hook_directories(tmp_path):
    p=tmp_path/'fresh';p.mkdir();(p/'user.txt').write_bytes(b'keep')
    assert M.change(p,payload())['action']=='create'
    assert not (p/'.github').exists()
    assert M.change(p,payload(),apply=True)['action']=='create'
    assert target(p).read_bytes()==payload() and (p/'user.txt').read_bytes()==b'keep'

@pytest.mark.skipif(os.name!='nt',reason='native reparse leaf refusal')
def test_reparse_registration_leaf_refuses(project,tmp_path):
    import _winapi
    outside=tmp_path/'outside';outside.mkdir();(outside/'user').write_bytes(b'keep')
    _winapi.CreateJunction(str(outside),str(target(project)))
    with pytest.raises(ValueError):M.change(project,payload(),apply=True)
    assert (outside/'user').read_bytes()==b'keep'

def test_deep_json_is_a_controlled_refusal():
    with pytest.raises(ValueError,match='COPILOT-REGISTRATION-(DEPTH|SHAPE)'):
        M.validate(b'['*2000+b'0'+b']'*2000)

def test_decoder_recursion_is_controlled(monkeypatch):
    def refuse(*args,**kwargs):raise RecursionError('synthetic decoder limit')
    monkeypatch.setattr(M.json,'loads',refuse)
    with pytest.raises(ValueError,match='COPILOT-REGISTRATION-DEPTH'):M.validate(payload())

def test_non_utf8_candidate_refuses():
    with pytest.raises(ValueError):M.validate(payload().decode().encode('utf-16'))
