class AccountDirectory:
    def __init__(self, accounts, now=50):
        self.accounts = accounts
        self.now = now

    def get_account(self, account_id):
        account = self.accounts.get(account_id)
        if not account:
            return None
        return dict(account)
