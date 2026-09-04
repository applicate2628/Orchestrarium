"""Repository byte pins must survive checkout on every supported host."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ATTRIBUTES = ROOT / ".gitattributes"
REQUIRED_RULES = (
    ".gitattributes text eol=lf",
    "*.py text eol=lf",
    "*.json text eol=lf",
    "*.jsonl text eol=lf",
    "*.md text eol=lf",
    "*.toml text eol=lf",
    "*.yaml text eol=lf",
    "*.yml text eol=lf",
    "*.sh text eol=lf",
    "*.ps1 text eol=lf",
)
REPRESENTATIVES = (
    "scripts/production_installer.py",
    "shared/agents-mode.presets.json",
    "references-claude/ru/claude-md-structural-enforcement.md",
    "src.codex/skills/github-pr-review-bot/SKILL.md",
)
HISTORICAL_FIXTURE = "tests/fixtures/canonical-skill-priors/codex/example/SKILL.md"


def _attributes(path: str) -> dict[str, str]:
    result = subprocess.run(
        ["git", "check-attr", "text", "eol", "--", path],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    parsed: dict[str, str] = {}
    for row in result.stdout.splitlines():
        _path, attribute, value = row.rsplit(": ", 2)
        parsed[attribute] = value
    return parsed


def test_byte_pinned_text_families_are_explicitly_lf() -> None:
    lines = ATTRIBUTES.read_text(encoding="utf-8").splitlines()
    for rule in REQUIRED_RULES:
        assert lines.count(rule) == 1
    fixture_rule = "tests/fixtures/canonical-skill-priors/*/*/** -text"
    assert lines.count(fixture_rule) == 1
    assert lines.index(fixture_rule) > max(lines.index(rule) for rule in REQUIRED_RULES)

    for relative in REPRESENTATIVES:
        assert _attributes(relative) == {"text": "set", "eol": "lf"}
        assert b"\r\n" not in (ROOT / relative).read_bytes()

    assert _attributes(HISTORICAL_FIXTURE)["text"] == "unset"
