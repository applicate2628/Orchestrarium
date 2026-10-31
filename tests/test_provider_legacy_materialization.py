"""Legacy layout conversion uses the common identity-bound mutation owner."""
from pathlib import Path
import os
import pytest
from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
INSTALL = load_module(ROOT / "scripts/production_installer.py", "legacy_materialization_backend")


def layout(tmp_path, provider="claude", root_link=False):
    source = tmp_path / ".agents/skills"
    source.mkdir(parents=True)
    for name in ("alpha", "beta"):
        (source / name).mkdir()
        (source / name / "SKILL.md").write_bytes(name.encode())
        (source / name / "personal.txt").write_bytes(b"user extra")
    target = tmp_path / ("." + provider) / "skills"
    target.parent.mkdir(parents=True)
    if root_link:
        INSTALL._create_directory_projection(source, target, prefer_junction=os.name == "nt")
        links = [target]
    else:
        target.mkdir()
        links = [target / name for name in ("alpha", "beta")]
        for link in links:
            INSTALL._create_directory_projection(source / link.name, link, prefer_junction=os.name == "nt")
        (target / "personal.md").write_bytes(b"not managed")
    return source, target, links


def invoke(tmp_path, provider="claude", *flags):
    return INSTALL.install(provider, ["--target", str(tmp_path), "--allow-unsafe-target",
                                      "--materialize-legacy-skills", *flags])


@pytest.mark.parametrize("root_link", [False, True])
@pytest.mark.parametrize("provider", ["codex", "claude"])
def test_preview_apply_reentry_preserves_referents_and_extras(tmp_path, provider, root_link):
    source, target, links = layout(tmp_path, provider, root_link)
    originals = {p: INSTALL._InstallTransaction._capture_node(p) for p in links}
    digest = INSTALL._tree_sha256(source, ignore_runtime_cache=True)
    assert invoke(tmp_path, provider) == 0
    assert {p: INSTALL._InstallTransaction._capture_node(p) for p in links} == originals
    assert invoke(tmp_path, provider, "--apply", "--dry-run") == 0
    assert {p: INSTALL._InstallTransaction._capture_node(p) for p in links} == originals
    assert invoke(tmp_path, provider, "--apply") == 0
    if provider == "codex":
        assert all(not p.exists() and not p.is_symlink() for p in links)
        if not root_link:
            assert (target / "personal.md").read_bytes() == b"not managed"
    else:
        for name in ("alpha", "beta"):
            assert (target / name / "SKILL.md").read_bytes() == name.encode()
            assert (target / name / "personal.txt").read_bytes() == b"user extra"
            assert not os.path.samefile(source / name / "SKILL.md", target / name / "SKILL.md")
    assert INSTALL._tree_sha256(source, ignore_runtime_cache=True) == digest
    assert all(not INSTALL._contains_reparse(p) for p in links)
    assert invoke(tmp_path, provider, "--apply") == 0


def test_second_replacement_failure_restores_all_original_links(tmp_path, monkeypatch):
    source, target, links = layout(tmp_path)
    original_nodes = {p: INSTALL._InstallTransaction._capture_node(p) for p in links}
    original = INSTALL._CreateOnlyMutablePath.materialize_exact_projection
    count = 0
    def injected(self, *args):
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError("injected second projection failure")
        return original(self, *args)
    monkeypatch.setattr(INSTALL._CreateOnlyMutablePath, "materialize_exact_projection", injected)
    assert invoke(tmp_path, "claude", "--apply") == 1
    assert {p: INSTALL._InstallTransaction._capture_node(p) for p in links} == original_nodes
    assert (source / "alpha/personal.txt").read_bytes() == b"user extra"


def test_external_link_refused_before_any_mutation(tmp_path):
    source, target, links = layout(tmp_path)
    outside = tmp_path / "unrelated"
    outside.mkdir()
    foreign = target / "zzz-foreign"
    INSTALL._create_directory_projection(outside, foreign, prefer_junction=os.name == "nt")
    original = {p: INSTALL._InstallTransaction._capture_node(p) for p in [*links, foreign]}
    assert invoke(tmp_path, "claude", "--apply") == 1
    assert {p: INSTALL._InstallTransaction._capture_node(p) for p in original} == original


def test_unselected_client_unchanged(tmp_path):
    source, target, links = layout(tmp_path)
    peer = tmp_path / ".codex/skills"
    peer.parent.mkdir()
    INSTALL._create_directory_projection(source, peer, prefer_junction=os.name == "nt")
    before = INSTALL._InstallTransaction._capture_node(peer)
    assert invoke(tmp_path, "claude", "--apply") == 0
    assert INSTALL._InstallTransaction._capture_node(peer) == before
    assert os.path.samefile(peer, source)


