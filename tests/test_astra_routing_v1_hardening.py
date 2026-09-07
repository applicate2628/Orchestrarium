from __future__ import annotations

import importlib.util
import sys
from collections.abc import Collection, Iterator
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src.codex" / "skills" / "astra-routing" / "scripts" / "resolve.py"


def _load():
    spec = importlib.util.spec_from_file_location("astra_routing_v1_hardening", MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ChangingInventory(Collection[str]):
    """Return a different valid inventory on the second iteration."""

    def __init__(self) -> None:
        self.iterations = 0

    def __contains__(self, value: object) -> bool:
        return value == "gpt-5.6-sol"

    def __len__(self) -> int:
        return 1

    def __iter__(self) -> Iterator[str]:
        self.iterations += 1
        if self.iterations == 1:
            return iter(("gpt-5.6-sol",))
        return iter(("gpt-6-astra",))


def test_model_inventory_is_normalized_exactly_once() -> None:
    module = _load()
    inventory = ChangingInventory()
    result = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models=inventory,
        route_evidence="mathematics-quality-floor",
    )

    assert inventory.iterations == 1
    assert result["status"] == "unavailable"
    assert result["stableId"] == "E_ASTRA_V1_UNAVAILABLE"


def test_duplicate_or_exceptional_inventory_fails_closed() -> None:
    module = _load()
    duplicate = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models=("gpt-6-astra", "gpt-6-astra"),
        route_evidence="mathematics-quality-floor",
    )
    assert duplicate["status"] == "denied"
    assert duplicate["stableId"] == "E_ASTRA_V1_REQUEST_INVALID"

    class BrokenInventory(Collection[str]):
        def __contains__(self, value: object) -> bool:
            return False

        def __len__(self) -> int:
            return 1

        def __iter__(self) -> Iterator[str]:
            raise RuntimeError("untrusted inventory failed")

    broken = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models=BrokenInventory(),
        route_evidence="mathematics-quality-floor",
    )
    assert broken["status"] == "denied"
    assert broken["stableId"] == "E_ASTRA_V1_REQUEST_INVALID"


def test_route_selection_never_grants_execution_authority() -> None:
    module = _load()
    selected = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models=("gpt-6-astra",),
        route_evidence="mathematics-quality-floor",
    )
    denied = module.resolve_v1_astra_route(
        task_class="mathematical-research",
        available_models=(),
        route_evidence="mathematics-quality-floor",
    )

    assert selected["status"] == "selected"
    assert selected["requiresAdapterAdmission"] is True
    assert selected["executionAuthorized"] is False
    assert denied["requiresAdapterAdmission"] is False
    assert denied["executionAuthorized"] is False
