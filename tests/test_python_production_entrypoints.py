"""Regression tests for Python-owned production entrypoints and retirement."""
from __future__ import annotations

import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PS1 = {
    "scripts/install-gemini.ps1",
    "scripts/install-qwen.ps1",
    "src.gemini/scripts/validate-pack.ps1",
    "src.qwen/scripts/validate-pack.ps1",
}
EXAMPLE_SHELL_ENTRYPOINTS = {
    "scripts/install-gemini.sh",
    "scripts/install-qwen.sh",
}
DEPRECATED_EXAMPLE_COMPATIBILITY_SHELL_ENTRYPOINTS = frozenset(
    {"scripts/universal-hooks/scripts/mcp-usage-reminder.sh"}
)
PRODUCTION_SHELL_ENTRYPOINTS = frozenset(
    {
        "install.sh",
        "scripts/agent-run-ledger.sh",
        "scripts/check-publication-gate.sh",
        "scripts/check-work-items-state.sh",
        "scripts/install-claude.sh",
        "scripts/install-codex.sh",
        "scripts/universal-hooks/scripts/check-publication-safety.sh",
        "scripts/validate-review-loop-state.sh",
        "scripts/validate-work-item-state.sh",
        "src.claude/agents/scripts/await-codex-dispatch.sh",
        "src.claude/agents/scripts/check-publication-safety.sh",
        "src.claude/agents/scripts/invoke-claude-api.sh",
        "src.claude/agents/scripts/invoke-claude-prompt.sh",
        "src.claude/agents/scripts/invoke-codex-prompt.sh",
        "src.claude/agents/scripts/validate-skill-pack.sh",
        "src.codex/skills/lead/scripts/check-publication-safety.sh",
        "src.codex/skills/lead/scripts/validate-skill-pack.sh",
    }
)
BASH = shutil.which("bash")
BASH_SMOKE_AVAILABLE = BASH is not None and os.name != "nt"
EARLY_AGENT_INSTRUCTIONS = {
    "default.toml": """General-purpose fallback agent.
Inherit the parent session's task context and focus on the assigned subtask.
Stay within the requested scope and return a concise, usable result.""",
    "explorer.toml": """Read-heavy codebase exploration agent.
Stay in exploration mode, gather evidence efficiently, and return factual findings with clear pointers.
Do not drift into implementation unless the parent explicitly asks for it.""",
    "worker.toml": """Execution-focused agent for implementation and fixes.
Carry out the assigned implementation task directly, stay within scope, and avoid redesign unless the parent explicitly asks for it.
Return concrete progress and outcomes for the requested slice.""",
}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


INSTALLER = _load(ROOT / "scripts" / "production_installer.py", "production_installer_test")

RETIRED_PASSIVE_POLLING_PS1 = b"""<#
.SYNOPSIS
    Thin wrapper around check-passive-polling-stop.py for PowerShell hosts.
.DESCRIPTION
    Hook entry shape (Stop):
      powershell -NoProfile -ExecutionPolicy Bypass -File <this-script>
    stdin: Stop JSON envelope from Claude Code or Codex.
    stdout: block JSON if a passive-polling stop is detected without a
            relevant current-turn state probe; nothing otherwise.
    exit: always 0 (decision carried by stdout payload; fail-open on any
          internal error so legitimate work is never blocked).
#>
param()

$ErrorActionPreference = 'Continue'

try {
  $scriptDir = Split-Path -Parent $PSCommandPath
  $helper = Join-Path $scriptDir 'check-passive-polling-stop.py'

  $pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
  if (-not $pythonCmd) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
  }
  if (-not $pythonCmd) { exit 0 }
  if (-not (Test-Path -LiteralPath $helper -PathType Leaf)) { exit 0 }

  $stdinText = [Console]::In.ReadToEnd()
  $stdinText | & $pythonCmd.Source $helper
} catch {
  # fail-open on any wrapper-side error
}

exit 0
"""


def test_only_deprecated_example_powershell_files_remain() -> None:
    relative_paths = (path.relative_to(ROOT) for path in ROOT.rglob("*.ps1"))
    actual = {
        path.as_posix() for path in relative_paths if ".scratch" not in path.parts
    }
    assert actual == EXCLUDED_PS1


