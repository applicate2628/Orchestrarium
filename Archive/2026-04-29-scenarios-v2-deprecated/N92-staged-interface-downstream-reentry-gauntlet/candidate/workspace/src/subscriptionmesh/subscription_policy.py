class SubscriptionPolicy:
    def __init__(self, rules=None):
        self.rules = rules or {}

    def check(self, customer, request):
        if not customer:
            return "missing-customer"
        if request.get("tenant") in self.rules.get("disabledTenants", []):
            return "tenant-disabled"
        if request.get("feature") not in customer.get("features", []):
            return "feature-not-entitled"
        return True
