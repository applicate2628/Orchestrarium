from __future__ import annotations

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
    # MUTANT class-id=integrity: cryptographic verification removed. The alg check, kid
    # check, and HMAC signature comparison are all gone, so a forged token (tampered exp,
    # flipped signature bytes) or an `alg: none` token is accepted as long as the payload
    # bindings, expiry, and replay checks pass. Tenant/user/resource binding, expiry, and
    # replay are the correct reference logic. A regression test whose "tamper" case only
    # mutates a *bound* field (tenant/user/resource) is masked by binding and PASSES here;
    # only a test that forges the signature, tampers an unbound field (exp), or submits
    # `alg: none` detects this -> "integrity undetected".
    try:
        header_b64, payload_b64, signature_b64 = token.split(".", 2)
        payload = json.loads(_b64_decode(payload_b64).decode("utf-8"))
    except Exception:
        return False, {}, "malformed"

    if int(payload.get("exp", 0)) < now:
        return False, payload, "expired"
    if payload.get("tenant_id") != expected_tenant:
        return False, payload, "tenant-mismatch"
    if payload.get("user_id") != expected_user:
        return False, payload, "user-mismatch"
    if payload.get("resource_id") != expected_resource:
        return False, payload, "resource-mismatch"

    nonce = str(payload.get("nonce", ""))
    if nonce in used_nonces:
        return False, payload, "replay"
    used_nonces.add(nonce)
    return True, payload, "ok"
