"""Qualified host integrations, not a registry of SDK model vendors.

One lifecycle owner serves all entries. Adding a model-provider adapter does not
qualify its host installation, configuration editing or hook transport.
"""
CLIENTS = {
    "codex": {
        "id": "codex", "label": "Codex", "primary": True,
        "canonical_runtime": ".agents/skills/lead", "transport_runtime": ".agents/skills/lead",
        "source_root": "src.codex", "references_root": "references-codex",
        "roots": (".codex", ".agents"), "provider_root": ".codex",
        "payload_roots": (".agents/skills", ".agents/contracts", ".codex/agents",
                          ".codex/contracts", ".codex/orchestrarium-runtime"),
        "documents": {"global": {".codex/AGENTS.md": "codex"},
                      "project": {"AGENTS.md": "codex"}},
        "mode_file": {"global": ".codex/.agents-mode.yaml", "project": ".agents/.agents-mode.yaml"},
        "registration": ".codex/hooks.json", "hook_format": "shell",
        "native_config": ".codex/config.toml", "default_agent_key": None,
        "feature_defaults": {"multi_agent_v2": True},
        "legacy_shared_roots": ((".codex/skills", ".agents/skills"),),
    },
    "claude": {
        "id": "claude", "label": "Claude Code", "primary": False,
        "canonical_runtime": ".claude/skills/lead", "transport_runtime": ".claude/agents",
        "source_root": "adapters/claude", "references_root": "adapters/claude/references",
        "roots": (".claude",), "provider_root": ".claude",
        "payload_roots": (".claude/skills", ".claude/agents", ".claude/commands", ".claude/contracts"),
        "documents": {"global": {".claude/CLAUDE.md": "claude", ".claude/AGENTS.md": "shared"},
                      "project": {".claude/CLAUDE.md": "claude", ".claude/AGENTS.md": "shared"}},
        "mode_file": {"global": ".claude/.agents-mode.yaml", "project": ".claude/.agents-mode.yaml"},
        "registration": ".claude/settings.json", "hook_format": "exec",
        "native_config": None, "default_agent_key": "agent", "feature_defaults": {},
        "legacy_shared_roots": ((".claude/skills", ".agents/skills"),),
    },
}


def get_client(name: str) -> dict:
    try:
        return CLIENTS[name]
    except (KeyError, TypeError) as exc:
        raise ValueError("No qualified host-install adapter: " + str(name)) from exc
