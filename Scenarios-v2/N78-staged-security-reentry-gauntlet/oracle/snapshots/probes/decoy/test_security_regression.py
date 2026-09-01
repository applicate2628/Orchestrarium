import json
import unittest

from capvault import CapabilityService, ExportRequest, audit_decision, sanitize_return_url


class SecurityRegressionTests(unittest.TestCase):
    def make_service(self):
        return CapabilityService({"main": b"secret"}, ttl_seconds=60)

    def make_token(self):
        request = ExportRequest(
            tenant_id="tenant-a",
            user_id="user-a",
            resource_id="resource-a",
            redirect_url="https://files.example.com/downloads/a.csv",
            issued_at=100,
            nonce="nonce-a",
        )
        return self.make_service().issue(request), request

    def test_tamper_tenant_user_resource_binding_and_replay(self):
        service = self.make_service()
        token, request = self.make_token()
        used = set()
        allowed = service.authorize(
            token,
            expected_tenant=request.tenant_id,
            expected_user=request.user_id,
            expected_resource=request.resource_id,
            redirect_url=request.redirect_url,
            now=120,
            used_nonces=used,
        )
        self.assertTrue(allowed.allowed)
        self.assertFalse(
            service.authorize(
                token,
                expected_tenant=request.tenant_id,
                expected_user=request.user_id,
                expected_resource=request.resource_id,
                redirect_url=request.redirect_url,
                now=121,
                used_nonces=used,
            ).allowed
        )
        self.assertFalse(
            service.authorize(
                token,
                expected_tenant=request.tenant_id,
                expected_user="user-b",
                expected_resource=request.resource_id,
                redirect_url=request.redirect_url,
                now=120,
                used_nonces=set(),
            ).allowed
        )

    def test_redirect_traps_and_audit_redaction(self):
        token, request = self.make_token()
        default_url = "https://files.example.com/downloads/"
        self.assertEqual(default_url, sanitize_return_url("https://files.example.com.evil.test/downloads/a.csv"))
        self.assertEqual(default_url, sanitize_return_url("https://files.example.com@evil.test/downloads/a.csv"))
        decision = self.make_service().authorize(
            token,
            expected_tenant=request.tenant_id,
            expected_user=request.user_id,
            expected_resource=request.resource_id,
            redirect_url=request.redirect_url,
            now=120,
            used_nonces=set(),
        )
        audit_text = json.dumps(audit_decision(decision, token, "main")).lower()
        self.assertIn("fingerprint", audit_text)
        self.assertNotIn(token.lower(), audit_text)


if __name__ == "__main__":
    unittest.main()
