"""Information-only official agent SDK setup; never installs or starts a provider.

This catalog is separate from qualified native host integrations in clients.py.
Official packages own their dependencies and runtimes. Orchestrarium does not
rewrite their metadata, remove dependencies, or redistribute their binaries.
"""
from __future__ import annotations

import os
import shlex

# Ordered for the selected Antigravity-first agent SDK direction, not host routing.
SDK_PROVIDERS = {
    "antigravity": {
        "label": "Google Antigravity",
        "package": "google-antigravity",
        "source": "https://antigravity.google/docs/sdk/overview",
        "runtime": "The official platform wheel includes a compiled agent runtime.",
        "auth": "Programmatic workers use supported Google API or cloud credentials; a native Antigravity Lead is a separate session.",
    },
    "codex": {
        "label": "OpenAI Codex",
        "package": "openai-codex",
        "source": "https://github.com/openai/codex/tree/main/sdk/python",
        "runtime": "The official SDK declares openai-codex-cli-bin; normal pip installation also installs its CLI dependency.",
        "auth": "Use the admitted Codex account/API binding. Installing a package does not authorize a model call.",
    },
    "claude": {
        "label": "Claude Agent SDK",
        "package": "claude-agent-sdk",
        "source": "https://code.claude.com/docs/en/agent-sdk/quickstart",
        "runtime": "Official platform wheels normally include a Claude Code binary; source installs can require a separate native installation.",
        "auth": "Programmatic workers use authorized Anthropic API or supported cloud-provider credentials, not a wrapped Claude subscription session.",
    },
    "copilot": {
        "label": "GitHub Copilot",
        "package": "github-copilot-sdk",
        "source": "https://github.com/github/copilot-sdk/blob/main/python/README.md",
        "runtime": "The official Python SDK can download its pinned runtime on first managed use; an explicit external CLI is also supported. Review this before any first use.",
        "auth": "Use the provider-supported authentication and the separately authorized quota. VS Code Copilot as a native Lead is a different integration.",
    },
    "kimi": {
        "label": "Kimi Agent SDK",
        "package": "kimi-agent-sdk",
        "source": "https://github.com/MoonshotAI/kimi-agent-sdk",
        "runtime": "The current official Python SDK depends on the legacy kimi-cli package and its runtime; this does not establish compatibility with the newer Kimi Code CLI.",
        "auth": "Use the officially supported Kimi authentication and separately authorized quota; availability does not wire this SDK into the existing Orchestrarium adapter.",
    },
    "grok": {
        "label": "Grok Build",
        "package": None,
        "source": "https://docs.x.ai/build/cli/headless-scripting",
    },
}


def _command(arguments: list[str], *, windows: bool) -> str:
    if windows:
        return "& " + " ".join("'" + value.replace("'", "''") + "'" for value in arguments)
    return shlex.join(arguments)


def setup_guidance(provider: str, python: str | None, *, windows: bool | None = None) -> str:
    """Render commands only; no environment inspection, download or execution."""
    spec = SDK_PROVIDERS[provider]
    lines = [
        f"Official agent SDK setup: {spec['label']}",
        "Information only: nothing installed, configured, authenticated or launched.",
        "Native Lead integration and programmatic worker setup are separate.",
    ]
    if spec["package"] is None:
        lines.append("No official agent SDK installation recipe has been verified here for this provider.")
        lines.append("No ordinary API client or CLI is substituted for an agent SDK.")
        lines.append("The vendor documents Grok Build through Agent Client Protocol (ACP), a separate CLI integration, not a verified Grok Python agent SDK package.")
        lines.append("Official integration documentation: " + spec["source"])
        return "\n".join(lines)
    if not python or not python.strip() or any(character in python for character in "\r\n\0"):
        raise ValueError("Specify --sdk-python with the Python executable of the selected worker environment.")
    windows = os.name == "nt" if windows is None else windows
    lines.extend([
        "Select a dedicated environment for the worker; do not assume the installer or global Python is that environment.",
        "These commands do not select/register that environment in a worker launcher.",
        "Launch the repository SDK entrypoint with that same selected Python; its process owner uses the same interpreter for workers. Do not inject another environment through PYTHONPATH.",
        "The base installer Python is separate from the selected provider worker environment.",
        "Official package contents: " + spec["runtime"],
        "Official instructions: " + spec["source"],
        "Run only after reviewing the package and runtime installation:",
        _command([python, "-m", "pip", "install", "--upgrade", spec["package"]], windows=windows),
        _command([python, "-m", "pip", "check"], windows=windows),
        "pip resolves published Python/dependency compatibility, not Orchestrarium adapter compatibility.",
        "Record the installed version and verify the selected adapter before model use; this proposal does not claim a new adapter is implemented.",
        spec["auth"],
    ])
    return "\n".join(lines)
