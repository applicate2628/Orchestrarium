"""Source contract checks; no installed role or provider execution."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "src.codex/skills"
CLAUDE = ROOT / ("adapters/claude" if (ROOT / "adapters/claude").is_dir() else "src.claude")
SDK = (ROOT / "docs/sdk-execution.md").is_file()


def role(name: str) -> str:
    return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")


def test_lead_checks_actual_activation_against_frozen_input():
    body = role("lead")
    assert "actual activation" in body
    assert "catalog visibility is not activation" in body


def test_planner_checks_parallel_dependency_graph_without_another_gate():
    body = role("planner")
    assert "dependency cycle" in body
    assert "shared write surface" in body
    assert "not a new gate" in body


def test_analyst_reassigns_implementation_instead_of_widening_role():
    body = role("analyst")
    assert "different assigned profession" in body
    assert "negative control" in body


def test_product_evidence_detects_misleading_aggregation():
    body = role("product-analyst")
    assert "population and denominator" in body
    assert "counter-signal" in body
    assert "proxy" in body


def test_product_manager_names_displaced_work_and_switching_fact():
    body = role("product-manager")
    assert "best displaced option" in body
    assert "observation that would change the order" in body


def test_consultant_resolves_independent_model_before_drafting():
    for body in (role("consultant"), (CLAUDE / "agents/consultant.md").read_text(encoding="utf-8")):
        branch = next(line for line in body.splitlines() if line.startswith(">    - `internal`:"))
        assert "different-model" in branch and "before drafting" in branch
        assert "--permission-mode bypassPermissions" not in body
        assert "strongest counterargument" in body
    ui = (SKILLS / "consultant/agents/openai.yaml").read_text(encoding="utf-8")
    assert "blind options" in ui and "reserveResolver=" not in ui


def test_worker_pins_base_and_checks_scope_before_integration():
    body = role("external-worker")
    assert "frozen base revision" in body
    assert "observed changed paths" in body
    assert ("scoped-worker admission, currentness and terminal receiving" in body) is SDK
    if SDK:
        assert body.index("For the explicitly selected legacy CLI route:") < body.index("Use the approved thin wrapper") < body.index("For an explicitly selected, supported SDK worker route")
        assert "## Legacy CLI launcher details" in body


def test_reviewer_distinguishes_checked_scope_and_receiving_versions():
    body = role("external-reviewer")
    assert "checked, not checked, or unverified" in body
    assert "frozen revision" in body
    assert ("Version 3" in body) is SDK
    claude = ROOT / ("adapters/claude" if SDK else "src.claude")
    wrapper = (claude / "agents/external-reviewer.md").read_text(encoding="utf-8")
    assert ("direct Codex SDK review route" in wrapper) is SDK
    if SDK:
        assert wrapper.index("For the explicitly selected legacy CLI route:") < wrapper.index("Use the approved thin wrapper") < wrapper.index("For the explicitly selected direct Codex SDK review route")

    if SDK:
        assert body.index("For the explicitly selected legacy CLI route:") < body.index("Use the approved thin wrapper") < body.index("For the explicitly selected, supported Codex SDK review route")
        assert "## Legacy CLI launcher details" in body
