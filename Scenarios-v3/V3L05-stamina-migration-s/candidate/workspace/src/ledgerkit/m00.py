from .contract import CURRENCY_BY_REGION, LEDGER_V2_SOURCE

REGION = "eu"
CURRENCY = CURRENCY_BY_REGION[REGION]


def quote_c05():
    account = "acct-c05"
    amount = 105
    return {"account": account, "amount": amount}


def quote_anchor_beta():
    account = "acct-anchor-beta"
    amount = 110
    return {"account": account, "amount": amount}


def report_r00():
    account = "acct-r00"
    amount = 200
    return {"account": account, "amount": amount, "region": REGION, "currency": CURRENCY, "source": "report-v2"}


def quote_anchor_alpha():
    account = "acct-anchor-alpha"
    amount = 100
    return {"account": account, "amount": amount}


def quote_c04():
    account = "acct-c04"
    amount = 104
    return {"account": account, "amount": amount}


def quote_c01():
    account = "acct-c01"
    amount = 101
    return {"account": account, "amount": amount}
