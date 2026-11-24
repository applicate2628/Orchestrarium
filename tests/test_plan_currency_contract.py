"""Instruction-surface regression guards, not runtime/model behavior tests."""
from pathlib import Path
from policy_text_contract import selected_unit

ROOT = Path(__file__).resolve().parent.parent
OWNER = "shared/AGENTS.shared.md"
RULE = "Reuse before hand-rolling"
CASES = {
    "changed_owner_and_existing_neighbor": (
        "linked or otherwise evidenced neighboring repositories",
        "current repository owns a capability because an old plan names it",
        "Material evidence that an accepted plan's owner, boundaries or missing-capability premise has changed",
        "bounded architectural revalidation through the existing Architect/review route",
        "before dependent implementation or dispatch",
    ),
    "superseded_plan_and_later_refusal": (
        "including superseding decisions",
        "Generic continuation does not re-admit superseded scope or override a later explicit refusal",
    ),
    "unchanged_resume_and_historical_name": (
        "Age, a historical name or a resumed unchanged task alone triggers no new gate",
    ),
    "exact_readmission_and_structural_conflict": (
        "explicit re-admission resolves scope, not an unresolved structural conflict",
    ),
    "missing_evidence_and_independent_work": (
        "Missing relevant evidence holds only the dependent choice",
        "independent admitted work continues",
    ),
}

def _requires(source, fragments):
    unit = " ".join(selected_unit(source, "Behavior and contract discipline", RULE).split())
    for fragment in fragments:
        assert fragment in unit, fragment

def test_currency_scenarios_remain_in_canonical_policy():
    for fragments in CASES.values():
        _requires((ROOT / OWNER).read_text(encoding="utf-8"), fragments)

def test_removed_clause_or_example_only_cannot_satisfy_contract():
    source = (ROOT / OWNER).read_text(encoding="utf-8")
    fragments = tuple(fragment for group in CASES.values() for fragment in group)
    unit = selected_unit(source, "Behavior and contract discipline", RULE)
    variants = [source.replace(fragment, "", 1) for fragment in fragments]
    variants.append(source.replace(unit, "\n\n" + chr(96)*3 + "text\n" + unit + "\n" + chr(96)*3 + "\n"))
    for changed in variants:
        try:
            _requires(changed, fragments)
        except AssertionError:
            continue
        raise AssertionError("weakened or example-only contract accepted")

def test_receiving_projections_keep_canonical_trigger():
    for relative, heading in (
        ("src.codex/skills/lead/subagent-contracts.md", "Shared handoff template"),
        ("adapters/claude/agents/contracts/subagent-contracts.md", "Handoff template"),
        ("shared/references/subagent-operating-model.md", "4. Standard task template for any subagent"),
    ):
        unit = selected_unit((ROOT / relative).read_text(encoding="utf-8"), heading, "Reuse-assessment carry-forward.")
        for fragment in (
            "Under shared Reuse before hand-rolling",
            "evidenced neighboring owners and implementations",
            "materially invalidated architectural assumptions",
            "before dependent action or dispatch",
            "generic continuation is not re-admission of superseded scope",
            "Age or unchanged resumed work alone adds no gate",
        ):
            assert fragment in unit

def test_architect_consumes_bounded_current_evidence():
    text = (ROOT / "src.codex/skills/architect/SKILL.md").read_text(encoding="utf-8")
    assert "current implementation and evidenced neighboring repositories" in text
    assert "existing artifact and review route" in text
    assert "do not revive superseded scope or seek blanket re-approval of unchanged work" in text

def test_operating_models_route_to_existing_revalidation_owner():
    for relative in ("src.codex/skills/lead/operating-model.md", "adapters/claude/agents/contracts/operating-model.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "materially changed architectural assumptions" in text
        assert "bounded revalidation in shared Reuse before hand-rolling" in text
        assert "retain the existing owner/review route" in text
