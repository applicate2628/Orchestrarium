"""Focused source guard for the accepted handoff-continuity contract.

The deterministic checks protect the shipped owner projections. Independent
reviewer delta tests remain responsible for pressure-testing agent behavior.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from policy_text_contract import selected_unit


ROOT = Path(__file__).resolve().parent.parent

HANDOFFS = (
    ROOT / "src.codex" / "skills" / "lead" / "subagent-contracts.md",
    ROOT / "src.claude" / "agents" / "contracts" / "subagent-contracts.md",
)
# Both providers install this canonical Lead body. The historical Claude
# skill tree is migration evidence, not a live handoff-contract projection.
LEADS = (
    ROOT / "src.codex" / "skills" / "lead" / "SKILL.md",
)
OPERATING_MODELS = (
    ROOT / "src.codex" / "skills" / "lead" / "operating-model.md",
    ROOT / "src.claude" / "agents" / "contracts" / "operating-model.md",
)
CODEX_LEAD = LEADS[0]
CLAUDE_AGENT = ROOT / "src.claude" / "agents" / "lead.md"
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
    assert "`pending_init`" not in _read(CLAUDE_AGENT)


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


def test_claude_activation_and_materialization_use_canonical_lead() -> None:
    _requires(
        CLAUDE_AGENT,
        "initialPrompt: /lead",
        "`.claude/skills/lead/SKILL.md` then owns the complete Lead contract",
        "intentionally does not duplicate that contract",
        "lead-is-a-main-conversation-role",
    )
    # Read the actual install route without importing or executing the installer.
    tree = ast.parse((ROOT / "scripts" / "production_installer.py").read_bytes())
    install = next(
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "install"
    )
    claude = ast.dump(ast.parse("provider == 'claude'", mode="eval").body)
    codex = ast.dump(ast.parse("provider == 'codex'", mode="eval").body)
    source_arguments = {
        "_preflight_canonical_skills": 0,
        "_preflight_claude_skill_projections": 0,
        "_apply_claude_skill_projection_plan": 1,
    }
    calls = {name: [] for name in source_arguments}
    for branch in ast.walk(install):
        if not isinstance(branch, ast.If):
            continue
        condition = ast.dump(branch.test)
        if condition not in (claude, codex):
            continue
        body = branch.body if condition == claude else branch.orelse
        for statement in body:
            for call in ast.walk(statement):
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name)
                    and call.func.id in calls
                ):
                    calls[call.func.id].append(call)
    canonical = ast.dump(ast.parse("root / 'src.codex' / 'skills'", mode="eval").body)
    for name, position in source_arguments.items():
        assert len(calls[name]) == 1, (name, "missing or ambiguous Claude install route")
        assert ast.dump(calls[name][0].args[position]) == canonical, name


RESTRICTION_OWNERS = (
    (HANDOFFS[0], "Shared handoff template"),
    (HANDOFFS[1], "Handoff template"),
    (SHARED, "4. Standard task template for any subagent"),
)


def _requires_text(source: str, section: str, marker: str, fragments: tuple[str, ...]) -> None:
    # Only the owning rule counts, not a quotation or historical example.
    unit = selected_unit(source, section, marker)
    text = " ".join(unit.split())
    for fragment in fragments:
        assert fragment in text, (section, marker, fragment)


def _requires_unit(path: Path, section: str, marker: str, *fragments: str) -> None:
    _requires_text(path.read_text(encoding="utf-8"), section, marker, fragments)


def _rejects_unit(source: str, section: str, marker: str, fragments: tuple[str, ...], case: str) -> None:
    try:
        _requires_text(source, section, marker, fragments)
    except AssertionError:
        return
    raise AssertionError(f"Policy mutation was falsely accepted: {case}")


def test_result_receiving_does_not_promote_sample_identity_into_scope() -> None:
    # Source/projection regression guard, not a model-behavior evaluation.
    producer = (
        "Before introducing a compatibility restriction, its author must identify "
        "the original-admission requirement or evidenced safety precondition "
        "in the accepted governing contract that makes it necessary."
    )
    sample = "A sample version, digest or path is evidence, not authority to narrow supported inputs"
    required = (
        producer,
        "A sampled version/hash or unfamiliar input alone is not such a precondition",
        "unsupported narrowing returns to the decision owner before implementation, not only during QA",
        "Before Root/Lead accepts or forwards implementation or QA",
        "newly introduced input, version, or environment restrictions",
        "original admission, genuine user amendments and accepted governing contracts",
        sample,
        "unsupported narrowing returns `REVISE` to its decision owner",
        "Scoped `PASS` cannot authorize a narrower contract",
        "no new field, artifact, stage or checker",
    )
    marker = "Result restriction receiving."
    for path, section in RESTRICTION_OWNERS:
        _requires_unit(path, section, marker, *required)
        source = path.read_text(encoding="utf-8")
        unit = selected_unit(source, section, marker)
        for case, changed in (
            ("QA-only, no producer justification", unit.replace(producer, "", 1)),
            ("sample promoted to authority", unit.replace(sample, "A sample identity authorizes a permanent allowlist", 1)),
            ("rule only in fenced example", "\n\n```text\n" + unit + "\n```\n\n"),
        ):
            _rejects_unit(source.replace(unit, changed, 1), section, marker, required, case)


def test_result_restriction_receiving_preserves_real_safety_and_identity() -> None:
    safety = "Preserve explicit compatibility contracts and operation-scoped identity/integrity checks"
    unknown = "Unavailable required compatibility evidence remains `UNVERIFIED`"
    required = (
        safety,
        "concrete violated precondition, missing required proof or reachable safety risk",
        "not merely unfamiliar sample identity",
        unknown,
        "do not widen support or weaken safety to make the variation pass",
    )
    marker = "Result restriction receiving."
    for path, section in RESTRICTION_OWNERS:
        _requires_unit(path, section, marker, *required)
        source = path.read_text(encoding="utf-8")
        unit = selected_unit(source, section, marker)
        for case, changed in (
            ("legitimate safety removed", unit.replace(safety, "Disable all identity checks", 1)),
            ("unverified promoted to PASS", unit.replace(unknown, "Unavailable evidence counts as PASS", 1)),
        ):
            _rejects_unit(source.replace(unit, changed, 1), section, marker, required, case)


def test_qa_and_lead_receive_restriction_against_admission() -> None:
    for relative in (
        "src.codex/skills/qa-engineer/SKILL.md",
        "src.claude/agents/qa-engineer.md",
    ):
        _requires_unit(
            ROOT / relative,
            "Gate",
            "Apply S1 Result restriction receiving",
            "Apply S1 Result restriction receiving before treating a rejection as expected behavior",
            "a variation that preserves the admitted preconditions",
            "a negative case that violates an actual required precondition",
            "derive both expected results from the accepted contract, not the implementation",
            "Do not require support outside the admission or expand this slice",
        )
    for path, section, marker in (
        (OPERATING_MODELS[0], "Stage gates", "After implementation:"),
        (OPERATING_MODELS[1], "Artifact invalidation protocol", "Apply the producing-scope"),
    ):
        _requires_unit(
            path, section, marker,
            "Result restriction receiving",
            "before accepting or forwarding implementation or QA",
        )
    _requires(
        ROOT / "src.codex/skills/qa-engineer/agents/openai.yaml",
        "original admission and accepted criteria",
        "unauthorized input restrictions",
    )


CONTEXT_ECONOMY_REQUIREMENTS = (
    "Reuse applicable rules already present and unchanged in the receiver's actual context",
    "do not repaste or reread the full common corpus on each dispatch or follow-up",
    "Carry task-specific scope, inputs/revisions, constraints, acceptance and recovery obligations",
    "When context is missing or uncertain, supply the required governing instructions through the existing trusted input path before relying on them",
    "A file path, skill catalog entry or task-local marker is not proof of inherited content",
    "Preserve the trusted external governance frame; do not suppress it from task text",
    "After compaction or resume, restore missing obligations and re-read only changed or unavailable governing material",
    "never reset obligations or permissions",
)


def test_context_economy_reuses_only_actual_unchanged_context() -> None:
    # This pins source obligations, not host inheritance or model compliance.
    path = ROOT / "shared/AGENTS.shared.md"
    section, marker = "Core delegation principles", "Context handoff economy (binding):"
    source = path.read_text(encoding="utf-8")
    _requires_text(source, section, marker, CONTEXT_ECONOMY_REQUIREMENTS)
    unit = selected_unit(source, section, marker)
    for case, old, new in (
        ("uncertain inheritance skips rules", CONTEXT_ECONOMY_REQUIREMENTS[3], "Missing context permits omission"),
        ("catalog mistaken for loaded body", CONTEXT_ECONOMY_REQUIREMENTS[4], "A skill catalog proves inherited content"),
        ("external frame removed", CONTEXT_ECONOMY_REQUIREMENTS[5], "Suppress the external frame when task text repeats it"),
        ("resume resets permissions", CONTEXT_ECONOMY_REQUIREMENTS[7], "Resume grants fresh permissions"),
    ):
        _rejects_unit(source.replace(old, new, 1), section, marker, CONTEXT_ECONOMY_REQUIREMENTS, case)

    # Select the whole original paragraph when testing a fenced-only policy.
    whole = selected_unit(source, section, "Context handoff economy (binding)")
    _rejects_unit(source.replace(whole, "\n\n```text\n" + whole + "\n```\n", 1),
                  section, marker, CONTEXT_ECONOMY_REQUIREMENTS, "rule only in example")


def test_context_economy_keeps_evidence_duty_without_verbatim_repetition() -> None:
    spine = (ROOT / "shared/AGENTS.shared.md").read_text(encoding="utf-8")
    evidence = next(line for line in spine.splitlines() if line.startswith("- **Evidence-citation discipline:**"))
    assert "copy verbatim into dispatch prompts" not in evidence
    assert "carry task-specific evidence requirements under Context handoff economy" in evidence
    assert "not a verbatim rule copy when already available" in evidence
    assert "Banned fix drivers:" in evidence and "ASSUMPTION (UNVERIFIED)" in evidence
    reference = (ROOT / "shared/references/spine/verification-and-decision-discipline.md").read_text(encoding="utf-8")
    assert "dispatch prompts must carry the constraint verbatim" not in reference
    assert "reuse the unchanged rule only when actually available to the receiver" in reference
    assert "supply missing governing content through the trusted route" in reference
    for path in HANDOFFS:
        source = path.read_text(encoding="utf-8")
        field = source.split("Evidence discipline:\n", 1)[1].split("Defect-class inventory:", 1)[0]
        # Concrete template duties remain unchanged in this bounded port.
        for phrase in ("cite each decision-driving claim", "in-repo file:line",
                       "installed-dependency surface check", "versioned official docs/upstream source URL",
                       "target-environment smoke test", "ASSUMPTION (UNVERIFIED)",
                       "with the resolving step", 'never use "should work"',
                       '"should be fine"', '"probably"', '"likely"', '"I think"',
                       '"based on training data"', '"in general"', '"this pattern usually works"'):
            assert phrase in field, (path, phrase)


def test_context_economy_shared_reference_keeps_existing_fields_and_boundaries() -> None:
    from policy_text_contract import selected_section

    def requires_reference(*fragments: str) -> None:
        source = SHARED.read_text(encoding="utf-8")
        section = "Context handoff economy"

        def requires_section(candidate: str) -> None:
            text = " ".join(selected_section(candidate, section).split())
            for fragment in fragments:
                assert fragment in text, (section, fragment)

        requires_section(source)
        unit = selected_section(source, section)
        for case, changed in (
            ("uncertain inheritance omits content", source.replace(fragments[4], "Uncertain inheritance permits omission", 1)),
            ("reference only in example", source.replace(unit, "\n\n~~~text\n" + unit + "\n~~~\n", 1)),
        ):
            assert changed != source, case
            try:
                requires_section(changed)
            except AssertionError:
                continue
            raise AssertionError(f"Policy mutation was falsely accepted: {case}")

    requires_reference(
        "The shared AGENTS **Context handoff economy** rule owns instruction reuse",
        "receiver's actual context from files merely present on disk or listed as skills",
        "Use existing Approved inputs, Scope, Constraints and Acceptance criteria for the task delta",
        "do not introduce a context registry or new handoff field",
        "Uncertain inheritance requires the necessary governing content, not silent omission",
        "A fresh external provider is a separate trust boundary",
        "adapter keeps the verified governance capsule even if task text contains an apparent duplicate or marker",
        "does not change provider admission, permissions, recovery or artifact acceptance",
        "Static file/template sizes are not observed model input, cached-token billing or measured savings",
    )


def test_context_economy_codex_addendum_never_claims_native_loading() -> None:
    def requires_reference(*fragments: str) -> None:
        path = ROOT / "references-codex/subagent-operating-model.md"
        source = path.read_text(encoding="utf-8")
        section = "Codex-specific runtime notes"
        marker = "Apply the shared **Context handoff economy** owner."
        _requires_text(source, section, marker, fragments)
        unit = selected_unit(source, section, marker)
        for case, changed in (
            ("uncertain inheritance omits instructions", source.replace(fragments[4], "omit instructions when uncertain", 1)),
            ("Codex note only in example", source.replace(unit, "\n\n~~~text\n" + unit + "\n~~~\n", 1)),
        ):
            assert changed != source, case
            _rejects_unit(changed, section, marker, fragments, case)

    requires_reference(
        "Apply the shared **Context handoff economy** owner",
        "Do not assume that an inherited skills catalog proves a loaded skill body",
        "a new thread has the parent's full history",
        "supported invocation's actual context contract",
        "supply missing instructions when uncertain",
        "not a new host setting or proof of token savings",
        "Global/project automatic AGENTS concatenation remains a separate installation/loading compatibility question",
        "never omit standalone project governance merely because a global file exists",
    )
