from .models import semantic_key


def record_audit(state, action, request, detail=None):
    entry = {
        "seq": len(state.audit) + 1,
        "action": action,
        "key": semantic_key(request),
        "source": request.get("source"),
        "detail": detail or {},
    }
    state.audit.append(entry)
    return entry
