def normalize_requests(requests):
    requests.sort(key=lambda request: request["id"])
    for index, request in enumerate(requests):
        request["position"] = index
        request.setdefault("depends_on", [])
        request.setdefault("deployment_group", request["id"])
    return requests
