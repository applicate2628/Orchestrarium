"""Checkout conversion must not change exact installed/source contracts."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _pinned_sources():
    manifest = json.loads((ROOT / "shared/provider-prompt-projections.v1.json").read_text())
    roles = json.loads((ROOT / "src.codex/agents/orchestrarium-role-manifest.json").read_text())
    return sorted({
        "shared/provider-prompt-projections.v1.json", "shared/role-routing-policy.v1.json",
        "src.codex/agents/orchestrarium-role-manifest.json", "src.claude/CLAUDE.md",
        "shared/agents-mode.presets.json", "scripts/validate-claude-md.py",
        "scripts/linked_runtime_subroots.py",
        "tests/fixtures/provider-prompt-priors/pre-e7/provider_prompt.py",
        "tests/test_claude_md_size.py", "references-claude/README.md", "RELEASE_NOTES.md",
        "references-claude/claude-md-structural-enforcement.md",
        "references-claude/ru/claude-md-structural-enforcement.md",
        *(entry["source"] for entry in manifest["files"].values()),
        *("src.codex/agents/" + entry["relativePath"] for entry in roles["roles"].values()),
    })


def test_windows_checkout_preserves_exact_pinned_bytes_and_unrelated_policy(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()

    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    git("init", "-q")
    git("config", "core.autocrlf", "false")
    git("config", "core.safecrlf", "false")
    (repo / ".gitattributes").write_bytes((ROOT / ".gitattributes").read_bytes())
    originals = {name: (ROOT / name).read_bytes() for name in _pinned_sources()}
    prior = "tests/fixtures/canonical-skill-priors/test/revision/scripts/prior.py"
    originals[prior] = b"historical\r\nbytes\r\n"
    for name, raw in originals.items():
        target = repo / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
    for name in ("unrelated.py", "unrelated.ps1", "unrelated.md"):
        (repo / name).write_bytes(b"unrelated\n")
    git("add", ".")
    git("config", "core.autocrlf", "true")
    for name in (*originals, "unrelated.py", "unrelated.ps1", "unrelated.md"):
        (repo / name).unlink()
    git("checkout-index", "--all", "--force")
    changed = [name for name, raw in originals.items() if (repo / name).read_bytes() != raw]
    assert not changed, f"checkout changed byte-pinned files: {changed}"
    for name in ("unrelated.py", "unrelated.ps1", "unrelated.md"):
        assert (repo / name).read_bytes() == b"unrelated\r\n", name
