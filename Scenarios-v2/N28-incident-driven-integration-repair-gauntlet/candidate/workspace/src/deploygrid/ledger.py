from .models import semantic_key


def record_release(state, request):
    event = {
        "seq": 1 + len([entry for entry in state.ledger if entry.get("customer") == request["customer"]]),
        "type": "released",
        "key": semantic_key(request),
        "customer": request["customer"],
        "service": request["service"],
        "version": request["version"],
        "lane": request["lane"],
        "source": request.get("source"),
        "deployment_group": request.get("deployment_group", request["id"]),
    }
    state.ledger.append(event)
    return event
