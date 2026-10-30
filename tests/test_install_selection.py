"""The common console front door selects; existing installers own effects."""
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]

@pytest.fixture
def installer(monkeypatch):
    spec = importlib.util.spec_from_file_location('root_selection_installer', ROOT / 'install.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []
    monkeypatch.setattr(module, '_run_production', lambda name, args: calls.append((name, list(args))) or 0)
    monkeypatch.setattr(module.sys.stdin, 'isatty', lambda: True)
    return module, calls


def answer(monkeypatch, *answers):
    values = iter(answers)
    monkeypatch.setattr('builtins.input', lambda prompt: next(values))


def test_explicit_clients_forward_existing_installer_arguments(installer):
    module, calls = installer
    assert module.main(['--clients', 'claude', 'codex', '--target', '/tmp/two words', '--dry-run']) == 0
    assert calls == [('codex', ['--target', '/tmp/two words', '--dry-run']),
                     ('claude', ['--target', '/tmp/two words', '--dry-run'])]


def test_duplicate_clients_do_not_duplicate_operations(installer):
    module, calls = installer
    assert module.main(['--clients', 'codex', 'codex', '--global']) == 0
    assert calls == [('codex', ['--global'])]


def test_noninteractive_without_selection_has_no_effect(installer, monkeypatch):
    module, calls = installer
    monkeypatch.setattr(module.sys.stdin, 'isatty', lambda: False)
    assert module.main(['--global']) == 2
    assert not calls


@pytest.mark.parametrize('choice', ['q', '', '3', '999', '1,garbage'])
def test_cancel_or_invalid_selection_never_expands_scope(installer, monkeypatch, choice):
    module, calls = installer
    answer(monkeypatch, choice)
    assert module.main(['--global']) in (0, 2)
    assert not calls


def test_menu_previews_then_applies_exact_selected_clients(installer, monkeypatch):
    module, calls = installer
    answer(monkeypatch, '2,1', 'y')
    assert module.main(['--global']) == 0
    assert calls == [('codex', ['--global', '--dry-run']), ('claude', ['--global', '--dry-run']),
                     ('codex', ['--global']), ('claude', ['--global'])]


def test_cancel_after_preview_never_applies(installer, monkeypatch):
    module, calls = installer
    answer(monkeypatch, '1', 'n')
    assert module.main(['--global']) == 0
    assert calls == [('codex', ['--global', '--dry-run'])]


def test_preview_failure_blocks_apply(installer, monkeypatch):
    module, calls = installer
    answer(monkeypatch, '1')
    monkeypatch.setattr(module, '_run_production', lambda name, args: calls.append((name, args)) or 7)
    assert module.main(['--global']) == 7
    assert calls == [('codex', ['--global', '--dry-run'])]


def test_list_clients_never_invokes_installer(installer):
    module, calls = installer
    assert module.main(['--list-clients']) == 0
    assert not calls


def test_uninstall_menu_requires_confirmation_then_sets_apply(installer, monkeypatch):
    module, calls = installer
    answer(monkeypatch, "2", "y")
    assert module.main(["--uninstall", "--global"]) == 0
    assert calls == [("claude", ["--uninstall", "--global", "--dry-run"]),
                     ("claude", ["--uninstall", "--global", "--apply"])]


def test_every_client_uses_one_command_entrypoint(monkeypatch):
    from types import SimpleNamespace
    spec = importlib.util.spec_from_file_location("common_client_entry_test", ROOT / "install.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []
    monkeypatch.setattr(module.subprocess, "run", lambda argv, **kw: calls.append(argv) or SimpleNamespace(returncode=0))
    for name, _ in module.CLIENTS:
        assert module._run_production(name, ["--dry-run"]) == 0
    assert all(Path(argv[1]).name == "install-client.py" and argv[2] == "--client" for argv in calls)
    assert [argv[3] for argv in calls] == [name for name, _ in module.CLIENTS]


def test_primary_client_and_unknown_adapter_fail_closed(installer):
    module, calls = installer
    assert [name for name, client in module.CLIENT_CATALOG.items() if client["primary"]] == ["codex"]
    with pytest.raises(SystemExit):
        module.main(["--clients", "unknown-host", "--global"])
    assert calls == []


def test_partial_uninstall_reports_preserved_state_and_unattempted_clients(installer, monkeypatch, capsys):
    module, calls = installer
    monkeypatch.setattr(module, '_run_production', lambda name, args: calls.append((name,args)) or 2)
    assert module.main(['--clients','codex','claude','--global','--uninstall','--apply']) == 2
    output=capsys.readouterr().out
    assert 'STOPPED (2)' in output and 'installer report' in output.lower()
    assert 'claude: NOT ATTEMPTED' in output
    assert len(calls)==1


def test_successful_preview_is_not_reported_as_applied(installer, capsys):
    module, calls=installer
    assert module.main(['--clients','codex','--global','--dry-run'])==0
    assert 'PREVIEW' in capsys.readouterr().out


def test_conflicting_lifecycle_operations_are_rejected_before_install():
    from _module_loading_support import load_module
    backend=load_module(ROOT/'scripts/production_installer.py','exclusive_lifecycle_ops')
    assert backend.install('codex', ['--uninstall','--materialize-legacy-skills','--apply']) == 2


def test_legacy_dryrun_alias_never_prompts_for_apply(installer,monkeypatch,capsys):
    module,calls=installer
    answer(monkeypatch,'1')
    assert module.main(['--global','-DryRun'])==0
    assert calls==[('codex',['--global','-DryRun'])]
    assert 'PREVIEW COMPLETE' in capsys.readouterr().out
