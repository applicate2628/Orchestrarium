from __future__ import annotations

from .fingerprint import derive_fingerprint, validate_modes
from .lease import acquire, release


def execute_plan(state, settings: dict, plan, fail_artifact=None):
    events = []
    for request in plan:
        validate_modes(request)
        fingerprint = derive_fingerprint(settings, request)
        acquire(state, request.artifact_id)
        if fingerprint in state.cache:
            event = {
                "type": "cache-restore",
                "artifact_id": request.artifact_id,
                "fingerprint": fingerprint,
                "stage_root": settings["stage_root"],
                "channel": settings["channel"],
                "reason": "cache",
            }
            state.ledger.append(event)
            events.append(event)
            release(state, request.artifact_id)
            continue
        if request.artifact_id == fail_artifact:
            event = {
                "type": "failed",
                "artifact_id": request.artifact_id,
                "fingerprint": fingerprint,
                "stage_root": settings["stage_root"],
                "channel": settings["channel"],
                "source": request.source,
                "reason": "simulated failure",
            }
            state.ledger.append(event)
            events.append(event)
            raise RuntimeError(f"staging failed for {request.artifact_id}")
        state.cache.add(fingerprint)
        event = {
            "type": "staged",
            "artifact_id": request.artifact_id,
            "fingerprint": fingerprint,
            "stage_root": settings["stage_root"],
            "channel": settings["channel"],
            "source": request.source,
            "reason": "staged",
        }
        state.ledger.append(event)
        events.append(event)
        release(state, request.artifact_id)
    return events
