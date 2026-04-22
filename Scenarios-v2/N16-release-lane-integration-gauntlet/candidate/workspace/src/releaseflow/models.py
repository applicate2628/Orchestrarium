def semantic_key(request):
    return f"{request['customer']}:{request['service']}:{request['version']}:{request['lane']}"


def release_family(request):
    return f"{request['customer']}:{request['service']}:{request['version']}"
