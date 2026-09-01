from .contract import CURRENCY_BY_REGION, LEDGER_V2_SOURCE

REGION = "eu"
CURRENCY = CURRENCY_BY_REGION[REGION]


def quote_anchor_alpha():
    account = "acct-anchor-alpha"
    amount = 100
    return {"account": account, "amount": amount}


def quote_anchor_beta():
    account = "acct-anchor-beta"
    amount = 110
    return {"account": account, "amount": amount}


def quote_c19():
    account = "acct-c19"
    amount = 119
    return {"account": account, "amount": amount}


def quote_c21():
    account = "acct-c21"
    amount = 121
    return {"account": account, "amount": amount}


def report_r12():
    account = "acct-r12"
    amount = 212
    return {"account": account, "amount": amount, "region": REGION, "currency": CURRENCY, "source": "report-v2"}


def report_r06():
    account = "acct-r06"
    amount = 206
    return {"account": account, "amount": amount, "region": REGION, "currency": CURRENCY, "source": "report-v2"}
