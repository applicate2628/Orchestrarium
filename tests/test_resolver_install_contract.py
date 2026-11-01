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
    assignments = {
        target.id: node.value
        for node in module.body if isinstance(node, ast.Assign)
        for target in node.targets if isinstance(target, ast.Name)
    }

    def strings(node: ast.AST, visiting: frozenset[str]) -> tuple[str, ...]:
        if isinstance(node, ast.Name):
            assert node.id not in visiting, "cyclic tuple inventory"
            assert node.id in assignments, "unknown tuple inventory"
            return strings(assignments[node.id], visiting | {node.id})
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return strings(node.left, visiting) + strings(node.right, visiting)
        assert isinstance(node, ast.Tuple), "inventory must be a static tuple"
        result = []
        for item in node.elts:
            if isinstance(item, ast.Starred):
                result.extend(strings(item.value, visiting))
            else:
                value = ast.literal_eval(item)
                assert isinstance(value, str)
                result.append(value)
        return tuple(result)

    assert name in assignments, f"assignment {name!r} not found in {path}"
    return strings(assignments[name], frozenset({name}))


def test_shipped_resolver_and_reminder_rationale_agree() -> None:
    helpers = _string_tuple_assignment(INSTALLER, "RUNTIME_HELPERS")
    reminder = REMINDER.read_text(encoding="utf-8")

    assert "resolve-agents-mode.py" in helpers
    assert "is NOT shipped to install targets" not in reminder
    assert "sibling ``agents_mode_runtime.py`` support leaf owns the first-match read" in reminder
    assert "full resolver, ``resolve-agents-mode.py``, is\nshipped beside this hook" in reminder
    assert "does not import or execute it" in reminder


def test_static_inventory_supports_named_sdk_tuple_without_execution(tmp_path: Path) -> None:
    source = tmp_path / "inventory.py"
    source.write_text('SDK = ("sdk/worker.py",)\nHELPERS = ("resolver.py", *SDK) + ("extra.py",)\nraise RuntimeError("never execute")\n')
    assert _string_tuple_assignment(source, "HELPERS") == ("resolver.py", "sdk/worker.py", "extra.py")


def test_static_inventory_refuses_dynamic_and_cyclic_entries(tmp_path: Path) -> None:
    import pytest
    source = tmp_path / "inventory.py"
    for text in ('HELPERS = load_helpers()\n', 'HELPERS = (*HELPERS,)\n'):
        source.write_text(text)
        with pytest.raises(AssertionError):
            _string_tuple_assignment(source, "HELPERS")
