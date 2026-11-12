from synthetic_bundle_support import build_synthetic_bundle
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
    build_synthetic_bundle(builder, SOURCE, runtime, out, target='linux-x64', release='development')
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
        build_synthetic_bundle(builder, SOURCE,tmp_path/'missing',out,target='linux-x64',release='development')
    assert marker.read_text()=='keep'


def test_unknown_target_refused_before_output(builder,tmp_path):
    out=tmp_path/'out'
    with pytest.raises(ValueError):build_synthetic_bundle(builder, SOURCE,tmp_path,out,target='unknown',release='development')
    assert not out.exists()


def test_escaping_runtime_symlink_refused(builder,tmp_path):
    runtime=tmp_path/'runtime';(runtime/'bin').mkdir(parents=True)
    outside=tmp_path/'foreign';outside.write_bytes(b'not executed')
    try:(runtime/'bin/python3').symlink_to(outside)
    except OSError as e:
        if getattr(e,'winerror',None)==1314:pytest.skip('Windows symlink privilege required')
        raise
    out=tmp_path/'out'
    with pytest.raises(ValueError):build_synthetic_bundle(builder, SOURCE,runtime,out,target='linux-x64',release='development')
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
    # The main-layout bundle preserves complete provider mirrors.
    import shutil
    shutil.copy2(SOURCE / 'scripts/universal_hooks_manifest.py', source / 'scripts/universal_hooks_manifest.py')
    for relative in ('scripts/universal-hooks', 'src.codex/skills/lead/scripts',
                     'src.codex/skills/lead/hooks', 'src.claude/agents/scripts',
                     'src.claude/agents/hooks'):
        shutil.copytree(SOURCE / relative, source / relative, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
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
        build_synthetic_bundle(builder, source, runtime, output, target='linux-x64', release='development')
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
        build_synthetic_bundle(builder, source, runtime, alias / 'output', target='linux-x64', release='development')
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
        build_synthetic_bundle(builder, source, runtime, tmp_path / 'output', target='linux-x64', release='development')
    assert not (tmp_path / 'output').exists()


def test_locked_codex_notices_are_version_bound_and_shipped(builder, tmp_path):
    import hashlib
    notice_root = SOURCE / 'scripts/distribution/notices/openai-codex'
    manifest = json.loads((notice_root / 'source.json').read_text())
    expected = {'openai-codex'}
    assert set(manifest['packages']) == expected
    for filename, key in [('linux-x64-cp315.sources.json', 'packages'),
                          ('windows-x64-cp315.sources.json', 'wheels')]:
        lock = json.loads((SOURCE / 'scripts/distribution/locks' / filename).read_text())
        selected = {p['name']: p['version'] for p in lock[key] if p['name'] in expected}
        assert selected == manifest['packages']
    assert len(manifest['upstreamCommit']) == 40
    assert set(manifest['files']) == {'LICENSE', 'NOTICE'}
    for name, evidence in manifest['files'].items():
        assert evidence['url'] == f"https://raw.githubusercontent.com/openai/codex/{manifest['upstreamCommit']}/{name}"
        assert hashlib.sha256((notice_root / name).read_bytes()).hexdigest() == evidence['sha256']
    runtime = tmp_path / 'runtime'; (runtime / 'bin').mkdir(parents=True)
    (runtime / 'bin/python3').write_bytes(b'synthetic; never executed')
    output = tmp_path / 'bundle'
    build_synthetic_bundle(builder, SOURCE, runtime, output, target='linux-x64', release='development')
    for name in ('LICENSE', 'NOTICE', 'source.json'):
        assert (output / 'app/scripts/distribution/notices/openai-codex' / name).read_bytes() == (notice_root / name).read_bytes()


def test_shipped_notices_keep_exact_bytes_in_autocrlf_checkout(builder, tmp_path):
    import shutil
    import subprocess
    git = shutil.which('git')
    assert git is not None
    runtime = tmp_path / 'runtime'
    (runtime / 'bin').mkdir(parents=True)
    (runtime / 'bin/python3').write_bytes(b'synthetic interpreter; never executed')
    shipped = build_synthetic_bundle(builder, SOURCE, runtime, tmp_path / 'bundle',
                            target='linux-x64', release='development') / 'app'
    notices = shipped / 'scripts/distribution/notices'
    names = ['.gitattributes'] + sorted(
        p.relative_to(shipped).as_posix() for p in notices.rglob('*') if p.is_file()
    )
    assert 'scripts/distribution/notices/openai-codex/LICENSE' in names
    assert any(name.startswith('scripts/distribution/notices/python-build-standalone/') for name in names)
    origin = tmp_path / 'origin'
    origin.mkdir()
    for name in names:
        path = origin / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(((SOURCE if name == '.gitattributes' else shipped) / name).read_bytes())
    empty = tmp_path / 'empty-git-context'
    empty.mkdir()
    config = empty / 'config'
    config.write_text('')
    template, hooks = empty / 'template', empty / 'hooks'
    template.mkdir()
    hooks.mkdir()
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith('GIT_')}
    env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=str(config), GIT_TEMPLATE_DIR=str(template))
    def run(*args):
        return subprocess.run([git, '-c', 'core.hooksPath=' + str(hooks), *args],
                              check=True, capture_output=True, timeout=30, env=env)
    run('init', '-q', str(origin))
    run('-C', str(origin), '-c', 'core.autocrlf=false', 'add', '.')
    run('-C', str(origin), '-c', 'user.name=Synthetic', '-c', 'user.email=synthetic@example.invalid',
        'commit', '-qm', 'notice byte fixture')
    checkout = tmp_path / 'checkout'
    run('-c', 'core.autocrlf=true', 'clone', '-q', str(origin), str(checkout))
    for name in names[1:]:
        assert (checkout / name).read_bytes() == (shipped / name).read_bytes()


