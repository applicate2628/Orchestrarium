from .contract import CURRENCY_BY_REGION, LEDGER_V2_SOURCE

REGION = "eu"
CURRENCY = CURRENCY_BY_REGION[REGION]


def quote_c24():
    account = "acct-c24"
    amount = 124
    return {"account": account, "amount": amount}


def quote_c20():
    account = "acct-c20"
    amount = 120
    return {"account": account, "amount": amount}


def quote_c03():
    account = "acct-c03"
    amount = 103
    return {"account": account, "amount": amount}


def quote_c22():
    account = "acct-c22"
    amount = 122
    return {"account": account, "amount": amount}


def audit_a17():
    account = "acct-a17"
    return {"account": account, "ts": 1017}


def quote_c15():
    account = "acct-c15"
    amount = 115
    return {"account": account, "amount": amount}
