"""Bounded input work and bounded diagnostic output for the Astra selector."""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Collection, Iterator
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src.codex" / "skills" / "astra-routing" / "scripts" / "resolve.py"


def _load():
    spec = importlib.util.spec_from_file_location("astra_input_bounds_test", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _request(module, **changes):
    values = {
        "task_class": "mathematical-research",
        "available_models": ("gpt-6-astra",),
        "route_evidence": "mathematics-quality-floor",
    }
    values.update(changes)
    return module.resolve_v1_astra_route(**values)


class CountedInventory(Collection[str]):
    """Finite source with independent reported and actually yielded lengths."""

    def __init__(self, count: int, reported: int = 1) -> None:
        self.count = count
        self.reported = reported
        self.reads = 0
        self.iterations = 0

    def __contains__(self, value: object) -> bool:
        return False

    def __len__(self) -> int:
        return self.reported

    def __iter__(self) -> Iterator[str]:
        self.iterations += 1
        for index in range(self.count):
            self.reads += 1
            yield "gpt-6-astra" if index == 0 else f"fixture-model-{index}"


@pytest.mark.parametrize("reported", (0, 1, 128, 260))
def test_over_limit_inventory_stops_at_first_excess_item(reported: int) -> None:
    module = _load()
    inventory = CountedInventory(260, reported)
    result = _request(module, available_models=inventory)
    assert result["stableId"] == "E_ASTRA_V1_REQUEST_INVALID"
    assert inventory.iterations == 1
    assert inventory.reads == 129, "size validation must bound consumption itself"


@pytest.mark.parametrize("count", (1, 127, 128))
def test_bounded_single_snapshot_accepts_the_whole_allowed_inventory(count: int) -> None:
    module = _load()
    inventory = CountedInventory(count)
    result = _request(module, available_models=inventory)
    assert result["status"] == "selected"
    assert result["model"] == "gpt-6-astra"
    assert inventory.iterations == 1
    assert inventory.reads == count


@pytest.mark.parametrize(
    "changes",
    (
        {"task_class": None},
        {"requested_effort": ""},
        {"allow_max_effort": 1},
        {"requested_fanout": True},
        {"route_evidence": "x" * 129},
    ),
)
def test_invalid_scalar_shape_does_not_consume_inventory(changes: dict) -> None:
    module = _load()
    inventory = CountedInventory(3)
    result = _request(module, available_models=inventory, **changes)
    assert result["stableId"] == "E_ASTRA_V1_REQUEST_INVALID"
    assert inventory.iterations == 0
    assert inventory.reads == 0


@pytest.mark.parametrize(
    "value", ("x" * 129, "x" * 8192, "bad\x00evidence", ""),
    ids=("over-bound", "long-text", "nul", "empty"),
)
def test_invalid_evidence_is_not_echoed_in_the_denial(value: str) -> None:
    module = _load()
    result = _request(module, route_evidence=value)
    assert result["stableId"] == "E_ASTRA_V1_REQUEST_INVALID"
    assert result["routeEvidence"] is None
    assert len(json.dumps(result)) < 2048


@pytest.mark.parametrize(
    "value", ("x" * 129, "bad\x00task", None), ids=("over-bound", "nul", "not-text")
)
def test_invalid_task_label_is_not_echoed_in_the_denial(value) -> None:
    module = _load()
    result = _request(module, task_class=value)
    assert result["stableId"] == "E_ASTRA_V1_REQUEST_INVALID"
    assert result["taskClass"] == ""


def test_empty_and_duplicate_inventory_still_fail_without_launch_flags() -> None:
    module = _load()
    empty = _request(module, available_models=())
    duplicate = _request(module, available_models=("gpt-6-astra", "gpt-6-astra"))
    assert empty["status"] == "unavailable"
    assert duplicate["status"] == "denied"
    for result in (empty, duplicate):
        assert result["codexFlags"] == []
        assert result["executionAuthorized"] is False
        assert result["authorizing"] is False


def test_inventory_conversion_error_is_a_typed_denial() -> None:
    class UnhashableModel(str):
        __hash__ = None

    module = _load()
    result = _request(module, available_models=(UnhashableModel("gpt-6-astra"),))
    assert result["stableId"] == "E_ASTRA_V1_REQUEST_INVALID"
    assert result["codexFlags"] == []


def test_denial_keeps_valid_bounded_context_for_other_bad_fields() -> None:
    module = _load()
    result = _request(module, requested_fanout=True)
    assert result["stableId"] == "E_ASTRA_V1_REQUEST_INVALID"
    assert result["taskClass"] == "mathematical-research"
    assert result["routeEvidence"] == "mathematics-quality-floor"


def test_cli_denial_output_stays_bounded(capsys: pytest.CaptureFixture[str]) -> None:
    module = _load()
    status = module.main([
        "--task-class", "mathematical-research", "--available-model", "gpt-6-astra",
        "--route-evidence", "x" * 8192,
    ])
    captured = capsys.readouterr()
    assert status == 2
    assert captured.err == ""
    assert len(captured.out.encode("utf-8")) < 2048
    result = json.loads(captured.out)
    assert result["routeEvidence"] is None
    assert result["codexFlags"] == []
    assert result["executionAuthorized"] is False
