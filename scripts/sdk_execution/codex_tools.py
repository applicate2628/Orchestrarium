"""Pure, provider-local Model Context Protocol (MCP) selection for Codex.

This is an explicit set of identities, not endpoint configuration or authority.
The caller owns host eligibility, configuration admission, and acquisition of a
completed thread-scoped catalog. Inventory equality proves neither all native /
dynamic / extension tools nor atomic isolation from future configuration reloads.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import unicodedata


MAX_SERVERS = 128
MAX_TOOLS = 4096
MAX_IDENTIFIER_LENGTH = 256

# Construct and admit the effective invocation configuration BEFORE launching.
# Never append these to an already admitted request or write global/role config.
CODEX_MCP_ISOLATION_OVERRIDES = (
    "features.plugins=false",
    "features.apps=false",
    "agents.enabled=false",
    "features.multi_agent_v2=false",
)


class CodexMcpScopeError(ValueError):
    """Malformed selection, census, or inventory; diagnostic contains no payload."""


def _identifier(value: Any) -> str:
    if (type(value) is not str or not 1 <= len(value) <= MAX_IDENTIFIER_LENGTH
            or not value.strip()
            or any(unicodedata.category(char) in {"Cc", "Cs"} for char in value)):
        raise CodexMcpScopeError("MCP identities must be bounded plain nonempty strings")
    return value


@dataclass(frozen=True, slots=True)
class CodexMcpScope:
    """Canonical immutable SET of exact, case-sensitive server/tool identities.

    Empty servers means no selected MCP tools. A selected server must have an
    explicit nonempty tool tuple; no wildcard or implicit allow-all exists.
    """

    servers: tuple[tuple[str, tuple[str, ...]], ...]

    def __post_init__(self) -> None:
        if type(self.servers) is not tuple or len(self.servers) > MAX_SERVERS:
            raise CodexMcpScopeError("MCP scope must be a bounded server tuple")
        seen: set[str] = set()
        total = 0
        canonical = []
        for pair in self.servers:
            if type(pair) is not tuple or len(pair) != 2:
                raise CodexMcpScopeError("MCP selection requires server/tool pairs")
            name, tools = pair
            _identifier(name)
            if name in seen:
                raise CodexMcpScopeError("Duplicate MCP server identity")
            seen.add(name)
            if type(tools) is not tuple or not tools:
                raise CodexMcpScopeError("Selected MCP server requires an explicit nonempty tool tuple")
            total += len(tools)
            if total > MAX_TOOLS:
                raise CodexMcpScopeError("MCP selection exceeds tool limit")
            for tool in tools:
                _identifier(tool)
            if len(set(tools)) != len(tools):
                raise CodexMcpScopeError("Duplicate MCP tool identity")
            canonical.append((name, tuple(sorted(tools))))
        object.__setattr__(self, "servers", tuple(sorted(canonical)))

    def to_dict(self) -> dict[str, Any]:
        """Return a fresh exact wire shape, containing only admitted identities."""
        return {"servers": [{"name": name, "tools": list(tools)} for name, tools in self.servers]}

    @classmethod
    def from_dict(cls, value: Any) -> CodexMcpScope:
        """Read the exact wire shape; missing and unexpected fields fail closed."""
        if type(value) is not dict or set(value) != {"servers"}:
            raise CodexMcpScopeError("MCP scope requires exactly the servers field")
        rows = value["servers"]
        if type(rows) is not list or len(rows) > MAX_SERVERS:
            raise CodexMcpScopeError("MCP servers must be a bounded list")
        pairs = []
        total = 0
        for row in rows:
            if type(row) is not dict or set(row) != {"name", "tools"}:
                raise CodexMcpScopeError("MCP server requires exactly name and tools fields")
            if type(row["tools"]) is not list:
                raise CodexMcpScopeError("MCP tools must be an explicit list")
            total += len(row["tools"])
            if total > MAX_TOOLS:
                raise CodexMcpScopeError("MCP selection exceeds tool limit")
            pairs.append((row["name"], tuple(row["tools"])))
        return cls(tuple(pairs))

    def thread_overrides(self, configured_server_names: tuple[str, ...] | list[str]) -> dict[str, Any]:
        """Disable each unselected known server; restrict selected existing ones.

        Selected enablement is inherited, never forced true. The caller must
        establish eligibility; this map cannot reactivate a disabled server. Inherited
        disabled_tools is preserved; conflicting denials fail inventory equality,
        never get cleared. Config maps merge: an empty table does NOT clear
        inherited servers, and this census cannot exclude future reload additions.
        No endpoint, command or credential is copied into this result.
        """
        if type(configured_server_names) not in (tuple, list) or len(configured_server_names) > MAX_SERVERS:
            raise CodexMcpScopeError("MCP configured census must be a bounded list or tuple")
        names: set[str] = set()
        for name in configured_server_names:
            _identifier(name)
            if name in names:
                raise CodexMcpScopeError("Duplicate configured MCP server identity")
            names.add(name)
        selected = dict(self.servers)
        if not selected.keys() <= names:
            raise CodexMcpScopeError("Selected MCP server absent from configured census")
        return {"mcp_servers": {
            name: {"enabled_tools": list(selected[name])}
            if name in selected else {"enabled": False}
            for name in sorted(names)
        }}

    def validate_inventory(self, rows: list[dict[str, Any]] | tuple[dict[str, Any], ...]) -> tuple[tuple[str, tuple[str, ...]], ...]:
        """Validate explicitly supplied, completed THREAD-SCOPED status rows.

        Caller owns pagination, freshness and live per-server acquisition; this
        pure function cannot establish those properties. Rows must expose the
        exact filtered tools. Optional toolsError/pluginId omission means null under
        the public schema, not missing evidence. Unselected rows may only describe disabled ordinary
        servers with no tools/errors/plugin identity. Other metadata is ignored,
        never returned. Only the immutable admitted identities are returned.
        """
        if type(rows) not in (list, tuple) or len(rows) > MAX_SERVERS:
            raise CodexMcpScopeError("MCP inventory must be a bounded list or tuple")
        selected = dict(self.servers)
        seen: set[str] = set()
        total = 0
        required = {"name", "runtimeStatus", "tools"}
        for row in rows:
            if type(row) is not dict or not required <= row.keys():
                raise CodexMcpScopeError("MCP inventory row is missing required status fields")
            name = _identifier(row["name"])
            if name in seen:
                raise CodexMcpScopeError("Duplicate MCP inventory server identity")
            seen.add(name)
            if row.get("toolsError") is not None or row.get("pluginId") is not None:
                raise CodexMcpScopeError("MCP discovery error or ambiguous plugin server")
            tools = row["tools"]
            if type(tools) is not dict:
                raise CodexMcpScopeError("MCP inventory tools must be an identity map")
            total += len(tools)
            if total > MAX_TOOLS:
                raise CodexMcpScopeError("MCP inventory exceeds tool limit")
            status = row["runtimeStatus"]
            if name not in selected:
                if type(status) is not str or status != "disabled" or tools:
                    raise CodexMcpScopeError("Unselected MCP server must be disabled and empty")
                continue
            if type(status) is not str or status != "connected":
                raise CodexMcpScopeError("Selected MCP server is not connected")
            for key, descriptor in tools.items():
                _identifier(key)
                if type(descriptor) is not dict or "name" not in descriptor:
                    raise CodexMcpScopeError("MCP tool descriptor requires its exact identity")
                if _identifier(descriptor["name"]) != key:
                    raise CodexMcpScopeError("MCP tool descriptor identity mismatch")
            if set(tools) != set(selected[name]):
                raise CodexMcpScopeError("MCP inventory differs from admitted tool identities")
        if not selected.keys() <= seen:
            raise CodexMcpScopeError("Selected MCP server missing from inventory")
        return self.servers
