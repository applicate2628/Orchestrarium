from ledgerpatch import LedgerEvent, build_account_ledger, summarize_ledger


def test_visible_charge_and_refund_path():
    events = [
        LedgerEvent("e-1", "acct-a", "2026-04", "USD", "charge", 1200, 1),
        LedgerEvent("e-2", "acct-a", "2026-04", "USD", "refund", 200, 2),
        LedgerEvent("e-3", "acct-b", "2026-04", "EUR", "charge", 500, 3),
    ]

    rows = build_account_ledger(events)

    assert [(row.account_id, row.currency, row.net_cents) for row in rows] == [
        ("acct-a", "USD", 1000),
        ("acct-b", "EUR", 500),
    ]
    assert summarize_ledger(rows) == {"USD": 1000, "EUR": 500}
