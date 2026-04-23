def old_stage_order(requests):
    return sorted(requests, key=lambda request: request.priority, reverse=True)
