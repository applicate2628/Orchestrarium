from __future__ import annotations

from collections.abc import Iterable

from .models import DiscountRule


class PricingCatalog:
    def __init__(self, rules: Iterable[DiscountRule]):
        self.rules = tuple(rules)

    def __iter__(self):
        return iter(self.rules)

    def __len__(self):
        return len(self.rules)
