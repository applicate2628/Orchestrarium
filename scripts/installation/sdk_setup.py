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
        "package": "microsoft-copilot-sdk",
        "source": "https://github.com/microsoft/copilot-sdk/blob/main/python/README.md",
        "runtime": "Published wheels pin the runtime version; the SDK downloads and stages the matching runtime on first managed use unless explicitly configured otherwise. COPILOT_SKIP_CLI_DOWNLOAD=1 disables automatic download; COPILOT_CLI_PATH selects an existing binary. This setup does not run the runtime downloader or start Copilot. Review runtime acquisition before any first use.",
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
        "If the official package is missing, run only after reviewing the package and runtime installation:",
        _command([python, "-m", "pip", "install", spec["package"]], windows=windows),
        _command([python, "-m", "pip", "check"], windows=windows),
        "pip resolves published Python/dependency compatibility, not Orchestrarium adapter compatibility.",
        "Record the installed version and verify the selected adapter before model use; this proposal does not claim a new adapter is implemented.",
        spec["auth"],
    ])
    return "\n".join(lines)


def environment_python(directory: Path) -> Path:
    """Return the platform venv interpreter, without PATH/global fallback."""
    return directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


# A selected venv's CPython does not set sys.prefix to the venv under -S
# before 3.14. Bind the interpreter directory and pyvenv.cfg instead, and
# compute only this venv's local metadata roots using its explicit scheme.
_PACKAGE_PRESENT = 0
_PACKAGE_ABSENT = 10
_PACKAGE_UNKNOWN = 2
_PRESENCE_PROBE = r"""
from email.parser import Parser
from pathlib import Path
import re
import stat
import sys
import sysconfig

def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()

def local_mode(path):
    details = path.lstat()
    if getattr(details, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        return 0
    return details.st_mode

def probe():
    root = Path(sys.argv[1]).resolve(strict=True)
    want = normalize(sys.argv[2])
    paths = sysconfig.get_paths("venv", vars={"base": str(root), "platbase": str(root)})
    scripts = Path(paths["scripts"]).resolve(strict=True)
    if not scripts.is_relative_to(root) or not Path(sys.executable).parent.samefile(scripts):
        return 2
    cfg = root / "pyvenv.cfg"
    if cfg.is_symlink() or not cfg.is_file():
        return 2
    entries = [value.strip().lower()
               for line in cfg.read_text(encoding="utf-8").splitlines()
               for key, separator, value in (line.partition("="),)
               if separator and key.strip().lower() == "include-system-site-packages"]
    if entries != ["false"]:
        return 2
    sites = set()
    matches = []
    for key in ("purelib", "platlib"):
        path = Path(paths[key]).resolve()
        if not path.is_relative_to(root):
            return 2
        if path in sites:
            continue
        sites.add(path)
        try:
            entries = list(path.iterdir())
        except FileNotFoundError:
            continue
        for entry in entries:
            suffix = entry.suffix.lower()
            if suffix not in {".dist-info", ".egg-info"} or (
                    normalize(entry.stem.partition("-")[0]) != want and normalize(entry.stem) != want):
                continue
            mode = local_mode(entry)
            if stat.S_ISDIR(mode):
                leaf = entry / ("METADATA" if suffix == ".dist-info" else "PKG-INFO")
            elif suffix == ".egg-info" and stat.S_ISREG(mode):
                leaf = entry
            else:
                return 2
            if not stat.S_ISREG(local_mode(leaf)):
                return 2
            matches.append(leaf)
    if not matches:
        return 10
    if len(matches) != 1:
        return 2
    # Read only the checked leaf: distribution metadata fallback may probe
    # additional paths and follow a link even under an ordinary directory.
    info = Parser().parsestr(matches[0].read_text(encoding="utf-8"), headersonly=True)
    names, versions = info.get_all("Name") or [], info.get_all("Version") or []
    return 0 if (len(names) == len(versions) == 1 and normalize(names[0]) == want
                 and versions[0].strip()) else 2

try:
    result = probe()
except (OSError, RuntimeError, TypeError, ValueError, KeyError):
    result = 2
raise SystemExit(result)
"""


def setup_environment(provider: str, directory: str, *, apply: bool = False) -> int:
    """Preview or apply an explicitly selected official package installation.

    An existing venv is an explicit user selection, not an Orchestrarium-owned
    installation. Its unrelated contents are retained; never upgrade an existing SDK.
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
    print("The selected venv is reused; an existing SDK is never upgraded." if existing
          else "A new isolated Python venv will be created at: " + str(target), flush=True)
    create = [sys.executable, "-I", "-m", "venv", str(target)]
    probe = [str(python), "-I", "-S", "-B", "-c", _PRESENCE_PROBE, str(target), spec["package"]]
    install = [str(python), "-I", "-m", "pip", "--isolated", "install", "--no-cache-dir",
               "--disable-pip-version-check", "--index-url", "https://pypi.org/simple", spec["package"]]
    check = [str(python), "-I", "-m", "pip", "--isolated", "check"]
    print("Selected operation plan:", flush=True)
    if not existing:
        print(_command(create, windows=os.name == "nt"), flush=True)
    print("Check official package metadata in the selected venv without importing the provider.", flush=True)
    print("Only if missing:", flush=True)
    for command in (install, check):
        print(_command(command, windows=os.name == "nt"), flush=True)
    if not apply:
        print("Preview only. Add --apply to check presence and install only if absent.", flush=True)
        return 0
    temporary = None
    success = False
    environment = {name: value for name, value in os.environ.items()
                   if not name.upper().startswith("PIP_")
                   and name.upper() not in {"PYTHONHOME", "PYTHONPATH", "PYTHONUSERBASE", "VIRTUAL_ENV"}}
    environment["PIP_CONFIG_FILE"] = os.devnull

    def status(command):
        return subprocess.run(command, env=environment, check=False).returncode

    def prepare_temporary():
        target.parent.mkdir(parents=True, exist_ok=True)
        directory = Path(tempfile.mkdtemp(prefix=".sdk-setup-", dir=target.parent))
        environment.update(TEMP=str(directory), TMP=str(directory), TMPDIR=str(directory))
        return directory

    def report_failure(result):
        print(f"SDK setup stopped with exit {result}; the selected environment is retained. "
              "Retry a complete venv, or explicitly repair/select a new directory after partial creation.",
              file=sys.stderr)
        return result

    try:
        if not existing:
            temporary = prepare_temporary()
            if (result := status(create)):
                return report_failure(result)
        presence = status(probe)
        if presence == _PACKAGE_PRESENT:
            success = True
            print("Official package metadata present; no installation or upgrade performed.", flush=True)
            print("No worker, authentication or model call was started; adapter compatibility is a separate check.", flush=True)
            return 0
        if presence != _PACKAGE_ABSENT:
            print("SDK presence could not be established in the selected venv; no package changes were made.",
                  file=sys.stderr)
            return report_failure(presence)
        if temporary is None:
            temporary = prepare_temporary()
        for command in (install, check):
            if (result := status(command)):
                return report_failure(result)
        if status(probe) != _PACKAGE_PRESENT:
            print("Official package metadata could not be verified after pip completed.", file=sys.stderr)
            return report_failure(_PACKAGE_UNKNOWN)
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
