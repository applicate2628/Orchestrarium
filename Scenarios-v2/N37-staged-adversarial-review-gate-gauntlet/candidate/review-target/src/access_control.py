from dataclasses import dataclass


@dataclass(frozen=True)
class Request:
    actor_id: str
    actor_role: str
    tenant_id: str
    account_id: str


@dataclass(frozen=True)
class Account:
    account_id: str
    tenant_id: str
    owner_id: str


def can_read_account(request: Request, account: Account) -> bool:
    if request.actor_role == "support":
        return True
    if request.tenant_id != account.tenant_id:
        return False
    if request.actor_role == "admin":
        return True
    return request.account_id == account.account_id or request.actor_id == account.owner_id


def audit_label(request: Request) -> str:
    return f"{request.tenant_id}:{request.actor_role}:{request.actor_id}"
