from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROOT_OWNER = ROOT / "scripts" / "provider_prompt.py"
CLAUDE_SCRIPTS = ROOT / "src.claude" / "agents" / "scripts"


def test_root_is_the_only_authored_transport_owner() -> None:
    assert ROOT_OWNER.is_file()
    assert not (CLAUDE_SCRIPTS / "provider_prompt.py").exists()


def test_codex_and_claude_host_wrappers_remain_thin_adjacent_consumers() -> None:
    for provider in ("codex", "claude"):
        python_wrapper = CLAUDE_SCRIPTS / f"invoke-{provider}-prompt.py"
        shell_wrapper = CLAUDE_SCRIPTS / f"invoke-{provider}-prompt.sh"
        assert python_wrapper.is_file()
        assert shell_wrapper.is_file()
        python_text = python_wrapper.read_text(encoding="utf-8")
        assert "from provider_prompt import launch" in python_text
        assert f'launch("{provider}", sys.argv[1:])' in python_text
        assert "provider_prompt.py" not in shell_wrapper.read_text(encoding="utf-8")
