"""Official agent SDK proposals have no installer/provider effects."""
import importlib.util
import os
from pathlib import Path
import shlex
import sys
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from installation.sdk_setup import SDK_PROVIDERS, setup_guidance


def load_installer():
    spec = importlib.util.spec_from_file_location("sdk_setup_installer", ROOT / "install.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("provider,package", [
    ("antigravity", "google-antigravity"), ("codex", "openai-codex"),
    ("claude", "claude-agent-sdk"), ("copilot", "microsoft-copilot-sdk"),
    ("kimi", "kimi-agent-sdk"),
])
def test_official_package_proposal_not_api_client_substitute(provider, package):
    text = setup_guidance(provider, "my worker/bin/python", windows=False)
    lines = text.splitlines()
    command = next(line for line in lines if " -m pip install " in line)
    assert shlex.split(command) == ["my worker/bin/python", "-m", "pip", "install", package]
    assert "--no-deps" not in text
    assert "nothing installed" in text
    assert "does not claim a new adapter" in text
    assert "Official package contents:" in text
    assert "Native Lead" in text


def test_grok_does_not_substitute_regular_api_or_cli():
    text = setup_guidance("grok", None)
    assert "No official agent SDK installation recipe has been verified" in text
    assert "pip install" not in text


@pytest.mark.parametrize("python", [None, "", " ", "bad\npython", "bad\rpython", "bad\0python"])
def test_explicit_worker_interpreter_required(python):
    with pytest.raises(ValueError, match="--sdk-python"):
        setup_guidance("codex", python)


def test_windows_command_quotes_exact_interpreter_not_shell_interpolation():
    text = setup_guidance("codex", "worker's $env/path/python.exe", windows=True)
    assert "& 'worker''s $env/path/python.exe' '-m' 'pip' 'install' 'openai-codex'" in text


def test_host_catalog_not_expanded_by_sdk_availability():
    from installation.clients import CLIENTS
    assert tuple(CLIENTS) == ("codex", "claude", "antigravity")
    assert {"copilot", "kimi", "grok"}.isdisjoint(CLIENTS)
    assert tuple(SDK_PROVIDERS)[0] == "antigravity"


@pytest.mark.parametrize("provider", list(SDK_PROVIDERS))
def test_guidance_never_runs_installation_or_provider(provider, capsys):
    installer = load_installer()
    with patch.object(installer, "_run_production", side_effect=AssertionError("host installation")), \
         patch("subprocess.run", side_effect=AssertionError("process")), \
         patch("subprocess.Popen", side_effect=AssertionError("provider")), \
         patch("builtins.input", side_effect=AssertionError("interactive input")):
        assert installer.main(["--sdk-setup", provider, "--sdk-python", "selected-python"]) == 0
    assert "Information only" in capsys.readouterr().out


@pytest.mark.parametrize("extra", [
    ["--clients", "codex"], ["--list-clients"], ["--global"],
    ["--dry-run"], ["--uninstall"], ["--apply"], ["--unknown"],
])
def test_guidance_does_not_swallow_or_forward_lifecycle_arguments(extra):
    installer = load_installer()
    with patch.object(installer, "_run_production", side_effect=AssertionError("host installation")):
        with pytest.raises(SystemExit) as exc:
            installer.main(["--sdk-setup", "codex", "--sdk-python", "selected-python", *extra])
    assert exc.value.code == 2


def test_interpreter_without_guidance_is_not_forwarded():
    installer = load_installer()
    with pytest.raises(SystemExit) as exc:
        installer.main(["--sdk-python", "selected-python", "--clients", "codex"])
    assert exc.value.code == 2


def test_sdk_setup_without_interpreter_reports_actionable_error(capsys):
    installer = load_installer()
    with pytest.raises(SystemExit) as exc:
        installer.main(["--sdk-setup", "codex"])
    assert exc.value.code == 2
    assert "--sdk-python" in capsys.readouterr().err


