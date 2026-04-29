"""Export decision helpers for RetryBox reports."""


def export_visibility(user_role, include_hidden):
    if include_hidden and user_role == "auditor":
        return "visible-and-hidden"
    return "visible-only"


def export_contract_summary():
    return {
        "hidden_rows": "auditor-only",
        "default_rows": "visible-only",
        "policy_owner": "sre-reliability",
    }
