from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "scripts" / "invoke-codex-prompt.py"

EXPECTED_HELP = """usage: invoke-codex-prompt.py --help
       invoke-codex-prompt.py TOPIC --terminal-receipt PATH [OPTIONS] [-- CODEX_FLAGS...]

File-based prompt transport for Codex CLI.

options:
  --help                         show this help message and exit
  --prompt-file PATH             read the prompt from PATH
  -PromptFile PATH               legacy spelling for --prompt-file
  --terminal-receipt PATH        write the required terminal receipt to PATH
  --ledger PATH                  append the optional terminal ledger event
  -Ledger PATH                   legacy spelling for --ledger
  --ledger-role ROLE             record the ledger execution role
  -LedgerRole ROLE               legacy spelling for --ledger-role
  --ledger-lane LANE             record the ledger lane
  -LedgerLane LANE               legacy spelling for --ledger-lane
  --ledger-artifact PATH         record the ledger artifact
  -LedgerArtifact PATH           legacy spelling for --ledger-artifact
  --ledger-closes RUN_ID         declare one run closed; repeatable
  -LedgerCloses RUN_ID           legacy spelling for --ledger-closes
  --timeout-secs SECONDS         set a positive finite timeout
  -TimeoutSecs SECONDS           legacy spelling for --timeout-secs
  --result-max-bytes BYTES       set a positive result limit
  -ResultMaxBytes BYTES          legacy spelling for --result-max-bytes
  --capture-max-bytes BYTES      set a positive capture limit
  -CaptureMaxBytes BYTES         legacy spelling for --capture-max-bytes
  --                             pass remaining arguments to Codex CLI
"""


def _environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return environment


def _run(wrapper: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-B", str(wrapper), *arguments],
        cwd=wrapper.parent,
        env=_environment(),
        text=True,
        capture_output=True,
        check=False,
    )


def test_exact_help_is_local_and_requires_no_provider_dependencies(tmp_path: Path) -> None:
    wrapper = tmp_path / WRAPPER.name
    shutil.copyfile(WRAPPER, wrapper)

    completed = _run(wrapper, "--help")

    assert completed.returncode == 0
    assert completed.stdout == EXPECTED_HELP
    assert completed.stderr == ""


def test_extra_help_arguments_do_not_bypass_provider_launch(tmp_path: Path) -> None:
    wrapper = tmp_path / WRAPPER.name
    shutil.copyfile(WRAPPER, wrapper)
    (tmp_path / "provider_prompt.py").write_text(
        """import json
import sys

def launch(provider, argv):
    sys.stdout.write(json.dumps({"provider": provider, "argv": argv}, separators=(",", ":")))
    return 73
""",
        encoding="utf-8",
    )

    completed = _run(wrapper, "--help", "extra")

    assert completed.returncode == 73
    assert json.loads(completed.stdout) == {
        "provider": "codex",
        "argv": ["--help", "extra"],
    }
    assert completed.stderr == ""


def test_normal_launch_without_terminal_receipt_remains_fail_closed() -> None:
    completed = _run(
        WRAPPER,
        "review-pre-pr",
        "--task-class",
        "review",
        "--role",
        "architecture-reviewer",
    )

    assert completed.returncode == 1
    assert completed.stdout == ""
    assert completed.stderr == "FAIL: E_EXTERNAL_LAUNCH_FLAGS_UNSAFE\n"
