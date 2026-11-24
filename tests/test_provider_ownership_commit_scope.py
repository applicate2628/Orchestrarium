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


@pytest.mark.parametrize("case", [
    "external", "internal", "missing-binding", "wrong-transaction", "overlap",
    "retarget-at-receipt", "ordinary-alias", "ordinary-descendant",
    "skills-alias", "skills-descendant", "retarget-held",
])
def test_linked_payload_receipt_uses_admitted_physical_owner(tmp_path, monkeypatch, case):
    import hashlib
    import json
    from test_selected_claude_linked_physical import _link

    transaction_temp = tmp_path / "transaction-temp"
    transaction_temp.mkdir()
    monkeypatch.setattr(INSTALL.tempfile, "tempdir", str(transaction_temp))
    home = tmp_path / "home"
    target = home / ".claude"
    target.mkdir(parents=True)
    physical = (home if case == "internal" else tmp_path) / "physical-agents"
    if case in {"ordinary-alias", "ordinary-descendant", "skills-alias", "skills-descendant"}:
        physical = target / ("skills" if case.startswith("skills-") else "commands")
        if case.endswith("-descendant"):
            physical = physical / "nested"
    (physical / "scripts").mkdir(parents=True)
    (physical / "shared").mkdir()
    logical = target / "agents"
    _link(logical, physical)
    old = physical / "old-owned.md"
    old.write_bytes(b"retained prior ownership\n")
    neighbor = physical / "custom.md"
    neighbor.write_bytes(b"unowned neighbor\n")
    runtime = physical / "scripts/example.py"
    runtime.write_bytes(b"bound runtime\n")
    manifest = physical / "shared" / INSTALL.TRANSPORT_PROJECTION_MANIFEST
    manifest.write_bytes(b"bound manifest\n")
    prior_files = {".claude/agents/" + path.relative_to(physical).as_posix():
                   hashlib.sha256(path.read_bytes()).hexdigest() for path in (old, runtime, manifest)}
    before = CODEC.encode_record(prior_files, "claude", "global", configs={})
    receipt = target / CODEC.RECEIPT_NAME
    receipt.write_bytes(before)
    _, authority = INSTALL._resolve_global_claude_linked_subroot(ROOT, target, "global", "agents")
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    marker = foreign / "user.md"
    marker.write_bytes(b"foreign content\n")
    created = physical / "generated/new.md"
    plan = SimpleNamespace(skills=(), nonlead_expected=(), lead_receipt=None,
        transport_stage=SimpleNamespace(files=(("example.py", runtime.read_bytes()),),
            manifest_payload=manifest.read_bytes()))
    held_link = target / "held-original-link"
    replaced_link = target / "replaced-link"

    def capture(*args):
        if case in {"retarget-at-receipt", "retarget-held"}:
            logical.rename(held_link)
            _link(logical, foreign)
        return {}

    monkeypatch.setattr(INSTALL, "_capture_provider_configs", capture)

    def operation():
        with INSTALL._InstallTransaction([receipt, runtime, manifest, created.parent], enabled=True) as transaction:
            owner = INSTALL._CreateOnlyMutablePath(home, transaction, dry_run=False)
            physical_owner = INSTALL._CreateOnlyMutablePath(
                physical, transaction, dry_run=False, linked_authority=authority)
            bindings = (physical_owner,)
            if case == "missing-binding":
                bindings = ()
            elif case == "wrong-transaction":
                bindings = (INSTALL._CreateOnlyMutablePath(physical,
                    INSTALL._InstallTransaction([], enabled=False), dry_run=False, linked_authority=authority),)
            elif case == "overlap":
                _link(target / "commands", physical)
                _, commands_authority = INSTALL._resolve_global_claude_linked_subroot(ROOT, target, "global", "commands")
                bindings += (INSTALL._CreateOnlyMutablePath(
                    physical, transaction, dry_run=False, linked_authority=commands_authority),)
            physical_owner.create_file(created.relative_to(physical), b"new owned file\n")
            try:
                INSTALL._record_provider_install(ROOT, "claude", "global", target, home,
                    transaction, owner, before.decode("utf-8"), {}, target / "CLAUDE.md", None,
                    target / "settings.json", physical, False,
                    canonical_plan=plan, canonical_target=target / "skills", payload_owners=bindings)
            finally:
                if case != "retarget-held" and (held_link.exists() or held_link.is_symlink()):
                    logical.rename(replaced_link)
                    held_link.rename(logical)
            transaction.commit()

    if case in {"external", "internal"}:
        operation()
        received = CODEC.decode_record(receipt.read_bytes(), "claude", "global")
        assert received["files"] == {**prior_files,
            ".claude/agents/generated/new.md": hashlib.sha256(created.read_bytes()).hexdigest()}
        assert ".claude/agents/generated" in received["directories"]
    else:
        with pytest.raises((ValueError, RuntimeError), match="E_PROVIDER_RECEIPT_INVALID|E_RUNTIME_SUBROOT_IDENTITY_CHANGED|E_ROLLBACK") as failure:
            operation()
        assert receipt.read_bytes() == before
        if case == "retarget-held":
            assert isinstance(failure.value, INSTALL._InstallFailure)
            assert failure.value.stable_id == "E_ROLLBACK_SETTLEMENT_FAILED"
            assert failure.value.recovery_path is not None and failure.value.recovery_path.is_dir()
            assert created.read_bytes() == b"new owned file\n"
            assert logical.resolve() == foreign.resolve()
            evidence = {"failure": failure.value.stable_id,
                "recovery": str(failure.value.recovery_path), "retained_file": str(created),
                "receipt_restored": True, "foreign_content_preserved": marker.read_bytes() == b"foreign content\n"}
            (tmp_path / "recovery-observation.json").write_text(json.dumps(evidence, indent=2) + "\n")
            print("retarget-held:", json.dumps(evidence, sort_keys=True))
        else:
            assert not created.exists()
    assert neighbor.read_bytes() == b"unowned neighbor\n"
    assert marker.read_bytes() == b"foreign content\n"
    if case == "retarget-held":
        with pytest.raises(ValueError, match="E_RUNTIME_SUBROOT_IDENTITY_CHANGED"):
            authority.assert_current()
    else:
        authority.assert_current()


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
    plan = SimpleNamespace(skills=(SimpleNamespace(name="demo", managed_before=None),),
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


@pytest.mark.parametrize("mutation", ["none", "selected-update", "foreign-bytes", "foreign-identity"])
def test_record_consumes_managed_member_image_without_expanding_mutation_paths(tmp_path, monkeypatch, mutation):
    import shutil

    target = tmp_path / ".claude"
    skills = target / "skills"
    installed = skills / "demo"
    (installed / "agents").mkdir(parents=True)
    body = installed / "SKILL.md"
    body.write_bytes(b"owned body\n")
    unchanged = installed / "agents/openai.yaml"
    unchanged.write_bytes(b"owned metadata\n")
    managed_before = INSTALL._stage_tree_manifest(installed)
    source = tmp_path / "source/demo"
    shutil.copytree(installed, source)
    extra = installed / "operator-note.txt"
    extra.write_bytes(b"protected operator content\n")
    if mutation == "selected-update":
        (source / "SKILL.md").write_bytes(b"updated owned body\n")
    member = INSTALL._plan_canonical_skill_members(
        INSTALL._CanonicalSkillPlan("demo", source, INSTALL._tree_sha256(source),
            INSTALL._tree_sha256(installed), None, True), installed, managed_before, None)
    plan = SimpleNamespace(skills=(member,), nonlead_expected=(("demo", member.managed_after),),
        lead_receipt=None, member_selection=None)
    receipt = target / CODEC.RECEIPT_NAME
    paths = [receipt, *INSTALL._canonical_skill_snapshot_paths(skills, plan)]
    assert all(path != unchanged and path not in unchanged.parents for path in paths)
    monkeypatch.setattr(INSTALL, "_capture_provider_configs", lambda *args: {})
    with INSTALL._InstallTransaction(paths, enabled=True) as transaction:
        owner = INSTALL._CreateOnlyMutablePath(tmp_path, transaction, dry_run=False)
        if mutation == "selected-update":
            owner.migrate_exact_file(body.relative_to(tmp_path), dict(managed_before)["SKILL.md"],
                (source / "SKILL.md").read_bytes(), retention_parent=target.relative_to(tmp_path))
        elif mutation == "foreign-bytes":
            unchanged.write_bytes(b"foreign changed metadata\n")
        elif mutation == "foreign-identity":
            replacement = tmp_path / "replacement.yaml"
            replacement.write_bytes(unchanged.read_bytes())
            replacement.replace(unchanged)
        record = lambda: INSTALL._record_provider_install(
            ROOT, "claude", "target", target, tmp_path, transaction, owner, None, {},
            target / "CLAUDE.md", None, target / "settings.json", target / "agents", False,
            canonical_plan=plan, canonical_target=skills)
        if mutation.startswith("foreign-"):
            foreign = INSTALL._InstallTransaction._capture_node(unchanged)
            with pytest.raises(ValueError, match="E_CANONICAL_SKILLS_RECEIPT_DRIFT"):
                record()
            assert not receipt.exists()
            assert INSTALL._InstallTransaction._point_matches(unchanged, foreign, check_file_content=True)
        else:
            record()
            received = CODEC.decode_record(receipt.read_bytes(), "claude", "project")
            assert received["files"] == {
                (installed / relative).relative_to(tmp_path).as_posix(): digest
                for relative, digest in member.managed_after if digest != "directory"}
            assert extra.relative_to(tmp_path).as_posix() not in received["files"]
        assert extra.read_bytes() == b"protected operator content\n"
        transaction.commit()
