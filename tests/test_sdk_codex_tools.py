"""Pure Codex Model Context Protocol selection tests; no provider execution."""
from dataclasses import FrozenInstanceError
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sdk_execution.codex_tools import (
    CODEX_MCP_ISOLATION_OVERRIDES, CodexMcpScope, CodexMcpScopeError,
)


def row(name="Docs", tool_names=("read",), **changes):
    result = {"name": name, "runtimeStatus": "connected", "toolsError": None,
              "pluginId": None, "tools": {tool: {"name": tool} for tool in tool_names}}
    result.update(changes)
    return result


def test_immutable_canonical_roundtrip_exact_case():
    scope = CodexMcpScope((("docs", ("z", "A")), ("Docs", ("read",))))
    assert scope.servers == (("Docs", ("read",)), ("docs", ("A", "z")))
    assert CodexMcpScope.from_dict(scope.to_dict()) == scope
    with pytest.raises(FrozenInstanceError):
        scope.servers = ()
    exported = scope.to_dict()
    exported["servers"][0]["tools"].append("write")
    assert scope.servers[0][1] == ("read",)


def test_empty_scope_disables_known_servers_not_future_reload():
    scope = CodexMcpScope(())
    assert scope.to_dict() == {"servers": []}
    assert scope.thread_overrides(("Docs", "other")) == {
        "mcp_servers": {"Docs": {"enabled": False}, "other": {"enabled": False}}}
    assert scope.thread_overrides(()) == {"mcp_servers": {}}
    assert scope.validate_inventory([]) == ()
    assert scope.validate_inventory([row(tool_names=(), runtimeStatus="disabled")]) == ()
    with pytest.raises(CodexMcpScopeError):
        scope.validate_inventory([row()])


def test_selected_subset_preserves_inherited_denials():
    scope = CodexMcpScope((("Docs", ("read",)),))
    overrides = scope.thread_overrides(("other", "Docs"))
    assert overrides == {"mcp_servers": {
        "Docs": {"enabled_tools": ["read"]},
        "other": {"enabled": False}}}
    assert "disabled_tools" not in overrides["mcp_servers"]["Docs"]
    assert scope.validate_inventory([row(secret="never returned")]) == scope.servers
    with pytest.raises(CodexMcpScopeError):
        scope.validate_inventory([row(tool_names=())])


@pytest.mark.parametrize("value", [None, {}, {"servers": [], "extra": 1},
    {"servers": ()}, {"servers": [{}]}, {"servers": [{"name": "x"}]},
    {"servers": [{"name": "x", "tools": ["a"], "url": "endpoint"}]},
    {"servers": [{"name": "x", "tools": "a"}]}])
def test_strict_wire_shape(value):
    with pytest.raises(CodexMcpScopeError):
        CodexMcpScope.from_dict(value)


@pytest.mark.parametrize("servers", [[], (("Docs", ()),), (("Docs", ["read"]),),
    (("Docs", ("read", "read")),), (("Docs", ("read",)), ("Docs", ("other",))),
    ((True, ("read",)),), (("Docs", (False,)),), (("", ("read",)),),
    (("   ", ("read",)),), (("x\n", ("read",)),), (("x" * 257, ("read",)),),
    (("Docs", ("x" * 257,)),)])
def test_invalid_scope(servers):
    with pytest.raises(CodexMcpScopeError):
        CodexMcpScope(servers)


def test_bounded_sizes():
    assert len(CodexMcpScope(tuple((f"s{i}", ("t",)) for i in range(128))).servers) == 128
    with pytest.raises(CodexMcpScopeError):
        CodexMcpScope(tuple((f"s{i}", ("t",)) for i in range(129)))
    assert len(CodexMcpScope((("s", tuple(f"t{i}" for i in range(4096))),)).servers[0][1]) == 4096
    with pytest.raises(CodexMcpScopeError):
        CodexMcpScope((("s", tuple(f"t{i}" for i in range(4097))),))


@pytest.mark.parametrize("census", [(), ("docs",), ("Docs", "Docs"), (True,), "Docs", ("",), tuple(f"s{i}" for i in range(129))])
def test_missing_or_invalid_census(census):
    with pytest.raises(CodexMcpScopeError):
        CodexMcpScope((("Docs", ("read",)),)).thread_overrides(census)


@pytest.mark.parametrize("changes", [
    {"runtimeStatus": None}, {"runtimeStatus": "connecting"}, {"runtimeStatus": "failed"},
    {"runtimeStatus": "disabled"}, {"runtimeStatus": "stale"}, {"toolsError": "failed"},
    {"toolsError": ""}, {"pluginId": "plugin"}, {"pluginId": ""},
    {"tools": []}, {"tools": None}, {"tools": {"read": {"name": "other"}}},
    {"tools": {"read": {}}}, {"tools": {"read": "read"}},
    {"tools": {"read": {"name": "read"}, "write": {"name": "write"}}},
])
def test_selected_inventory_rejects_unavailable_or_mismatched_rows(changes):
    with pytest.raises(CodexMcpScopeError):
        CodexMcpScope((("Docs", ("read",)),)).validate_inventory([row(**changes)])


@pytest.mark.parametrize("field", ["name", "runtimeStatus", "tools"])
def test_missing_inventory_fields(field):
    value = row()
    del value[field]
    with pytest.raises(CodexMcpScopeError):
        CodexMcpScope((("Docs", ("read",)),)).validate_inventory([value])


def test_missing_duplicate_and_malformed_inventory():
    scope = CodexMcpScope((("Docs", ("read",)),))
    for rows in ([], [row(), row()], None, {}, [None], [row(name=True)]):
        with pytest.raises(CodexMcpScopeError):
            scope.validate_inventory(rows)
    with pytest.raises(CodexMcpScopeError):
        CodexMcpScope((("Docs", ("read", "other")),)).validate_inventory([
            row(tools={"read": {"name": "read"}, "other": {"name": "read"}})])


@pytest.mark.parametrize("changes", [{"tools": {"read": {"name": "read"}}},
    {"runtimeStatus": None}, {"runtimeStatus": "connected"}, {"toolsError": "oops"},
    {"pluginId": "plugin"}])
def test_unselected_server_must_be_disabled_empty_and_unambiguous(changes):
    value = row(tool_names=(), runtimeStatus="disabled")
    value.update(changes)
    with pytest.raises(CodexMcpScopeError):
        CodexMcpScope(()).validate_inventory([value])


def test_startup_isolation_is_explicit_invocation_only():
    assert CODEX_MCP_ISOLATION_OVERRIDES == (
        "features.plugins=false", "features.apps=false", "agents.enabled=false",
        "features.multi_agent_v2=false",
    )


def test_exact_names_with_spaces_quotes_and_unicode_are_not_normalized():
    name = ' Docs."é" '
    scope = CodexMcpScope(((name, ("read item",)),))
    assert CodexMcpScope.from_dict(scope.to_dict()) == scope
    assert scope.thread_overrides((name, 'other server."文"')) == {
        "mcp_servers": {name: {"enabled_tools": ["read item"]},
                        'other server."文"': {"enabled": False}}}
    assert scope.validate_inventory([row(name=name, tool_names=("read item",))]) == scope.servers


@pytest.mark.parametrize("field", ["toolsError", "pluginId"])
def test_optional_null_inventory_metadata_may_be_omitted(field):
    value = row()
    del value[field]
    scope = CodexMcpScope((("Docs", ("read",)),))
    assert scope.validate_inventory([value]) == scope.servers
