"""Temporary real install -> historical link layout -> migration -> uninstall."""
from pathlib import Path
import os
import subprocess
import sys
from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
INSTALL = load_module(ROOT / "scripts/production_installer.py", "legacy_roundtrip_backend")


def test_migrated_client_installs_and_uninstalls_without_claiming_user_extras(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    def run(client, *args):
        result = subprocess.run([sys.executable, str(ROOT / "install.py"), "--clients", client,
            "--target", str(project), "--allow-unsafe-target", *args], cwd=ROOT,
            capture_output=True, text=True, encoding="utf-8", timeout=300)
        assert result.returncode == 0, result.stdout + result.stderr
        return result
    run("codex", "--no-hypothesis-hook")
    shared = project / ".agents/skills"
    (shared / "backend-engineer/user-extra.txt").write_bytes(b"preserve")
    peer = project / ".claude/skills"
    peer.parent.mkdir()
    INSTALL._create_directory_projection(shared, peer, prefer_junction=os.name == "nt")
    source_digest = INSTALL._tree_sha256(shared, ignore_runtime_cache=True)
    run("claude", "--materialize-legacy-skills", "--apply")
    assert INSTALL._tree_sha256(shared, ignore_runtime_cache=True) == source_digest
    run("claude", "--no-hypothesis-hook")
    run("claude", "--uninstall", "--apply")
    assert (peer / "backend-engineer/user-extra.txt").read_bytes() == b"preserve"
    assert not (peer / "backend-engineer/SKILL.md").exists()
    assert INSTALL._tree_sha256(shared, ignore_runtime_cache=True) == source_digest


def test_codex_old_alias_retirement_then_uninstall_preserves_user_extra(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    def run(*args):
        result = subprocess.run([sys.executable, str(ROOT / 'install.py'), '--clients', 'codex',
            '--target', str(project), '--allow-unsafe-target', *args], cwd=ROOT,
            capture_output=True, text=True, encoding='utf-8', timeout=300)
        assert result.returncode == 0, result.stdout + result.stderr
    run('--no-hypothesis-hook')
    shared = project / '.agents/skills'
    extra = shared / 'backend-engineer/user-extra.txt'
    extra.write_bytes(b'keep')
    alias = project / '.codex/skills'
    INSTALL._create_directory_projection(shared, alias, prefer_junction=os.name == 'nt')
    run('--materialize-legacy-skills', '--apply')
    assert not alias.exists() and not alias.is_symlink()
    run('--uninstall', '--apply')
    assert extra.read_bytes() == b'keep'
    assert not (shared / 'backend-engineer/SKILL.md').exists()
