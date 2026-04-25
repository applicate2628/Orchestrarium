from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .service import quote_account


def quote_invoice(payload: dict[str, Any]) -> dict[str, Any]:
    account_id = payload["customer_id"]
    sku = payload["sku"]
    quantity = int(payload.get("quantity", 1))
    return asdict(quote_account(account_id, sku, quantity))
