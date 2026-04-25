from __future__ import annotations

from typing import Any


def build_quote_row(quote: dict[str, Any]) -> dict[str, Any]:
    return {
        "customer_id": quote["account_id"],
        "sku": quote["sku"],
        "total_cents": quote["total_cents"],
    }
