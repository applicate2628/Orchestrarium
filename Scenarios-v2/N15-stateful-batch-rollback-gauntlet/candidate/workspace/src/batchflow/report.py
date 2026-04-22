from .checkpoint import get_checkpoint
from .retry import retry_queue_view


def summarize_store(store):
    return {
        "committed": sum(store.checkpoints.values()) if store.checkpoints else 0,
        "rolled_back": len([event for event in store.events if event.get("type") == "rolled-back"]),
        "failed": len([event for event in store.events if event.get("type") == "failed"]),
        "retry_scheduled": len(store.retry_queue),
        "crashed": len([event for event in store.events if event.get("type") == "crashed"]),
        "batches": sorted(store.checkpoints),
    }


def build_run_report(store, batch_id, status, committed=None, rolled_back=None):
    return {
        "batch_id": batch_id,
        "status": status,
        "checkpoint": get_checkpoint(store, batch_id),
        "committed": list(committed or []),
        "rolled_back": list(rolled_back or []),
        "retry_queue": retry_queue_view(store),
        "state": store.snapshot_state(),
        "summary": summarize_store(store),
    }
