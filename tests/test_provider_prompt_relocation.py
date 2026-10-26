from __future__ import annotations

import hashlib
import importlib.util
import runpy
from types import SimpleNamespace
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
ROOT_OWNER = ROOT / "scripts" / "provider_prompt.py"
CLAUDE_SCRIPTS = ROOT / "src.claude" / "agents" / "scripts"


def test_root_is_the_only_authored_transport_owner() -> None:
    assert ROOT_OWNER.is_file()
    assert not (CLAUDE_SCRIPTS / "provider_prompt.py").exists()


def test_codex_and_claude_host_wrappers_remain_thin_adjacent_consumers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    monkeypatch.setitem(sys.modules, "provider_prompt", SimpleNamespace(
        launch=lambda provider, argv: calls.append((provider, argv)) or 17,
    ))
    for provider in ("codex", "claude"):
        python_wrapper = CLAUDE_SCRIPTS / f"invoke-{provider}-prompt.py"
        shell_wrapper = CLAUDE_SCRIPTS / f"invoke-{provider}-prompt.sh"
        assert python_wrapper.is_file()
        assert shell_wrapper.is_file()
        python_text = python_wrapper.read_text(encoding="utf-8")
        assert "from provider_prompt import launch" in python_text
        argv = ["fixture", "--prompt-file", "synthetic-task.md"]
        monkeypatch.setattr(sys, "argv", [str(python_wrapper), *argv])
        with pytest.raises(SystemExit) as result:
            runpy.run_path(str(python_wrapper), run_name="__main__")
        assert result.value.code == 17
        assert calls.pop() == (provider, argv)
        assert "provider_prompt.py" not in shell_wrapper.read_text(encoding="utf-8")


def _load_owner(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_ledger_source_pairing_ignores_a_cwd_owner(tmp_path, monkeypatch):
    module = _load_owner(ROOT_OWNER, 'ledger_source_association')
    decoy = tmp_path / 'scripts'
    decoy.mkdir()
    (decoy / 'agent-run-ledger.py').write_text('raise AssertionError("cwd owner")\n', encoding='utf-8')
    monkeypatch.chdir(tmp_path)
    assert module.ledger_helper().samefile(ROOT / 'scripts/agent-run-ledger.py')
    assert Path(module._ledger_owner().__file__).samefile(ROOT / 'scripts/agent-run-ledger.py')


def _ledger_project_scope(tmp_path, *, provider_target=None):
    from test_legacy_obligation_migration import make_directory_link
    base = tmp_path / 'scope'
    canonical = base / '.agents/skills/lead'
    provider_root = base / '.claude' if provider_target is None else provider_target
    assert provider_root.parent == base
    marker = tmp_path / 'selected-ledger-executed'
    for relative in ('scripts/agent-run-ledger.py', 'scripts/validate-work-item-state.py',
            'scripts/mutate-work-item.py', 'scripts/solution_attempt/reducer.py',
            'shared/schemas/agent-runs.schema.json'):
        path = canonical / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'# synthetic ordinary member\n')
    (canonical / 'scripts/agent-run-ledger.py').write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n", encoding='utf-8')
    for name in ('provider_prompt.py', 'linked_runtime_subroots.py'):
        (canonical / 'scripts' / name).write_bytes((ROOT / 'scripts' / name).read_bytes())
    peer = provider_root / 'agents/scripts/provider_prompt.py'
    peer.parent.mkdir(parents=True)
    peer.write_bytes(ROOT_OWNER.read_bytes())
    projection = provider_root / 'skills/lead'
    projection.parent.mkdir(parents=True)
    make_directory_link(projection, canonical)
    module = _load_owner(peer, 'projection_bound_ledger_' + str(id(tmp_path)))
    return module, base, canonical, projection, marker


