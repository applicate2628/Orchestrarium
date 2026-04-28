from __future__ import annotations

from collections.abc import Iterable

from .catalog import PricingCatalog
from .models import DiscountRule, QuoteRequest, QuoteResult


class QuoteEngine:
    def __init__(self, catalog: PricingCatalog):
        self.catalog = catalog

    def quote_many(self, requests: Iterable[QuoteRequest]) -> list[QuoteResult]:
        return [self.quote(request) for request in requests]

    def quote(self, request: QuoteRequest) -> QuoteResult:
        best_rule: DiscountRule | None = None
        best_key: tuple[int, int, int, int] | None = None

        for index, rule in enumerate(self.catalog.rules):
            if not self._matches(rule, request):
                continue
            key = (rule.priority, rule.min_quantity, len(rule.sku_prefix), -index)
            if best_key is None or key > best_key:
                best_key = key
                best_rule = rule

        gross = request.quantity * request.unit_price_cents
        if best_rule is None:
            return QuoteResult(
                request_id=request.request_id,
                account_id=request.account_id,
                sku=request.sku,
                gross_cents=gross,
                discount_bps=0,
                net_cents=gross,
                applied_rule_id=None,
                reason="no-rule",
            )

        discount = gross * best_rule.discount_bps // 10000
        return QuoteResult(
            request_id=request.request_id,
            account_id=request.account_id,
            sku=request.sku,
            gross_cents=gross,
            discount_bps=best_rule.discount_bps,
            net_cents=gross - discount,
            applied_rule_id=best_rule.rule_id,
            reason="matched",
        )

    @staticmethod
    def _matches(rule: DiscountRule, request: QuoteRequest) -> bool:
        return (
            (rule.tier == "*" or rule.tier == request.tier)
            and (rule.region == "*" or rule.region == request.region)
            and request.sku.startswith(rule.sku_prefix)
            and request.quantity >= rule.min_quantity
            and rule.effective_from <= request.ordered_at < rule.effective_until
        )
