"""Offline failure recovery over real Kimi receipts and canonical ledger bytes."""
import json

import pytest

from test_sdk_kimi_received_e2e import make_received
from test_sdk_kimi import owner
from sdk_execution.kimi import KimiAdapterError


def rows(fixture):
    return [json.loads(line) for line in fixture.ledger_path.read_text(
        encoding="utf-8").splitlines() if line.strip()]


def test_uncommitted_receipt_never_claims_terminal_digest(tmp_path, monkeypatch):
    def configure():
        def refuse(_receipt, _payload):
            raise OSError("injected receipt commit failure")
        monkeypatch.setattr(owner.TerminalReceiptV1, "commit", refuse)
    fixture = make_received(tmp_path, monkeypatch, configure=configure)
    assert fixture.result.status != "completed"
    assert all("terminalReceiptSha256" not in row and
               "terminalReceiptSizeBytes" not in row for row in rows(fixture))
    before = fixture.ledger_path.read_bytes()
    with pytest.raises((KimiAdapterError, ValueError)):
        fixture.adapter.reconcile_received(fixture.request, output_context=fixture.output_context)
    assert fixture.ledger_path.read_bytes() == before
    assert len(fixture.requests) == 1


def test_delivery_loss_after_commit_keeps_canonical_recoverable_result(tmp_path, monkeypatch):
    original = owner.commit_reserved_terminal
    def configure():
        def refuse_delivery(reserved, payload, deliver):
            def broken(_payload):
                raise OSError("injected result sink failure")
            return original(reserved, payload, broken)
        monkeypatch.setattr(owner, "commit_reserved_terminal", refuse_delivery)
    fixture = make_received(tmp_path, monkeypatch, configure=configure)
    terminals = [row for row in rows(fixture) if row.get("eventKind") == "terminal"]
    assert len(terminals) == 1
    assert "resultDelivered=false" in terminals[0]["notes"]
    assert terminals[0]["terminalReceiptSizeBytes"] == len(fixture.receipt_path.read_bytes())
    ledger_before = fixture.ledger_path.read_bytes()
    receipt_before = fixture.receipt_path.read_bytes()
    recovered = fixture.adapter.reconcile_received(
        fixture.request, output_context=fixture.output_context)
    assert recovered.terminal_json is not None
    assert json.loads(recovered.terminal_json)["resultText"] == "artifact\nGATE: PASS\n"
    assert fixture.ledger_path.read_bytes() == ledger_before
    assert fixture.receipt_path.read_bytes() == receipt_before
    assert len(fixture.requests) == 1


def test_legacy_terminal_without_digest_is_metadata_only(tmp_path, monkeypatch):
    fixture = make_received(tmp_path, monkeypatch)
    assert fixture.result.status == "completed"
    legacy = rows(fixture)
    for row in legacy:
        row.pop("terminalReceiptSha256", None)
        row.pop("terminalReceiptSizeBytes", None)
    fixture.ledger_path.write_text(
        "".join(json.dumps(row) + "\n" for row in legacy), encoding="utf-8")
    before = fixture.ledger_path.read_bytes()
    recovered = fixture.adapter.reconcile_received(
        fixture.request, output_context=fixture.output_context)
    assert recovered.terminal_json is None
    assert json.loads(recovered.ledger_json)["eventKind"] == "terminal"
    assert fixture.ledger_path.read_bytes() == before
    assert len(fixture.requests) == 1


@pytest.mark.parametrize("change", ["same_size", "truncated"])
def test_modified_receipt_is_not_recovered_from_matching_ids(tmp_path, monkeypatch, change):
    fixture = make_received(tmp_path, monkeypatch)
    assert fixture.result.status == "completed"
    original = fixture.receipt_path.read_bytes()
    changed = original.replace(b"artifact", b"altered!") if change == "same_size" else original[:-1]
    assert changed != original
    if change == "same_size":
        assert len(changed) == len(original)
    fixture.receipt_path.write_bytes(changed)
    before = fixture.ledger_path.read_bytes()
    with pytest.raises(KimiAdapterError, match="terminal_receipt_changed"):
        fixture.adapter.reconcile_received(
            fixture.request, output_context=fixture.output_context)
    assert fixture.ledger_path.read_bytes() == before
    assert fixture.receipt_path.read_bytes() == changed
    assert len(fixture.requests) == 1


@pytest.mark.parametrize("denied_effect", ["kimi_receipt_read", "kimi_receipt_result"])
def test_current_permission_revocation_prevents_recovered_export(
        tmp_path, monkeypatch, denied_effect):
    fixture = make_received(tmp_path, monkeypatch)
    assert fixture.result.status == "completed"
    before = {path: path.read_bytes() for path in
              (fixture.ledger_path, fixture.receipt_path)}
    effects = []
    def current(request, effect):
        assert request == fixture.request
        effects.append(effect)
        if effect == denied_effect:
            raise ValueError("current owner revoked this receipt read")
    monkeypatch.setattr(fixture.adapter, "_assert_current", current)
    with pytest.raises(KimiAdapterError, match="kimi_receiving_authority_denied"):
        fixture.adapter.reconcile_received(
            fixture.request, output_context=fixture.output_context)
    assert effects == (["kimi_receipt_read"] if denied_effect == "kimi_receipt_read"
                       else ["kimi_receipt_read", "kimi_receipt_result"])
    assert before == {path: path.read_bytes() for path in before}
    assert len(fixture.requests) == 1
