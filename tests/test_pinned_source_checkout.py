"""Git checkout settings must not rewrite byte-pinned installer sources."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-c", "user.name=Checkout test", "-c",
         "user.email=checkout-test@example.invalid", *args],
        cwd=root, check=True, capture_output=True, timeout=30,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1",
             "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0"},
    )


@pytest.mark.parametrize("autocrlf,eol", [("true", "crlf"), ("input", "lf"), ("false", "crlf")])
def test_pinned_source_bytes_survive_checkout_settings(tmp_path, autocrlf, eol):
    if shutil.which("git") is None:
        pytest.skip("Git is required to exercise checkout conversion")
    original = tmp_path / "origin"
    original.mkdir()
    paths = {".gitattributes", "shared/role-routing-policy.v1.json",
             "src.codex/agents/orchestrarium-role-manifest.json",
             "references-claude/claude-md-structural-enforcement.md",
             "references-claude/ru/claude-md-structural-enforcement.md"}
    roles = json.loads((ROOT / "src.codex/agents/orchestrarium-role-manifest.json").read_text())
    paths.update("src.codex/agents/" + record["relativePath"] for record in roles["roles"].values())
    transport = json.loads((ROOT / "shared/provider-prompt-projections.v1.json").read_text())
    paths.update(record["source"] for record in transport["files"].values())
    # Existing mixed-newline payloads must retain their bytes too; normalizing
    # every source to LF would change accepted-prior tree identities.
    paths.update({"src.codex/skills/architect/agents/openai.yaml",
                  "src.claude/agents/hooks/dispatch_sentinels.py",
                  "scripts/arch-layering-slices.stamp"})
    expected = {}
    for relative in sorted(paths):
        data = (ROOT / relative).read_bytes()
        expected[relative] = data
        target = original / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    _git(original, "init", "-q")
    _git(original, "-c", "core.autocrlf=false", "add", ".")
    _git(original, "commit", "-qm", "Synthetic pinned-source checkout fixture")
    checkout = tmp_path / "checkout"
    _git(tmp_path, "-c", "core.autocrlf=" + autocrlf,
         "-c", "core.eol=" + eol, "clone", "--no-local", "--quiet",
         str(original), str(checkout))
    changed = [relative for relative, data in expected.items()
               if relative != ".gitattributes" and (checkout / relative).read_bytes() != data]
    assert not changed, "Checkout changed pinned bytes: " + ", ".join(changed)
    assert hashlib.sha256((checkout / "shared/role-routing-policy.v1.json").read_bytes()).hexdigest() == roles["policySha256"]
    for record in roles["roles"].values():
        assert hashlib.sha256((checkout / "src.codex/agents" / record["relativePath"]).read_bytes()).hexdigest() == record["sha256"]
    for record in transport["files"].values():
        assert hashlib.sha256((checkout / record["source"]).read_bytes()).hexdigest() == record["sha256"]
