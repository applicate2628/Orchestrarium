import base64
import json
import unittest

from capvault import CapabilityService, ExportRequest, audit_decision, sanitize_return_url


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + padding).encode("ascii"))


DEFAULT_URL = "https://files.example.com/downloads/"


class SecurityRegressionTests(unittest.TestCase):
    # Reference (four-probe #1): a complete security regression test. It exercises every
    # required defect class with an explicit denial assertion, so it PASSES on the fixed
    # reference and FAILS (via AssertionError) on the historical buggy baseline and on every
    # single-class mutant. Note the integrity coverage actually forges the token (flipped
    # signature, tampered exp, alg:none) rather than merely renaming a binding test "tamper".
    def _service(self):
        return CapabilityService({"live": b"hidden-secret-material"}, default_kid="live", ttl_seconds=120)

    def _request(self):
        return ExportRequest(
            tenant_id="tenant-a",
            user_id="user-a",
            resource_id="resource-a",
            redirect_url="https://files.example.com/downloads/export.csv",
            issued_at=1000,
            nonce="nonce-a",
        )

    def _authorize(self, token, **overrides):
        request = self._request()
        kwargs = dict(
            expected_tenant="tenant-a",
            expected_user="user-a",
            expected_resource="resource-a",
            redirect_url=request.redirect_url,
            now=1010,
            used_nonces=set(),
        )
        kwargs.update(overrides)
        return self._service().authorize(token, **kwargs)

    def test_valid_token_is_authorized(self):
        token = self._service().issue(self._request())
        self.assertTrue(self._authorize(token).allowed)

    def test_signature_tamper_and_forgery_rejected(self):
        token = self._service().issue(self._request())
        header_b64, payload_b64, signature_b64 = token.split(".", 2)

        flipped = ("A" if signature_b64[:1] != "A" else "B") + signature_b64[1:]
        forged_signature = f"{header_b64}.{payload_b64}.{flipped}"
        self.assertFalse(self._authorize(forged_signature).allowed)

        payload = json.loads(_b64_decode(payload_b64).decode("utf-8"))
        payload["exp"] = 10 ** 12
        tampered_exp = f"{header_b64}.{_b64_encode(json.dumps(payload, sort_keys=True).encode('utf-8'))}.{signature_b64}"
        self.assertFalse(self._authorize(tampered_exp).allowed)

    def test_alg_none_token_rejected(self):
        token = self._service().issue(self._request())
        _, payload_b64, _ = token.split(".", 2)
        none_header = _b64_encode(json.dumps({"alg": "none", "kid": "live"}, sort_keys=True).encode("utf-8"))
        self.assertFalse(self._authorize(f"{none_header}.{payload_b64}.").allowed)

    def test_tenant_binding(self):
        token = self._service().issue(self._request())
        self.assertFalse(self._authorize(token, expected_tenant="tenant-b").allowed)

    def test_user_binding(self):
        token = self._service().issue(self._request())
        self.assertFalse(self._authorize(token, expected_user="user-b").allowed)

    def test_resource_binding(self):
        token = self._service().issue(self._request())
        self.assertFalse(self._authorize(token, expected_resource="resource-b").allowed)

    def test_nonce_replay_rejected(self):
        service = self._service()
        request = self._request()
        token = service.issue(request)
        used: set[str] = set()
        first = service.authorize(
            token,
            expected_tenant="tenant-a",
            expected_user="user-a",
            expected_resource="resource-a",
            redirect_url=request.redirect_url,
            now=1010,
            used_nonces=used,
        )
        self.assertTrue(first.allowed)
        replay = service.authorize(
            token,
            expected_tenant="tenant-a",
            expected_user="user-a",
            expected_resource="resource-a",
            redirect_url=request.redirect_url,
            now=1011,
            used_nonces=used,
        )
        self.assertFalse(replay.allowed)

    def test_redirect_traps_fail_closed(self):
        for trap in (
            "https://files.example.com.evil.test/downloads/export.csv",
            "https://files.example.com@evil.test/downloads/export.csv",
            "https://files.example.com/downloads/export.csv%0d%0aLocation:%20https://evil.test",
        ):
            self.assertEqual(DEFAULT_URL, sanitize_return_url(trap))
        safe = "https://files.example.com/downloads/reports/2026/export.csv"
        self.assertEqual(safe, sanitize_return_url(safe))

    def test_audit_redaction(self):
        token = self._service().issue(self._request())
        decision = self._authorize(token)
        audit_text = json.dumps(audit_decision(decision, token, "live")).lower()
        self.assertIn("fingerprint", audit_text)
        self.assertNotIn(token.lower(), audit_text)
        self.assertNotIn("hidden-secret-material", audit_text)


if __name__ == "__main__":
    unittest.main()
