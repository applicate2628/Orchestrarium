"""Claude selection preserves the canonical ledger's paired optional caps."""
import pytest
from test_sdk_claude import claude_selection
from sdk_execution.claude import ClaudeRuntimeSelection, AdapterError


def test_omitted_caps_round_trip(tmp_path):
    selected = claude_selection(tmp_path, ledger_max_events=None, ledger_max_bytes=None)
    assert ClaudeRuntimeSelection.from_dict(selected.to_dict()) == selected
    assert selected.to_dict()["ledger_max_events"] is None
    assert selected.to_dict()["ledger_max_bytes"] is None


@pytest.mark.parametrize("changes", [
    {"ledger_max_events": None}, {"ledger_max_bytes": None},
    {"ledger_max_events": True}, {"ledger_max_bytes": False},
    {"ledger_max_events": 0}, {"ledger_max_bytes": -1},
    {"ledger_max_events": "100"}, {"ledger_max_bytes": 1.5},
    {"ledger_max_events": None, "ledger_max_bytes": None, "job_memory_limit_bytes": None},
    {"ledger_max_events": None, "ledger_max_bytes": None, "job_memory_limit_bytes": 0},
])
def test_invalid_caps_and_memory_refused(tmp_path, changes):
    with pytest.raises(AdapterError, match="explicit_positive_resource_budget_required"):
        claude_selection(tmp_path, **changes)
