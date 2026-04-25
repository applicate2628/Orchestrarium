from __future__ import annotations

from .models import Quote


CATALOG = {
    ("us", "basic"): (1000, "USD"),
    ("us", "pro"): (2100, "USD"),
    ("eu", "basic"): (1200, "EUR"),
    ("eu", "pro"): (2500, "EUR"),
}


def quote_account(account_id: str, sku: str, quantity: int = 1) -> Quote:
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    region = "us"
    unit_cents, currency = CATALOG[(region, sku)]
    return Quote(
        account_id=account_id,
        region=region,
        sku=sku,
        quantity=quantity,
        unit_cents=unit_cents,
        currency=currency,
        total_cents=unit_cents * quantity,
        source="api-legacy",
    )
