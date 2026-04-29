from .audit import audit_export
from .download_tokens import issue_download_token, verify_download_token
from .export_access import authorize_export
from .models import ExportRequest
from .redirects import sanitize_return_url


class ExportService:
    def __init__(self, accounts: dict, secret: bytes, *, ttl_seconds: int = 300):
        self.accounts = accounts
        self.secret = secret
        self.ttl_seconds = ttl_seconds
        self.used_nonces: set[str] = set()

    def create_export(self, request: ExportRequest, *, now: int | None = None) -> dict:
        account = self.accounts.get(request.resource_id, {})
        decision = authorize_export(request, account)
        safe_url = sanitize_return_url(request.return_url)
        if not decision.allowed:
            return {
                "allowed": False,
                "reason": decision.reason,
                "owner": decision.owner,
                "return_url": safe_url,
                "audit": audit_export(decision, "", self.secret),
            }
        token = issue_download_token(request, self.secret, ttl_seconds=self.ttl_seconds)
        return {
            "allowed": True,
            "reason": decision.reason,
            "owner": decision.owner,
            "return_url": safe_url,
            "token": token,
            "audit": audit_export(decision, token, self.secret),
        }

    def consume_token(self, token: str, *, expected_tenant: str, expected_user: str, expected_resource: str, now: int):
        return verify_download_token(
            token,
            self.secret,
            expected_tenant=expected_tenant,
            expected_user=expected_user,
            expected_resource=expected_resource,
            now=now,
            used_nonces=self.used_nonces,
        )
