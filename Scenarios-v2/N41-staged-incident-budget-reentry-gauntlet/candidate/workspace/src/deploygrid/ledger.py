from .models import semantic_key


def record_release(state, request):
    event = {
        "seq": state.next_seq(),
        "type": "released",
        "key": semantic_key(request),
        "tenant": request["tenant"],
        "service": request["service"],
        "version": request["version"],
        "lane": request["lane"],
        "window": request["window"],
        "source": request.get("source"),
        "deployment_group": request.get("deployment_group", request["id"]),
    }
    state.ledger.append(event)
    return event