def test_runtime_disclosures_do_not_claim_binary_free_packages():
    assert "cli-bin" in setup_guidance("codex", "python")
    assert "compiled agent runtime" in setup_guidance("antigravity", "python")
    assert "Claude Code binary" in setup_guidance("claude", "python")
    assert "first managed use" in setup_guidance("copilot", "python")
    assert "legacy kimi-cli" in setup_guidance("kimi", "python")
    assert "does not establish compatibility" in setup_guidance("kimi", "python")


def fake_venv(directory):
    from installation.sdk_setup import environment_python
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'pyvenv.cfg').write_text('test marker', encoding='utf-8')
    python = environment_python(directory)
    python.parent.mkdir(parents=True, exist_ok=True)
    python.write_text('test placeholder', encoding='utf-8')


def test_venv_preview_has_no_effect(tmp_path):
    from installation.sdk_setup import setup_environment
    target = tmp_path / 'new env'
    with patch('subprocess.run', side_effect=AssertionError('preview execution')):
        assert setup_environment('codex', str(target)) == 0
    assert not target.exists()


@pytest.mark.parametrize("provider,package", [("codex", "openai-codex"), ("copilot", "microsoft-copilot-sdk")])
def test_apply_isolated_normal_pip_and_same_interpreter(tmp_path, monkeypatch, provider, package):
    import os
    from types import SimpleNamespace
    from installation.sdk_setup import setup_environment, environment_python
    target = tmp_path / 'worker env'
    calls = []
    for name in ('PIP_TARGET', 'PIP_PREFIX', 'PIP_USER', 'PIP_CONFIG_FILE', 'PYTHONPATH', 'PYTHONHOME'):
        monkeypatch.setenv(name, 'must-not-inherit')
    def run(command, *, env, check):
        calls.append((command, env))
        if 'venv' in command:
            fake_venv(target)
        return SimpleNamespace(returncode=10 if len(calls) == 2 else 0)
    with patch('subprocess.run', side_effect=run):
        assert setup_environment(provider, str(target), apply=True) == 0
    assert calls[0][0] == [sys.executable, '-I', '-m', 'venv', str(target)]
    assert calls[1][0][:5] == [str(environment_python(target)), '-I', '-S', '-B', '-c']
    assert calls[1][0][-2:] == [str(target), package]
    install = calls[2][0]
    assert install[:6] == [str(environment_python(target)), '-I', '-m', 'pip', '--isolated', 'install']
    assert '--upgrade' not in install
    assert '--no-deps' not in install and install[-1] == package
    assert install[install.index('--index-url') + 1] == 'https://pypi.org/simple'
    assert calls[3][0][-1] == 'check'
    assert calls[4][0] == calls[1][0]
    env = calls[0][1]
    assert env['PIP_CONFIG_FILE'] == os.devnull
    assert not any(key in env for key in ('PIP_TARGET', 'PIP_PREFIX', 'PIP_USER', 'PYTHONPATH', 'PYTHONHOME'))
    temporary = Path(env['TEMP'])
    assert temporary.parent == tmp_path and not temporary.exists()
    assert env['TMP'] == env['TMPDIR'] == str(temporary)


def test_existing_selected_venv_reused_and_unrelated_files_preserved(tmp_path):
    from types import SimpleNamespace
    from installation.sdk_setup import setup_environment
    fake_venv(tmp_path)
    marker = tmp_path / 'important.txt'
    marker.write_text('keep', encoding='utf-8')
    with patch('subprocess.run', return_value=SimpleNamespace(returncode=0)) as run:
        assert setup_environment('claude', str(tmp_path), apply=True) == 0
    assert len(run.call_args_list) == 1
    assert marker.read_text(encoding='utf-8') == 'keep'


@pytest.mark.parametrize('stage,status', [(0, 3), (1, 2), (2, 7), (3, 1), (4, 2)])
def test_failure_retains_state_and_returns_stage_status(tmp_path, capsys, stage, status):
    from types import SimpleNamespace
    from installation.sdk_setup import setup_environment
    target = tmp_path / 'worker'
    calls = []
    def run(command, *, env, check):
        index = len(calls)
        calls.append(command)
        if index == 0:
            fake_venv(target)
        return SimpleNamespace(returncode=status if index == stage else 10 if index == 1 else 0)
    with patch('subprocess.run', side_effect=run):
        assert setup_environment('codex', str(target), apply=True) == status
    assert len(calls) == stage + 1
    assert target.exists() and list(tmp_path.glob('.sdk-setup-*'))
    assert 'retained' in capsys.readouterr().err


