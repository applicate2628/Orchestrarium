"""Official agent SDK proposals have no installer/provider effects."""
import importlib.util
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
    ("claude", "claude-agent-sdk"), ("copilot", "github-copilot-sdk"),
    ("kimi", "kimi-agent-sdk"),
])
def test_official_package_proposal_not_api_client_substitute(provider, package):
    text = setup_guidance(provider, "my worker/bin/python", windows=False)
    lines = text.splitlines()
    command = next(line for line in lines if " -m pip install " in line)
    assert shlex.split(command) == ["my worker/bin/python", "-m", "pip", "install", "--upgrade", package]
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
    assert "& 'worker''s $env/path/python.exe' '-m' 'pip' 'install' '--upgrade' 'openai-codex'" in text


def test_host_catalog_not_expanded_by_sdk_availability():
    from installation.clients import CLIENTS
    assert tuple(CLIENTS) == ("codex", "claude")
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
