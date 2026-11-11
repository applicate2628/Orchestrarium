"""Document refusal must precede installation effects; ownership stays strict."""
from pathlib import Path
import pytest
from _module_loading_support import load_module
ROOT = Path(__file__).resolve().parents[1]
OWNER = load_module(ROOT / "scripts/production_installer.py", "claude_document_preflight")

@pytest.mark.parametrize("dry_run", [False, True])
def test_ambiguous_document_refuses_before_skill_preflight(tmp_path, monkeypatch, capsys, dry_run):
    project = tmp_path / "project"
    target = project / ".claude"
    target.mkdir(parents=True)
    raw = b"# User preamble\r\n@AGENTS.md\r\n# Claude Code Pack\r\nunknown legacy body\r\n"
    (target / "CLAUDE.md").write_bytes(raw)
    settings = b'{"theme": "dark", "agent": "operator-agent"}\r\n'
    (target / "settings.json").write_bytes(settings)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("USERPROFILE", raising=False)
    def forbidden(*args, **kwargs):
        pytest.fail("ambiguous document reached skill planning")
    monkeypatch.setattr(OWNER, "_preflight_canonical_skills", forbidden)
    failures = []
    prepare = OWNER._prepare_claude_docs
    def observe(*args, **kwargs):
        try:
            return prepare(*args, **kwargs)
        except ValueError as exc:
            failures.append(str(exc))
            raise
    monkeypatch.setattr(OWNER, "_prepare_claude_docs", observe)
    args = ["--target", str(project), "--force", "--allow-unsafe-target", "--no-hypothesis-hook"]
    if dry_run:
        args.append("--dry-run")
    assert OWNER.install("claude", args) == 1
    assert failures == ["E_CLAUDE_DOC_LEGACY_AMBIGUOUS: CLAUDE.md"]
    assert "validation-failed" in capsys.readouterr().err
    assert (target / "CLAUDE.md").read_bytes() == raw
    assert (target / "settings.json").read_bytes() == settings
    assert sorted(p.relative_to(project).as_posix() for p in project.rglob("*")) == [
        ".claude", ".claude/CLAUDE.md", ".claude/settings.json"]

def test_owned_document_and_settings_survive_real_install_reinstall(tmp_path, monkeypatch):
    project = tmp_path / "project"
    target = project / ".claude"
    target.mkdir(parents=True)
    prefix = "# User preamble\nKeep this text.\n\n"
    (target / "CLAUDE.md").write_text(prefix + "@AGENTS.md\n"
        "<!-- BEGIN ORCHESTRARIUM CLAUDE MANAGED -->\nold owned body\n"
        "<!-- END ORCHESTRARIUM CLAUDE MANAGED -->\n", encoding="utf-8")
    raw_settings = b'{"agent": "operator-agent", "theme": "dark"}\n'
    (target / "settings.json").write_bytes(raw_settings)
    (target / ".agents-mode.yaml").write_text("delegationMode: force\n", encoding="utf-8")
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("USERPROFILE", raising=False)
    args = ["--target", str(project), "--force", "--allow-unsafe-target", "--no-hypothesis-hook"]
    assert OWNER.install("claude", args) == 0
    before = (target / "CLAUDE.md").read_bytes()
    payload = (ROOT / "src.claude/CLAUDE.md").read_text(encoding="utf-8")
    expected = (prefix + "@AGENTS.md\n<!-- BEGIN ORCHESTRARIUM CLAUDE MANAGED -->\n"
        + payload[len("@AGENTS.md\n"):] + "<!-- END ORCHESTRARIUM CLAUDE MANAGED -->\n")
    assert (target / "CLAUDE.md").read_text(encoding="utf-8") == expected
    assert (target / "settings.json").read_bytes() == raw_settings
    assert (target / "skills/lead/SKILL.md").is_file()
    assert OWNER.install("claude", args) == 0
    assert (target / "CLAUDE.md").read_bytes() == before
    assert (target / "settings.json").read_bytes() == raw_settings

def test_late_failure_rolls_back_entire_isolated_install(tmp_path, monkeypatch, capsys):
    project = tmp_path / "project"
    target = project / ".claude"
    (target / "agents").mkdir(parents=True)
    (target / "agents/lead.md").write_bytes(b"operator-owned old definition\n")
    (target / "settings.json").write_bytes(b'{"theme": "dark", "hooks": {}}\n')
    (target / ".agents-mode.yaml").write_bytes(b"delegationMode: force\n")
    def snapshot():
        result = {}
        for path in project.rglob("*"):
            name = path.relative_to(project).as_posix()
            assert not path.is_symlink() and not path.is_junction(), name
            result[name] = path.read_bytes() if path.is_file() else None
        return result
    before = snapshot()
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.delenv("USERPROFILE", raising=False)
    calls = []
    def reject(*args, **kwargs):
        calls.append(True)
        return ["injected post-install verification failure"]
    monkeypatch.setattr(OWNER, "_verify_files", reject)
    assert OWNER.install("claude", ["--target", str(project), "--force",
        "--allow-unsafe-target", "--no-hypothesis-hook"]) == 1
    assert calls
    assert "E_ROLLBACK_SETTLEMENT_FAILED" not in capsys.readouterr().err
    assert snapshot() == before
