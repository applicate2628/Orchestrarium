from .contract import CURRENCY_BY_REGION, LEDGER_V2_SOURCE

REGION = "uk"
CURRENCY = CURRENCY_BY_REGION[REGION]


def quote_c06():
    account = "acct-c06"
    amount = 106
    return {"account": account, "amount": amount}


def report_r02():
    account = "acct-r02"
    amount = 202
    return {"account": account, "amount": amount, "region": REGION, "currency": CURRENCY, "source": "report-v2"}


def quote_c01():
    account = "acct-c01"
    amount = 101
    return {"account": account, "amount": amount}


def quote_c07():
    account = "acct-c07"
    amount = 107
    return {"account": account, "amount": amount}


def audit_a05():
    account = "acct-a05"
    return {"account": account, "ts": 1005}
