from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LedgerEvent:
    event_id: str
    account_id: str
    period: str
    currency: str
    kind: str
    amount_cents: int
    sequence: int
    voids_event_id: str | None = None


@dataclass(frozen=True)
class LedgerRow:
    account_id: str
    period: str
    currency: str
    net_cents: int
    event_count: int
    evidence_ids: tuple[str, ...]
