"""Source-based policy vectors, not native runtime qualification.

Reference: MoonshotAI/kimi-code 50ec3c3940a3f265cf1b99123d6d2ebf9c23aaa0
packages/agent-core-v2/src/agent/toolPolicy/evaluate.ts:8-56.
Global enabled (when nonempty) intersects profile tools; deny wins.
The native toolPolicyService.ts:36-46 also vetoes before execution.
"""
from __future__ import annotations

import fnmatch
import tomllib

import pytest

from test_kimi_transport import _load_owner


def _source_policy_vector(profile, global_policy, name):
    # Literal builtins / MCP glob subset used by these pinned source vectors.
    def matches(pattern):
        return (fnmatch.fnmatchcase(name, pattern)
                if name.startswith("mcp__") and pattern.startswith("mcp__")
                else name == pattern)

    def active(allow, deny):
        return ((allow is None or any(matches(p) for p in allow))
                and not any(matches(p) for p in deny))

    return (active(profile.get("tools"), profile.get("disallowedTools", []))
            and active(global_policy.get("enabled") or None,
                       global_policy.get("disabled", [])))


@pytest.mark.parametrize("tools,children,profile,name,expected", [
    ((), (), {}, "Read", False),
    ((), (), {}, "Agent", False),
    ((), (), {}, "AgentSwarm", False),
    (("Read",), (), {}, "Read", True),
    (("Read",), (), {"tools": ["Read", "Bash"]}, "Bash", False),
    (("Read",), (), {"tools": []}, "Read", False),
    (("Read",), (), {"disallowedTools": ["Read"]}, "Read", False),
    (("Read",), (), {}, "Agent", False),
    (("mcp__local__*",), (), {}, "mcp__local__search", True),
    (("mcp__local__*",), (), {}, "mcp__other__search", False),
    (("Agent",), ("*",), {}, "Agent", True),
    (("Agent",), ("*",), {}, "AgentSwarm", False),
    (("Agent",), ("*",), {"tools": []}, "Agent", False),
])
def test_generated_private_config_is_upper_bound(tmp_path, tools, children, profile, name, expected):
    owner = _load_owner()
    user = tmp_path / "user"
    user.mkdir()
    selected = owner.KimiCapabilitySelectionV1(tools=tools, subagents=children)
    owner._validate_kimi_child_selection(tools, children)
    config = tomllib.loads(owner._kimi_private_config(user / "config.toml", selected).decode())
    assert config["tools"]["enabled"]  # Never accidentally native unrestricted [].
    assert _source_policy_vector(profile, config["tools"], name) is expected


def test_native_empty_global_allowlist_is_not_deny_all():
    assert _source_policy_vector({}, {"enabled": [], "disabled": []}, "Read")
