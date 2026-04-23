class PolicyEvaluator:
    def __init__(self, rules=None):
        self.rules = rules or {}

    def evaluate(self, record, event):
        if not record:
            return "missing-session"
        if event.get("tenant") in self.rules.get("blockedTenants", []):
            return "blocked-tenant"
        if event.get("action") == "delete" and "admin" not in record.get("roles", []):
            return "requires-admin"
        return True
