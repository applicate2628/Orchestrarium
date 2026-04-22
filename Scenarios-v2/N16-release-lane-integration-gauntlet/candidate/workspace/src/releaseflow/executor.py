from .audit import record_audit
from .config import resolve_profile
from .dedupe import collapse_requests
from .intake import normalize_requests
from .ledger import record_release
from .notifier import notify_release
from .planner import build_plan
from .report import summarize_state
from .rollback import rollback_group
from .scheduler import scheduled_requests, should_defer


def run_release(state, config, requests, *, fail_group=None):
    profile = resolve_profile(config)
    normalized = normalize_requests(requests)
    collapsed = collapse_requests(normalized)
    plan = build_plan(collapsed, profile)
    deployed = []
    rolled_back = []

    for item in scheduled_requests(plan, profile):
        request = item["request"]
        if should_defer(request, profile):
            state.deferred.append(request)
            record_audit(state, "deferred", request)
            continue

        event = record_release(state, request)
        notify_release(state, event)
        record_audit(state, "released", request)
        deployed.append(event["key"])

        if request.get("deployment_group") == fail_group:
            rolled_back = rollback_group(state, fail_group)
            record_audit(state, "rolled-back", request, {"group": fail_group})
            break

    summary = summarize_state(state)
    return {
        "deployed": deployed,
        "rolled_back": rolled_back,
        "summary": summary,
        "snapshot": state.snapshot(),
    }
