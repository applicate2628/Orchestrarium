from __future__ import annotations

import base64
import json
from typing import Any

from .models import ExportRequest


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode((text + padding).encode("ascii"))


def issue_token(
    secret_ring: dict[str, bytes | str],
    default_kid: str,
    ttl_seconds: int,
    request: ExportRequest,
) -> str:
    payload = {
        "kid": default_kid,
        "tenant_id": request.tenant_id,
        "user_id": request.user_id,
        "resource_id": request.resource_id,
        "nonce": request.nonce,
        "iat": request.issued_at,
        "exp": request.issued_at + ttl_seconds,
    }
    return _b64_encode(json.dumps(payload, sort_keys=True).encode("utf-8"))


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
        payload = json.loads(_b64_decode(token).decode("utf-8"))
    except Exception:
        return False, {}, "malformed"

    if int(payload.get("exp", 0)) < now:
        return False, payload, "expired"
    if payload.get("resource_id") != expected_resource:
        return False, payload, "resource-mismatch"

    nonce = str(payload.get("nonce", ""))
    if nonce in used_nonces:
        return False, payload, "replay"
    used_nonces.add(nonce)
    return True, payload, "ok"
