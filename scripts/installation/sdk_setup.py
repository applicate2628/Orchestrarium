"""Official agent SDK setup proposals and explicit isolated installation.

This catalog is separate from qualified native host integrations in clients.py.
Official packages own their dependencies and runtimes. Orchestrarium does not
rewrite their metadata, remove dependencies, or redistribute their binaries.
"""
from __future__ import annotations

import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

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


def environment_python(directory: Path) -> Path:
    """Return the platform venv interpreter, without PATH/global fallback."""
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def setup_environment(provider: str, directory: str, *, apply: bool = False) -> int:
    """Preview or apply an explicitly selected official package installation.

    An existing venv is an explicit user selection, not an Orchestrarium-owned
    installation. Its unrelated contents are retained; pip owns package upgrades.
    No worker, authentication or model call is started here.
    """
    spec = SDK_PROVIDERS[provider]
    if spec["package"] is None:
        print(setup_guidance(provider, None))
        if apply:
            print("No verified agent SDK package to install; nothing applied.", file=sys.stderr)
            return 2
        return 0
    if not directory or not directory.strip() or any(c in directory for c in "\r\n\0"):
        raise ValueError("Specify --sdk-venv with the selected environment directory.")
    target = Path(directory).expanduser().absolute()
    python = environment_python(target)
    existing = target.exists()
    if existing and (not target.is_dir() or not (target / "pyvenv.cfg").is_file() or not python.is_file()):
        raise ValueError("Selected existing directory is not a complete Python venv; it was not modified. Repair it explicitly or select a new environment directory.")
    print(setup_guidance(provider, str(python)), flush=True)
    print("Base Python for a new environment: " + sys.executable, flush=True)
    print("This uses the current installer Python, not an automatic Python upgrade.", flush=True)
    print("Existing selected venv packages may be upgraded by official pip resolution." if existing
          else "A new isolated Python venv will be created at: " + str(target), flush=True)
    commands = []
    if not existing:
        commands.append([sys.executable, "-I", "-m", "venv", str(target)])
    verify = ("import os,sys; raise SystemExit(0 if sys.prefix != sys.base_prefix and "
              "os.path.samefile(sys.prefix, sys.argv[1]) else 2)")
    commands.extend([
        [str(python), "-I", "-c", verify, str(target)],
        [str(python), "-I", "-m", "pip", "--isolated", "install", "--upgrade", "--no-cache-dir",
         "--disable-pip-version-check", "--index-url", "https://pypi.org/simple", spec["package"]],
        [str(python), "-I", "-m", "pip", "--isolated", "check"],
    ])
    print("Selected operation plan:", flush=True)
    for command in commands:
        print(_command(command, windows=os.name == "nt"), flush=True)
    if not apply:
        print("Preview only. Add --apply to perform this disclosed SDK/runtime installation.", flush=True)
        return 0
    temporary = None
    success = False
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=".sdk-setup-", dir=target.parent))
        environment = {name: value for name, value in os.environ.items()
                       if not name.upper().startswith("PIP_")
                       and name.upper() not in {"PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE", "VIRTUAL_ENV"}}
        # pip honors os.devnull here even with --isolated: no global/user/site config.
        environment.update(TEMP=str(temporary), TMP=str(temporary), TMPDIR=str(temporary),
                           PIP_CONFIG_FILE=os.devnull)
        for command in commands:
            status = subprocess.run(command, env=environment, check=False).returncode
            if status:
                print(f"SDK setup stopped with exit {status}; the selected environment is retained. Retry a complete venv, or explicitly repair/select a new directory after partial creation.", file=sys.stderr)
                return status
        success = True
        print("Official SDK installation and pip check completed. Selected worker Python: " + str(python), flush=True)
        print("No worker, authentication or model call was started; adapter compatibility is a separate check.", flush=True)
        return 0
    except OSError as exc:
        print(f"SDK setup could not execute: {exc}. Selected environment retained.", file=sys.stderr)
        return 1
    finally:
        if temporary is not None:
            if success:
                try:
                    shutil.rmtree(temporary)
                except OSError as exc:
                    print(f"SDK installation succeeded, but temporary cleanup needs attention: {temporary}: {exc}", file=sys.stderr)
            else:
                print("Setup temporary diagnostics retained at: " + str(temporary), file=sys.stderr)
