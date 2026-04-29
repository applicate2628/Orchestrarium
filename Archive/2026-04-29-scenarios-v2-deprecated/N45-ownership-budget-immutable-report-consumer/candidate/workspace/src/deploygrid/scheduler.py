def should_defer(request, profile):
    return False


def scheduled_requests(plan, profile):
    return [{"action": "deploy", "request": request} for request in plan]
