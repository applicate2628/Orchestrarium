from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DiscountRule:
    rule_id: str
    tier: str
    region: str
    sku_prefix: str
    min_quantity: int
    discount_bps: int
    priority: int
    effective_from: int
    effective_until: int


@dataclass(frozen=True)
class QuoteRequest:
    request_id: str
    account_id: str
    tier: str
    region: str
    sku: str
    quantity: int
    ordered_at: int
    unit_price_cents: int


@dataclass(frozen=True)
class QuoteResult:
    request_id: str
    account_id: str
    sku: str
    gross_cents: int
    discount_bps: int
    net_cents: int
    applied_rule_id: str | None
    reason: str
