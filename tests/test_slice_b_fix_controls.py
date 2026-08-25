from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("slice_b_fix_controls", ROOT / "scripts/provider_prompt.py")
assert SPEC and SPEC.loader
OWNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = OWNER
SPEC.loader.exec_module(OWNER)


def test_wrapper_parser_safety_and_authority_guards() -> None:
    fingerprint = "a" * 64
    assert OWNER.parse_grok_bounded_result(
        b'{"type":"result","output":"advisory"}', fingerprint
    ) == "advisory"
    with pytest.raises(ValueError, match="E_GROK_RESULT_SHAPE_UNVERIFIED"):
        OWNER.parse_grok_bounded_result(b"[]", fingerprint)
    with pytest.raises(ValueError, match="E_EXTERNAL_RESULT_UNSAFE"):
        OWNER.assert_external_result_safe("API_KEY=secret")


def test_external_parser_requires_one_declared_wire_shape_and_semantic_gate() -> None:
    fingerprint = "a" * 64
    assert OWNER.parse_external_provider_result(
        "grok", b'{"type":"result","output":"GATE: REVISE"}', fingerprint
    ) == "GATE: REVISE"
    with pytest.raises(ValueError, match="E_EXTERNAL_RESULT_UNVERIFIED"):
        OWNER.parse_external_provider_result(
            "grok", b'{"type":"result","output":"GATE: BLOCKED"}', fingerprint
        )
    with pytest.raises(ValueError, match="E_EXTERNAL_RESULT_UNVERIFIED"):
        OWNER.parse_external_provider_result(
            "kimi", b'{"type":"assistant_message","text":"GATE: PASS"}\n{}\n', fingerprint
        )


def test_external_controls_do_not_change_legacy_provider_flag_forwarding() -> None:
    legacy = OWNER.parse_control(["topic", "--task-class", "review", "--role", "qa-engineer"])
    assert legacy.task_class is None and legacy.role is None
    assert legacy.provider_flags == ["--task-class", "review", "--role", "qa-engineer"]
    external = OWNER.parse_external_control(
        ["topic", "--task-class", "review", "--role", "qa-engineer"]
    )
    assert external.task_class == "review" and external.role == "qa-engineer"


def test_external_prompt_snapshot_is_bounded_and_strict_utf8(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_bytes(b"12345")
    control = OWNER.Control(prompt_file=prompt)
    monkeypatch.setattr(OWNER, "PROMPT_SNAPSHOT_MAX_BYTES", 4)
    with pytest.raises(ValueError, match="E_EXTERNAL_PROMPT_INVALID"):
        OWNER.prompt_bytes(control, external=True)
    prompt.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="E_EXTERNAL_PROMPT_INVALID"):
        OWNER.prompt_bytes(control, external=True)


@pytest.mark.parametrize(
    "field",
    ("workItem", "assignedInternalRole", "provider", "model", "effort", "mappingLoss", "artifactIdentity", "externalDispatchId", "externalEvidenceRunId", "actualExecutionPath"),
)
def test_external_terminal_ledger_rejects_each_provenance_override(field: str) -> None:
    control = OWNER.Control(ledger="item", task_class="review", role="qa-engineer", ledger_artifact="design.md")
    payload = OWNER.external_execution_provenance(
        control, "kimi", "dispatch", "kimi-code/k3", "unsupported", "no-native-effort-control"
    ).payload()
    payload[field] = "forged"
    with pytest.raises(ValueError, match="E_EXTERNAL_LEDGER_UNVERIFIED"):
        OWNER.external_terminal_ledger_args(
            control, "kimi", "kimi-code/k3", "unsupported", "dispatch", {"executionProvenance": payload}
        )
