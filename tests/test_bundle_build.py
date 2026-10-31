"""Local bundle assembly preserves sources and refuses destructive targets."""
import importlib.util
import json
import os
from pathlib import Path
import pytest

SOURCE = Path(__file__).resolve().parents[1]

@pytest.fixture
def builder():
    spec = importlib.util.spec_from_file_location('orche_bundle_build', SOURCE/'scripts/distribution/build.py')
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def test_build_uses_relative_layout_and_keeps_source(builder, tmp_path):
    runtime = tmp_path/'runtime'; (runtime/'bin').mkdir(parents=True)
    (runtime/'bin/python3').write_bytes(b'not executed')
    out = tmp_path/'bundle'
    builder.build(SOURCE, runtime, out, target='linux-x64', release='development')
    data = json.loads((out/'bundle.json').read_text())
    assert data['python'] == 'python/bin/python3'
    assert data['entry'] == 'app/install.py'
    assert (out/'app/install.py').read_bytes() == (SOURCE/'install.py').read_bytes()
    assert (out/'launch.py').read_bytes() == (SOURCE/'scripts/distribution/launch.py').read_bytes()
    # Windows does not expose POSIX executable permission bits.
    if os.name != 'nt':
        assert (out/'orche').stat().st_mode & 0o111
    assert not (out/'app/tests').exists() and not (out/'app/.git').exists()
    assert (runtime/'bin/python3').read_bytes() == b'not executed'


def test_existing_output_is_never_overwritten(builder,tmp_path):
    out=tmp_path/'out';out.mkdir();marker=out/'user';marker.write_text('keep')
    with pytest.raises((ValueError,FileExistsError)):
        builder.build(SOURCE,tmp_path/'missing',out,target='linux-x64',release='development')
    assert marker.read_text()=='keep'


def test_unknown_target_refused_before_output(builder,tmp_path):
    out=tmp_path/'out'
    with pytest.raises(ValueError):builder.build(SOURCE,tmp_path,out,target='unknown',release='development')
    assert not out.exists()


def test_escaping_runtime_symlink_refused(builder,tmp_path):
    runtime=tmp_path/'runtime';(runtime/'bin').mkdir(parents=True)
    outside=tmp_path/'foreign';outside.write_bytes(b'not executed')
    try:(runtime/'bin/python3').symlink_to(outside)
    except OSError as e:
        if getattr(e,'winerror',None)==1314:pytest.skip('Windows symlink privilege required')
        raise
    out=tmp_path/'out'
    with pytest.raises(ValueError):builder.build(SOURCE,runtime,out,target='linux-x64',release='development')
    assert not out.exists()


def small_inputs(builder, tmp_path):
    source = tmp_path / 'source'; source.mkdir()
    for name in builder.APP_INPUTS:
        path = source / name
        if (SOURCE / name).is_dir():
            path.mkdir(parents=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('trusted fixture\n')
    entry = source / 'scripts/distribution/launch.py'
    entry.parent.mkdir(parents=True); entry.write_text('# fixture launcher\n')
    runtime = tmp_path / 'runtime'; (runtime / 'bin').mkdir(parents=True)
    (runtime / 'bin/python3').write_bytes(b'synthetic; never executed')
    return source, runtime


def test_source_link_swap_before_copy_call_is_rejected(builder, tmp_path, monkeypatch):
    source, runtime = small_inputs(builder, tmp_path)
    outside = tmp_path / 'outside'; outside.write_bytes(b'outside private bytes')
    leaf = source / 'README.md'
    probe = tmp_path / 'symlink-capability'
    try:
        probe.symlink_to(outside)
    except OSError as error:
        if getattr(error, 'winerror', None) == 1314:
            pytest.skip('Windows symlink privilege required')
        raise
    probe.unlink()
    real_copy = builder.shutil.copy2
    swapped = False
    def swap_then_copy(src, dst, **kwargs):
        nonlocal swapped
        if Path(src) == leaf and not swapped:
            swapped = True
            leaf.unlink(); leaf.symlink_to(outside)
        return real_copy(src, dst, **kwargs)
    monkeypatch.setattr(builder.shutil, 'copy2', swap_then_copy)
    output = tmp_path / 'output'
    with pytest.raises(ValueError):
        builder.build(source, runtime, output, target='linux-x64', release='development')
    assert swapped
    assert not (output / 'bundle.json').exists()
    copied = output / 'app/README.md'
    assert not copied.exists() or copied.is_symlink()
    assert outside.read_bytes() == b'outside private bytes'


def test_output_parent_symlink_is_refused(builder, tmp_path):
    source, runtime = small_inputs(builder, tmp_path)
    outside = tmp_path / 'external-parent'; outside.mkdir()
    alias = tmp_path / 'alias'
    try:
        alias.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        if getattr(error, 'winerror', None) == 1314:
            pytest.skip('Windows symlink privilege required')
        raise
    with pytest.raises(ValueError):
        builder.build(source, runtime, alias / 'output', target='linux-x64', release='development')
    assert list(outside.iterdir()) == []


def test_reparse_directory_is_refused_before_traversal(builder, tmp_path, monkeypatch):
    from types import SimpleNamespace
    source, runtime = small_inputs(builder, tmp_path)
    original = Path.lstat
    def reparse(path, *args, **kwargs):
        value = original(path, *args, **kwargs)
        if path == runtime:
            return SimpleNamespace(st_mode=value.st_mode, st_file_attributes=1024)
        return value
    monkeypatch.setattr(Path, 'lstat', reparse)
    with pytest.raises(ValueError):
        builder.build(source, runtime, tmp_path / 'output', target='linux-x64', release='development')
    assert not (tmp_path / 'output').exists()
