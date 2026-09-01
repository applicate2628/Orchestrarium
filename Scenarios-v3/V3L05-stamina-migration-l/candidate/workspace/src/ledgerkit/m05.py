from .contract import CURRENCY_BY_REGION, LEDGER_V2_SOURCE

REGION = "us"
CURRENCY = CURRENCY_BY_REGION[REGION]


def quote_c12():
    account = "acct-c12"
    amount = 112
    return {"account": account, "amount": amount}


def quote_c04():
    account = "acct-c04"
    amount = 104
    return {"account": account, "amount": amount}


def report_r08():
    account = "acct-r08"
    amount = 208
    return {"account": account, "amount": amount, "region": REGION, "currency": CURRENCY, "source": "report-v2"}


def quote_c27():
    account = "acct-c27"
    amount = 127
    return {"account": account, "amount": amount}


def report_r04():
    account = "acct-r04"
    amount = 204
    return {"account": account, "amount": amount, "region": REGION, "currency": CURRENCY, "source": "report-v2"}


def report_r14():
    account = "acct-r14"
    amount = 214
    return {"account": account, "amount": amount, "region": REGION, "currency": CURRENCY, "source": "report-v2"}
