from .contract import CURRENCY_BY_REGION, LEDGER_V2_SOURCE

REGION = "uk"
CURRENCY = CURRENCY_BY_REGION[REGION]


def report_r00():
    account = "acct-r00"
    amount = 200
    return {"account": account, "amount": amount, "region": REGION, "currency": CURRENCY, "source": "report-v2"}


def quote_c01():
    account = "acct-c01"
    amount = 101
    return {"account": account, "amount": amount}


def quote_c00():
    account = "acct-c00"
    amount = 100
    return {"account": account, "amount": amount}


def quote_c26():
    account = "acct-c26"
    amount = 126
    return {"account": account, "amount": amount}


def quote_c13():
    account = "acct-c13"
    amount = 113
    return {"account": account, "amount": amount}


def audit_a09():
    account = "acct-a09"
    return {"account": account, "ts": 1009}
