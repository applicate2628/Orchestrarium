from billingmesh.entitlements import can_export, export_visibility


def test_eu_premium_needs_override(account, eu_tenant, finance_actor):
    account.plan = "premium"
    assert can_export(account, eu_tenant, finance_actor) is False


def test_auditor_can_include_hidden(auditor_actor):
    assert export_visibility(auditor_actor, include_hidden=True) == "visible-and-hidden"


def test_non_auditor_hidden_export_is_downgraded(finance_actor):
    assert export_visibility(finance_actor, include_hidden=True) == "visible-only"
