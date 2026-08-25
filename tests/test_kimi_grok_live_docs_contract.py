"""Keep unavailable Kimi/Grok policy names out of executable documentation."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# This is the complete live Markdown/YAML inventory allowed to name either
# unavailable provider. New hits require an explicit review of their wording.
EXPECTED_HIT_FILES = frozenset({
    "INSTALL.md",
    "README.md",
    "docs/agents-mode-reference.md",
    "docs/external-worker-design.md",
    "docs/provider-runtime-layouts.md",
    "shared/AGENTS.shared.md",
    "shared/agents-mode.defaults.yaml",
    "src.claude/CLAUDE.md",
    "src.claude/agents/consultant.md",
    "src.claude/agents/contracts/external-dispatch.md",
    "src.claude/agents/contracts/operating-model.md",
    "src.claude/agents/contracts/subagent-contracts.md",
    "src.claude/commands/agents-init-project.md",
    "src.claude/commands/agents-second-opinion.md",
    "src.codex/AGENTS.codex.md",
    "src.codex/skills/consultant/SKILL.md",
    "src.codex/skills/consultant/agents/openai.yaml",
    "src.codex/skills/design-panel/SKILL.md",
    "src.codex/skills/init-project/SKILL.md",
    "src.codex/skills/init-project/agents/openai.yaml",
    "src.codex/skills/lead/external-dispatch.md",
    "src.codex/skills/lead/operating-model.md",
    "src.codex/skills/review-loop/SKILL.md",
    "src.codex/skills/second-opinion/SKILL.md",
    "src.codex/skills/second-opinion/agents/openai.yaml",
})

SEMANTIC_TERMS = re.compile(
    r"\b(?:route|use|select(?:ed|ion)?|resolved|execution|launch(?:er|ed|ing)?|spawn|probe|read-only)\b",
    re.IGNORECASE,
)
SAFE_TERMS = re.compile(
    r"\b(?:unavailable|disabled|policy[- ](?:only|classifier|name)|non-executing)\b",
    re.IGNORECASE,
)
FORBIDDEN_TERMS = re.compile(r"\b(?:explicit-only|read-only route)\b", re.IGNORECASE)
KIMI_GROK_SELECTION = re.compile(
    r"\b(?:kimi|grok)\b[^.]{0,80}\bselect(?:ed|ion)?\b", re.IGNORECASE
)
POLICY_ENUMERATION = re.compile(
    r"`externalProvider:\s*auto \| codex \| claude \| gemini \| qwen \| kimi \| grok`",
    re.IGNORECASE,
)


def _live_docs_and_yaml() -> tuple[Path, ...]:
    roots = (ROOT / "docs", ROOT / "shared", ROOT / "src.codex", ROOT / "src.claude")
    candidates = [ROOT / "README.md", ROOT / "INSTALL.md"]
    for directory in roots:
        candidates.extend(
            path
            for path in directory.rglob("*")
            if path.is_file() and path.suffix in {".md", ".yaml", ".yml"}
        )
    return tuple(
        sorted(
            path
            for path in candidates
            if "archive" not in path.parts
            and "fixtures" not in path.parts
            and path.name not in {"RELEASE_NOTES.md", "CHANGELOG.md", "HISTORY.md"}
        )
    )


def _provider_clauses(line: str) -> tuple[str, ...]:
    return tuple(re.split(r"(?<=[.!?])\s+", line))


def test_kimi_grok_live_inventory_and_nonexecution_language() -> None:
    """Every live executable-sounding mention must also state the unavailable boundary."""

    hits: dict[str, tuple[str, ...]] = {}
    for path in _live_docs_and_yaml():
        lines = tuple(
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if re.search(r"\b(?:kimi|grok)\b", line, re.IGNORECASE)
        )
        if lines:
            hits[path.relative_to(ROOT).as_posix()] = lines

    assert set(hits) == EXPECTED_HIT_FILES

    for relative_path, lines in hits.items():
        for line in lines:
            # Sentence clauses prevent an unrelated earlier provider mode from
            # satisfying or violating the Kimi/Grok-only policy boundary.
            for clause in _provider_clauses(line):
                if not re.search(r"\b(?:kimi|grok)\b", clause, re.IGNORECASE):
                    continue
                if SEMANTIC_TERMS.search(clause) and not POLICY_ENUMERATION.search(clause):
                    assert SAFE_TERMS.search(clause), (
                        f"unsafe Kimi/Grok clause in {relative_path}: {clause}"
                    )
                assert not FORBIDDEN_TERMS.search(clause), (
                    f"selectable Kimi/Grok wording in {relative_path}: {clause}"
                )
                if KIMI_GROK_SELECTION.search(clause):
                    assert "never select" in clause.lower(), (
                        f"Kimi/Grok selection wording in {relative_path}: {clause}"
                    )

    for relative_path, lines in hits.items():
        text = "\n".join(lines)
        assert "Kimi CLI" not in text, f"resolved-provider template leaks Kimi in {relative_path}"
        assert "Grok CLI" not in text, f"resolved-provider template leaks Grok in {relative_path}"
        assert "external CLI (Kimi" not in text, f"execution template leaks Kimi in {relative_path}"
        assert "external CLI (Grok" not in text, f"execution template leaks Grok in {relative_path}"
