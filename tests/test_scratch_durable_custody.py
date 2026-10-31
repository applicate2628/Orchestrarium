"""Exact-byte, independently anchored Git custody; synthetic data, no disposal."""
import importlib.util
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('durable_cleanup_owner', ROOT/'scripts/maintenance/cleanup.py')
cleanup = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = cleanup
spec.loader.exec_module(cleanup)


def git(root, *args):
    p = subprocess.run(['git', '-C', str(root), *args], capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    return p.stdout.strip()


def repo(path):
    path.mkdir(parents=True)
    git(path, 'init', '-q')
    git(path, 'config', 'user.name', 'Synthetic')
    git(path, 'config', 'user.email', 'synthetic@example.invalid')
    git(path, 'config', 'core.autocrlf', 'false')
    return path


def commit(root, data=b'AAAA\n'):
    (root/'tracked.txt').write_bytes(data)
    git(root, 'add', 'tracked.txt')
    git(root, 'commit', '-qm', 'synthetic retained source')


def scratch(root, data=b'AAAA\n'):
    tree = root/'.scratch/evidence'; tree.mkdir(parents=True)
    leaf = tree/'work.data'; leaf.write_bytes(data)
    return tree, leaf


def test_durable_named_ref_accepts_exact_source_bytes(tmp_path):
    root = repo(tmp_path/'repository'); commit(root)
    tree, _ = scratch(root)
    result = cleanup.classify_owned_tree(tree, root)
    assert result.git_check_complete and result.all_git_recoverable


def test_loose_unreferenced_blob_is_not_durable_custody(tmp_path):
    root = repo(tmp_path/'repository'); tree, leaf = scratch(root)
    git(root, 'hash-object', '-w', '--no-filters', str(leaf))
    assert git(root, 'for-each-ref', '--format=%(refname)') == ''
    assert not cleanup.classify_owned_tree(tree, root).all_git_recoverable


def test_git_store_inside_scratch_is_not_independent_custody(tmp_path):
    root = repo(tmp_path/'.scratch/repository'); commit(root)
    tree, _ = scratch(root)
    assert not cleanup.classify_owned_tree(tree, root).all_git_recoverable


def test_alternates_back_to_scratch_do_not_establish_custody(tmp_path):
    origin = repo(tmp_path/'.scratch/origin'); commit(origin)
    root = tmp_path/'repository'
    git(tmp_path, 'clone', '-q', '--shared', str(origin), str(root))
    tree, _ = scratch(root)
    assert not cleanup.classify_owned_tree(tree, root).all_git_recoverable


def test_same_size_timestamp_rewrite_does_not_reuse_old_git_hash(tmp_path):
    root = repo(tmp_path/'repository'); commit(root)
    tree, leaf = scratch(root)
    assert cleanup.classify_owned_tree(tree, root).all_git_recoverable
    before = leaf.stat(); leaf.write_bytes(b'BBBB\n')
    os.utime(leaf, ns=(before.st_atime_ns, before.st_mtime_ns))
    assert not cleanup.classify_owned_tree(tree, root).all_git_recoverable


def test_hash_probe_never_runs_clean_filter_or_accepts_transformed_bytes(tmp_path):
    root = repo(tmp_path/'repository'); commit(root)
    marker = root/'filter-ran'
    script = root/'synthetic_filter.py'
    script.write_text("from pathlib import Path\nimport sys\nPath(sys.argv[1]).write_text('called')\nsys.stdin.buffer.read()\nsys.stdout.buffer.write(b'AAAA\\n')\n", encoding='utf-8')
    git(root, 'config', 'filter.synthetic.clean', shlex.join([sys.executable, str(script), str(marker)]))
    git(root, 'config', 'filter.synthetic.required', 'true')
    (root/'.gitattributes').write_text('*.data filter=synthetic\n', encoding='utf-8')
    tree, _ = scratch(root, b'unique synthetic bytes\n')
    result = cleanup.classify_owned_tree(tree, root)
    assert not marker.exists()
    assert not result.all_git_recoverable


def test_temporary_worktree_can_use_retained_ref_in_independent_common_store(tmp_path):
    origin = repo(tmp_path/'repository'); commit(origin)
    worktree = tmp_path/'.scratch/checkout'
    git(origin, 'worktree', 'add', '-q', '-b', 'retained-custody', str(worktree))
    tree, _ = scratch(worktree)
    result = cleanup.classify_owned_tree(tree, worktree)
    assert result.git_check_complete and result.all_git_recoverable


def test_long_scratch_path_keeps_exact_byte_custody_without_global_git_config(tmp_path):
    root = repo(tmp_path / 'repository'); commit(root)
    git(root, 'config', 'core.longpaths', 'false')
    tree, leaf = scratch(root)
    parent = tree / ('nested-' + 'a' * 70)
    parent.mkdir()
    long_leaf = parent / ('payload-' + 'b' * 70 + '.txt')
    leaf.rename(long_leaf)
    assert len(str(long_leaf)) > 260
    result = cleanup.classify_owned_tree(tree, root)
    assert result.git_check_complete and result.all_git_recoverable
    assert git(root, 'config', '--get', 'core.longpaths') == 'false'
