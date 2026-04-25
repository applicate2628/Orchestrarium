from __future__ import annotations

import argparse
import json

from .api import quote_invoice


def render_quote(argv: list[str]) -> str:
    parser = argparse.ArgumentParser(prog="billinglink-quote")
    parser.add_argument("--customer-id", required=True)
    parser.add_argument("--sku", required=True)
    parser.add_argument("--quantity", type=int, default=1)
    args = parser.parse_args(argv)

    payload = {"customer_id": args.customer_id, "sku": args.sku, "quantity": args.quantity}
    return json.dumps(quote_invoice(payload), sort_keys=True) + "\n"
