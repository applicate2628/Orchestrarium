#!/usr/bin/env python3
"""Regression checks for the installed resolver/reminder ownership contract."""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "production_installer.py"
REMINDER = (
    ROOT
    / "src.codex"
    / "skills"
    / "lead"
    / "scripts"
    / "agents-mode-reminder.py"
)


def _string_tuple_assignment(path: Path, name: str) -> tuple[str, ...]:
    module = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            continue
        value = ast.literal_eval(node.value)
        assert isinstance(value, tuple)
        assert all(isinstance(item, str) for item in value)
        return value
    raise AssertionError(f"assignment {name!r} not found in {path}")


def test_shipped_resolver_and_reminder_rationale_agree() -> None:
    helpers = _string_tuple_assignment(INSTALLER, "RUNTIME_HELPERS")
    reminder = REMINDER.read_text(encoding="utf-8")

    assert "resolve-agents-mode.py" in helpers
    assert "is NOT shipped to install targets" not in reminder
    assert "is shipped beside this hook" in reminder
    assert "does not import or\nexecute it" in reminder
