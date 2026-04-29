from copy import deepcopy


def normalize_requests(requests):
    normalized = []
    for index, request in enumerate(requests):
        item = deepcopy(request)
        item["position"] = index
        item.setdefault("depends_on", [])
        item.setdefault("deployment_group", item["id"])
        item.setdefault("requested_at", index)
        normalized.append(item)
    return normalized
