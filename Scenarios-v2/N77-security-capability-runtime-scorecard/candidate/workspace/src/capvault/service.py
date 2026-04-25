from __future__ import annotations

from .models import Decision, ExportRequest
from .redirects import sanitize_return_url
from .tokens import issue_token, verify_token


class CapabilityService:
    def __init__(self, secret_ring: dict[str, bytes | str], default_kid: str = "main", ttl_seconds: int = 300):
        self.secret_ring = secret_ring
        self.default_kid = default_kid
        self.ttl_seconds = ttl_seconds

    def issue(self, request: ExportRequest) -> str:
        return issue_token(self.secret_ring, self.default_kid, self.ttl_seconds, request)

    def authorize(
        self,
        token: str,
        *,
        expected_tenant: str,
        expected_user: str,
        expected_resource: str,
        redirect_url: str,
        now: int,
        used_nonces: set[str],
    ) -> Decision:
        valid, payload, reason = verify_token(
            self.secret_ring,
            token,
            expected_tenant=expected_tenant,
            expected_user=expected_user,
            expected_resource=expected_resource,
            now=now,
            used_nonces=used_nonces,
        )
        safe_redirect = sanitize_return_url(redirect_url)
        if not valid:
            return Decision(False, reason, "", "")
        return Decision(True, "ok", safe_redirect, str(payload.get("nonce", "")))
