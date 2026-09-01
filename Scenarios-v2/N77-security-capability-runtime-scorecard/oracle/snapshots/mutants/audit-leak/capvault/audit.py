from __future__ import annotations

from .models import Decision


def audit_decision(decision: Decision, token: str, secret_kid: str) -> dict[str, str | bool]:
    return {
        "allowed": decision.allowed,
        "reason": decision.reason,
        "redirect_url": decision.redirect_url,
        "token": token,
        "secret_kid": secret_kid,
    }
