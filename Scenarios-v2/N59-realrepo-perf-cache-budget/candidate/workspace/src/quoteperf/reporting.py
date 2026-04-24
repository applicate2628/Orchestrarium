from __future__ import annotations

from collections.abc import Iterable

from .engine import QuoteEngine
from .models import QuoteRequest


def summarize_quotes(engine: QuoteEngine, requests: Iterable[QuoteRequest]) -> dict:
    results = engine.quote_many(list(requests))
    by_rule: dict[str, int] = {}
    for result in results:
        key = result.applied_rule_id or "no-rule"
        by_rule[key] = by_rule.get(key, 0) + 1
    return {
        "count": len(results),
        "gross_cents": sum(result.gross_cents for result in results),
        "net_cents": sum(result.net_cents for result in results),
        "by_rule": by_rule,
    }
