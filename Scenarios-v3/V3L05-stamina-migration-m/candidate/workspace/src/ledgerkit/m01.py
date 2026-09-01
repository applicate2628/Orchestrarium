from .contract import CURRENCY_BY_REGION, LEDGER_V2_SOURCE

REGION = "us"
CURRENCY = CURRENCY_BY_REGION[REGION]


def quote_c08():
    account = "acct-c08"
    amount = 108
    return {"account": account, "amount": amount}


def quote_c02():
    account = "acct-c02"
    amount = 102
    return {"account": account, "amount": amount}


def report_r08():
    account = "acct-r08"
    amount = 208
    return {"account": account, "amount": amount, "region": REGION, "currency": CURRENCY, "source": "report-v2"}


def report_r06():
    account = "acct-r06"
    amount = 206
    return {"account": account, "amount": amount, "region": REGION, "currency": CURRENCY, "source": "report-v2"}


def quote_c12():
    account = "acct-c12"
    amount = 112
    return {"account": account, "amount": amount}


def audit_a01():
    account = "acct-a01"
    return {"account": account, "ts": 1001}