def test_uninstall_and_materialization_cannot_be_combined(tmp_path):
    source, target, links = layout(tmp_path)
    before = {p: INSTALL._InstallTransaction._capture_node(p) for p in links}
    assert invoke(tmp_path, "claude", "--uninstall", "--apply") != 0
    assert {p: INSTALL._InstallTransaction._capture_node(p) for p in links} == before

def test_nested_link_in_referent_refuses_conversion(tmp_path):
    source, target, links = layout(tmp_path)
    outside = tmp_path / "unrelated"
    outside.mkdir()
    nested = source / "alpha/nested"
    INSTALL._create_directory_projection(outside, nested, prefer_junction=os.name == "nt")
    before = {p: INSTALL._InstallTransaction._capture_node(p) for p in links}
    assert invoke(tmp_path, "claude", "--apply") == 1
    assert {p: INSTALL._InstallTransaction._capture_node(p) for p in links} == before


def test_source_drift_between_discovery_and_transaction_is_not_adopted(tmp_path, monkeypatch):
    source, target, links = layout(tmp_path)
    original = INSTALL._CreateOnlyMutablePath.materialize_exact_projection
    def changed(self, relative, referent, digest):
        (referent / "personal.txt").write_bytes(b"concurrent edit")
        return original(self, relative, referent, digest)
    monkeypatch.setattr(INSTALL._CreateOnlyMutablePath, "materialize_exact_projection", changed)
    before = {p: INSTALL._InstallTransaction._capture_node(p) for p in links}
    assert invoke(tmp_path, "claude", "--apply") == 1
    assert {p: INSTALL._InstallTransaction._capture_node(p) for p in links} == before
    # Rollback must not overwrite an independently edited read-only referent.
    assert (source / "alpha/personal.txt").read_bytes() == b"concurrent edit"


def test_codex_retires_legacy_alias_without_duplicate_payload(tmp_path):
    source, target, links = layout(tmp_path, 'codex', root_link=True)
    before = INSTALL._tree_sha256(source, ignore_runtime_cache=True)
    assert invoke(tmp_path, 'codex', '--apply') == 0
    assert not target.exists() and not target.is_symlink()
    assert INSTALL._tree_sha256(source, ignore_runtime_cache=True) == before


def test_codex_alias_retirement_failure_restores_original_nodes(tmp_path, monkeypatch):
    source, target, links = layout(tmp_path, 'codex')
    before = {p: INSTALL._InstallTransaction._capture_node(p) for p in links}
    original = INSTALL._CreateOnlyMutablePath.retain_path
    count = 0
    def injected(self, *args, **kwargs):
        nonlocal count
        count += 1
        if count == 2:
            raise RuntimeError('injected second alias retirement failure')
        return original(self, *args, **kwargs)
    monkeypatch.setattr(INSTALL._CreateOnlyMutablePath, 'retain_path', injected)
    assert invoke(tmp_path, 'codex', '--apply') == 1
    assert {p: INSTALL._InstallTransaction._capture_node(p) for p in links} == before
    assert (source / 'alpha/personal.txt').read_bytes() == b'user extra'

@pytest.mark.parametrize('drift', [False, True])
def test_legacy_hash_receipt_requires_factory_identity(tmp_path, monkeypatch, drift):
    source, target, links = layout(tmp_path)
    legacy = INSTALL._legacy_tree_sha256(source / 'alpha', ignore_runtime_cache=True)
    strong = INSTALL._tree_sha256(source / 'alpha', ignore_runtime_cache=True)
    monkeypatch.setitem(INSTALL.ADDITIONAL_STOCK_SKILL_ACCEPTED_PRIOR_TREE_SHA256,
                        'alpha', {legacy: strong})
    payload = INSTALL._nonlead_receipt_bytes({'alpha': legacy}, schema=INSTALL._NONLEAD_RECEIPT_SCHEMA)
    (source / INSTALL._NONLEAD_RECEIPT_NAME).write_bytes(payload)
    if drift:
        (source / 'alpha/SKILL.md').write_bytes(b'changed')
    assert invoke(tmp_path, 'claude', '--apply') == (1 if drift else 0)
    receipt = target / INSTALL._NONLEAD_RECEIPT_NAME
    if drift:
        assert not receipt.exists()
        assert all(INSTALL._contains_reparse(p) for p in links)
    else:
        assert receipt.read_bytes() == payload
        assert (source / INSTALL._NONLEAD_RECEIPT_NAME).read_bytes() == payload
