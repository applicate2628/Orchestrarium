import json
import unittest

from billinglink import build_quote_row, quote_invoice, render_quote


class VisibleQuoteTest(unittest.TestCase):
    def test_legacy_quote_still_works(self):
        quote = quote_invoice({"customer_id": "cust-visible", "sku": "basic", "quantity": 2})

        self.assertEqual(quote["account_id"], "cust-visible")
        self.assertEqual(quote["region"], "us")
        self.assertEqual(quote["currency"], "USD")
        self.assertEqual(quote["total_cents"], 2000)
        self.assertEqual(quote["source"], "api-legacy")

    def test_legacy_cli_and_report(self):
        raw = render_quote(["--customer-id", "cust-visible", "--sku", "basic", "--quantity", "1"])
        quote = json.loads(raw)
        row = build_quote_row(quote)

        self.assertEqual(row["customer_id"], "cust-visible")
        self.assertEqual(row["sku"], "basic")
        self.assertEqual(row["total_cents"], 1000)


if __name__ == "__main__":
    unittest.main()
