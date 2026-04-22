from .checkpoint import get_checkpoint, set_checkpoint
from .journal import append_event
from .planner import normalize_plan
from .report import build_run_report
from .retry import schedule_retry
from .rollback import rollback_attempt


def _as_set(value):
    if value is None:
        return set()
    if isinstance(value, str):
        return {value}
    return set(value)


def execute_batch(store, batch_id, plan, *, fail_before=None, fail_after=None, crash_after=None):
    steps = normalize_plan(plan)
    fail_before = _as_set(fail_before)
    fail_after = _as_set(fail_after)
    start = get_checkpoint(store, batch_id)
    attempt_id = store.next_attempt_id()
    committed = []

    if start >= len(steps):
        return build_run_report(store, batch_id, "already-complete")

    for index, step in enumerate(steps[start:], start=start):
        step_id = step["id"]

        if step_id in fail_before:
            if step.get("retryable"):
                schedule_retry(store, batch_id, step, "fail-before")
                append_event(store, {"type": "retry-scheduled", "batch_id": batch_id, "attempt_id": attempt_id, "step_id": step_id})
            append_event(store, {"type": "failed", "batch_id": batch_id, "attempt_id": attempt_id, "step_id": step_id})
            rolled_back = rollback_attempt(store, batch_id, attempt_id)
            return build_run_report(store, batch_id, "failed", committed, rolled_back)

        undo = store.apply_step(step)
        store.undo_log.append({"batch_id": batch_id, "attempt_id": attempt_id, "step_id": step_id, "undo": undo})
        committed.append(step_id)
        append_event(store, {"type": "committed", "batch_id": batch_id, "attempt_id": attempt_id, "step_id": step_id})
        set_checkpoint(store, batch_id, index + 1)

        if step_id in fail_after:
            if step.get("retryable"):
                schedule_retry(store, batch_id, step, "fail-after")
                append_event(store, {"type": "retry-scheduled", "batch_id": batch_id, "attempt_id": attempt_id, "step_id": step_id})
            append_event(store, {"type": "failed", "batch_id": batch_id, "attempt_id": attempt_id, "step_id": step_id})
            rolled_back = rollback_attempt(store, batch_id, attempt_id)
            return build_run_report(store, batch_id, "failed", committed, rolled_back)

        if step_id == crash_after:
            append_event(store, {"type": "crashed", "batch_id": batch_id, "attempt_id": attempt_id, "step_id": step_id})
            return build_run_report(store, batch_id, "crashed", committed)

    return build_run_report(store, batch_id, "completed", committed)
