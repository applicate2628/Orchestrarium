from .journal import append_event


def rollback_attempt(store, batch_id, attempt_id):
    rolled_back = []
    for record in reversed(list(store.undo_log)):
        if record["batch_id"] != batch_id:
            continue
        store.undo(record["undo"])
        rolled_back.append(record["step_id"])
        append_event(
            store,
            {
                "type": "rolled-back",
                "batch_id": batch_id,
                "attempt_id": attempt_id,
                "step_id": record["step_id"],
            },
        )
    return rolled_back
