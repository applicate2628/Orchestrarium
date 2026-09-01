def cache_key(request):
    return f"{request.workspace}:{request.target}:{request.source_hash}"
