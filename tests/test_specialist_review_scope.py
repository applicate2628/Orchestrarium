"""Source-level role parity guards; not evidence of provider/model compliance."""
from pathlib import Path
import tomllib

import pytest

ROOT = Path(__file__).resolve().parents[1]
CLAUDE = ROOT / ("adapters/claude" if (ROOT / "adapters/claude").is_dir() else "src.claude")


def role_sources(name: str) -> tuple[str, ...]:
    return (
        (ROOT / "src.codex/skills" / name / "SKILL.md").read_text(encoding="utf-8"),
        (CLAUDE / "agents" / f"{name}.md").read_text(encoding="utf-8"),
    )


def test_qa_independent_gate_does_not_extend_native_write_permission():
    role = tomllib.loads((ROOT / "src.codex/agents/qa-engineer.toml").read_text(encoding="utf-8"))
    assert role["sandbox_mode"] == "read-only"
    for source in role_sources("qa-engineer"):
        assert "read-only QA dispatch reports the missing falsifier to the existing test owner" in source
        assert "separately and explicitly admitted writable QA assignment" in source
        assert "self-authored test result as independent gate evidence" in source
        assert "known-bad prior result" in source and "valid control pass" in source


@pytest.mark.parametrize(("name", "guard", "retired"), [
    ("security-engineer", "evidenced likelihood and impact", "attacker effort × blast radius"),
    ("security-reviewer", "does not turn a mandatory `not-verifiable` into `PASS`",
     "`not-run` without a reason blocks `PASS`"),
    ("architecture-reviewer", "one independent counter-scenario", None),
    ("knowledge-archivist", "a resolving link to the wrong live decision is still drift", None),
])
def test_specialist_contract_change_reaches_both_provider_sources(name, guard, retired):
    codex, claude = role_sources(name)
    for source in (codex, claude):
        assert guard in source
        if retired is not None:
            assert retired not in source
    # The changed rule is the same, even though the surrounding provider roles differ.
    assert [line for line in codex.splitlines() if guard in line] == [
        line for line in claude.splitlines() if guard in line
    ]
