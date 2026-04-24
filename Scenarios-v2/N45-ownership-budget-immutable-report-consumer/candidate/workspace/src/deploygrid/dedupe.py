from .models import semantic_key


def collapse_requests(requests):
    winners = {}
    replaced = {}
    for request in requests:
        key = semantic_key(request)
        current = winners.get(key)
        if current is None or request.get("requested_at", 0) >= current.get("requested_at", 0):
            if current is not None:
                replaced.setdefault(key, []).append(current)
            winners[key] = request
        else:
            replaced.setdefault(key, []).append(request)
    collapsed = []
    for request in winners.values():
        request["_replaced"] = replaced.get(semantic_key(request), [])
        collapsed.append(request)
    return collapsed
