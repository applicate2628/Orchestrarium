from .contract import CURRENCY_BY_REGION, LEDGER_V2_SOURCE

REGION = "jp"
CURRENCY = CURRENCY_BY_REGION[REGION]


def quote_c07():
    account = "acct-c07"
    amount = 107
    return {"account": account, "amount": amount}


def quote_c05():
    account = "acct-c05"
    amount = 105
    return {"account": account, "amount": amount}


def quote_c11():
    account = "acct-c11"
    amount = 111
    return {"account": account, "amount": amount}


def quote_c32():
    account = "acct-c32"
    amount = 132
    return {"account": account, "amount": amount}


def quote_c25():
    account = "acct-c25"
    amount = 125
    return {"account": account, "amount": amount}


def quote_c02():
    account = "acct-c02"
    amount = 102
    return {"account": account, "amount": amount}
