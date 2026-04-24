def semantic_key(request):
    return f"{request['tenant']}:{request['service']}:{request['version']}:{request['lane']}:{request['window']}"


def deploy_family(request):
    return f"{request['tenant']}:{request['service']}:{request['version']}:{request['window']}"
