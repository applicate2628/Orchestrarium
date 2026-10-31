from pathlib import Path
import os
import pytest
from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
INSTALL = load_module(ROOT / "scripts/production_installer.py", "projection_materialization_tests")


def setup(tmp_path):
    source = tmp_path / ".agents/skills/demo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_bytes(b"original skill")
    (source / "user-note.txt").write_bytes(b"preserve this extra")
    target = tmp_path / ".claude/skills/demo"
    target.parent.mkdir(parents=True)
    INSTALL._create_directory_projection(source, target, prefer_junction=os.name == "nt")
    digest = INSTALL._tree_sha256(source, ignore_runtime_cache=True)
    return source, target, digest


def test_materialization_copies_bytes_without_modifying_referent(tmp_path):
    source, target, digest = setup(tmp_path)
    before = {p.name: p.read_bytes() for p in source.iterdir()}
    with INSTALL._InstallTransaction([source, target], enabled=True, link_object_paths=(target,), readonly_paths=(source,)) as transaction:
        owner = INSTALL._CreateOnlyMutablePath(tmp_path, transaction, dry_run=False)
        owner.materialize_exact_projection(target.relative_to(tmp_path), source, digest)
        transaction.commit()
    assert not target.is_symlink()
    assert not getattr(os.path, "isjunction", lambda p: False)(target)
    assert {p.name: p.read_bytes() for p in target.iterdir()} == before
    assert {p.name: p.read_bytes() for p in source.iterdir()} == before
    assert not os.path.samefile(source / "SKILL.md", target / "SKILL.md")


def test_failure_restores_original_link_object(tmp_path):
    source, target, digest = setup(tmp_path)
    before = INSTALL._InstallTransaction._capture_node(target)
    with pytest.raises(RuntimeError, match="injected after materialization"):
        with INSTALL._InstallTransaction([source, target], enabled=True, link_object_paths=(target,), readonly_paths=(source,)) as transaction:
            owner = INSTALL._CreateOnlyMutablePath(tmp_path, transaction, dry_run=False)
            owner.materialize_exact_projection(target.relative_to(tmp_path), source, digest)
            raise RuntimeError("injected after materialization")
    assert INSTALL._InstallTransaction._capture_node(target) == before
    assert os.path.samefile(source, target)
    assert (source / "user-note.txt").read_bytes() == b"preserve this extra"
