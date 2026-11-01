"""Relative bundle launch must never fall back to ambient Python."""
import importlib.util
import json
import os
import sys
from pathlib import Path
import pytest

PATH = Path(__file__).resolve().parents[1] / 'scripts/distribution/launch.py'

@pytest.fixture
def launcher():
    spec = importlib.util.spec_from_file_location('orche_bundle_launcher', PATH)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def bundle(tmp_path, launcher):
    root = tmp_path / 'bundle with spaces'
    (root / 'python/bin').mkdir(parents=True)
    (root / 'app').mkdir()
    exe = root / 'python/bin/python3'
    exe.write_bytes(b'synthetic interpreter; never executed')
    (root / 'app/install.py').write_text('# synthetic entry')
    data = {'schemaVersion': 1, 'product': 'Orche', 'release': 'development',
            'target': launcher.current_target(), 'python': 'python/bin/python3',
            'entry': 'app/install.py'}
    (root / 'bundle.json').write_text(json.dumps(data))
    return root, exe, data


def test_relative_launch_survives_relocation(launcher, tmp_path, monkeypatch):
    root, exe, _ = bundle(tmp_path, launcher)
    moved = root.with_name('moved Ω'); root.rename(moved)
    monkeypatch.chdir(tmp_path)
    python, entry = launcher.resolve_launch(moved, moved / 'python/bin/python3')
    assert python == moved / 'python/bin/python3'
    assert entry == moved / 'app/install.py'


@pytest.mark.parametrize('path', ['../outside', '/outside', 'C:/outside', r'..\outside'])
def test_manifest_escape_refused(launcher, tmp_path, path):
    root, exe, data = bundle(tmp_path, launcher)
    data['python'] = path
    (root / 'bundle.json').write_text(json.dumps(data))
    with pytest.raises(ValueError): launcher.resolve_launch(root, exe)


def test_wrong_interpreter_refused(launcher, tmp_path):
    root, exe, _ = bundle(tmp_path, launcher)
    other = tmp_path / 'python'; other.write_bytes(exe.read_bytes())
    with pytest.raises(ValueError): launcher.resolve_launch(root, other)


def test_missing_interpreter_has_no_fallback(launcher, tmp_path):
    root, exe, _ = bundle(tmp_path, launcher); exe.unlink()
    with pytest.raises((ValueError, OSError)): launcher.resolve_launch(root, exe)


def test_wrong_target_refused(launcher, tmp_path):
    root, exe, data = bundle(tmp_path, launcher); data['target'] = 'unsupported'
    (root / 'bundle.json').write_text(json.dumps(data))
    with pytest.raises(ValueError): launcher.resolve_launch(root, exe)


def test_symlink_escape_refused(launcher, tmp_path):
    root, exe, _ = bundle(tmp_path, launcher)
    outside = tmp_path / 'outside'; outside.write_bytes(exe.read_bytes())
    exe.unlink()
    try: exe.symlink_to(outside)
    except OSError as error:
        if getattr(error, 'winerror', None) == 1314: pytest.skip('Windows symlink privilege required')
        raise
    with pytest.raises(ValueError): launcher.resolve_launch(root, exe)


def test_python_environment_isolated_without_changing_other_inputs(launcher):
    source = {'PATH':'existing', 'PYTHONHOME':'bad', 'pythonpath':'bad', 'CODEX_HOME':'selected'}
    result = launcher.child_environment(source)
    assert result == {'PATH':'existing','CODEX_HOME':'selected','PYTHONNOUSERSITE':'1',
                      'PYTHONDONTWRITEBYTECODE':'1'}
    assert source['PYTHONHOME'] == 'bad'


def test_duplicate_manifest_keys_refused(launcher, tmp_path):
    root, exe, data = bundle(tmp_path, launcher)
    raw = json.dumps(data)
    (root/'bundle.json').write_text(raw[:-1] + ', "product":"Orche"}')
    with pytest.raises(ValueError): launcher.resolve_launch(root,exe)


