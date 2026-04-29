def route_event(event, registry):
    handler = registry.lookup(event.get("action"))
    if handler is None:
        return {"ok": False, "reason": "missing-handler"}
    result = handler(event)
    if result is True:
        return {"ok": True, "reason": "ok"}
    if isinstance(result, dict):
        return result
    return {"ok": bool(result), "reason": "legacy-result"}
