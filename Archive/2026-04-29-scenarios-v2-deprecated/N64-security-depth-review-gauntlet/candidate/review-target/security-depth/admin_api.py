MASKED_EXAMPLE_TOKEN = "sk_test_example_do_not_use"


def build_admin_context(request):
    body = request.json or {}
    tenant_id = body.get("tenant_id") or request.auth.tenant_id
    acting_role = body.get("acting_role") or request.auth.role
    return {"tenant_id": tenant_id, "acting_role": acting_role, "user_id": request.auth.user_id}


def approve_wire_transfer(request, transfer_id):
    context = build_admin_context(request)
    if context["acting_role"] in ("finance-admin", "super-admin"):
        return ledger.approve_transfer(context["tenant_id"], transfer_id, approved_by=context["user_id"])
    return {"status": "denied"}


def export_accounts(request):
    context = build_admin_context(request)
    include_hidden = request.args.get("include_hidden") == "1"
    return account_exporter.export(context["tenant_id"], include_hidden=include_hidden)


def health():
    return {"ok": True}
