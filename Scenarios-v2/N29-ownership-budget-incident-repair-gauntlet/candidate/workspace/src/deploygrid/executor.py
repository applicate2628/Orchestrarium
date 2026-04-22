from .audit import record_audit
from .config import resolve_profile
from .dedupe import collapse_requests
from .intake import normalize_requests
from .ledger import record_release
from .models import semantic_key
from .notifier import notify_release
from .policy import can_deploy, is_frozen
from .report import summarize_state
from .rollback import rollback_group


def _event_keys(state, event_type):
    # BUG: resume/retry state ignores durable ledger entries and replays committed side effects.
    return set()


def _lane_rank(profile, request):
    order = profile.get("lane_order", ["canary", "prod"])
    try:
        return order.index(request.get("lane"))
    except ValueError:
        return len(order)


def _already_audited(state, action, request):
    return any(
        entry.get("action") == action
        and entry.get("key") == semantic_key(request)
        and entry.get("source") == request.get("source")
        for entry in state.audit
    )


def _record_once(state, action, request, detail=None):
    if not _already_audited(state, action, request):
        return record_audit(state, action, request, detail)
    return None


def _cycle_nodes(requests):
    lookup = {semantic_key(request): request for request in requests}
    graph = {
        key: [dependency for dependency in request.get("depends_on", []) if dependency in lookup]
        for key, request in lookup.items()
    }
    visiting = set()
    visited = set()
    cycles = set()

    def visit(key, path):
        if key in visiting:
            cycles.update(path[path.index(key):])
            return
        if key in visited:
            return
        visiting.add(key)
        for dependency in graph[key]:
            visit(dependency, path + [dependency])
        visiting.remove(key)
        visited.add(key)

    for key in graph:
        visit(key, [key])
    return cycles


def _prepare_batch(state, profile, requests):
    released = _event_keys(state, "released")
    active = []
    for request in requests:
        for replaced in request.pop("_replaced", []):
            _record_once(state, "superseded", replaced)

        request_key = semantic_key(request)
        if request_key in released:
            continue
        if is_frozen(request, profile):
            state.deferred.append(request)
            _record_once(state, "deferred", request)
            continue
        active.append(request)

    cycles = _cycle_nodes(active)
    if cycles:
        state.cycles.append(sorted(cycles))
    ready = []
    for request in active:
        if semantic_key(request) in cycles:
            state.blocked.append(request)
            _record_once(state, "blocked", request, {"reason": "dependency loop"})
        else:
            ready.append(request)
    return ready


def _release(state, request):
    event = record_release(state, request)
    notify_release(state, event)
    _record_once(state, "released", request)
    return event


def run_deploy(state, config, requests, *, fail_group=None, crash_after_key=None):
    profile = resolve_profile(config)
    normalized = normalize_requests(requests)
    collapsed = collapse_requests(normalized)
    remaining = sorted(
        _prepare_batch(state, profile, collapsed),
        key=lambda request: (_lane_rank(profile, request), -request.get("priority", 0), request.get("position", 0)),
    )
    deployed = []
    released = _event_keys(state, "released")

    while remaining:
        progressed = False
        next_remaining = []
        remaining_keys = {semantic_key(request) for request in remaining}
        for request in remaining:
            dependencies_met = all(dependency in released for dependency in request.get("depends_on", []))
            canary_may_still_run = (
                request.get("lane") == "prod"
                and f"{request['tenant']}:{request['service']}:{request['version']}:canary:{request['window']}" in remaining_keys
            )
            if dependencies_met and can_deploy(request, released):
                event = _release(state, request)
                released.add(event["key"])
                deployed.append(event["key"])
                progressed = True
                if event["key"] == crash_after_key:
                    raise RuntimeError(f"simulated crash after {crash_after_key}")
            elif canary_may_still_run or not dependencies_met:
                next_remaining.append(request)
            else:
                state.blocked.append(request)
                _record_once(state, "blocked", request, {"reason": "missing prerequisite"})
                progressed = True
        if not progressed:
            for request in next_remaining:
                state.blocked.append(request)
                _record_once(state, "blocked", request, {"reason": "unresolved dependency"})
            break
        remaining = next_remaining

    rolled_back = []
    if fail_group:
        attempt_keys = set(deployed)
        rolled_back = rollback_group(state, fail_group, attempt_keys)
        for request in collapsed:
            if request.get("deployment_group") == fail_group:
                _record_once(state, "rolled-back", request, {"group": fail_group})
                break

    summary = summarize_state(state)
    return {
        "deployed": deployed,
        "rolled_back": rolled_back,
        "summary": summary,
        "snapshot": state.snapshot(),
    }
