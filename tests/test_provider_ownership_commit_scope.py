from pathlib import Path
from types import SimpleNamespace
import pytest
from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
INSTALL = load_module(ROOT / "scripts/production_installer.py", "ownership_commit_scope_backend")
CODEC = load_module(ROOT / "scripts/installation/ownership.py", "ownership_commit_scope_codec")


@pytest.mark.parametrize("retain_prior", [False, True])
def test_skipped_hook_capture_does_not_read_or_adopt_unselected_control(tmp_path, retain_prior):
    target = tmp_path / ".claude"
    target.mkdir()
    registration = target / "settings.json"
    foreign = b'{"agent":"user-agent","user-setting":true}\n'
    registration.write_bytes(foreign)
    key = ".claude/settings.json"
    prior = {key: {"kind": "hooks", "handlers": [], "agentAdded": True}} if retain_prior else {}
    documents = [tmp_path / path for path in INSTALL.get_client("claude")["documents"]["project"]]
    with INSTALL._InstallTransaction(documents, enabled=True) as transaction:
        owner = INSTALL._CreateOnlyMutablePath(tmp_path, transaction, dry_run=False)
        result = INSTALL._capture_provider_configs(
            ROOT, "claude", "project", target, tmp_path, owner, {}, prior,
            target / "CLAUDE.md", None, registration, target / "agents", False)
        assert result == prior
        assert registration.read_bytes() == foreign
        transaction.commit()


def test_selected_hook_capture_uses_admitted_control_and_refuses_foreign_bytes(tmp_path):
    target = tmp_path / ".claude"
    target.mkdir()
    registration = target / "settings.json"
    selected = b'{"agent":"lead","hooks":{}}\n'
    foreign = b'{"agent":"user-agent","hooks":{}}\n'
    registration.write_bytes(selected)
    documents = [tmp_path / path for path in INSTALL.get_client("claude")["documents"]["project"]]
    with INSTALL._InstallTransaction([*documents, registration], enabled=True) as transaction:
        owner = INSTALL._CreateOnlyMutablePath(tmp_path, transaction, dry_run=False)
        args = (ROOT, "claude", "project", target, tmp_path, owner,
                {registration: None}, {}, target / "CLAUDE.md", None,
                registration, target / "agents", True)
        assert INSTALL._capture_provider_configs(*args) == {
            ".claude/settings.json": {"kind": "hooks", "handlers": [], "agentAdded": True}}
        registration.write_bytes(foreign)
        try:
            with pytest.raises(ValueError, match="E_ROLLBACK_RESTORE_BLOCKED_BY_IDENTITY: producer input bytes"):
                INSTALL._capture_provider_configs(*args)
            assert registration.read_bytes() == foreign
        finally:
            registration.write_bytes(selected)
        transaction.commit()


def test_project_receipt_has_no_required_preference_file(tmp_path):
    target = tmp_path / ".claude"
    target.mkdir()
    owner = INSTALL._CreateOnlyMutablePath(
        tmp_path, INSTALL._InstallTransaction([], enabled=False), dry_run=False)
    registration = target / "settings.json"
    before = {registration: None}
    result = INSTALL._capture_provider_configs(
        ROOT, "claude", "project", target, tmp_path, owner, before, {},
        target / "CLAUDE.md", None, registration, target / "agents", False)
    assert result == {}
    assert not tuple(target.iterdir())


def test_global_receipt_preserves_unowned_sparse_preferences(tmp_path):
    target = tmp_path / ".claude"
    target.mkdir()
    mode = target / ".agents-mode.yaml"
    original = b"# Explicit user preference\r\nmcpMode: force\r\n"
    mode.write_bytes(original)
    owner = INSTALL._CreateOnlyMutablePath(
        tmp_path, INSTALL._InstallTransaction([], enabled=False), dry_run=False)
    registration = target / "settings.json"
    result = INSTALL._capture_provider_configs(
        ROOT, "claude", "global", target, tmp_path, owner,
        {mode: original.decode(), registration: None}, {},
        target / "CLAUDE.md", mode, registration, target / "agents", False)
    assert result == {}
    assert mode.read_bytes() == original


def test_install_record_excludes_transient_rollback_copies(tmp_path, monkeypatch):
    target = tmp_path / ".claude"
    skills = target / "skills"
    durable = skills / "demo/SKILL.md"
    retained_root = skills / ".orchestrarium-retained-example"
    retained = retained_root / "SKILL.md"
    node = SimpleNamespace(kind="file", data="a" * 64)
    transaction = SimpleNamespace(
        _original={skills: {}}, _expected={skills: {durable: node, retained: node}},
        paths=(skills,), _slice_a_created=[], _temporary=tmp_path / "backup",
        _migration_retention={}, _effects=[SimpleNamespace(retained=retained_root,
            prepared_path=None, quarantine=None)])
    received = []
    owner = SimpleNamespace(dry_run=False, anchor=tmp_path,
                            create_file=lambda relative, payload: received.append(payload))
    monkeypatch.setattr(INSTALL, "_read_owned_text", lambda *args, **kwargs: None)
    monkeypatch.setattr(INSTALL, "_capture_provider_configs", lambda *args: {})
    INSTALL._record_provider_install(ROOT, "claude", "target", target, tmp_path,
        transaction, owner, None, {}, target / "CLAUDE.md", target / ".agents-mode.yaml",
        target / "settings.json", target / "agents", False)
    record = CODEC.decode_record(received[0], "claude", "project")
    assert record["files"] == {durable.relative_to(tmp_path).as_posix(): "a" * 64}

