def audit_export(decision, token: str, secret: bytes) -> dict:
    return {
        "allowed": decision.allowed,
        "reason": decision.reason,
        "owner": decision.owner,
        "token": token,
        "secret": secret.decode("utf-8", errors="ignore"),
    }
