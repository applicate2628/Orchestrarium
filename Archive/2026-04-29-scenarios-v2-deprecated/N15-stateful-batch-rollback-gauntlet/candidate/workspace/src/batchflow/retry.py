def schedule_retry(store, batch_id, step, reason):
    record = {"batch_id": batch_id, "step_id": step["id"], "reason": reason}
    store.retry_queue.append(record)
    store.retry_queue.sort(key=lambda item: item["step_id"])
    return record


def retry_queue_view(store):
    return [f"{item['batch_id']}:{item['step_id']}" for item in store.retry_queue]