def test_record_uses_admitted_skill_members_not_all_copied_legacy_files(tmp_path, monkeypatch):
    target = tmp_path / ".claude"
    skills = target / "skills"
    managed = skills / "demo/SKILL.md"
    extra = skills / "demo/user-extra.txt"
    node = SimpleNamespace(kind="file", data="a" * 64)
    transaction = SimpleNamespace(
        _original={skills: {managed: node, extra: node}},
        _expected={skills: {managed: node, extra: node}},
        paths=(skills,), _slice_a_created=[], _temporary=None,
        _migration_retention={}, _effects=[])
    received = []
    owner = SimpleNamespace(dry_run=False, anchor=tmp_path,
                            create_file=lambda relative, payload: received.append(payload))
    plan = SimpleNamespace(skills=(SimpleNamespace(name="demo"),),
        nonlead_expected=(("demo", (("SKILL.md", "a" * 64),)),),
        lead_receipt=None)
    monkeypatch.setattr(INSTALL, "_read_owned_text", lambda *args, **kwargs: None)
    monkeypatch.setattr(INSTALL, "_capture_provider_configs", lambda *args: {})
    INSTALL._record_provider_install(ROOT, "claude", "target", target, tmp_path,
        transaction, owner, None, {}, target / "CLAUDE.md", target / ".agents-mode.yaml",
        target / "settings.json", target / "agents", False,
        canonical_plan=plan, canonical_target=skills)
    record = CODEC.decode_record(received[0], "claude", "project")
    assert record["files"] == {managed.relative_to(tmp_path).as_posix(): "a" * 64}


def test_record_consumes_bound_transport_migration_not_path_census(tmp_path, monkeypatch):
    import hashlib
    target = tmp_path / '.claude'
    transport = target / 'agents'
    path = transport / 'scripts/example.py'
    manifest = transport / 'shared' / INSTALL.TRANSPORT_PROJECTION_MANIFEST
    payload, manifest_payload = b'new transport', b'qualified manifest'
    node = SimpleNamespace(kind='file', data=hashlib.sha256(payload).hexdigest())
    manifest_node = SimpleNamespace(kind='file', data=hashlib.sha256(manifest_payload).hexdigest())
    migration = SimpleNamespace(leaf_path=path)
    transaction = SimpleNamespace(
        _original={manifest: {}}, _expected={manifest: {manifest: manifest_node}},
        paths=(manifest,), _slice_a_created=[], _slice_a_migrated=[migration],
        _temporary=None, _migration_retention={}, _effects=[],
        _current_role=lambda record, old: node,
        _point_matches=lambda selected, expected, **kwargs: selected == path and expected is node)
    received = []
    owner = SimpleNamespace(dry_run=False, anchor=tmp_path,
        create_file=lambda relative, data: received.append(data))
    plan = SimpleNamespace(skills=(), nonlead_expected=(), lead_receipt=None,
        transport_stage=SimpleNamespace(files=(('example.py', payload),), manifest_payload=manifest_payload))
    monkeypatch.setattr(INSTALL, '_read_owned_text', lambda *args, **kwargs: None)
    monkeypatch.setattr(INSTALL, '_capture_provider_configs', lambda *args: {})
    INSTALL._record_provider_install(ROOT, 'claude', 'target', target, tmp_path,
        transaction, owner, None, {}, target / 'CLAUDE.md', target / '.agents-mode.yaml',
        target / 'settings.json', transport, False,
        canonical_plan=plan, canonical_target=target / 'skills')
    record = CODEC.decode_record(received[0], 'claude', 'project')
    assert record['files'][path.relative_to(tmp_path).as_posix()] == node.data
    transaction._point_matches = lambda *args, **kwargs: False
    import pytest
    with pytest.raises(INSTALL._InstallFailure, match='E_PROVIDER_RECEIPT_DRIFT'):
        INSTALL._record_provider_install(ROOT, 'claude', 'target', target, tmp_path,
            transaction, owner, None, {}, target / 'CLAUDE.md', target / '.agents-mode.yaml',
            target / 'settings.json', transport, False,
            canonical_plan=plan, canonical_target=target / 'skills')
    assert len(received) == 1
