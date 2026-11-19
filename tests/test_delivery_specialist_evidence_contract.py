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
    ("performance-reviewer", "SKILL.md", ("exact candidate code", "exact owning baseline", "do not require adjacent commits", "recompute", "accepted metric")),
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


@pytest.mark.parametrize("role", ["performance-engineer", "performance-reviewer"])
def test_performance_evidence_distinguishes_absolute_budget_from_delta(role: str) -> None:
    for path in (SKILLS / role / "SKILL.md", CLAUDE / "agents" / f"{role}.md"):
        content = path.read_text(encoding="utf-8")
        assert "absolute budget" in content, path
        assert "comparative claim" in content, path
        assert "A performance claim passes only with a before/after pair" not in content, path


def test_reliability_receives_only_admitted_route_artifacts() -> None:
    for path in (
        SKILLS / "reliability-engineer" / "SKILL.md",
        CLAUDE / "agents" / "reliability-engineer.md",
    ):
        content = path.read_text(encoding="utf-8")
        assert "only when the admitted route requires them" in content, path
        assert "Require accepted research and design artifacts plus" not in content, path


def test_vcpkg_uses_the_same_command_contract_on_both_routes() -> None:
    skill = (SKILLS / "vcpkg-builder" / "SKILL.md").read_text(encoding="utf-8")
    reference = (
        SKILLS / "vcpkg-builder" / "references" / "lane-workflow.md"
    ).read_text(encoding="utf-8")
    assert "accepted command contract" in skill and "accepted command contract" in reference
    assert "accepted build plan or an equally explicit quick-fix command contract" in skill
    assert "Verify the accepted command contract and required artifact hashes" in skill
    assert "without running a build" in skill and "missing post-run oracle evidence" in skill
    assert "from the accepted plan" not in reference