def test_python_ownership_policy_is_repo_local_and_excludes_example_packs() -> None:
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    hygiene = (
        ROOT / "shared" / "references" / "repository-source-hygiene.md"
    ).read_text(encoding="utf-8")
    release_notes = (ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8")

    for text in (agents, hygiene):
        assert "Python owns executable-script logic" in text
        assert "thin unconditional launcher" in text
        assert "rollback copy" in text
        assert "not shared installed governance for arbitrary target projects" in text or "not a rule installed into arbitrary target repositories" in text
        assert "deprecated Gemini/Qwen example packs remain outside" in text

    assert "Python as the sole owner of executable script logic" in release_notes
    assert "deprecated Gemini/Qwen example packs remain unchanged" in release_notes


def _production_shell_entrypoints() -> frozenset[str]:
    return frozenset(
        path.relative_to(ROOT).as_posix()
        for path in ROOT.rglob("*.sh")
        if ".scratch" not in path.parts
        and ".git" not in path.parts
        and path.relative_to(ROOT).parts[0] not in {"src.gemini", "src.qwen"}
        and path.relative_to(ROOT).as_posix() not in EXAMPLE_SHELL_ENTRYPOINTS
        and path.relative_to(ROOT).as_posix()
        not in DEPRECATED_EXAMPLE_COMPATIBILITY_SHELL_ENTRYPOINTS
    )


def _assert_thin_python_launcher(text: str) -> None:
    """Reject shell-owned behavior while allowing interpreter discovery/error text."""
    assert text.startswith("#!")
    assert "command -v python" in text
    assert 'exec "$' in text
    assert ".py" in text
    forbidden = (
        "case ",
        "function ",
        "() {",
        "<<",
        "\ncat ",
        "\nsed ",
        "\ngrep ",
        "\nawk ",
        "\ngit ",
        "\ncurl ",
        "python -c",
        "\nsource ",
    )
    assert not any(token in text for token in forbidden)


def test_production_shell_census_is_exact_and_python_owned() -> None:
    assert _production_shell_entrypoints() == PRODUCTION_SHELL_ENTRYPOINTS
    guarded_entrypoints = (
        PRODUCTION_SHELL_ENTRYPOINTS
        | DEPRECATED_EXAMPLE_COMPATIBILITY_SHELL_ENTRYPOINTS
    )
    for relative in guarded_entrypoints:
        shell = ROOT / relative
        assert shell.with_suffix(".py").is_file(), relative
        _assert_thin_python_launcher(shell.read_text(encoding="utf-8"))


def test_shell_launcher_rejects_independent_logic_fixture() -> None:
    bad_launcher = """#!/usr/bin/env bash
command -v python3 >/dev/null
git status --short
exec \"$PYTHON\" \"$SCRIPT_DIR/owner.py\" \"$@\"
"""
    with pytest.raises(AssertionError):
        _assert_thin_python_launcher(bad_launcher)


@pytest.mark.skipif(
    not BASH_SMOKE_AVAILABLE,
    reason="POSIX bash launcher smoke is unavailable on this host",
)
@pytest.mark.parametrize(
    "entrypoint",
    sorted(
        PRODUCTION_SHELL_ENTRYPOINTS
        | DEPRECATED_EXAMPLE_COMPATIBILITY_SHELL_ENTRYPOINTS
    ),
)
def test_posix_launcher_forwards_stdin_argv_and_exit_code(entrypoint: str) -> None:
    shell = ROOT / entrypoint
    with tempfile.TemporaryDirectory() as td:
        temp = Path(td)
        fake_python = temp / "python3"
        argv_path = temp / "argv.txt"
        stdin_path = temp / "stdin.txt"
        fake_python.write_text(
            "#!/usr/bin/env bash\nprintf '%s\\n' \"$@\" > \"$LAUNCHER_ARGV\"\ncat > \"$LAUNCHER_STDIN\"\nexit 23\n",
            encoding="utf-8",
        )
        fake_python.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(temp) + os.pathsep + env.get("PATH", "")
        env["LAUNCHER_ARGV"] = str(argv_path)
        env["LAUNCHER_STDIN"] = str(stdin_path)
        result = subprocess.run(
            [BASH, str(shell), "first", "second value"],
            input="stdin payload\n",
            text=True,
            encoding="utf-8",
            capture_output=True,
            cwd=temp,
            env=env,
        )
        assert result.returncode == 23, (entrypoint, result.stderr)
        argv = argv_path.read_text(encoding="utf-8").splitlines()
        assert Path(argv[0]).resolve() == shell.with_suffix(".py").resolve()
        assert argv[1:] == ["first", "second value"]
        assert stdin_path.read_text(encoding="utf-8") == "stdin payload\n"


def test_publication_scanner_python_mirrors_match_canon() -> None:
    canon = (ROOT / "scripts/universal-hooks/scripts/check-publication-safety.py").read_bytes()
    assert (ROOT / "src.claude/agents/scripts/check-publication-safety.py").read_bytes() == canon
    assert (ROOT / "src.codex/skills/lead/scripts/check-publication-safety.py").read_bytes() == canon


@pytest.mark.parametrize(
    "manifest,source,relative",
    (
        (
            INSTALLER._CODEX_RETIRED_PS1,
            ROOT / "src.codex/skills/lead/scripts/check-publication-safety.ps1",
            "skills/lead/scripts/check-publication-safety.ps1",
        ),
        (
            INSTALLER._CLAUDE_RETIRED_PS1,
            ROOT / "src.claude/agents/scripts/check-publication-safety.ps1",
            "agents/scripts/check-publication-safety.ps1",
        ),
    ),
)
def test_publication_scanner_powershell_wrapper_is_retired_not_shipped(
    manifest: dict[str, str], source: Path, relative: str
) -> None:
    assert relative in manifest
    assert not source.exists()
    assert source.with_suffix(".py").is_file()


@pytest.mark.parametrize(
    "manifest,relative",
    (
        (
            INSTALLER._CODEX_RETIRED_PS1,
            "skills/lead/scripts/check-passive-polling-stop.ps1",
        ),
        (
            INSTALLER._CLAUDE_RETIRED_PS1,
            "agents/scripts/check-passive-polling-stop.ps1",
        ),
    ),
)
def test_retired_cleanup_removes_only_exact_pack_bytes(
    tmp_path: Path, manifest: dict[str, str], relative: str
) -> None:
    expected = manifest[relative]
    target = tmp_path / relative
    target.parent.mkdir(parents=True)
    assert hashlib.sha256(RETIRED_PASSIVE_POLLING_PS1).hexdigest() == expected

    target.write_bytes(RETIRED_PASSIVE_POLLING_PS1)
    INSTALLER._reclaim_retired(tmp_path, {relative: expected}, False)
    assert not target.exists()

    target.write_bytes(RETIRED_PASSIVE_POLLING_PS1 + b"\ncustom")
    INSTALLER._reclaim_retired(tmp_path, {relative: expected}, False)
    assert target.read_bytes() == RETIRED_PASSIVE_POLLING_PS1 + b"\ncustom"


def _replace_model(text: str, model: str) -> str:
    marker = 'model = "gpt-5.6-sol"'
    assert text.count(marker) == 1
    return text.replace(marker, f'model = "{model}"', 1)


def _replace_instructions(text: str, instructions: str) -> str:
    prefix, separator, remainder = text.partition('developer_instructions = """\n')
    assert separator
    _, closing, suffix = remainder.partition('\n"""\n')
    assert closing
    return prefix + separator + instructions + closing + suffix


def _historical_agent_fixtures(name: str) -> tuple[str, ...]:
    current = (ROOT / "src.codex" / "agents" / name).read_text(encoding="utf-8")
    gpt_55 = _replace_model(current, "gpt-5.5")
    gpt_54 = _replace_model(current, "gpt-5.4")
    early_gpt_54 = _replace_instructions(
        gpt_54, EARLY_AGENT_INSTRUCTIONS[name]
    )
    return gpt_55, gpt_54, early_gpt_54


@pytest.mark.parametrize("name", tuple(INSTALLER.HISTORICAL_CODEX_AGENT_SHA256))
def test_historical_agent_manifest_matches_exact_shipped_fixtures(name: str) -> None:
    actual = {
        INSTALLER._agent_override_sha256(fixture)
        for fixture in _historical_agent_fixtures(name)
    }
    assert actual == INSTALLER.HISTORICAL_CODEX_AGENT_SHA256[name]


@pytest.mark.parametrize("name", tuple(INSTALLER.HISTORICAL_CODEX_AGENT_SHA256))
@pytest.mark.parametrize("template_index", range(4))
def test_reclaim_codex_presets_removes_only_known_pack_templates(
    tmp_path: Path, name: str, template_index: int
) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    current = (ROOT / "src.codex" / "agents" / name).read_text(encoding="utf-8")
    (source / name).write_text(current, encoding="utf-8")
    pack_owned = (current, *_historical_agent_fixtures(name))[template_index]
    (target / name).write_bytes(pack_owned.replace("\n", "\r\n").encode("utf-8"))

    INSTALLER._reclaim_codex_presets(source, target, False)

    assert not (target / name).exists()


def test_reclaim_codex_presets_preserves_model_only_explorer_customization(
    tmp_path: Path,
) -> None:
    name = "explorer.toml"
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    current = (ROOT / "src.codex" / "agents" / name).read_text(encoding="utf-8")
    custom = _replace_model(current, "custom/explorer-model")
    (source / name).write_text(current, encoding="utf-8")
    installed = target / name
    custom_bytes = custom.encode("utf-8")
    installed.write_bytes(custom_bytes)

    INSTALLER._reclaim_codex_presets(source, target, False)

    assert installed.read_bytes() == custom_bytes


def test_reclaim_codex_presets_preserves_body_custom_worker_byte_for_byte(
    tmp_path: Path,
) -> None:
    name = "worker.toml"
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    current = (ROOT / "src.codex" / "agents" / name).read_text(encoding="utf-8")
    custom = _replace_instructions(
        current,
        "User-customized worker override.\nPreserve this body exactly.",
    )
    (source / name).write_text(current, encoding="utf-8")
    installed = target / name
    custom_bytes = custom.encode("utf-8")
    installed.write_bytes(custom_bytes)

    INSTALLER._reclaim_codex_presets(source, target, False)

    assert installed.read_bytes() == custom_bytes


@pytest.mark.parametrize("script", ("scripts/install-codex.py", "scripts/install-claude.py"))
def test_python_installers_expose_help(script: str) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / script), "--help"],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0
    assert "--hook-runtime" not in result.stdout