def test_child_reexec_uses_bundle_and_preserves_argument_boundaries(launcher, tmp_path, monkeypatch):
    root, exe, data = bundle(tmp_path, launcher)
    monkeypatch.setattr(launcher,'__file__',str(root/'launch.py'))
    monkeypatch.setattr(launcher.sys,'executable',str(exe))
    monkeypatch.setenv('PYTHONHOME','hostile')
    calls=[]
    monkeypatch.setattr(launcher,'_exec_child',lambda path,args,env:(calls.append((path,args,env)),0)[1])
    assert launcher.main(['--permanent-runtime','--clients','codex','--target','path with spaces'])==0
    path,args,env=calls[0]
    assert path==str(exe)
    assert args==[str(exe),'-I',str(root/'app/install.py'),'--clients','codex','--target','path with spaces']
    assert 'PYTHONHOME' not in env and env['PYTHONNOUSERSITE']=='1'


def test_explicit_retention_runs_before_reexec(launcher,tmp_path,monkeypatch):
    root,exe,data=bundle(tmp_path,launcher)
    destination=tmp_path/'retained'
    monkeypatch.setattr(launcher,'__file__',str(root/'launch.py'))
    monkeypatch.setattr(launcher.sys,'executable',str(exe))
    prepared=[]
    def retain(source,target):
        prepared.append((source,target))
        (target/'python/bin').mkdir(parents=True)
        (target/'python/bin/python3').write_bytes(b'not executed')
        (target/'launch.py').write_text('# retained entry')
        return target/'python/bin/python3',target/'launch.py'
    monkeypatch.setattr(launcher,'retain_bundle',retain,raising=False)
    calls=[];monkeypatch.setattr(launcher,'_exec_child',lambda *args:(calls.append(args),0)[1])
    assert launcher.main(['--retain-to',str(destination),'--clients','codex'])==0
    assert prepared==[(root,destination)]
    assert calls[0][1]==[str(destination/'python/bin/python3'),'-I',str(destination/'launch.py'),'--permanent-runtime','--clients','codex']


def test_missing_retention_target_never_executes(launcher,tmp_path,monkeypatch):
    root,exe,_=bundle(tmp_path,launcher)
    monkeypatch.setattr(launcher,'__file__',str(root/'launch.py'))
    monkeypatch.setattr(launcher.sys,'executable',str(exe))
    calls=[];monkeypatch.setattr(launcher,'_exec_child',lambda *args:(calls.append(args),0)[1])
    assert launcher.main(['--retain-to'])==2
    assert not calls


def test_retention_uses_shared_builder_and_refuses_existing_target(launcher,tmp_path):
    spec=importlib.util.spec_from_file_location('build_fixture',PATH.with_name('build.py'))
    builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    target=launcher.current_target()
    runtime=tmp_path/'runtime'
    exe=runtime/builder.TARGETS[target];exe.parent.mkdir(parents=True)
    exe.write_bytes(b'synthetic interpreter; never executed')
    source=builder.build(PATH.parents[2],runtime,tmp_path/'original',target=target,release='development')
    (tmp_path/'parent').mkdir()
    destination=tmp_path/'parent'/'..'/'permanent Ω'
    python,entry=launcher.retain_bundle(source,destination)
    assert python.read_bytes()==exe.read_bytes()
    assert entry.read_bytes()==PATH.read_bytes()
    assert (destination/'app/install.py').read_bytes()==(source/'app/install.py').read_bytes()
    marker=destination/'user';marker.write_text('keep')
    with pytest.raises(FileExistsError):launcher.retain_bundle(source,destination)
    assert marker.read_text()=='keep'


def test_relative_retention_destination_refused(launcher,tmp_path):
    root,_,_=bundle(tmp_path,launcher)
    with pytest.raises(ValueError):launcher.retain_bundle(root,Path('relative'))


def test_retention_failure_does_not_start_installer(launcher,tmp_path,monkeypatch):
    root,exe,_=bundle(tmp_path,launcher)
    monkeypatch.setattr(launcher,'__file__',str(root/'launch.py'))
    monkeypatch.setattr(launcher.sys,'executable',str(exe))
    def fail(*args):raise FileExistsError('occupied destination')
    monkeypatch.setattr(launcher,'retain_bundle',fail)
    calls=[];monkeypatch.setattr(launcher,'_exec_child',lambda *args:(calls.append(args),0)[1])
    assert launcher.main(['--retain-to',str(tmp_path/'occupied'),'--clients','codex'])==2
    assert calls==[]


def test_manifest_symlink_outside_bundle_refused(launcher,tmp_path):
    root,exe,_=bundle(tmp_path,launcher)
    outside=tmp_path/'outside-manifest.json'
    (root/'bundle.json').rename(outside)
    try:(root/'bundle.json').symlink_to(outside)
    except OSError as error:
        if getattr(error,'winerror',None)==1314:pytest.skip('Windows symlink privilege required')
        raise
    with pytest.raises(ValueError):launcher.resolve_launch(root,exe)


