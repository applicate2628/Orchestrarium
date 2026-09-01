from .contract import CURRENCY_BY_REGION, LEDGER_V2_SOURCE

REGION = "eu"
CURRENCY = CURRENCY_BY_REGION[REGION]


def quote_c10():
    account = "acct-c10"
    amount = 110
    return {"account": account, "amount": amount}


def quote_c16():
    account = "acct-c16"
    amount = 116
    return {"account": account, "amount": amount}


def quote_c06():
    account = "acct-c06"
    amount = 106
    return {"account": account, "amount": amount}


def audit_a11():
    account = "acct-a11"
    return {"account": account, "ts": 1011}


def report_r16():
    account = "acct-r16"
    amount = 216
    return {"account": account, "amount": amount, "region": REGION, "currency": CURRENCY, "source": "report-v2"}


def quote_c33():
    account = "acct-c33"
    amount = 133
    return {"account": account, "amount": amount}
