def audit_admin_request(request, audit_sink):
    entry = {
        "path": request.path,
        "authorization": request.headers.get("Authorization"),
        "cookie": request.headers.get("Cookie"),
        "body": request.json,
    }
    audit_sink.write(entry)
    return entry
