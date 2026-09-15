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
    "src.claude/agents/external-worker.md",
    "src.claude/commands/agents-external-brigade.md",
    "src.claude/commands/agents-help.md",
    "src.claude/commands/agents-init-project.md",
    "src.claude/commands/agents-second-opinion.md",
    "src.codex/AGENTS.codex.md",
    "src.codex/skills/consultant/SKILL.md",
    "src.codex/skills/consultant/agents/openai.yaml",
    "src.codex/skills/design-panel/SKILL.md",
    "src.codex/skills/external-brigade/SKILL.md",
    "src.codex/skills/external-worker/SKILL.md",
    "src.codex/skills/init-project/SKILL.md",
    "src.codex/skills/init-project/agents/openai.yaml",
    "src.codex/skills/lead/external-dispatch.md",
    "src.codex/skills/lead/operating-model.md",
    "src.codex/skills/review-loop/SKILL.md",
    "src.codex/skills/second-opinion/SKILL.md",
    "src.codex/skills/second-opinion/agents/openai.yaml",
    "shared/references/cross-pack-reconciliation.md",
    "shared/references/spine/governance-glossary.md",
})
KIMI_WORKER_SURFACES = frozenset(
    {
        "src.claude/agents/external-worker.md",
        "src.codex/skills/external-worker/SKILL.md",
    }
)
KIMI_WORKER_ADMISSION_TERMS = (
    "explicit Kimi engineering",
    "`engineering` mutation class",
    "taxonomy mapping",
    "`external-worker`",
    "validated capability file",
    "caller-scoped worker tools",
    "result remains nonauthorizing",
    "integration owner independently verifies every change",
    "empty tools, Model Context Protocol servers, and subagents with permission `reject`",
)
KIMI_LOCAL_SCALAR_NONADMISSION_TERMS = (
    "selectable here: auto | codex | claude",
    "kimi is explicit-only",
    "not initialized as a project-local scalar",
)
KIMI_ADVISORY_TOGGLE_SURFACES = frozenset(
    {"src.codex/skills/second-opinion/SKILL.md"}
)
KIMI_ADVISORY_TOGGLE_TERMS = (
    "independent advisory memo",
    "Shipped `auto` stays on the Codex/Claude pair",
    "Kimi is explicit-only",
    "canonical Windows wrapper",
    "Grok remains unavailable",
)

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
    "read-only/read-tools boundary": re.compile(
        r"\b(?:read-only|read tools)\b", re.IGNORECASE
    ),
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
    r"`externalProvider:\s*auto \| codex \| claude \| kimi \| grok`",
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
                    if mentions_grok and relative_path != "shared/references/spine/governance-glossary.md":
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
        if relative_path in KIMI_WORKER_SURFACES:
            for required in KIMI_WORKER_ADMISSION_TERMS:
                assert required in text, (
                    f"Kimi engineering admission lacks {required!r} in {relative_path}"
                )
            continue
        if "not initialized as a project-local scalar" in text:
            for required in KIMI_LOCAL_SCALAR_NONADMISSION_TERMS:
                assert required in text, (
                    f"Kimi local-scalar non-admission lacks {required!r} in {relative_path}"
                )
            continue
        if relative_path in KIMI_ADVISORY_TOGGLE_SURFACES:
            full_text = (ROOT / relative_path).read_text(encoding="utf-8")
            for required in KIMI_ADVISORY_TOGGLE_TERMS:
                assert required in full_text, (
                    f"Kimi advisory-toggle boundary lacks {required!r} in {relative_path}"
                )
            continue
        if KIMI_ADMISSION_TRIGGER.search(text):
            for boundary, pattern in KIMI_ADMISSION_TERMS.items():
                if boundary == "explicit" and relative_path == "shared/AGENTS.shared.md":
                    assert "Lead may choose Kimi for bounded independent read-only" in text
                    assert "Kimi: not `auto`/gate/counter" in text
                    continue
                assert pattern.search(text), (
                    f"Kimi admission lacks {boundary} in {relative_path}"
                )
        elif (
            SEMANTIC_TERMS.search(text)
            and relative_path != "shared/references/spine/governance-glossary.md"
        ):
            assert GROK_NONEXECUTION_TERMS.search(text), (
                f"Kimi is neither safely admitted nor unavailable in {relative_path}"
            )
        assert "Grok CLI" not in text, f"resolved-provider template leaks Grok in {relative_path}"
        assert "external CLI (Grok" not in text, f"execution template leaks Grok in {relative_path}"
