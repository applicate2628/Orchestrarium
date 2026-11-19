"""Static checks for evidence discipline in the live delivery skills."""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "src.codex" / "skills"
CLAUDE = ROOT / ("adapters/claude" if (ROOT / "adapters/claude").is_dir() else "src.claude")


@pytest.mark.parametrize(("role", "name", "clauses"), [
    ("backend-engineer", "SKILL.md", ("caller deadline", "effective attempt limit", "timeout does not prove", "reconcil")),
    ("data-engineer", "SKILL.md", ("durable write and checkpoint", "affected keys and values", "safe pause", "resume")),
    ("platform-engineer", "SKILL.md", ("full commit SHA", "mutable version tag", "serving health", "mixed-version")),
    ("toolchain-engineer", "SKILL.md", ("independently rebuild", "isolated caches", "different workspace paths", "identical-input")),
    ("reliability-engineer", "SKILL.md", ("eligible events", "low or zero traffic", "short/long", "data-loss")),
    ("performance-engineer", "SKILL.md", ("meaningful change", "interleave", "tail sample", "raw per-run")),
    ("performance-reviewer", "SKILL.md", ("exact baseline and candidate", "do not require adjacent commits", "recompute", "accepted metric")),
    ("vcpkg-builder", "references/lane-workflow.md", ("fresh compilation", "binary-cache reuse", "already-installed/no-op", "ABI identity")),
    ("vcpkg-ports-updater", "references/upstream-sync.md", ("packaging-only", "reset", "incomparable", "consumer", "release tag alone")),
])
def test_delivery_evidence_contract(role: str, name: str, clauses: tuple[str, ...]) -> None:
    paths = [SKILLS / role / name]
    if name == "SKILL.md":
        paths.append(CLAUDE / "agents" / f"{role}.md")
    for path in paths:
        content = path.read_text(encoding="utf-8").casefold()
        missing = [clause for clause in clauses if clause.casefold() not in content]
        assert not missing, (path, missing)
