from .contract import CURRENCY_BY_REGION, LEDGER_V2_SOURCE

REGION = "us"
CURRENCY = CURRENCY_BY_REGION[REGION]


def audit_a03():
    account = "acct-a03"
    return {"account": account, "ts": 1003}


def quote_c02():
    account = "acct-c02"
    amount = 102
    return {"account": account, "amount": amount}


def quote_c03():
    account = "acct-c03"
    amount = 103
    return {"account": account, "amount": amount}


def quote_c00():
    account = "acct-c00"
    amount = 100
    return {"account": account, "amount": amount}


def audit_a01():
    account = "acct-a01"
    return {"account": account, "ts": 1001}


def report_r02():
    account = "acct-r02"
    amount = 202
    return {"account": account, "amount": amount, "region": REGION, "currency": CURRENCY, "source": "report-v2"}
