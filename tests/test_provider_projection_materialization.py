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


@pytest.mark.skipif(os.name != "nt", reason="Windows security descriptors")
@pytest.mark.parametrize("rollback", [False, True])
def test_materialization_retains_source_security_and_exact_link_rollback(tmp_path, rollback):
    from test_windows_tree_security_preservation import _create_protected, _security

    source = tmp_path / ".agents/skills/demo"
    source.parent.mkdir(parents=True)
    _create_protected(source, directory=True)
    (source / "SKILL.md").write_bytes(b"original skill")
    _create_protected(source / "private-note.txt", sddl="D:P(A;;FA;;;OW)")
    (source / "private-note.txt").write_bytes(b"private synthetic note")
    target = tmp_path / ".claude/skills/demo"
    target.parent.parent.mkdir()
    _create_protected(target.parent, directory=True,
        sddl="D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;OW)(A;OICI;FR;;;WD)")
    INSTALL._create_directory_projection(source, target, prefer_junction=True)
    source_nodes = {p: INSTALL._InstallTransaction._capture_node(p) for p in (source, *source.iterdir())}
    security = {p.relative_to(source): _security(p) for p in source_nodes}
    original_link = INSTALL._InstallTransaction._capture_node(target)
    link_security = _security(target)
    assert security[Path(".")] != link_security
    digest = INSTALL._tree_sha256(source)

    def convert():
        with INSTALL._InstallTransaction([source, target], enabled=True,
                link_object_paths=(target,), readonly_paths=(source,)) as transaction:
            owner = INSTALL._CreateOnlyMutablePath(tmp_path, transaction, dry_run=False)
            owner.materialize_exact_projection(target.relative_to(tmp_path), source, digest)
            assert {relative: _security(target / relative) for relative in security} == security
            if rollback:
                raise RuntimeError("injected after secured materialization")
            transaction.commit()

    if rollback:
        with pytest.raises(RuntimeError, match="injected after secured materialization"):
            convert()
        assert INSTALL._InstallTransaction._capture_node(target) == original_link
        assert _security(target) == link_security
    else:
        convert()
        assert not os.path.isjunction(target)
        assert not target.is_symlink()
        assert (target / "private-note.txt").read_bytes() == b"private synthetic note"
    assert {p: INSTALL._InstallTransaction._capture_node(p) for p in source_nodes} == source_nodes
    assert {relative: _security(source / relative) for relative in security} == security


@pytest.mark.skipif(os.name != "nt", reason="Windows security descriptors")
def test_materialization_refuses_source_security_drift_before_publication(tmp_path, monkeypatch):
    from test_windows_tree_security_preservation import _change_fixture_dacl, _security

    source, target, digest = setup(tmp_path)
    original_link = INSTALL._InstallTransaction._capture_node(target)
    source_file = source / "user-note.txt"
    old_security = _security(source_file)
    copy_tree = INSTALL._copy_tree
    def drift(*args, **kwargs):
        copy_tree(*args, **kwargs)
        _change_fixture_dacl(source_file)
    monkeypatch.setattr(INSTALL, "_copy_tree", drift)
    with pytest.raises(ValueError, match="E_READ_ONLY_DEPENDENCY_CHANGED"):
        with INSTALL._InstallTransaction([source, target], enabled=True,
                link_object_paths=(target,), readonly_paths=(source,)) as transaction:
            owner = INSTALL._CreateOnlyMutablePath(tmp_path, transaction, dry_run=False)
            owner.materialize_exact_projection(target.relative_to(tmp_path), source, digest)
    assert INSTALL._InstallTransaction._capture_node(target) == original_link
    assert _security(source_file) != old_security
    assert source_file.read_bytes() == b"preserve this extra"
