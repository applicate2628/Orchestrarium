from .entitlements import export_visibility


def build_export(account, tenant, actor, include_hidden: bool) -> dict:
    visibility = export_visibility(actor, include_hidden)
    return {
        "account_id": account.id,
        "tenant_id": tenant.id,
        "visibility": visibility,
        "source": "policy-registry-v2",
    }
