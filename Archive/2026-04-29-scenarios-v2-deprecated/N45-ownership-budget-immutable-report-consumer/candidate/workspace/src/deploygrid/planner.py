def build_plan(requests, profile):
    return sorted(requests, key=lambda request: request.get("priority", 0), reverse=True)
