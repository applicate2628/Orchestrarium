"""Source-only guard for ready-solution receiving; not a model-behavior test."""

from pathlib import Path

from policy_text_contract import selected_unit

ROOT = Path(__file__).resolve().parent.parent
OWNERS = (
    ("src.codex/skills/lead/subagent-contracts.md", "Shared handoff template"),
    ("src.claude/agents/contracts/subagent-contracts.md", "Handoff template"),
    ("shared/references/subagent-operating-model.md", "4. Standard task template for any subagent"),
)
MARKER = "Reuse-assessment carry-forward."
BASELINE = (
    "For admitted adoption of a ready solution, use that solution as the baseline",
    "before nontrivial reimplementation",
    "smallest safely authorized check at the requested entry path",
    "Unavailable execution leaves that behavior unverified, not failed",
)
SAFETY = (
    "a concrete source/API incompatibility or safety defect may justify a bounded correction without unsafe execution",
    "independent work that does not assume replacement is necessary",
    "Preserve original useful behavior and required safety, performance, data, authority and publication guarantees",
    "no new report, web search, stage, checker, or tracking file",
)
RECEIVING = (
    "Root/Lead receiving and any already-required review compare the chosen route and next actual operation with the original reuse outcome",
    "passing tests of newly written scaffolding cannot justify that scaffolding",
    "After a user redirects the approach, make the next ready substantive operation serve that correction or state the exact hold",
    "name the actual tested artifact and entry path",
    "never credit an extracted-component harness as the ready product",
)


def _requires(source: str, section: str, fragments: tuple[str, ...]) -> None:
    text = " ".join(selected_unit(source, section, MARKER).split())
    for fragment in fragments:
        assert fragment in text, (section, fragment)


def test_ready_baseline_precedes_reimplementation() -> None:
    for relative, section in OWNERS:
        _requires((ROOT / relative).read_text(encoding="utf-8"), section, BASELINE)


def test_safety_and_unavailable_execution_keep_their_boundaries() -> None:
    for relative, section in OWNERS:
        _requires((ROOT / relative).read_text(encoding="utf-8"), section, SAFETY)


def test_receiving_checks_route_and_corrected_action_not_only_slice_tests() -> None:
    for relative, section in OWNERS:
        _requires((ROOT / relative).read_text(encoding="utf-8"), section, RECEIVING)


def test_removed_duties_or_example_only_rule_are_rejected() -> None:
    for relative, section in OWNERS:
        source = (ROOT / relative).read_text(encoding="utf-8")
        unit = selected_unit(source, section, MARKER)
        variants = [unit.replace(fragment, "", 1) for fragment in BASELINE + SAFETY + RECEIVING]
        variants.append("\n\n\x60\x60\x60text\n" + unit + "\n\x60\x60\x60\n\n")
        for changed in variants:
            assert changed != unit
            try:
                _requires(source.replace(unit, changed, 1), section, BASELINE + SAFETY + RECEIVING)
            except AssertionError:
                continue
            raise AssertionError((relative, "weakened receiving was accepted"))
