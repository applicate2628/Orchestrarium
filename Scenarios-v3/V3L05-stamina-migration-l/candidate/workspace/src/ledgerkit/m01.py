from .contract import CURRENCY_BY_REGION, LEDGER_V2_SOURCE

REGION = "us"
CURRENCY = CURRENCY_BY_REGION[REGION]


def audit_a13():
    account = "acct-a13"
    return {"account": account, "ts": 1013}


def quote_c17():
    account = "acct-c17"
    amount = 117
    return {"account": account, "amount": amount}


def report_r10():
    account = "acct-r10"
    amount = 210
    return {"account": account, "amount": amount, "region": REGION, "currency": CURRENCY, "source": "report-v2"}


def audit_a03():
    account = "acct-a03"
    return {"account": account, "ts": 1003}


def quote_c31():
    account = "acct-c31"
    amount = 131
    return {"account": account, "amount": amount}


def quote_c23():
    account = "acct-c23"
    amount = 123
    return {"account": account, "amount": amount}
