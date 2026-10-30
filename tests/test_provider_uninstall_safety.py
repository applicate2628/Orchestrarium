from pathlib import Path
import hashlib
import os
import pytest
from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
INSTALL = load_module(ROOT / "scripts/production_installer.py", "provider_uninstall_safety_backend")
CODEC = load_module(ROOT / "scripts/installation/ownership.py", "provider_uninstall_safety_codec")


def prepare(tmp_path):
    project = tmp_path / "project"
    first = project / ".claude/skills/alpha/SKILL.md"
    second = project / ".claude/skills/beta/SKILL.md"
    for path in [first, second]:
        path.parent.mkdir(parents=True)
        path.write_bytes(b"owned bytes")
    files = {path.relative_to(project).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest() for path in [first, second]}
    receipt = project / ".claude/.orche-install.v1.json"
    receipt.write_bytes(CODEC.encode_record(files, "claude", "project", configs={}))
    return project, first, second, receipt


def test_modified_skill_and_foreign_file_survive_uninstall(tmp_path):
    project, first, second, receipt = prepare(tmp_path)
    first.write_bytes(b"user edited")
    foreign = project / ".claude/private-note.txt"
    foreign.write_bytes(b"user only")
    result = INSTALL.install("claude", ["--target", str(project), "--allow-unsafe-target", "--uninstall", "--apply"])
    assert result == 2
    assert first.read_bytes() == b"user edited"
    assert foreign.read_bytes() == b"user only"
    assert not second.exists()
    remaining = CODEC.decode_record(receipt.read_bytes(), "claude", "project")
    assert set(remaining["files"]) == {first.relative_to(project).as_posix()}


def test_late_removal_failure_rolls_back_payload_and_receipt(tmp_path, monkeypatch):
    project, first, second, receipt = prepare(tmp_path)
    before = {path: path.read_bytes() for path in [first, second, receipt]}
    original = INSTALL._CreateOnlyMutablePath.remove_exact_file
    count = 0
    def injected(self, relative, digest):
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError("injected second removal failure")
        return original(self, relative, digest)
    monkeypatch.setattr(INSTALL._CreateOnlyMutablePath, "remove_exact_file", injected)
    result = INSTALL.install("claude", ["--target", str(project), "--allow-unsafe-target", "--uninstall", "--apply"])
    assert result == 1
    assert {path: path.read_bytes() for path in before} == before


def test_old_shared_claude_projection_blocks_codex_mutation(tmp_path):
    shared = tmp_path / ".agents/skills"
    shared.mkdir(parents=True)
    peer = tmp_path / ".claude/skills"
    peer.parent.mkdir()
    INSTALL._create_directory_projection(shared, peer, prefer_junction=os.name == "nt")
    with pytest.raises(ValueError, match="E_SHARED_LAYOUT_MIGRATION_REQUIRED"):
        INSTALL._require_provider_copy_isolation(ROOT, "codex", "target", tmp_path / ".codex", tmp_path)
    assert shared.is_dir()
    assert os.path.samefile(shared, peer)


def test_alias_with_noncanonical_name_still_blocks_shared_storage_removal(tmp_path):
    shared = tmp_path / ".agents/skills/backend-engineer"
    shared.mkdir(parents=True)
    alias = tmp_path / ".claude/skills/my-personal-alias"
    alias.parent.mkdir(parents=True)
    INSTALL._create_directory_projection(shared, alias, prefer_junction=os.name == "nt")
    with pytest.raises(ValueError, match="E_SHARED_LAYOUT_MIGRATION_REQUIRED"):
        INSTALL._require_provider_copy_isolation(ROOT, "codex", "target", tmp_path / ".codex", tmp_path)


def test_own_legacy_alias_requires_migration_before_uninstall(tmp_path):
    shared = tmp_path / ".agents/skills"
    shared.mkdir(parents=True)
    alias = tmp_path / ".codex/skills"
    alias.parent.mkdir()
    INSTALL._create_directory_projection(shared, alias, prefer_junction=os.name == "nt")
    INSTALL._require_provider_copy_isolation(ROOT, "codex", "target", tmp_path / ".codex", tmp_path)
    with pytest.raises(ValueError, match="E_SHARED_LAYOUT_MIGRATION_REQUIRED"):
        INSTALL._require_provider_copy_isolation(ROOT, "codex", "target", tmp_path / ".codex", tmp_path, removing=True)