def test_foreign_or_partial_directory_never_overwritten(tmp_path):
    from installation.sdk_setup import setup_environment
    marker = tmp_path / 'important.txt'
    marker.write_text('keep', encoding='utf-8')
    with patch('subprocess.run', side_effect=AssertionError('must not run')):
        with pytest.raises(ValueError, match='Repair it explicitly'):
            setup_environment('codex', str(tmp_path), apply=True)
    assert marker.read_text(encoding='utf-8') == 'keep'


def test_grok_apply_does_not_create_environment(tmp_path):
    from installation.sdk_setup import setup_environment
    target = tmp_path / 'unused'
    with patch('subprocess.run', side_effect=AssertionError('must not run')):
        assert setup_environment('grok', str(target), apply=True) == 2
    assert not target.exists()


def test_temp_creation_failure_returns_error(tmp_path, capsys):
    from installation.sdk_setup import setup_environment
    with patch('tempfile.mkdtemp', side_effect=OSError('disk unavailable')):
        assert setup_environment('codex', str(tmp_path / 'new'), apply=True) == 1
    assert 'disk unavailable' in capsys.readouterr().err


def test_cleanup_failure_does_not_mask_success(tmp_path, capsys):
    from types import SimpleNamespace
    from installation.sdk_setup import setup_environment
    fake_venv(tmp_path)
    with patch('subprocess.run', side_effect=[SimpleNamespace(returncode=value) for value in (10, 0, 0, 0)]), patch('shutil.rmtree', side_effect=OSError('busy')):
        assert setup_environment('codex', str(tmp_path), apply=True) == 0
    assert 'cleanup needs attention' in capsys.readouterr().err


def test_apply_only_routes_sdk_owner():
    installer = load_installer()
    with patch.object(installer, 'setup_environment', return_value=7) as setup, patch.object(installer, '_run_production', side_effect=AssertionError('host')):
        assert installer.main(['--sdk-setup', 'codex', '--sdk-venv', 'worker', '--apply']) == 7
    setup.assert_called_once_with('codex', 'worker', apply=True)


@pytest.mark.parametrize('args', [
    ['--sdk-venv', 'worker'],
    ['--sdk-setup', 'codex', '--sdk-python', 'python', '--sdk-venv', 'worker'],
    ['--sdk-setup', 'codex', '--sdk-venv', 'worker', '--uninstall', '--apply'],
])
def test_conflicting_apply_arguments_no_effect(args):
    installer = load_installer()
    with patch('subprocess.run', side_effect=AssertionError('must not run')):
        with pytest.raises(SystemExit) as exc:
            installer.main(args)
    assert exc.value.code == 2


def test_copilot_guidance_uses_current_official_package_without_runtime_execution():
    text = setup_guidance("copilot", "selected-python")
    assert "https://github.com/microsoft/copilot-sdk/blob/main/python/README.md" in text
    assert "github-copilot-sdk" not in text
    assert "pin the runtime version" in text
    assert "COPILOT_SKIP_CLI_DOWNLOAD=1" in text
    assert "COPILOT_CLI_PATH" in text
    assert "first managed use" in text
    assert "download-runtime" not in text


def test_present_metadata_has_no_install_effect(tmp_path, capsys):
    from types import SimpleNamespace
    from installation.sdk_setup import setup_environment
    fake_venv(tmp_path)
    with patch('subprocess.run', return_value=SimpleNamespace(returncode=0)) as run, \
         patch('tempfile.mkdtemp', side_effect=AssertionError('present environment has no writes')):
        assert setup_environment('codex', str(tmp_path), apply=True) == 0
    assert len(run.call_args_list) == 1
    assert 'pip' not in run.call_args.args[0]
    assert 'compatibility' in capsys.readouterr().out


