"""Static drift checks for the existing QA-owned finding disposition contract."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
CLAUDE = ROOT / ("adapters/claude" if (ROOT / "adapters/claude/agents").is_dir() else "src.claude")
CODEX = ROOT / "src.codex/skills"


def test_named_roles_do_not_reintroduce_literal_or_implicit_registry_writes():
    surfaces = [*CODEX.glob("*/SKILL.md"), *(CLAUDE / "agents").glob("*.md"),
                *(CLAUDE / "agents/contracts").glob("*.md"),
                CODEX / "lead/operating-model.md"]
    scan = re.compile(r"\bfile (?:it|the issue|a low-severity bug)\b.*(?:bug registry|work-items/bugs/)", re.I)
    hits = [(p.relative_to(ROOT).as_posix(), line) for p in surfaces
            for line in p.read_text(encoding="utf-8").splitlines()
            if scan.search(line.replace("**", ""))]
    assert not hits, hits


def test_both_installable_qa_contracts_own_optional_registry_and_direct_write_authority():
    for path in (CODEX / "qa-engineer/SKILL.md", CLAUDE / "agents/qa-engineer.md"):
        text = path.read_text(encoding="utf-8").split("## Bug registry", 1)[1].split("## Bug status lifecycle", 1)[0]
        assert "configured bug registry path" in text
        assert "When no registry is configured" in text
        assert "in-band" in text and "explicitly grants registry-write authority" in text
        assert "sandbox permits that path" in text
