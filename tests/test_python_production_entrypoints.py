"""Regression tests for Python-owned production entrypoints and retirement."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
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


def test_no_powershell_implementation_files_remain() -> None:
    relative_paths = (path.relative_to(ROOT) for path in ROOT.rglob("*.ps1"))
    actual = {
        path.as_posix() for path in relative_paths if ".scratch" not in path.parts
    }
    assert actual == set()


def test_python_ownership_policy_is_repo_local() -> None:
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
    assert "Python as the sole owner of executable script logic" in release_notes


def _production_shell_entrypoints(root: Path = ROOT) -> frozenset[str]:
    return frozenset(
        relative.as_posix()
        for path in root.rglob("*.sh")
        if ".scratch" not in (relative := path.relative_to(root)).parts
        and ".git" not in relative.parts
        and relative.as_posix()
        not in DEPRECATED_EXAMPLE_COMPATIBILITY_SHELL_ENTRYPOINTS
    )


def test_shell_census_does_not_filter_a_worktree_because_its_ancestor_is_scratch(
    tmp_path: Path,
) -> None:
    """Only a repo-relative .scratch segment is excluded from shell census."""

    worktree = tmp_path / ".scratch" / "detached-worktree"
    script = worktree / "scripts" / "probe.sh"
    script.parent.mkdir(parents=True)
    script.write_text("#!/bin/sh\n", encoding="utf-8")
    assert _production_shell_entrypoints(worktree) == frozenset({"scripts/probe.sh"})


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


def test_global_home_selection_uses_home_when_posix_lacks_userprofile() -> None:
    assert INSTALLER._select_global_home_environment(
        None, "/tmp/orchestrarium-home", platform="posix"
    ) == ("HOME", "/tmp/orchestrarium-home", None)


def test_global_home_selection_ignores_userprofile_on_posix() -> None:
    assert INSTALLER._select_global_home_environment(
        "/ignored-userprofile",
        "/tmp/orchestrarium-home",
        platform="posix",
    ) == ("HOME", "/tmp/orchestrarium-home", None)


def test_install_docs_match_platform_global_home_contract() -> None:
    install = (ROOT / "INSTALL.md").read_text(encoding="utf-8")

    assert (
        "For global installs, POSIX requires `HOME` and ignores `USERPROFILE`; "
        "Windows requires `USERPROFILE` and does not fall back to `HOME`."
        in install
    )


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


@pytest.mark.skipif(
    not BASH_SMOKE_AVAILABLE,
    reason="POSIX bash installer dry-run is unavailable on this host",
)
@pytest.mark.parametrize("entrypoint", ("scripts/install-codex.sh", "scripts/install-claude.sh"))
def test_posix_global_dry_run_uses_home_without_userprofile(entrypoint: str) -> None:
    with tempfile.TemporaryDirectory() as td:
        home = Path(td) / "home"
        home.mkdir()
        env = os.environ.copy()
        env.pop("USERPROFILE", None)
        env["HOME"] = str(home)
        result = subprocess.run(
            [BASH, str(ROOT / entrypoint), "--global", "--dry-run", "--no-hypothesis-hook"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )

    assert result.returncode == 0, result.stdout + result.stderr
    provider = "codex" if "codex" in entrypoint else "claude"
    assert f"Target: {home / f'.{provider}'}" in result.stdout


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


def test_codex_production_entrypoint_creates_only_source_manifest_roles(
    tmp_path: Path,
) -> None:
    """The source manifest validates payload bytes but is never an installed receipt."""

    project = tmp_path / "project"
    project.mkdir()
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "install-codex.py"),
            "--target",
            str(project),
            "--force",
            "--allow-unsafe-target",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RESULT: OK - Codex pack installed" in result.stdout

    source_manifest = json.loads(
        (ROOT / "src.codex" / "agents" / "orchestrarium-role-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    installed_agents = project / ".codex" / "agents"
    assert len(source_manifest["roles"]) == 17
    assert not (installed_agents / "orchestrarium-role-manifest.json").exists()
    for role_name, source_record in source_manifest["roles"].items():
        assert (installed_agents / source_record["relativePath"]).is_file()
    assert not hasattr(INSTALLER, "_reclaim_codex_presets")


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
