import unittest

from capvault import CapabilityService, ExportRequest, audit_decision


class VisibleCapabilityTests(unittest.TestCase):
    def test_happy_path_export_link(self):
        service = CapabilityService({"main": b"visible-secret"}, ttl_seconds=300)
        request = ExportRequest(
            tenant_id="tenant-visible",
            user_id="user-visible",
            resource_id="export-visible",
            redirect_url="https://files.example.com/downloads/export.csv",
            issued_at=1000,
            nonce="visible-nonce",
        )
        token = service.issue(request)
        decision = service.authorize(
            token,
            expected_tenant="tenant-visible",
            expected_user="user-visible",
            expected_resource="export-visible",
            redirect_url=request.redirect_url,
            now=1010,
            used_nonces=set(),
        )
        self.assertTrue(decision.allowed)
        self.assertEqual("ok", decision.reason)
        self.assertEqual(request.redirect_url, decision.redirect_url)
        self.assertIn("allowed", audit_decision(decision, token, "main"))


if __name__ == "__main__":
    unittest.main()
