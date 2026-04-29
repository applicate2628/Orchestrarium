def is_frozen(request, profile):
    for rule in profile.get("freeze", []):
        if all(request.get(name) == value for name, value in rule.items()):
            return True
    return False


def can_deploy(request, released_keys):
    if request.get("lane") != "prod":
        return True
    canary = f"{request['tenant']}:{request['service']}:{request['version']}:canary:{request['window']}"
    return canary in released_keys
