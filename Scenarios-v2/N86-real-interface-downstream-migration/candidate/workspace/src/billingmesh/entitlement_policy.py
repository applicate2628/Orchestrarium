class EntitlementPolicy:
    def __init__(self, rules=None):
        self.rules = rules or {}

    def check(self, account, request):
        if not account:
            return "missing-account"
        if request.get("tenant") in self.rules.get("disabledTenants", []):
            return "tenant-disabled"
        if request.get("feature") not in account.get("features", []):
            return "feature-not-entitled"
        return True
