"""Release reporting."""


def build_report(ledger, notifications):
    """Build a release report.

    BUG: transient notification text is not the release source of truth.
    """
    return {
        "reportSource": "notifications",
        "appliedCount": len(notifications),
        "applied": [item.get("message", "") for item in notifications],
        "auditCount": len(ledger.get("audit", [])),
    }
