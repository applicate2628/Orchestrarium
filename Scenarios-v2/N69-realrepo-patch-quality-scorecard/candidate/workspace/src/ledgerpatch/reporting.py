from __future__ import annotations

from .models import LedgerRow


def summarize_ledger(rows: list[LedgerRow]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for row in rows:
        totals[row.currency] = totals.get(row.currency, 0) + row.net_cents
    return totals
