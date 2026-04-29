import unittest

from statedock import replay_events


class VisibleReplayTests(unittest.TestCase):
    def test_legacy_credit_debit_replay(self):
        snapshot = replay_events(
            [
                {
                    "account_id": "visible-a",
                    "user_id": "u1",
                    "operation": "credit",
                    "sequence": 1,
                    "amount": 100,
                },
                {
                    "account_id": "visible-a",
                    "user_id": "u2",
                    "operation": "debit",
                    "sequence": 2,
                    "amount": 30,
                },
            ]
        )
        self.assertEqual(snapshot["balances"]["visible-a"], 70)


if __name__ == "__main__":
    unittest.main()