def test_ledger_binding_retains_actual_installer_target_spelling(tmp_path, monkeypatch):
    import os
    from test_provider_prompt_projections import _load_installer
    installer = _load_installer()
    requested = tmp_path / 'scope' / '.ClAuDe'
    args = SimpleNamespace(global_install=False, target=os.fspath(requested), allow_unsafe_target=True)
    mode, target, project = installer._target('claude', args)
    assert mode == 'target' and os.fspath(target) == os.fspath(requested)
    assert os.fspath(project) == os.fspath(requested.parent)
    home = tmp_path / 'owned-home'
    home.mkdir()
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
    module, base, canonical, projection, marker = _ledger_project_scope(tmp_path, provider_target=target)
    binding = module._ledger_helper_binding()
    assert binding is not None
    # Compare actual path objects' spelling: WindowsPath equality casefolds.
    assert [os.fspath(row[0]) for row in binding.roots] == [
        os.fspath(base / '.agents'), os.fspath(target / 'agents'), os.fspath(target / 'skills'),
    ]
    assert binding.helper.samefile(canonical / 'scripts/agent-run-ledger.py')
    binding.assert_current()
    assert not marker.exists()


@pytest.mark.parametrize('use', ['inprocess', 'subprocess'])
def test_ledger_projection_witness_survives_until_actual_use(tmp_path, monkeypatch, use):
    from test_legacy_obligation_migration import make_directory_link
    module, base, canonical, projection, marker = _ledger_project_scope(tmp_path)
    selected = module._ledger_helper_binding()
    assert selected is not None
    unrelated = tmp_path / 'unrelated-lead'
    unrelated.mkdir()
    before = projection.resolve(strict=True)
    projection.rmdir()
    make_directory_link(projection, unrelated)
    assert projection.resolve(strict=True) != before
    monkeypatch.setattr(module, '_ledger_helper_binding', lambda: selected)
    if use == 'inprocess':
        with pytest.raises(ValueError, match='WI-LEDGER-RESOURCE-DRIFT'):
            module._ledger_owner()
    else:
        executed = []
        with module.ProcessRunnerV1() as runner:
            monkeypatch.setattr(runner, 'run', lambda request: executed.append(True))
            assert module.run_ledger(runner, ['--work-item', 'unselected', 'rollup']) is False
        assert executed == []
    assert not marker.exists()


def test_ledger_projection_is_rechecked_before_canonical_bootstrap(tmp_path, monkeypatch):
    from test_legacy_obligation_migration import make_directory_link
    module, base, canonical, projection, marker = _ledger_project_scope(tmp_path)
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: base))
    authority = canonical / 'scripts/linked_runtime_subroots.py'
    bootstrap_marker = tmp_path / 'bootstrap-executed'
    authority.write_bytes(authority.read_bytes() +
        f"\nfrom pathlib import Path\nPath({str(bootstrap_marker)!r}).write_text('executed')\n".encode())
    unrelated = tmp_path / 'unrelated-lead'
    unrelated.mkdir()
    read, reached = Path.read_bytes, []
    def read_then_retarget(path):
        payload = read(path)
        if path == authority:
            projection.rmdir()
            make_directory_link(projection, unrelated)
            reached.append(True)
        return payload
    monkeypatch.setattr(Path, 'read_bytes', read_then_retarget)
    assert module.ledger_helper() is None
    assert reached == [True] and not bootstrap_marker.exists() and not marker.exists()


def test_ledger_initial_wrong_projection_and_unrelated_file_do_not_change_scope(tmp_path):
    from test_legacy_obligation_migration import make_directory_link
    module, base, canonical, projection, marker = _ledger_project_scope(tmp_path)
    selected = module._ledger_helper_binding()
    assert selected is not None
    (canonical / 'unrelated-note.txt').write_text('Unselected ordinary state.\n', encoding='utf-8')
    selected.assert_current()
    unrelated = tmp_path / 'unrelated-lead'
    unrelated.mkdir()
    projection.rmdir()
    make_directory_link(projection, unrelated)
    assert module.ledger_helper() is None
    with pytest.raises(ValueError, match='WI-LEDGER-RESOURCE-MISSING'):
        module._ledger_owner()
    assert not marker.exists()


