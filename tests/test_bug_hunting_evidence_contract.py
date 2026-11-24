"""Regression contract for scoped, hypothesis-appropriate bug diagnosis."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")


def test_canonical_skill_accepts_appropriate_evidence_without_log_monopoly():
    text = read("src.codex/skills/bug-hunting/SKILL.md")
    assert "Static evidence and deterministic unit tests" in text
    assert "runtime or integration evidence" in text
    assert "full, absolute runtime confirmation" not in text
    assert "only a clean runtime log" not in text
    assert "Any moment where you find yourself about to issue an `Edit`" not in text


def test_diagnostics_account_for_observer_effects_and_secrets():
    text = read("src.codex/skills/bug-hunting/SKILL.md")
    assert "observer effects" in text
    for risk in ("timing", "allocation", "locks", "blocking I/O", "secrets"):
        assert risk in text
    assert "observably zero-risk" not in text


def test_scoped_stop_keeps_diagnosis_and_independent_work():
    paths = ("src.codex/skills/bug-hunting/SKILL.md", "adapters/claude/commands/agents-bugfix.md",
             "shared/AGENTS.shared.md", "shared/external-prompt-governance.md")
    for path in paths:
        text = read(path)
        assert "STOP all edits" not in text, path
        assert "affected" in text and "independent" in text, path
        assert "owner" in text and "sibling" in text, path


def test_live_referrals_do_not_reintroduce_logging_monopoly():
    paths = ("shared/references/spine/common-skills.md", "src.codex/skills/bug-hunting/agents/openai.yaml",
             "src.codex/skills/backend-engineer/SKILL.md", "src.codex/skills/qt-ui-engineer/SKILL.md",
             "adapters/claude/agents/backend-engineer.md", "adapters/claude/agents/qt-ui-engineer.md")
    for path in paths:
        text = read(path).lower()
        assert "log first" not in text, path
        assert "evidence" in text, path


def test_verification_and_capture_remain_scoped_and_honest():
    text = read("src.codex/skills/bug-hunting/SKILL.md")
    assert "implemented, not yet verified" in text
    assert "required acceptance" in text
    assert "not a guarantee" in text
    assert "already retained" in text
    assert "diagnostics removed" in text


def test_scoped_stop_rejects_lost_duties_and_unrelated_decoys():
    from test_orchestration_discipline_contract import stop_rule_duties
    text = read("shared/AGENTS.shared.md")
    assert all(stop_rule_duties(text).values())
    cases = (
        ("second-cross-break-stop", "pause speculative changes to the affected mechanism", "continue speculative changes"),
        ("owner-siblings-contract-diagnosis", "diagnose owner/siblings/shared contract", "patch only the symptom"),
        ("independent-continuation", "Continue safe diagnosis and independent authorized work", "Block independent work"),
        ("scoped-escalation", "expand the pause only for evidenced shared dependencies or safety risks", "expand the pause for any inconvenience"),
    )
    for duty, old, new in cases:
        assert text.count(old) == 1
        changed = text.replace(old, new, 1)
        assert not stop_rule_duties(changed)[duty]
        assert not stop_rule_duties(changed + "\n## Example\n" + old + "\n")[duty]
        assert not stop_rule_duties(text.replace(old, old + " only when convenient", 1))[duty]
