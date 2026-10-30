"""Provider-owned copies: ordinary install must not require skill links."""
from pathlib import Path
import os
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_fresh_claude_owns_regular_skill_copies(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    result = subprocess.run(
        [sys.executable, str(ROOT / "install.py"), "--clients", "claude",
         "--target", str(project), "--no-hypothesis-hook", "--allow-unsafe-target"],
        cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=240,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    skills = project / ".claude/skills"
    names = {p.name for p in (ROOT / "src.codex/skills").iterdir() if p.is_dir()}
    assert names
    for name in names:
        installed = skills / name
        assert installed.is_dir()
        assert not installed.is_symlink()
        assert not getattr(os.path, "isjunction", lambda p: False)(installed)
        assert (installed / "SKILL.md").is_file()
    assert not (project / ".agents/skills").exists()
    assert not (project / ".codex").exists()
    receipt = json.loads((project / ".claude/.orche-install.v1.json").read_text())
    assert ".claude/skills/backend-engineer/SKILL.md" in receipt["files"]
    assert all(name.startswith(".claude/") for name in receipt["files"])


def _payload_snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts}


def test_selected_provider_update_preserves_peer_and_user_files(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    def install(provider):
        result = subprocess.run(
            [sys.executable, str(ROOT / "install.py"), "--clients", provider,
             "--target", str(project), "--no-hypothesis-hook", "--allow-unsafe-target"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=240,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    install("claude")
    user_file = project / ".claude/skills/backend-engineer/user-note.txt"
    user_file.write_text("user data must survive", encoding="utf-8")
    install("claude")
    assert user_file.read_text(encoding="utf-8") == "user data must survive"
    receipt = json.loads((project / ".claude/.orche-install.v1.json").read_text())
    assert ".claude/skills/backend-engineer/user-note.txt" not in receipt["files"]
    before = _payload_snapshot(project / ".claude")
    install("codex")
    assert _payload_snapshot(project / ".claude") == before
    assert (project / ".agents/skills/backend-engineer/SKILL.md").is_file()
    assert not os.path.samefile(project / ".agents/skills/backend-engineer/SKILL.md",
                                project / ".claude/skills/backend-engineer/SKILL.md")