@pytest.mark.parametrize("target,triple,names,archive_sha", [
    ("windows-x64", "x86_64-pc-windows-msvc",
     "bzip2 cpython libffi liblzma libuuid openssl-3 sqlite tcl zstd",
     "5fc81405bbe4d0372302970372cde44fa0d755a0148a7d291168fba3e605a2f5"),
    ("linux-x64", "x86_64-unknown-linux-gnu",
     "bdb bzip2 cpython expat libX11 libXau libedit libffi liblzma libuuid libxcb mpdecimal ncurses openssl-3 sqlite tcl zlib-ng zlib zstd",
     "3488eafeae3c25a44895df9fd52a9be1f2fa11a45cb0580279e03c2bce5339b4"),
])
def test_python_notices_match_snapshot_metadata_and_ship(builder, tmp_path, target, triple, names, archive_sha):
    import hashlib
    notice_root = SOURCE / 'scripts/distribution/notices/python-build-standalone' / (target + '-cp315')
    manifest = json.loads((notice_root / 'source.json').read_text())
    lock = json.loads((SOURCE / 'scripts/distribution/locks' / (target + '-cp315.sources.json')).read_text())
    assert manifest['runtime'] == lock['runtime']
    assert manifest['target'] == triple
    assert manifest['pythonVersion'] == '3.15.2'
    assert manifest['metadataArchive']['sha256'] == archive_sha
    expected = {'LICENSE.' + name + '.txt' for name in
                names.split()}
    assert set(manifest['files']) == expected
    assert {Path(p).name for item in manifest['attributions'] for p in item['paths']} == expected
    for name, evidence in manifest['files'].items():
        assert evidence['archivePath'] == 'python/licenses/' + name
        assert hashlib.sha256((notice_root / name).read_bytes()).hexdigest() == evidence['sha256']
    runtime = tmp_path / 'runtime'; runtime.mkdir()
    interpreter = runtime / builder.TARGETS[target]
    interpreter.parent.mkdir(parents=True, exist_ok=True)
    interpreter.write_bytes(b'synthetic; never executed')
    output = tmp_path / 'bundle'
    build_synthetic_bundle(builder, SOURCE, runtime, output, target=target, release='development')
    for name in (*expected, 'source.json'):
        assert (output / 'app/scripts/distribution/notices/python-build-standalone' / (target + '-cp315') / name).read_bytes() == (notice_root / name).read_bytes()


@pytest.mark.parametrize("target, omitted", [("linux-x64", True), ("windows-x64", False)])
def test_sdk_runtime_omits_only_qualified_linux_optional_dbm(builder, tmp_path, target, omitted):
    runtime = tmp_path / "runtime"
    interpreter = runtime / builder.TARGETS[target]
    interpreter.parent.mkdir(parents=True)
    interpreter.write_bytes(b"synthetic interpreter; never executed")
    relative = Path("lib/python3.15/lib-dynload/_dbm.cpython-315-x86_64-linux-gnu.so")
    optional = runtime / relative
    optional.parent.mkdir(parents=True)
    optional.write_bytes(b"synthetic optional extension")
    unrelated = runtime / "user-data" / optional.name
    unrelated.parent.mkdir()
    unrelated.write_bytes(b"must remain")
    output = tmp_path / "bundle"
    build_synthetic_bundle(builder, SOURCE, runtime, output, target=target, release="development")
    assert (output / "python" / relative).exists() == (not omitted)
    assert optional.read_bytes() == b"synthetic optional extension"
    assert (output / "python/user-data" / optional.name).read_bytes() == b"must remain"


