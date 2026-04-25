from __future__ import annotations

from collections import defaultdict

from .models import LedgerEvent, LedgerRow


def build_account_ledger(events: list[LedgerEvent]) -> list[LedgerRow]:
    """Build per-account ledger totals from charge/refund events.

    Known defect: this starter implementation handles only the visible happy path. It does not
    replace duplicate events by latest sequence, does not honor void events, and leaves ordering
    behavior under-specified for hidden consumers.
    """

    totals: dict[tuple[str, str, str], int] = defaultdict(int)
    evidence: dict[tuple[str, str, str], list[str]] = defaultdict(list)

    for event in events:
        key = (event.account_id, event.period, event.currency)
        amount = event.amount_cents
        if event.kind == "refund":
            amount = -amount
        totals[key] += amount
        evidence[key].append(event.event_id)

    rows = [
        LedgerRow(
            account_id=account_id,
            period=period,
            currency=currency,
            net_cents=net_cents,
            event_count=len(evidence[(account_id, period, currency)]),
            evidence_ids=tuple(evidence[(account_id, period, currency)]),
        )
        for (account_id, period, currency), net_cents in totals.items()
    ]
    return sorted(rows, key=lambda row: (row.account_id, row.period, row.currency))
