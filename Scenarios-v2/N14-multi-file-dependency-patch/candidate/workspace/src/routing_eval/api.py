from __future__ import annotations

from .config import resolve_provider_order
from .render import render_summary
from .scorecard import summarize_scorecard
from .status import classify_attempt


def build_report(config: dict, attempts: list[dict]) -> dict:
    provider_order = resolve_provider_order(config)
    classified = [classify_attempt(attempt) for attempt in attempts]
    score = summarize_scorecard(classified)
    report_lines = render_summary(provider_order, classified, score)
    return {
        "provider_order": provider_order,
        "attempts": classified,
        "score": score,
        "report_lines": report_lines,
    }
