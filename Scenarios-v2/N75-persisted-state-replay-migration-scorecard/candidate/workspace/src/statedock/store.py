from .events import normalize_event


class StateStore:
    def __init__(self):
        self.balances = {}
        self.statuses = {}
        self.applied = []

    def apply(self, event):
        normalized = normalize_event(event)
        tenant = normalized["tenant"]
        op = normalized["op"]
        amount = normalized.get("amount", 0)
        if op in ("credit", "deposit"):
            self.balances[tenant] = self.balances.get(tenant, 0) + amount
        elif op in ("debit", "withdraw"):
            self.balances[tenant] = self.balances.get(tenant, 0) - amount
        elif op == "set_status":
            self.statuses[tenant] = normalized.get("status")
        self.applied.append(normalized)
        return self.snapshot()

    def replay(self, events):
        for event in events:
            self.apply(event)
        return self.snapshot()

    def rollback_to(self, checkpoint_id):
        return self.snapshot()

    def snapshot(self):
        return {
            "balances": dict(self.balances),
            "statuses": dict(self.statuses),
            "applied": list(self.applied),
        }
