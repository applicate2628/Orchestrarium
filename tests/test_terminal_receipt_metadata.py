"""Paired CLI receipt commitments do not replace lifecycle artifact metadata."""
import pytest
import jsonschema
from test_agent_run_ledger import load_ledger_module,prepare_valid_work_item

def event(item):
    return dict(schemaVersion=2,runId="receipt-terminal",workItem=item.name,role="external-reviewer",
        executionRole="external-reviewer",assignedRole="qa-engineer",provider="codex",model="fixture-model",
        status="blocked",gate="none",eventKind="terminal",launchRunId="receipt-launch",scope=["review"],
        effort="high",terminalClass="external-nonauthorizing",authorizing=False,
        actualExecutionPath="direct-external-cli",artifactIdentity="review-output",closesRunIds=[],
        evidence=[{"kind":"command","ref":"fixture receipt committed"}],
        startedAt="2026-11-18T00:00:00Z",updatedAt="2026-11-18T00:00:00Z")

def test_valid_receipt_commitment_and_legacy_event(tmp_path):
    validator=load_ledger_module().load_validator();item=prepare_valid_work_item(tmp_path)
    for value in [event(item),dict(event(item),terminalReceiptSha256="a"*64,terminalReceiptSizeBytes=7)]:
        errors=[];validator.validate_event(value,item,set(),errors)
        assert errors==[]
        jsonschema.validate(value,validator.AGENT_RUN_SCHEMA)
        assert "artifactRevision" not in value

@pytest.mark.parametrize("change",[
    {"terminalReceiptSizeBytes":None},{"terminalReceiptSizeBytes":True},
    {"terminalReceiptSizeBytes":0},{"terminalReceiptSha256":"A"*64},
    {"terminalReceiptSha256":None},{"eventKind":"launch"},
    {"actualExecutionPath":"direct-external-sdk"},{"authorizing":True},
    {"terminalClass":"internal-authorizing"}])
def test_receipt_pair_rejects_crossed_or_malformed_binding(tmp_path,change):
    validator=load_ledger_module().load_validator();item=prepare_valid_work_item(tmp_path)
    value=dict(event(item),terminalReceiptSha256="a"*64,terminalReceiptSizeBytes=7)
    value.update(change)
    if change.get("terminalReceiptSha256","missing") is None:value.pop("terminalReceiptSha256")
    if change.get("terminalReceiptSizeBytes","missing") is None:value.pop("terminalReceiptSizeBytes")
    errors=[];validator.validate_event(value,item,set(),errors)
    assert any("receipt requires paired" in error for error in errors),errors
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(value,validator.AGENT_RUN_SCHEMA)
