from quoteperf import DiscountRule, PricingCatalog, QuoteEngine, QuoteRequest, summarize_quotes


def make_request(**overrides):
    data = {
        "request_id": "q-1",
        "account_id": "acct-1",
        "tier": "pro",
        "region": "us",
        "sku": "sku-1000-widget",
        "quantity": 4,
        "ordered_at": 50,
        "unit_price_cents": 1000,
    }
    data.update(overrides)
    return QuoteRequest(**data)


def test_quote_prefers_higher_priority_rule():
    rules = [
        DiscountRule("base", "pro", "us", "sku-", 1, 100, 1, 0, 100),
        DiscountRule("better", "pro", "us", "sku-1000-", 1, 250, 5, 0, 100),
    ]
    result = QuoteEngine(PricingCatalog(rules)).quote(make_request())
    assert result.applied_rule_id == "better"
    assert result.discount_bps == 250


def test_summary_preserves_no_rule_bucket():
    engine = QuoteEngine(PricingCatalog([]))
    summary = summarize_quotes(engine, [make_request()])
    assert summary["count"] == 1
    assert summary["by_rule"] == {"no-rule": 1}
