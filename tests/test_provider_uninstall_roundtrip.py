"""Real temporary install/uninstall; never targets a live provider home."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def test_claude_uninstall_preview_apply_and_reentry_preserve_user_data(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    def run(*args):
        return subprocess.run([sys.executable, str(ROOT / "install.py"), "--clients", "claude",
            "--target", str(project), "--allow-unsafe-target", *args], cwd=ROOT,
            capture_output=True, text=True, encoding="utf-8", timeout=300)
    installed = run("--no-hypothesis-hook")
    assert installed.returncode == 0, installed.stdout + installed.stderr
    user = project / ".claude/user-note.txt"
    user.write_text("do not remove user data", encoding="utf-8")
    docs = project / ".claude/CLAUDE.md"
    docs.write_text(docs.read_text(encoding="utf-8") + "\nUser instructions stay.\n", encoding="utf-8")
    before = {p.relative_to(project).as_posix(): p.read_bytes()
              for p in project.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    preview = run("--uninstall")
    assert preview.returncode == 0, preview.stdout + preview.stderr
    after_preview = {p.relative_to(project).as_posix(): p.read_bytes()
                     for p in project.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    assert after_preview == before
    removed = run("--uninstall", "--apply")
    assert removed.returncode == 0, removed.stdout + removed.stderr
    assert user.read_text(encoding="utf-8") == "do not remove user data"
    assert "User instructions stay." in docs.read_text(encoding="utf-8")
    assert "BEGIN ORCHESTRARIUM" not in docs.read_text(encoding="utf-8")
    assert not (project / ".claude/skills/backend-engineer/SKILL.md").exists()
    assert not (project / ".agents/skills").exists()
    again = run("--uninstall", "--apply")
    assert again.returncode == 0, again.stdout + again.stderr


def test_codex_uninstall_leaves_claude_byte_identical(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    def run(provider, *args):
        result = subprocess.run([sys.executable, str(ROOT / "install.py"), "--clients", provider,
            "--target", str(project), "--allow-unsafe-target", *args], cwd=ROOT,
            capture_output=True, text=True, encoding="utf-8", timeout=300)
        assert result.returncode == 0, result.stdout + result.stderr
        return result
    run("claude", "--no-hypothesis-hook")
    run("codex", "--no-hypothesis-hook")
    def peer_bytes():
        return {p.relative_to(project / ".claude").as_posix(): p.read_bytes()
                for p in (project / ".claude").rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    before = peer_bytes()
    run("codex", "--uninstall", "--apply")
    assert peer_bytes() == before
    assert not (project / ".agents/skills/backend-engineer/SKILL.md").exists()
    assert (project / ".claude/skills/backend-engineer/SKILL.md").is_file()
    import tomllib
    config = tomllib.loads((project / ".codex/config.toml").read_text(encoding="utf-8"))
    assert not config.get("agents")
    assert "multi_agent_v2" not in config.get("features", {})
    run("codex", "--uninstall", "--apply")
