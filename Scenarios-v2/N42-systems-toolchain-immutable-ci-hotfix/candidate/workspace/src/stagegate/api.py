from __future__ import annotations

from .config import resolve_settings
from .executor import execute_plan
from .planner import build_plan
from .report import summarize_state


def run_stagegate(state, config, requests, env=None, fail_artifact=None):
    settings = resolve_settings(config, env or {})
    plan = build_plan(settings, requests)
    return execute_plan(state, settings, plan, fail_artifact=fail_artifact)
