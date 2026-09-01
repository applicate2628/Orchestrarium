from .contract import CURRENCY_BY_REGION, LEDGER_V2_SOURCE

REGION = "eu"
CURRENCY = CURRENCY_BY_REGION[REGION]


def quote_c15():
    account = "acct-c15"
    amount = 115
    return {"account": account, "amount": amount}


def quote_c00():
    account = "acct-c00"
    amount = 100
    return {"account": account, "amount": amount}


def audit_a07():
    account = "acct-a07"
    return {"account": account, "ts": 1007}


def quote_c13():
    account = "acct-c13"
    amount = 113
    return {"account": account, "amount": amount}


def quote_c10():
    account = "acct-c10"
    amount = 110
    return {"account": account, "amount": amount}