def test_ledger_ambiguous_global_module_association_refuses_before_code(tmp_path, monkeypatch):
    from test_legacy_obligation_migration import make_directory_link
    module, base, canonical, projection, marker = _ledger_project_scope(tmp_path)
    peer = base / '.claude/agents'
    saved = peer.with_name('retained-agents')
    assert not saved.exists() and peer.is_relative_to(tmp_path)
    peer.rename(saved)
    make_directory_link(peer, canonical)
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: base))
    module = _load_owner(canonical / 'scripts/provider_prompt.py', 'ambiguous_ledger_owner')
    assert module.ledger_helper() is None
    with pytest.raises(ValueError, match='WI-LEDGER-RESOURCE-MISSING'):
        module._ledger_owner()
    assert not marker.exists()


def test_global_ledger_owner_binds_distinct_logical_backings(tmp_path, monkeypatch):
    import os
    import shutil
    from test_provider_prompt_projections import _load_installer, _linked_global_claude, _linked_global_canonical_agents
    installer = _load_installer()
    logical, peer_backing = _linked_global_claude(tmp_path, monkeypatch, installer)
    agents, canonical_backing = _linked_global_canonical_agents(tmp_path, logical.parent)
    marker = tmp_path / 'peer-bootstrap-executed'
    (peer_backing / 'agents/scripts/linked_runtime_subroots.py').write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n", encoding='utf-8')
    expected = canonical_backing / 'skills/lead/scripts/agent-run-ledger.py'
    for index, module_path in enumerate((logical / 'agents/scripts/provider_prompt.py',
            peer_backing / 'agents/scripts/provider_prompt.py',
            agents / 'skills/lead/scripts/provider_prompt.py')):
        module = _load_owner(module_path, 'linked_ledger_owner_' + str(index))
        assert module.ledger_helper().samefile(expected)
        assert Path(module._ledger_owner().__file__).samefile(expected)
    shaped = tmp_path / 'shaped-backing/.claude/agents'
    shutil.copytree(peer_backing / 'agents', shaped)
    (logical / 'agents').unlink()
    os.symlink(shaped, logical / 'agents', target_is_directory=True)
    module = _load_owner(shaped / 'scripts/provider_prompt.py', 'shaped_global_ledger_owner')
    assert module.ledger_helper().samefile(expected)
    assert Path(module._ledger_owner().__file__).samefile(expected)
    assert not marker.exists()


@pytest.mark.parametrize('missing', ['agent-run-ledger.py', 'mutate-work-item.py'])
def test_current_claude_missing_canonical_member_never_uses_peer_or_cwd(tmp_path, monkeypatch, missing):
    from test_provider_prompt_projections import _load_installer
    installer = _load_installer()
    target = tmp_path / 'target'
    target.mkdir()
    assert installer.install('claude', ['--target', str(target), '--force', '--allow-unsafe-target', '--no-hypothesis-hook']) == 0
    (target / '.agents/skills/lead/scripts' / missing).unlink()
    decoy = tmp_path / 'cwd/scripts'
    decoy.mkdir(parents=True)
    marker = tmp_path / 'cwd-ledger-executed'
    (decoy / 'agent-run-ledger.py').write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n", encoding='utf-8')
    monkeypatch.chdir(decoy.parent)
    module = _load_owner(target / '.claude/agents/scripts/provider_prompt.py', 'missing_current_ledger_' + missing)
    assert module.ledger_helper() is None
    with pytest.raises(ValueError, match='WI-LEDGER-RESOURCE-MISSING'):
        module._ledger_owner()
    with module.ProcessRunnerV1() as runner:
        assert module.run_ledger(runner, ['--work-item', 'unselected', 'rollup']) is False
    assert not marker.exists()


