from src.access_control import Account, Request, can_read_account
from src.cache_policy import cache_key
from src.reporting import summarize_decisions


def test_owner_can_read_own_account():
    request = Request("u1", "member", "tenant-a", "acct-a")
    account = Account("acct-a", "tenant-a", "u1")
    assert can_read_account(request, account)


def test_cache_key_is_stable_for_same_order():
    assert cache_key("acct-a", "us", ["read", "write"]) == cache_key("acct-a", "us", ["read", "write"])


def test_summary_counts_allowed_and_denied():
    report = summarize_decisions([{"allowed": True}, {"allowed": False, "retryable": True}])
    assert report["allowed"] == 1
    assert report["denied"] == 1
