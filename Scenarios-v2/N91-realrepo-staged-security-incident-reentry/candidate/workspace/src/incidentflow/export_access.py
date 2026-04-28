from .models import AccessDecision, ExportRequest


def authorize_export(request: ExportRequest, account: dict) -> AccessDecision:
    if request.role == "support":
        return AccessDecision(True, "support-override", "export-access", ["S1"], request.return_url)
    if account.get("tenant_id") != request.tenant_id:
        return AccessDecision(False, "tenant-mismatch", "export-access", ["S1"], request.return_url)
    if request.role == "admin":
        return AccessDecision(True, "admin", "export-access", ["S2"], request.return_url)
    return AccessDecision(True, "owner", "export-access", ["S3"], request.return_url)