@pytest.mark.parametrize('use', ['inprocess', 'subprocess'])
def test_ledger_global_link_drift_is_checked_at_actual_use(tmp_path, monkeypatch, use):
    import shutil
    import os
    from test_provider_prompt_projections import _load_installer, _linked_global_claude, _linked_global_canonical_agents
    installer = _load_installer()
    logical, _peer_backing = _linked_global_claude(tmp_path, monkeypatch, installer)
    agents, backing = _linked_global_canonical_agents(tmp_path, logical.parent)
    replacement = tmp_path / 'replacement-agents'
    shutil.copytree(backing, replacement)
    module = _load_owner(logical / 'agents/scripts/provider_prompt.py', 'ledger_binding_drift_' + use)
    reached, executed = [], []
    def retarget():
        agents.unlink()
        os.symlink(replacement, agents, target_is_directory=True)
        reached.append(True)
    if use == 'inprocess':
        original = module.importlib.util.spec_from_file_location
        def prepare_then_retarget(name, path, *args, **kwargs):
            spec = original(name, path, *args, **kwargs)
            if name == '_provider_paired_ledger_owner':
                execute = spec.loader.exec_module
                def observed(value):
                    executed.append(True)
                    return execute(value)
                spec.loader.exec_module = observed
                retarget()
            return spec
        monkeypatch.setattr(module.importlib.util, 'spec_from_file_location', prepare_then_retarget)
        with pytest.raises(ValueError, match='WI-LEDGER-RESOURCE-DRIFT'):
            module._ledger_owner()
    else:
        original = module._runner_support_environment
        def prepare_then_retarget(source):
            result = original(source)
            retarget()
            return result
        monkeypatch.setattr(module, '_runner_support_environment', prepare_then_retarget)
        with module.ProcessRunnerV1() as runner:
            monkeypatch.setattr(runner, 'run', lambda request: executed.append(True))
            assert module.run_ledger(runner, ['--work-item', 'unselected', 'rollup']) is False
    assert reached == [True] and executed == []


