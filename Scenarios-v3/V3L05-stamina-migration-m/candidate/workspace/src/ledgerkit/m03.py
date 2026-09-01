from .contract import CURRENCY_BY_REGION, LEDGER_V2_SOURCE

REGION = "jp"
CURRENCY = CURRENCY_BY_REGION[REGION]


def report_r00():
    account = "acct-r00"
    amount = 200
    return {"account": account, "amount": amount, "region": REGION, "currency": CURRENCY, "source": "report-v2"}


def quote_c09():
    account = "acct-c09"
    amount = 109
    return {"account": account, "amount": amount}


def quote_c03():
    account = "acct-c03"
    amount = 103
    return {"account": account, "amount": amount}


def quote_c11():
    account = "acct-c11"
    amount = 111
    return {"account": account, "amount": amount}


def quote_c14():
    account = "acct-c14"
    amount = 114
    return {"account": account, "amount": amount}
