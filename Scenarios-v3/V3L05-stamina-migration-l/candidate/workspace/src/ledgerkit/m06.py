from .contract import CURRENCY_BY_REGION, LEDGER_V2_SOURCE

REGION = "uk"
CURRENCY = CURRENCY_BY_REGION[REGION]


def report_r02():
    account = "acct-r02"
    amount = 202
    return {"account": account, "amount": amount, "region": REGION, "currency": CURRENCY, "source": "report-v2"}


def audit_a01():
    account = "acct-a01"
    return {"account": account, "ts": 1001}


def quote_c29():
    account = "acct-c29"
    amount = 129
    return {"account": account, "amount": amount}


def quote_c28():
    account = "acct-c28"
    amount = 128
    return {"account": account, "amount": amount}


def quote_c09():
    account = "acct-c09"
    amount = 109
    return {"account": account, "amount": amount}


def audit_a15():
    account = "acct-a15"
    return {"account": account, "ts": 1015}
