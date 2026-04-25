import unittest

from entitlemesh import build_entitlement_snapshot, summarize_snapshot


class VisibleEntitlementTests(unittest.TestCase):
    def test_legacy_grant_revoke_snapshot(self):
        rows = build_entitlement_snapshot(
            [
                {
                    "event_id": "legacy-1",
                    "tenant_id": "tenant-visible",
                    "principal_id": "user-a",
                    "resource_id": "report",
                    "action": "grant",
                    "sequence": 1,
                    "plan": "basic",
                },
                {
                    "event_id": "legacy-2",
                    "tenant_id": "tenant-visible",
                    "principal_id": "user-b",
                    "resource_id": "report",
                    "action": "revoke",
                    "sequence": 2,
                },
            ]
        )

        self.assertEqual(
            [(row.principal_id, row.allowed, row.plan) for row in rows],
            [
                ("user-a", True, "basic"),
                ("user-b", False, ""),
            ],
        )
        self.assertEqual(summarize_snapshot(rows)["allowed"], 1)
