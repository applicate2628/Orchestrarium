import base64
import json


def _encode(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode(token: str) -> dict:
    padded = token + "=" * (-len(token) % 4)
    return json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))


def issue_download_token(request, secret: bytes, *, ttl_seconds: int) -> str:
    payload = {
        "tenant_id": request.tenant_id,
        "user_id": request.user_id,
        "resource_id": request.resource_id,
        "nonce": request.nonce,
        "issued_at": request.issued_at,
        "expires_at": request.issued_at + ttl_seconds,
    }
    return _encode(payload)


def verify_download_token(
    token: str,
    secret: bytes,
    *,
    expected_tenant: str,
    expected_user: str,
    expected_resource: str,
    now: int,
    used_nonces: set[str],
):
    payload = _decode(token)
    used_nonces.add(payload.get("nonce"))
    return payload
