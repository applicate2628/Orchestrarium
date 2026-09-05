"""Checkout conversion must preserve Claude's exact-byte reference contracts."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LF_ONLY_PATHS = (
    "tests/test_claude_md_size.py",
    "references-claude/claude-md-structural-enforcement.md",
    "references-claude/ru/claude-md-structural-enforcement.md",
    "references-claude/README.md",
    "RELEASE_NOTES.md",
)
BYTE_EXACT_PATHS = (
    "scripts/retained-source.py",
    "scripts/retained-script.ps1",
    "src.codex/skills/retained/agents/openai.yaml",
    "src.claude/agents/hooks/retained.py",
    "baseline/retained/source.py",
    "tests/fixtures/canonical-skill-priors/synthetic/lead/retained.py",
)


def _git(root: Path, *args: str) -> bytes:
    # This fixture never contacts a network remote. Ignore the invoking user's
    # worktree/index/config settings so the synthetic repositories stay local.
    env = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(
        ["git", "-c", "user.name=Checkout regression", "-c",
         "user.email=checkout-test@example.invalid", *args],
        cwd=root, env=env, check=True, capture_output=True, timeout=30,
    )
    return result.stdout


@pytest.mark.parametrize("autocrlf,eol", [("true", "crlf"), ("input", "lf"), ("false", "crlf")])
def test_claude_lf_contracts_survive_checkout_without_rewriting_prior_bytes(tmp_path, autocrlf, eol):
    if shutil.which("git") is None:
        pytest.skip("Git is required to exercise real checkout conversion")
    origin = tmp_path / "origin"
    origin.mkdir()
    (origin / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
    for relative in (*LF_ONLY_PATHS, *BYTE_EXACT_PATHS):
        path = origin / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"exact LF contract\n" if relative in LF_ONLY_PATHS else b"historical\r\npayload\r\n")
    _git(origin, "init", "-q")
    _git(origin, "-c", "core.autocrlf=false", "add", ".")
    _git(origin, "commit", "-qm", "Synthetic checkout regression")
    checkout = tmp_path / "checkout"
    _git(tmp_path, "-c", f"core.autocrlf={autocrlf}", "-c", f"core.eol={eol}",
         "clone", "--no-local", "--quiet", str(origin), str(checkout))

    for relative in LF_ONLY_PATHS:
        assert (checkout / relative).read_bytes() == b"exact LF contract\n", relative
    for relative in BYTE_EXACT_PATHS:
        assert (checkout / relative).read_bytes() == b"historical\r\npayload\r\n", relative
    # No new suffix-wide Python, Markdown, or PowerShell rule is allowed.
    attrs = _git(checkout, "check-attr", "text", "eol", "--", "unowned.py", "unowned.md", "unowned.ps1",
                 "tests/fixtures/canonical-skill-priors/synthetic/manifest.json").decode()
    assert all(line.endswith(": unspecified") for line in attrs.splitlines()), attrs
