"""Source-catalog guard only; does not execute UI fixtures or evaluate an agent."""
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CLAUDE = ROOT / "adapters" / "claude"
if not CLAUDE.is_dir():
    CLAUDE = ROOT / "src.claude"

CHECKS = {
    "accessibility-reviewer": ("2.4.11", "2.5.7", "2.5.8 exceptions", "actual announcement"),
    "frontend-engineer": ("stale completion", "semantic locators"),
    "model-view-engineer": ("destructive mutation", "stable identity"),
    "qt-ui-engineer": ("native mixed-DPI transition", "after close and reopen"),
    "ui-test-engineer": ("measured window device pixel ratio", "offscreen"),
    "ux-designer": ("user-visible completion", "participant evidence"),
    "ux-reviewer": ("unassisted walkthrough", "participant evidence"),
    "windows-gui-manual-testing": ("DPI-virtualized", "presentation timestamps", "UNVERIFIED"),
}


@pytest.mark.parametrize("role,markers", CHECKS.items())
def test_specialist_evidence_is_projected_to_both_client_sources(role, markers):
    codex = ROOT / "src.codex" / "skills" / role / "SKILL.md"
    # Claude consumes the canonical Windows workflow, not its historical source copy.
    clients = (codex,) if role == "windows-gui-manual-testing" else (
        codex, CLAUDE / "agents" / (role + ".md"),
    )
    for marker in markers:
        for client in clients:
            assert marker in client.read_text(encoding="utf-8"), (client, marker)
