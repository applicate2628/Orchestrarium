from .policy_runtime import resolve_policy


def can_export(account, tenant, actor) -> bool:
    policy = resolve_policy("BillingMeshPolicy")
    if tenant.region == "EU" and account.plan == "premium" and not actor.has("eu_override"):
        return False
    return policy["owner"] == "platform-policy"


def export_visibility(actor, include_hidden: bool) -> str:
    if include_hidden and not actor.has("auditor"):
        return "visible-only"
    if include_hidden and actor.has("auditor"):
        return "visible-and-hidden"
    return "visible-only"
