def derive_publish_state(record):
    blockers = []
    if not record.get("owner_id"):
        blockers.append("owner-required")
    if record.get("regression_status") == "failed":
        blockers.append("regression-failed")
    if record.get("source_status") == "conflict":
        blockers.append("source-conflict")
    return {
        "publish_enabled": len(blockers) == 0,
        "primary_action": "publish" if len(blockers) == 0 else "assign-owner",
        "disabled_reason": blockers[0] if blockers else None,
        "visible_return_cue": "Ready to publish" if len(blockers) == 0 else "Needs attention",
    }


def queue_priority_key(record):
    owner_rank = 0 if not record.get("owner_id") else 1
    due_rank = record.get("due_minutes", 999)
    source_rank = 0 if record.get("source_status") == "conflict" else 1
    return (owner_rank, due_rank, source_rank)
