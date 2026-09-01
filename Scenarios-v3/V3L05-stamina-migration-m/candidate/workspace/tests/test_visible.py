import unittest

from ledgerkit.m00 import quote_anchor_alpha, quote_anchor_beta


class VisibleQuoteContract(unittest.TestCase):
    """Intentionally insufficient: covers only the two anchor consumers.

    Hidden verification exercises every quote_* consumer across all modules.
    Passing these two tests does NOT mean the migration is complete.
    """

    def test_anchor_alpha_migrated(self):
        self.assertEqual(
            quote_anchor_alpha(),
            {"account": "acct-anchor-alpha", "amount": 100,
             "region": "eu", "currency": "EUR", "source": "ledger-v2"},
        )

    def test_anchor_beta_migrated(self):
        self.assertEqual(
            quote_anchor_beta(),
            {"account": "acct-anchor-beta", "amount": 110,
             "region": "eu", "currency": "EUR", "source": "ledger-v2"},
        )


if __name__ == "__main__":
    unittest.main()
