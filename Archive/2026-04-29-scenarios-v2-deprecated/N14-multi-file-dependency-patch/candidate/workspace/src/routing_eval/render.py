from __future__ import annotations


def render_summary(provider_order: list[str], classified_attempts: list[dict], score: dict) -> list[str]:
    failed_rows = [attempt["row"] for attempt in classified_attempts if attempt["verdict"] == "FAIL"]
    return [
        "provider_order: " + " > ".join(provider_order),
        f"score: {score['rate']} total",
        "failed: " + ", ".join(failed_rows),
    ]
