def record_audit(state, action, request, detail=None):
    entry = {
        "seq": len(state.audit) + 1,
        "action": action,
        "key": f"{request['customer']}:{request['service']}:{request['version']}:{request['lane']}",
        "detail": detail or {},
    }
    state.audit.append(entry)
    return entry
