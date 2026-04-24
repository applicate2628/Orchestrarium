def collapse_requests(requests):
    seen = set()
    collapsed = []
    for request in requests:
        if request["id"] in seen:
            continue
        seen.add(request["id"])
        collapsed.append(request)
    return collapsed
