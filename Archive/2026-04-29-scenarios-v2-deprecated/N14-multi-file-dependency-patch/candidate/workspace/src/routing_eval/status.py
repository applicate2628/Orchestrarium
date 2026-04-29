from __future__ import annotations


def classify_attempt(attempt: dict) -> dict:
    """Classify one row attempt for the scorecard."""
    if attempt.get("verificationPassed") is True:
        verdict = "PASS"
        reason = "verified"
    else:
        verdict = "FAIL"
        reason = attempt.get("runtimeError") or attempt.get("routeError") or "verification-failed"

    return {
        "row": attempt["row"],
        "provider": attempt["provider"],
        "verdict": verdict,
        "scoreable": True,
        "reason": reason,
    }
