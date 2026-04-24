from __future__ import annotations

from copy import deepcopy


class DeployState:
    def __init__(self):
        self.ledger = []
        self.notifications = []
        self.audit = []
        self.deferred = []
        self._seq = 0

    def next_seq(self):
        self._seq += 1
        return self._seq

    def snapshot(self):
        return {
            "ledger": deepcopy(self.ledger),
            "notifications": deepcopy(self.notifications),
            "audit": deepcopy(self.audit),
            "deferred": deepcopy(self.deferred),
        }
