from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AccountRef:
    account_id: str
    region: str = "us"


@dataclass(frozen=True)
class Quote:
    account_id: str
    region: str
    sku: str
    quantity: int
    unit_cents: int
    currency: str
    total_cents: int
    source: str
