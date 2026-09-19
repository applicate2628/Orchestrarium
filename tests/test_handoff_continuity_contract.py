"""Focused source guard for the accepted handoff-continuity contract.

The deterministic checks protect the shipped owner projections. Independent
reviewer delta tests remain responsible for pressure-testing agent behavior.
"""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent

HANDOFFS = (
    ROOT / "src.codex" / "skills" / "lead" / "subagent-contracts.md",
    ROOT / "src.claude" / "agents" / "contracts" / "subagent-contracts.md",
)
LEADS = (
    ROOT / "src.codex" / "skills" / "lead" / "SKILL.md",
    ROOT / "src.claude" / "skills" / "lead" / "SKILL.md",
)
OPERATING_MODELS = (
    ROOT / "src.codex" / "skills" / "lead" / "operating-model.md",
    ROOT / "src.claude" / "agents" / "contracts" / "operating-model.md",
)
CODEX_LEAD = LEADS[0]
CLAUDE_LEAD = LEADS[1]
SHARED = ROOT / "shared" / "references" / "subagent-operating-model.md"
CLAUDE_FULL_DELIVERY = (
    ROOT / "src.claude" / "agents" / "team-templates" / "full-delivery.json"
)


def _read(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def _requires(path: Path, *fragments: str) -> None:
    text = _read(path)
    for fragment in fragments:
        assert fragment in text, (path, fragment)


def test_pao_revision_and_scenario_reject_stale_environment_evidence() -> None:
    for path in HANDOFFS:
        _requires(
            path,
            "only when accepted work already has a Primary Acceptance Oracle (PAO)",
            "`Approved inputs` names its accepted revision",
            "`Scope` carries its exact scenario, source, configuration, environment, and invocation bounds",
            "`Acceptance criteria` carries success, failure, safety, cleanup, evidence, and owner requirements",
            "actual source, configuration, and environment used",
            "Any PAO revision, scoped scenario, source, configuration, or environment mismatch makes evidence stale and nonauthorizing",
            "Trivial work and work with no PAO gain no requirement",
        )


def test_upstream_claim_owner_survives_implementation_and_review() -> None:
    for path in LEADS + OPERATING_MODELS:
        _requires(
            path,
            "accepted Architect or domain artifact/revision unchanged in `Approved inputs`",
            "does not author, reorder, replace, or become owner of those claims",
            "maps each upstream claim number to its implementation surface and observed evidence/result",
            "claims and implementation evidence side by side",
            "accepted constraints and claim identity needed for independent challenge",
            "without requiring the entire unused design prose",
            "Missing or changed claims return `REVISE` to their Architect or domain owner",
            "No upstream claims means no synthetic claim set",
        )
        assert "Builder includes claims list" not in _read(path), path
        assert "claims list from the builder's artifact" not in _read(path), path


def test_context_dependent_tool_requires_its_existing_scope_binding() -> None:
    for path in HANDOFFS:
        _requires(
            path,
            "current runtime schema requires a context-dependent argument",
            "supplies that concrete argument from `Scope` or `Approved inputs`",
            "Recording only the tool name is incomplete",
            "caller guidance, not a validator or sandbox",
            "Do not add a handoff field or hardcode tool names",
        )


def test_pending_init_remains_unsettled_without_invented_failure_semantics() -> None:
    _requires(
        CODEX_LEAD,
        "`pending_init` is an observed non-terminal host state with undocumented cause",
        "does not prove model, provider, or executable unavailability",
        "Perform one bounded current-state probe",
        "preserve the run as unsettled",
        "existing bounded wait, stall, cancel, or resume posture",
        "do not infer retry, replacement, or provider-failure semantics",
        "`unspecified by runtime` alone neither denies nor authorizes the result",
        "Absence of an in-repository host adapter does not admit a new runtime subsystem",
    )
    assert "`pending_init`" not in _read(CLAUDE_LEAD)


def test_ordinary_required_effort_does_not_override_exact_profile_membership() -> None:
    for path in LEADS:
        _requires(
            path,
            "exact membership in task `admissibleProfiles` intersected with role `allowedProfiles`",
            "`requiredEffort` is descriptive compatibility metadata, not an independent ordinal floor",
            "Special corridor and explicit floor rules remain separate",
        )


def test_shared_scientific_chain_has_an_independent_conformance_gate() -> None:
    _requires(
        SHARED,
        "computational-scientist (model)",
        "scientific-software-engineer",
        "computational-scientist (scientific-conformance-review; independent run)",
        "qa-engineer",
    )
    for path in OPERATING_MODELS:
        _requires(
            path,
            "scientific-software-engineer",
            "computational-scientist (scientific-conformance-review; independent run)",
            "qa-engineer",
        )


def test_shared_handoff_owner_carries_the_cross_provider_semantics() -> None:
    _requires(
        SHARED,
        "Conditional PAO carry-forward",
        "Any PAO revision, scoped scenario, source, configuration, or environment mismatch makes evidence stale and nonauthorizing",
        "Upstream claim ownership",
        "does not author, reorder, replace, or become owner of those claims",
        "accepted constraints and claim identity needed for independent challenge",
        "without requiring the entire unused design prose",
        "Context-dependent tool arguments",
        "Recording only the tool name is incomplete",
        "Ordinary profile admission",
        "`requiredEffort` is descriptive compatibility metadata, not an independent ordinal floor",
    )


def test_claude_full_delivery_keeps_scientific_runs_conditional_and_ordered() -> None:
    template = json.loads(CLAUDE_FULL_DELIVERY.read_text(encoding="utf-8"))
    assert template["chain"] == [
        "intake",
        "research",
        "design",
        "plan",
        "implement",
        "QA",
        "review",
    ]
    assert template["requiredRoles"] == [
        "analyst",
        "architect",
        "planner",
        "qa-engineer",
    ]
    assert template["minRoles"] == 4

    roles = template["roles"]
    model_rows = [
        (index, row)
        for index, row in enumerate(roles)
        if row["agentType"] == "computational-scientist"
    ]
    assert len(model_rows) == 2
    assert model_rows[0][1] == {
        "agentType": "computational-scientist",
        "stage": "design",
        "whenNeeded": "scientific/numerical model",
    }
    assert model_rows[1][1] == {
        "agentType": "computational-scientist",
        "stage": "QA",
        "whenNeeded": (
            "independent scientific-conformance-review after "
            "scientific-software-engineer and before generic QA"
        ),
    }
    sse_index, sse = next(
        (index, row)
        for index, row in enumerate(roles)
        if row["agentType"] == "scientific-software-engineer"
    )
    assert sse == {
        "agentType": "scientific-software-engineer",
        "stage": "implement",
        "whenNeeded": "scientific/numerical implementation",
    }
    qa_index = next(
        index for index, row in enumerate(roles) if row["agentType"] == "qa-engineer"
    )
    assert model_rows[0][0] < sse_index < model_rows[1][0] < qa_index
    assert "two independent stage-scoped runs" in template["notes"]