def test_role_taxonomy_rejects_a_malicious_cwd_resolver_before_secret_or_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the exact sibling is a trust input; cwd is never a resolver fallback."""

    owner = _load_owner(ROOT_OWNER, "provider_prompt_taxonomy_cwd")
    malicious = tmp_path / "cwd" / "scripts" / "resolve-agents-mode.py"
    malicious.parent.mkdir(parents=True)
    marker = tmp_path / "resolver-side-effect"
    malicious.write_text(
        "from pathlib import Path\n"
        "import os\n"
        f"Path({str(marker)!r}).write_text(os.environ['TAXONOMY_SECRET'])\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(owner, "__file__", str(tmp_path / "isolated" / "provider_prompt.py"))
    monkeypatch.chdir(malicious.parent.parent)
    monkeypatch.setenv("TAXONOMY_SECRET", "must-not-be-read")
    monkeypatch.setattr(
        owner.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no process")),
    )

    with pytest.raises(ValueError, match="^E_EXTERNAL_PROVENANCE_ROLE_INVALID: role taxonomy"):
        owner.external_role_provenance(
            owner.Control(ledger_role="qa-engineer", ledger_role_explicit=True), "codex"
        )

    assert not marker.exists()


def test_role_taxonomy_rejects_malformed_or_linked_sibling(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner(ROOT_OWNER, "provider_prompt_taxonomy_degraded")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    sibling = scripts / "external-role-taxonomy.v1.json"
    sibling.write_text('{"schemaVersion": 1, "roles": {}}\n', encoding="utf-8")
    monkeypatch.setattr(owner, "__file__", str(scripts / "provider_prompt.py"))

    with pytest.raises(
        ValueError, match="^E_EXTERNAL_PROVENANCE_ROLE_TAXONOMY_INTEGRITY$"
    ):
        owner._external_role_taxonomy()

    linked = scripts / "linked-taxonomy.json"
    linked.write_bytes((ROOT / "shared" / "external-role-taxonomy.v1.json").read_bytes())
    sibling.unlink()
    try:
        sibling.symlink_to(linked)
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    with pytest.raises(ValueError, match="^E_EXTERNAL_PROVENANCE_ROLE_INVALID: role taxonomy"):
        owner._external_role_taxonomy()


def test_role_taxonomy_loads_only_the_structured_sibling_taxonomy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner(ROOT_OWNER, "provider_prompt_taxonomy_attested")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    sibling = scripts / "external-role-taxonomy.v1.json"
    payload = (ROOT / "shared" / "external-role-taxonomy.v1.json").read_bytes()
    sibling.write_bytes(payload)
    monkeypatch.setattr(owner, "__file__", str(scripts / "provider_prompt.py"))

    roles, reviewers, workers, unsupported = owner._external_role_taxonomy()

    assert "qa-engineer" in roles
    assert "frontend-engineer" in roles
    assert "qa-engineer" in reviewers
    assert workers
    assert unsupported == {
        "product-manager",
        "lead",
        "knowledge-archivist",
        "external-worker",
        "external-reviewer",
    }


@pytest.mark.parametrize("mutation", ("lane", "whitespace"))
def test_role_taxonomy_rejects_schema_valid_byte_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str
) -> None:
    owner = _load_owner(ROOT_OWNER, f"provider_prompt_taxonomy_drift_{mutation}")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    payload = (ROOT / "shared" / "external-role-taxonomy.v1.json").read_bytes()
    if mutation == "lane":
        payload = payload.replace(b'"external-worker"', b'"external-reviewer"', 1)
    else:
        payload += b"\n"
    (scripts / "external-role-taxonomy.v1.json").write_bytes(payload)
    monkeypatch.setattr(owner, "__file__", str(scripts / "provider_prompt.py"))

    with pytest.raises(
        ValueError,
        match="^E_EXTERNAL_PROVENANCE_ROLE_TAXONOMY_INTEGRITY$",
    ):
        owner._external_role_taxonomy()


def test_roleless_provenance_still_attests_taxonomy_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    owner = _load_owner(ROOT_OWNER, "provider_prompt_taxonomy_roleless_drift")
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    payload = (ROOT / "shared" / "external-role-taxonomy.v1.json").read_bytes() + b"\n"
    (scripts / "external-role-taxonomy.v1.json").write_bytes(payload)
    monkeypatch.setattr(owner, "__file__", str(scripts / "provider_prompt.py"))

    with pytest.raises(
        ValueError,
        match="^E_EXTERNAL_PROVENANCE_ROLE_TAXONOMY_INTEGRITY$",
    ):
        owner.external_role_provenance(owner.Control(), "claude")


def test_packed_capsule_view_needs_manifest_and_digest_not_shared_agents(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    pack_root = tmp_path / ".agents" / "skills"
    scripts = pack_root / "lead" / "scripts"
    scripts.mkdir(parents=True)
    (pack_root / "shared").mkdir()
    for name in (
        "provider_prompt.py",
        "external-prompt-governance.md",
        "external-role-taxonomy.v1.json",
    ):
        source = ROOT / (
            "shared"
            if name in {"external-prompt-governance.md", "external-role-taxonomy.v1.json"}
            else "scripts"
        ) / name
        (scripts / name).write_bytes(source.read_bytes())
    (pack_root / "shared" / "provider-prompt-projections.v1.json").write_bytes(
        (ROOT / "shared" / "provider-prompt-projections.v1.json").read_bytes()
    )
    owner = _load_owner(scripts / "provider_prompt.py", "provider_prompt_packed_view")
    monkeypatch.setattr(
        owner.subprocess,
        "Popen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("no process")),
    )

    assert owner.external_governance_capsule_snapshot() == (
        ROOT / "shared" / "external-prompt-governance.md"
    ).read_bytes()
    assert owner.launch("kimi", ["ignored-invalid-input"]) == 1


def test_canonical_scope_preserves_ordinary_descendant_guard(tmp_path, monkeypatch):
    from test_legacy_obligation_migration import make_directory_link
    _module, base, canonical, _projection, marker = _ledger_project_scope(tmp_path)
    home = tmp_path / 'owned-home'
    home.mkdir()
    monkeypatch.setattr(Path, 'home', classmethod(lambda cls: home))
    ordinary = _load_owner(canonical / 'scripts/provider_prompt.py', 'ordinary_canonical_case_guard')
    assert ordinary.ledger_helper().samefile(canonical / 'scripts/agent-run-ledger.py')
    retained = tmp_path / 'retained-lead'
    canonical.rename(retained)
    make_directory_link(canonical, retained)
    linked = _load_owner(canonical / 'scripts/provider_prompt.py', 'linked_canonical_case_guard')
    assert linked.ledger_helper() is None
    assert not marker.exists()
