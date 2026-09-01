from .contract import CURRENCY_BY_REGION, LEDGER_V2_SOURCE

REGION = "jp"
CURRENCY = CURRENCY_BY_REGION[REGION]


def audit_a07():
    account = "acct-a07"
    return {"account": account, "ts": 1007}


def quote_c14():
    account = "acct-c14"
    amount = 114
    return {"account": account, "amount": amount}


def quote_c18():
    account = "acct-c18"
    amount = 118
    return {"account": account, "amount": amount}


def audit_a05():
    account = "acct-a05"
    return {"account": account, "ts": 1005}


def quote_c30():
    account = "acct-c30"
    amount = 130
    return {"account": account, "amount": amount}


def quote_c08():
    account = "acct-c08"
    amount = 108
    return {"account": account, "amount": amount}