def test_dangling_retention_name_is_not_followed(launcher, tmp_path):
    spec = importlib.util.spec_from_file_location('retention_build_test', PATH.with_name('build.py'))
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    runtime = tmp_path / 'runtime'
    exe = runtime / builder.TARGETS[launcher.current_target()]
    exe.parent.mkdir(parents=True); exe.write_bytes(b'synthetic; never executed')
    root = builder.build(PATH.parents[2], runtime, tmp_path / 'original',
                         target=launcher.current_target(), release='development')
    redirect = tmp_path / 'outside-selected-name'
    chosen = tmp_path / 'chosen'
    try:
        chosen.symlink_to(redirect, target_is_directory=True)
    except OSError as error:
        if getattr(error, 'winerror', None) == 1314:
            pytest.skip('Windows symlink privilege required')
        raise
    with pytest.raises((FileExistsError, ValueError)):
        launcher.retain_bundle(root, chosen)
    assert chosen.is_symlink()
    assert not redirect.exists()


def test_apply_requires_explicit_runtime_lifetime(launcher, tmp_path, monkeypatch, capsys):
    root, exe, _ = bundle(tmp_path, launcher)
    monkeypatch.setattr(launcher, '__file__', str(root / 'launch.py'))
    monkeypatch.setattr(launcher.sys, 'executable', str(exe))
    calls = []
    monkeypatch.setattr(launcher, '_exec_child', lambda *args: (calls.append(args), 0)[1])
    assert launcher.main(['--clients', 'codex']) == 2
    assert calls == []
    assert '--retain-to' in capsys.readouterr().err


@pytest.mark.parametrize('args', [['--list-clients'], ['--help'], ['--clients', 'codex', '--dry-run']])
def test_read_only_launch_needs_no_permanent_placement(launcher, tmp_path, monkeypatch, args):
    root, exe, _ = bundle(tmp_path, launcher)
    monkeypatch.setattr(launcher, '__file__', str(root / 'launch.py'))
    monkeypatch.setattr(launcher.sys, 'executable', str(exe))
    calls = []
    monkeypatch.setattr(launcher, '_exec_child', lambda *values: (calls.append(values), 0)[1])
    assert launcher.main(args) == 0
    assert calls[0][1][3:] == args


def test_windows_child_waits_and_propagates_failure(launcher, monkeypatch):
    from types import SimpleNamespace
    monkeypatch.setattr(launcher.sys, 'platform', 'win32')
    args = ['C:/runtime with spaces/python.exe', '-I', 'C:/app space/install.py', 'value & literal']
    env = {'PATH': 'unchanged'}
    calls = []
    def run(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=23)
    monkeypatch.setattr(launcher.subprocess, 'run', run)
    assert launcher._exec_child(args[0], args, env) == 23
    assert calls == [(args, {'env': env})]


def test_posix_child_keeps_exec_replacement(launcher, monkeypatch):
    monkeypatch.setattr(launcher.sys, 'platform', 'linux')
    args = ['/runtime/python', '-I', '/app/install.py']
    env = {'PATH': 'unchanged'}
    calls = []
    monkeypatch.setattr(launcher.os, 'execve', lambda *values: calls.append(values))
    assert launcher._exec_child(args[0], args, env) == 0
    assert calls == [(args[0], args, env)]


@pytest.mark.skipif(sys.platform != 'win32', reason='native Windows argument/exit contract')
def test_windows_child_preserves_real_argument_boundaries(launcher, tmp_path):
    script = tmp_path / 'child with spaces.py'
    result = tmp_path / 'argument result.json'
    script.write_text('import json, pathlib, sys\npathlib.Path(sys.argv[1]).write_text(json.dumps(sys.argv[2:]), encoding="utf-8")\nraise SystemExit(23)\n', encoding='utf-8')
    values = ['space value', 'Unicode Ω', 'literal & not-shell', 'quote"inside', '']
    args = [sys.executable, '-I', str(script), str(result), *values]
    assert launcher._exec_child(sys.executable, args, launcher.child_environment(dict(os.environ))) == 23
    assert json.loads(result.read_text(encoding='utf-8')) == values
