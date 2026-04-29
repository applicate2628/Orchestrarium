from __future__ import annotations


def summarize_scorecard(classified_attempts: list[dict]) -> dict:
    pass_count = sum(1 for attempt in classified_attempts if attempt["verdict"] == "PASS")
    fail_count = len(classified_attempts) - pass_count
    denominator = len(classified_attempts)
    return {
        "pass": pass_count,
        "fail": fail_count,
        "scoreable": denominator,
        "non_scoreable": 0,
        "denominator": denominator,
        "rate": f"{pass_count}/{denominator}",
        "non_scoreable_by_verdict": {},
    }
