"""Ledger helper kept read-only for this fixture."""


def new_ledger():
    return {"applied": [], "audit": []}