@pytest.mark.parametrize("target,interpreter,site", [
    ("windows-x64", "python.exe", "Lib/site-packages"),
    ("linux-x64", "bin/python3", "lib/python3.15/site-packages"),
])
def test_bundle_excludes_embedded_codex_cli_but_preserves_sdk_and_input(builder, tmp_path, target, interpreter, site):
    source, runtime = small_inputs(builder, tmp_path)
    executable = runtime / interpreter
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_bytes(b"fixture interpreter, never executed")
    packages = runtime / site
    cli = packages / "codex_cli_bin"
    (cli / "bin").mkdir(parents=True)
    (cli / "bin/codex").write_bytes(b"fixture executable, never executed")
    metadata = packages / "openai_codex_cli_bin-0.163.0.dist-info"
    metadata.mkdir()
    (metadata / "METADATA").write_text("Name: openai-codex-cli-bin\n")
    alternate_metadata = packages / "OPENAI_CODEX_CLI_BIN-0.163.0.DIST-INFO"
    alternate_metadata.mkdir(exist_ok=True)
    (alternate_metadata / "METADATA").write_text("Name: openai-codex-cli-bin\n")
    sdk = packages / "openai_codex"
    sdk.mkdir()
    (sdk / "__init__.py").write_text("# SDK fixture\n")
    entrypoint = runtime / ("Scripts/codex.exe" if target.startswith("windows-") else "bin/codex")
    entrypoint.parent.mkdir(parents=True, exist_ok=True)
    entrypoint.write_bytes(b"fixture entrypoint")
    mixed_case_cli = packages / "Codex_Cli_Bin"
    mixed_case_cli.mkdir(exist_ok=True)
    (mixed_case_cli / "payload").write_bytes(b"fixture mixed case")
    other = runtime / "unrelated/codex_cli_bin"
    other.mkdir(parents=True)
    (other / "user-file").write_text("keep")
    output = tmp_path / "output"
    build_synthetic_bundle(builder, source, runtime, output, target=target, release="development")
    assert not (output / "python" / site / "codex_cli_bin").exists()
    assert not (output / "python" / site / metadata.name).exists()
    assert not (output / "python" / site / alternate_metadata.name).exists()
    assert (output / "python" / site / "openai_codex/__init__.py").read_text() == "# SDK fixture\n"
    assert not (output / "python" / entrypoint.relative_to(runtime)).exists()
    assert not (output / "python" / site / "Codex_Cli_Bin").exists()
    assert (output / "python/unrelated/codex_cli_bin/user-file").read_text() == "keep"
    assert (cli / "bin/codex").read_bytes() == b"fixture executable, never executed"
    assert (metadata / "METADATA").exists()


@pytest.mark.parametrize("target", ["linux-x64", "windows-x64"])
def test_bundle_omits_cli_only_attribution_but_keeps_sdk_notice_and_sources(builder, tmp_path, target):
    source, runtime = small_inputs(builder, tmp_path)
    interpreter = runtime / builder.TARGETS[target]
    interpreter.parent.mkdir(parents=True, exist_ok=True)
    interpreter.write_bytes(b"synthetic interpreter; never executed")
    notices = source / "scripts/distribution/notices/openai-codex"
    for relative in ("native/v8/LICENSE", "rust-dependencies/texts/source.txt", "LICENSE", "NOTICE"):
        path = notices / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original " + relative)
    other = source / "scripts/unrelated/native"
    other.mkdir(parents=True)
    (other / "keep.txt").write_text("keep")
    output = tmp_path / "output"
    build_synthetic_bundle(builder, source, runtime, output, target=target, release="development")
    packaged = output / "app/scripts/distribution/notices/openai-codex"
    assert not (packaged / "native").exists()
    assert not (packaged / "rust-dependencies").exists()
    assert (packaged / "LICENSE").read_text() == "original LICENSE"
    assert (packaged / "NOTICE").read_text() == "original NOTICE"
    assert (output / "app/scripts/unrelated/native/keep.txt").read_text() == "keep"
    assert (notices / "native/v8/LICENSE").read_text() == "original native/v8/LICENSE"
    assert (notices / "rust-dependencies/texts/source.txt").exists()


@pytest.mark.parametrize("platform,collection", [("windows-x64", "wheels"), ("linux-x64", "packages")])
def test_runtime_lock_excludes_cli_wheel_and_matches_sdk_metadata(platform, collection):
    root = SOURCE / "scripts/distribution/locks"
    lock = (root / (platform + "-cp315.txt")).read_text(encoding="utf-8")
    metadata = json.loads((root / (platform + "-cp315.sources.json")).read_text(encoding="utf-8"))
    rows = metadata[collection]
    packages = {p["name"]: p for p in rows}
    assert len(packages) == len(rows), "duplicate package names in source metadata"
    assert "openai-codex" in packages
    assert "openai-codex-cli-bin" not in packages
    assert "openai-codex-cli-bin" not in lock
    assert "openai-codex==" + packages["openai-codex"]["version"] + " --hash=sha256:" + packages["openai-codex"]["sha256"] in lock
    expected = {p["name"] + "==" + p["version"] + " --hash=sha256:" + p["sha256"] for p in packages.values()}
    actual = [line.strip() for line in lock.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    assert len(actual) == len(set(actual)) == len(packages)
    assert set(actual) == expected