def test_unknown_presence_leaves_environment_unchanged(tmp_path):
    from types import SimpleNamespace
    from installation.sdk_setup import setup_environment
    fake_venv(tmp_path)
    with patch('subprocess.run', return_value=SimpleNamespace(returncode=2)) as run, \
         patch('tempfile.mkdtemp', side_effect=AssertionError('unknown environment has no writes')):
        assert setup_environment('codex', str(tmp_path), apply=True) == 2
    assert len(run.call_args_list) == 1
    assert 'pip' not in run.call_args.args[0]


def test_isolated_metadata_probe_does_not_execute_pth_or_import_provider(tmp_path):
    import subprocess
    import sysconfig
    from installation.sdk_setup import _PRESENCE_PROBE, environment_python

    target = tmp_path / "worker env"
    subprocess.run([sys.executable, "-I", "-m", "venv", "--without-pip", str(target)], check=True)
    python = environment_python(target)
    site = Path(sysconfig.get_path("purelib", "venv", vars={"base": str(target), "platbase": str(target)}))
    site.mkdir(parents=True, exist_ok=True)
    sentinel = target / "startup-hook-ran"
    poison = f"from pathlib import Path; Path({str(sentinel)!r}).write_text('must not run')\n"
    (site / "startup.pth").write_text(
        f"import pathlib; pathlib.Path({str(sentinel)!r}).write_text('must not run')\n", encoding="utf-8")
    (site / "openai_codex.py").write_text(poison, encoding="utf-8")
    command = [str(python), "-I", "-S", "-B", "-c", _PRESENCE_PROBE, str(target), "openai-codex"]
    subprocess.run([str(python), "-I", "-B", "-c", "pass"], check=True, timeout=10)
    assert sentinel.exists()  # Prove the fixture executes when site startup is enabled.
    sentinel.unlink()

    def check(expected, selected=command):
        assert subprocess.run(selected, check=False, timeout=10).returncode == expected
        assert not sentinel.exists()

    check(10)
    first = site / "openai_codex-1.0.dist-info"
    first.mkdir()
    check(2)  # The matching distribution directory lacks its metadata.
    (first / "METADATA").write_text("Name: openai-codex\nVersion: 1.0\n", encoding="utf-8")
    check(0)
    check(2, [sys.executable, *command[1:]])  # Do not accept another environment's interpreter.
    second = site / "openai_codex-2.0.dist-info"
    second.mkdir()
    (second / "METADATA").write_text("Name: openai-codex\nVersion: 2.0\n", encoding="utf-8")
    check(2)
    cfg = target / "pyvenv.cfg"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace(
        "include-system-site-packages = false", "include-system-site-packages = true"),
        encoding="utf-8")
    check(2)


def test_isolated_metadata_probe_rejects_linked_metadata_leaf(tmp_path):
    import subprocess
    import sysconfig
    from installation.sdk_setup import _PRESENCE_PROBE, environment_python

    target = tmp_path / "worker"
    subprocess.run([sys.executable, "-I", "-m", "venv", "--without-pip", str(target)], check=True)
    site = Path(sysconfig.get_path("purelib", "venv", vars={"base": str(target), "platbase": str(target)}))
    distribution = site / "openai_codex-1.0.dist-info"
    distribution.mkdir(parents=True, exist_ok=True)
    leaf = distribution / "METADATA"
    outside = tmp_path / "outside-metadata"
    outside.write_text("Name: openai-codex\nVersion: 1.0\n", encoding="utf-8")
    try:
        leaf.symlink_to(outside)
    except OSError as exc:
        if os.name == "nt" and getattr(exc, "winerror", None) == 1314:
            pytest.skip("Windows symlink privilege unavailable")
        raise
    command = [str(environment_python(target)), "-I", "-S", "-B", "-c",
               _PRESENCE_PROBE, str(target), "openai-codex"]
    assert subprocess.run(command, check=False, timeout=10).returncode == 2
    leaf.unlink()
    leaf.write_text(outside.read_text(encoding="utf-8"), encoding="utf-8")
    assert subprocess.run(command, check=False, timeout=10).returncode == 0
