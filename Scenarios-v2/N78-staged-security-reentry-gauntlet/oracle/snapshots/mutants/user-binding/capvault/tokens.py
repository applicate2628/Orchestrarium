from __future__ import annotations

# MUTANT class-id=user-binding: the token's user_id is no longer bound to expected_user.
# All other checks are the correct reference logic. Detect by authorizing a valid token
# against a DIFFERENT expected_user and asserting denial -> 'user-binding undetected'.

import base64
import hmac
import hashlib
import json
from typing import Any

from .models import ExportRequest


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + padding).encode("ascii"))


def _json_b64(data: dict[str, Any]) -> str:
    return _b64_encode(json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def _secret_bytes(secret: bytes | str) -> bytes:
    return secret if isinstance(secret, bytes) else secret.encode("utf-8")


def issue_token(
    secret_ring: dict[str, bytes | str],
    default_kid: str,
    ttl_seconds: int,
    request: ExportRequest,
) -> str:
    if default_kid not in secret_ring:
        raise ValueError("unknown kid")
    header = {"alg": "HS256", "kid": default_kid, "typ": "capability"}
    payload = {
        "tenant_id": request.tenant_id,
        "user_id": request.user_id,
        "resource_id": request.resource_id,
        "nonce": request.nonce,
        "iat": request.issued_at,
        "exp": request.issued_at + ttl_seconds,
    }
    signing_input = f"{_json_b64(header)}.{_json_b64(payload)}"
    signature = hmac.new(_secret_bytes(secret_ring[default_kid]), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64_encode(signature)}"


def verify_token(
    secret_ring: dict[str, bytes | str],
    token: str,
    *,
    expected_tenant: str,
    expected_user: str,
    expected_resource: str,
    now: int,
    used_nonces: set[str],
) -> tuple[bool, dict[str, Any], str]:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".", 2)
        header = json.loads(_b64_decode(header_b64).decode("utf-8"))
        payload = json.loads(_b64_decode(payload_b64).decode("utf-8"))
    except Exception:
        return False, {}, "malformed"

    if header.get("alg") != "HS256":
        return False, payload, "unsupported-alg"
    kid = str(header.get("kid", ""))
    if kid not in secret_ring:
        return False, payload, "unknown-kid"
    signing_input = f"{header_b64}.{payload_b64}"
    expected = hmac.new(_secret_bytes(secret_ring[kid]), signing_input.encode("ascii"), hashlib.sha256).digest()
    try:
        supplied = _b64_decode(signature_b64)
    except Exception:
        return False, payload, "malformed-signature"
    if not hmac.compare_digest(expected, supplied):
        return False, payload, "bad-signature"
    if int(payload.get("exp", 0)) < now:
        return False, payload, "expired"
    if payload.get("tenant_id") != expected_tenant:
        return False, payload, "tenant-mismatch"
    if payload.get("resource_id") != expected_resource:
        return False, payload, "resource-mismatch"

    nonce = str(payload.get("nonce", ""))
    if nonce in used_nonces:
        return False, payload, "replay"
    used_nonces.add(nonce)
    return True, payload, "ok"
