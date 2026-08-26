"""Keep live Kimi and Grok documentation within their distinct policy bounds."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

# This is the complete live Markdown/YAML inventory allowed to name either
# provider. New hits require an explicit review of their wording.
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
GROK_NONEXECUTION_TERMS = re.compile(
    r"\b(?:unavailable|disabled|policy[- ](?:only|classifier|name)|non-executing)\b",
    re.IGNORECASE,
)
KIMI_ADMISSION_TERMS = {
    "explicit": re.compile(r"\bexplicit(?:-only)?\b", re.IGNORECASE),
    "read-only": re.compile(r"\bread-only\b", re.IGNORECASE),
    "independent verification": re.compile(
        r"\bindependent(?:ly)?\s+verif(?:y|ies|ied|ication)\b", re.IGNORECASE
    ),
    "nonauthorizing": re.compile(
        r"\bnon[- ]?authoriz(?:e[ds]?|ing)\b", re.IGNORECASE
    ),
}
KIMI_ADMISSION_TRIGGER = re.compile(
    r"(?:\bkimi\b\s+(?:is|may|can|uses?|remains)\b|"
    r"\b(?:choose|select(?:ed)?|route|use)\s+\bkimi\b|"
    r"\bexplicit(?:-only)?\s+\bkimi\b)",
    re.IGNORECASE,
)
GROK_SELECTION = re.compile(
    r"\bgrok\b[^.]{0,80}\bselect(?:ed|ion)?\b", re.IGNORECASE
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


def test_global_codex_kimi_clauses_do_not_claim_unavailability() -> None:
    """Only the Claude-specific documentation may describe Kimi as unavailable."""

    global_codex_surfaces = (
        ROOT / "INSTALL.md",
        ROOT / "docs" / "agents-mode-reference.md",
        ROOT / "src.codex" / "skills" / "init-project" / "SKILL.md",
        ROOT / "src.codex" / "skills" / "init-project" / "agents" / "openai.yaml",
        ROOT / "src.codex" / "skills" / "second-opinion" / "SKILL.md",
        ROOT / "src.codex" / "skills" / "second-opinion" / "agents" / "openai.yaml",
    )
    for path in global_codex_surfaces:
        for line in path.read_text(encoding="utf-8").splitlines():
            for clause in re.split(r"(?<=[.!?;])\s+|,\s+and\s+(?=Grok\b)", line):
                if re.search(r"\bKimi (?:is explicit-only|requires explicit global)", clause):
                    assert not re.search(r"\b(?:unavailable|disabled)\b", clause, re.IGNORECASE), (
                        f"stale Kimi unavailability clause in {path.relative_to(ROOT)}: {clause}"
                    )


def test_kimi_grok_live_inventory_and_nonexecution_language() -> None:
    """Every live mention must state its provider-specific safety boundary."""

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
                mentions_grok = re.search(r"\bgrok\b", clause, re.IGNORECASE)
                if SEMANTIC_TERMS.search(clause) and not POLICY_ENUMERATION.search(clause):
                    if mentions_grok:
                        assert GROK_NONEXECUTION_TERMS.search(clause), (
                            f"executable Grok clause in {relative_path}: {clause}"
                        )
                if GROK_SELECTION.search(clause):
                    assert re.search(
                        r"\bnever(?:\s+be)?\s+select", clause, re.IGNORECASE
                    ), (
                        f"Grok selection wording in {relative_path}: {clause}"
                    )

    for relative_path, lines in hits.items():
        text = "\n".join(lines)
        if KIMI_ADMISSION_TRIGGER.search(text):
            for boundary, pattern in KIMI_ADMISSION_TERMS.items():
                assert pattern.search(text), (
                    f"Kimi admission lacks {boundary} in {relative_path}"
                )
        elif SEMANTIC_TERMS.search(text):
            assert GROK_NONEXECUTION_TERMS.search(text), (
                f"Kimi is neither safely admitted nor unavailable in {relative_path}"
            )
        assert "Grok CLI" not in text, f"resolved-provider template leaks Grok in {relative_path}"
        assert "external CLI (Grok" not in text, f"execution template leaks Grok in {relative_path}"
