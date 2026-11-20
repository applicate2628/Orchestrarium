"""Trace ownership regression tests without importing/provisioning Agents SDK."""
from types import SimpleNamespace
import pytest
from test_sdk_coordination_runner import isolated_trace_provider


@pytest.mark.parametrize("failure", [None, "body", "setup", "shutdown"])
def test_trace_provider_is_restored_without_closing_previous(failure):
    previous = object()
    state = {"provider": previous, "closed": 0}
    def set_provider(value):
        state["provider"] = value
    class Owned:
        def set_disabled(self, value):
            assert value is True
            if failure == "setup":
                raise RuntimeError("setup failed")
        def shutdown(self):
            state["closed"] += 1
            if failure == "shutdown":
                raise RuntimeError("shutdown failed")
    api = SimpleNamespace(get_trace_provider=lambda: state["provider"],
                          set_trace_provider=set_provider)
    def exercise():
        with isolated_trace_provider(api, Owned) as owned:
            assert state["provider"] is owned
            if failure == "body":
                raise RuntimeError("body failed")
    if failure:
        with pytest.raises(RuntimeError, match=failure + " failed"):
            exercise()
    else:
        exercise()
    assert state["provider"] is previous
    assert state["closed"] == 1
