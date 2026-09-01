from __future__ import annotations

import hashlib

from .models import Decision


def audit_decision(decision: Decision, token: str, secret_kid: str) -> dict[str, str | bool]:
    return {
        "allowed": decision.allowed,
        "reason": decision.reason,
        "redirect_url": decision.redirect_url,
        "token_fingerprint": hashlib.sha256(token.encode("utf-8")).hexdigest()[:16],
        "key_id": secret_kid,
    }
