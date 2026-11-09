"""Source-contract regressions; these do not claim live model/Goal behavior."""
from pathlib import Path
import ast

import pytest
from policy_text_contract import selected_unit

ROOT = Path(__file__).resolve().parent.parent
OWNER = "Goal resumption and hold currency (binding)."
SHARED = ROOT / "shared/AGENTS.shared.md"
PROJECTIONS = (
    ("src.codex/skills/lead/SKILL.md", "Flow-continuity rule"),
    ("src.codex/skills/lead/operating-model.md", "Primary-task lock"),
    ("src.claude/agents/contracts/operating-model.md", "Primary-task lock"),
    ("shared/references/subagent-operating-model.md", "3.9 Rolling-loop execution"),
)
CASES = {
    "completed_no_goal_then_enable_next_day": (
        "later verified user enable/resume for that admitted task/scope",
        "completed one-off without-Goal request",
        "continue the remaining admitted work",
    ),
    "park_then_enable_next_day": (
        "completed parking or stop-after-current-run request",
        "not a permanent ban",
        "no second confirmation of already admitted scope",
    ),
    "new_goal_after_no_goal_work_has_no_old_identity_requirement": (
        "This includes a newly enabled Goal after work without Goal; no prior Goal ID is required",
    ),
    "cancel_and_pause_need_owner_authority_not_a_blocker": (
        "Set paused/cancelled only under current user/native-owner authority, never merely because execution is blocked",
    ),
    "different_goal_does_not_release_the_hold": (
        "A different task/Goal neither releases another task's current hold nor inherits its completed one-off holds",
    ),
    "completed_work_and_immutable_history_remain_closed": (
        "without reopening verified completed work or rewriting immutable history",
    ),
    "small_batches_are_not_total_stop": (
        "Batch-size limits constrain batches, not all progress",
    ),
    "stale_recovery_is_not_new_authority": (
        "Recovery notes record authority; they do not create it",
        "reconcile stale parked/blocked/complete summaries",
    ),
    "old_active_snapshot_does_not_prove_user_resume": (
        "query current native state",
        "preserve original task/native binding",
        "An active snapshot alone does not prove a later user resume",
    ),
    "new_stop_and_required_approvals_still_hold": (
        "Preserve later explicit stops, unfulfilled conditions, safety, scope, publication and spending approvals",
        "still-current native PAUSED",
    ),
    "unnecessary_question_or_three_empty_passes_not_blocker": (
        "an unanswered optional question, repeated recovery text or a no-progress counter is not blocker evidence",
        "never manufacture a global stop while independent authorized work is ready",
    ),
    "real_blocker_is_action_scoped": (
        "Before setting a Goal to blocked",
        "verify current user authority or concrete blockers covering every remaining authorized action",
        "name each cause and resume condition",
    ),
}

def check(source: str, required: tuple[str, ...]) -> None:
    rule = " ".join(selected_unit(source, "Core delegation principles", OWNER).split())
    for fragment in required:
        assert fragment in rule, fragment


@pytest.mark.parametrize("case", CASES)
def test_goal_resume_scenarios_are_owned_by_live_shared_rule(case: str) -> None:
    check(SHARED.read_text(encoding="utf-8"), CASES[case])


@pytest.mark.parametrize("case", CASES)
def test_goal_rule_rejects_missing_scenario_duty(case: str) -> None:
    source = SHARED.read_text(encoding="utf-8")
    check(source, CASES[case])
    unit = selected_unit(source, "Core delegation principles", OWNER)
    mutated = unit.replace(CASES[case][0], "Unsupported historical assumption", 1)
    with pytest.raises(AssertionError):
        check(source.replace(unit, mutated, 1), CASES[case])


def test_goal_rule_in_example_cannot_replace_binding_owner() -> None:
    source = SHARED.read_text(encoding="utf-8")
    unit = selected_unit(source, "Core delegation principles", OWNER)
    with pytest.raises(AssertionError):
        check(source.replace(unit, "\n```text\n" + unit + "\n```\n", 1), CASES["park_then_enable_next_day"])


@pytest.mark.parametrize("relative,section", PROJECTIONS)
def test_recovery_projection_reconciles_current_authority(relative: str, section: str) -> None:
    unit = selected_unit((ROOT / relative).read_text(encoding="utf-8"),
                         section, "After context compaction")
    assert "Goal resumption and hold currency" in unit
    assert "current authority" in unit
    assert "unless the user or persisted status says" not in unit
    assert "user/persisted holds" not in unit


def test_stop_after_current_run_is_consumed_by_later_resume() -> None:
    unit = selected_unit((ROOT / PROJECTIONS[0][0]).read_text(encoding="utf-8"),
                         "Flow-continuity rule", "For stop-after-current-run intent")
    assert "Goal resumption and hold currency" in unit
    assert "later user resume" in unit


@pytest.mark.parametrize("relative,constant", (
    ("scripts/universal-hooks/scripts/mcp_continuity_policy.py", "TURN_ANCHOR_CONTEXT"),
    ("src.codex/skills/lead/scripts/mcp_continuity_policy.py", "TURN_ANCHOR_CONTEXT"),
    ("src.claude/agents/scripts/mcp_continuity_policy.py", "TURN_ANCHOR_CONTEXT"),
    ("src.codex/skills/lead/hooks/check-parallel-mcp-momentum.py", "REMINDER"),
))
def test_reminders_reconcile_holds_without_becoming_state_mutators(relative: str, constant: str) -> None:
    tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
    node = next(node for node in tree.body if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == constant for target in node.targets))
    reminder = ast.literal_eval(node.value)
    assert "Apply shared Goal resumption and hold currency before treating an earlier hold as current" in reminder
    assert "Never cancel or block a resumed Goal from stale recovery alone" in reminder


def test_current_instruction_renderers_retain_goal_authority_rule() -> None:
    # Existing pure renderer extraction: no install, import of effect owners, or model call.
    import re
    tree = ast.parse((ROOT / "scripts/production_installer.py").read_text(encoding="utf-8"))
    names = {"_codex_document_payload", "_render_codex_document", "_render_claude_document"}
    nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert {node.name for node in nodes} == names
    ns = {"re": re, "_CLAUDE_DOC_MARKER_PREFIXES": tuple(
        f"<!-- {edge} ORCHESTRARIUM {kind} MANAGED"
        for kind in ("CLAUDE", "SHARED") for edge in ("BEGIN", "END"))}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in {"CODEX_BEGIN", "CODEX_END"}:
                    ns[target.id] = ast.literal_eval(node.value)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<pure instruction renderers>", "exec"), ns)
    shared = SHARED.read_text(encoding="utf-8")
    provider = (ROOT / "src.codex/AGENTS.codex.md").read_text(encoding="utf-8")
    payload = ns["CODEX_BEGIN"] + "\n" + ns["_codex_document_payload"](shared, provider) + ns["CODEX_END"] + "\n"
    for text in (
        ns["_render_codex_document"](None, payload),
        ns["_render_claude_document"](None, shared, claude=False),
    ):
        check(text, tuple(fragment for fragments in CASES.values() for fragment in fragments))
