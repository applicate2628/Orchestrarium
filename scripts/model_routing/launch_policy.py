"""Effective model-launch invariants; caller assertions are not user consent.

Provider/profile/role/host admission and genuine one-attempt receiving remain
with their actual owners. This module has no runtime or filesystem dependency.
"""
from __future__ import annotations


def launch_requirements(provider: str, model: str, effort: str) -> tuple[str | None, bool]:
    """Return a forbidden-choice reason and whether individual agreement is needed."""
    if not all(type(value) is str and value for value in (provider, model, effort)):
        return "effective-choice-incomplete", False
    if effort == "low":
        return "low-not-admitted", False
    if effort == "ultra":
        return "automatic-delegation-effort-not-admitted", False
    if provider == "codex":
        if model == "gpt-6-luna" and effort not in {"high", "xhigh", "max"}:
            return "luna-minimum-high", False
        if model in {"gpt-6.1-terra", "gpt-5.6-terra"} and effort not in {"medium", "high", "xhigh", "max"}:
            return "terra-minimum-medium", False
    return None, (provider == "codex" and model in {"gpt-6-astra", "gpt-6.2-astra"}) or effort == "max"


def qualify_launch(provider: str, model: str, effort: str, *,
                   user_approved_launch: bool = False,
                   user_approved_max: bool = False,
                   task_class: str | None = None,
                   astra_task_authorization: dict | None = None) -> str | None:
    """Qualify the table rule only; a True assertion never creates a human grant."""
    reason, needs_agreement = launch_requirements(provider, model, effort)
    if reason is not None:
        return reason
    # This is caller-carried evidence of an existing task grant, not permission
    # minted by a flag. Outer provider/quota permissions remain with their owner.
    scoped_astra = (
        provider == "codex" and model == "gpt-6.2-astra"
        and effort in {"high", "xhigh"}
        and task_class in {"critical-design", "critical-security", "review"}
        and type(astra_task_authorization) is dict
        and astra_task_authorization.get("taskClass") == task_class
        and all(type(astra_task_authorization.get(key)) is str
                and astra_task_authorization[key].strip()
                for key in ("scope", "approvalReference"))
    )
    if needs_agreement and not (
        scoped_astra or
        user_approved_launch is True or (effort == "max" and user_approved_max is True)
    ):
        return "individual-launch-approval-required"
    return None
