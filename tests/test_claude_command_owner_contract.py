"""Keep installed Claude command projections on their existing source owners."""

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CLAUDE = ROOT / "adapters" / "claude"
COMMANDS = CLAUDE / "commands"


def test_help_uses_the_installed_role_index_without_a_frozen_count():
    help_text = (COMMANDS / "agents-help.md").read_text(encoding="utf-8")
    role_summary = help_text.split("### Roles by team", 1)[1].split("### Quick examples", 1)[0]
    assert "role index" in role_summary
    assert "installed" in role_summary
    assert not re.search(r"\b\d+ roles\b", role_summary)
    assert not re.search(r"\bperf-(?:engineer|reviewer)\b", help_text)
    rows = set(re.findall(r"^\| `/(agents-[\w-]+)`", help_text, re.MULTILINE))
    assert rows == {command.stem for command in COMMANDS.glob("agents-*.md")}


def test_performance_commands_and_routing_use_the_bug_registry():
    for projection in (
        COMMANDS / "agents-perf.md",
        COMMANDS / "agents-status.md",
        CLAUDE / "agents/contracts/operating-model.md",
    ):
        text = projection.read_text(encoding="utf-8")
        assert "work-items/performance/" not in text, projection.name
        assert "configured bug registry" in text, projection.name
    status = (COMMANDS / "agents-status.md").read_text(encoding="utf-8")
    pm_step = status.split("6. **Reserved PM admissions.**", 1)[1].split("7. **Open lessons.**", 1)[0]
    assert "configured bug registry already read in step 3" in pm_step
    assert "status: open" in pm_step
    perf = (COMMANDS / "agents-perf.md").read_text(encoding="utf-8")
    assert "schema and statuses owned by the shared lifecycle contract" in perf


def test_bugfix_and_qa_leave_terminalization_to_the_lifecycle_owner():
    for projection in (
        COMMANDS / "agents-bugfix.md",
        CLAUDE / "agents/qa-engineer.md",
        ROOT / "src.codex/skills/qa-engineer/SKILL.md",
    ):
        text = projection.read_text(encoding="utf-8")
        assert "lifecycle owner alone" in text, projection.name
        assert "wontfix" not in text, projection.name
        assert "set `status: fixed`" not in text, projection.name
