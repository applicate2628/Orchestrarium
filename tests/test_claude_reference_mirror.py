"""Regression coverage for the Claude English/Russian reference mirror contract."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parent.parent
VALIDATOR = REPO_ROOT / "scripts" / "validate-claude-md.py"
EN_REFERENCE = REPO_ROOT / 'adapters/claude/references' / "claude-md-structural-enforcement.md"
RU_REFERENCE = (
    REPO_ROOT
    / 'adapters/claude/references'
    / "ru"
    / "claude-md-structural-enforcement.md"
)


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_claude_md_mirror", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mutated_ru(tmp_path: Path, old: str, new: str) -> Path:
    text = RU_REFERENCE.read_text(encoding="utf-8")
    assert old in text, f"mutation anchor missing: {old}"
    path = tmp_path / "ru-reference.md"
    path.write_text(text.replace(old, new, 1), encoding="utf-8", newline="\n")
    return path


def test_current_claude_reference_mirror_is_contract_complete() -> None:
    validator = _load_validator()

    ok, messages = validator.validate_reference_mirror(EN_REFERENCE, RU_REFERENCE)

    assert ok, "\n".join(messages)
    assert "PASS: Claude reference mirror payloads 4/4" in messages
    assert "PASS: Claude reference mirror hooks 11/11" in messages
    assert "PASS: Claude reference mirror status IDs 0/0" in messages
    assert "PASS: Claude reference mirror user markers 2/2" in messages
    assert "PASS: Russian hook-behavior-contracts payload pin" in messages


def test_russian_typed_routing_documents_nonblocking_delivery() -> None:
    paragraph = next(
        paragraph
        for paragraph in RU_REFERENCE.read_text(encoding="utf-8").split("\n\n")
        if paragraph.startswith("**Аудит Typed-routing.**")
    )

    for required in ("hookSpecificOutput.additionalContext", "stdout", "кодом 0"):
        assert required in paragraph
    for stale in ("stderr", "кодом 1"):
        assert stale not in paragraph


@pytest.mark.parametrize(
    ("old", "new", "failure_id"),
    (
        (
            "<!-- BEGIN ORCHESTRARIUM PAYLOAD: structural-overview -->",
            "<!-- BEGIN ORCHESTRARIUM PAYLOAD: structural-overview-drift -->",
            "CRM-PAYLOAD-ID-SET",
        ),
        ("check-typed-routing.py", "check-typed-routing-drift.py", "CRM-HOOK-NAME-SET"),
        (
            "**Хук PreToolUse bugfix-discipline.**",
            "**Хук PreToolUse bugfix-discipline.** TEST-STATUS-DRIFT",
            "CRM-STATUS-ID-SET",
        ),
        ("[skip-bugfix-discipline]", "[skip-bugfix-drift]", "CRM-USER-MARKER-SET"),
    ),
)
def test_reference_mirror_refuses_contract_inventory_drift(
    tmp_path: Path, old: str, new: str, failure_id: str
) -> None:
    validator = _load_validator()
    mutated = _mutated_ru(tmp_path, old, new)

    ok, messages = validator.validate_reference_mirror(EN_REFERENCE, mutated)

    assert not ok
    assert any(failure_id in message for message in messages), messages


def test_reference_mirror_refuses_unreviewed_russian_payload_byte_drift(
    tmp_path: Path,
) -> None:
    validator = _load_validator()
    mutated = _mutated_ru(
        tmp_path,
        "**Хук PreToolUse bugfix-discipline.**",
        "**Хук PreToolUse bugfix-discipline (drift).**",
    )

    ok, messages = validator.validate_reference_mirror(EN_REFERENCE, mutated)

    assert not ok
    assert any("CRM-RU-HOOK-PAYLOAD-PIN" in message for message in messages), messages


def test_matching_nonempty_status_inventory_is_accepted(tmp_path: Path) -> None:
    validator = _load_validator()
    copies = []
    for name, source in (("en.md", EN_REFERENCE), ("ru.md", RU_REFERENCE)):
        path = tmp_path / name
        # Outside the pinned payload: exercise inventory equality independently.
        path.write_text(source.read_text(encoding="utf-8") + "\nTEST-STATUS-SAMPLE\n", encoding="utf-8")
        copies.append(path)
    ok, messages = validator.validate_reference_mirror(*copies)
    assert ok, messages
    assert "PASS: Claude reference mirror status IDs 1/1" in messages
