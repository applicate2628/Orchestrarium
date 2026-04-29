from dataclasses import dataclass, field


@dataclass(frozen=True)
class ExportRequest:
    tenant_id: str
    user_id: str
    resource_id: str
    role: str
    return_url: str
    issued_at: int
    nonce: str
    break_glass_ticket: str = ""


@dataclass(frozen=True)
class AccessDecision:
    allowed: bool
    reason: str
    owner: str
    source_ids: list[str] = field(default_factory=list)
    return_url: str = ""
