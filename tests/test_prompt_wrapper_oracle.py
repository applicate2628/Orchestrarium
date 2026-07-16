"""Falsifier for the prompt-wrapper completion oracle's failure path.

Live incident (2026-07-16): two codex dispatches hit the provider usage limit,
producing an EMPTY .out and a nonzero exit. Under `set -euo pipefail` the
oracle's FINAL_LINE extraction (`grep | tail | tr`) aborted the wrapper —
grep exits 1 on an empty file and pipefail propagates it — BEFORE the blocked
terminal event was appended and before the three output paths were printed.
Result: permanently unsettled launch events, the exact defect class the
completion oracle exists to prevent.

Contract under test (both bash wrappers): a provider run that fails or emits
nothing must still (1) append a terminal event with status=blocked / gate=none
linked to the launch via launchRunId, (2) print the three artifact paths, and
(3) propagate the provider's exit code.
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WRAPPERS = {
    "codex": ROOT / "src.claude" / "agents" / "scripts" / "invoke-codex-prompt.sh",
    "claude": ROOT / "src.claude" / "agents" / "scripts" / "invoke-claude-prompt.sh",
}
BIN_ENV = {"codex": "CODEX_BIN", "claude": "CLAUDE_BIN"}
PROMPTS_DIR_ENV = {"codex": "CODEX_PROMPTS_DIR", "claude": "CLAUDE_PROMPTS_DIR"}


def _bash() -> str:
    found = shutil.which("bash")
    if found and "System32" not in found:
        return found
    for cand in (r"C:\Program Files\Git\bin\bash.exe",
                 r"C:\Program Files\Git\usr\bin\bash.exe"):
        if Path(cand).exists():
            return cand
    return found or "bash"


def _to_posix(p: Path) -> str:
    s = str(p).replace("\\", "/")
    if len(s) > 1 and s[1] == ":":
        s = "/" + s[0].lower() + s[2:]
    return s


def _make_fake_provider(tmp_path: Path, exit_code: int) -> Path:
    """A provider stand-in that consumes stdin, writes NOTHING to stdout
    (empty .out — the incident shape) and exits with the given code."""
    fake = tmp_path / "fake-provider.sh"
    fake.write_text(f"#!/usr/bin/env bash\ncat >/dev/null\nexit {exit_code}\n",
                    encoding="utf-8", newline="\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return fake


def _make_work_item(tmp_path: Path) -> Path:
    item = tmp_path / "work-items" / "active" / "2026-01-01-oracle-fixture"
    item.mkdir(parents=True)
    (item / "design.md").write_text("fixture artifact\n", encoding="utf-8")
    (item / "status.md").write_text(
        "# Status\n\n- state: open\n\n## Current state\n\nFixture item for the"
        " oracle falsifier.\n\n## Active agents\n\n- none\n\n"
        "## Completed agents\n\n- none\n\n## Next action\n\n- none\n",
        encoding="utf-8")
    return item


@pytest.mark.parametrize("which", ["codex", "claude"])
@pytest.mark.parametrize("provider_exit", [1, 0])
def test_empty_out_still_records_blocked_terminal(tmp_path, which, provider_exit):
    """Empty .out (with either nonzero OR zero provider exit) must yield a
    blocked terminal, printed paths, and the provider's exit code — not a
    pipefail death between launch and terminal."""
    wrapper = WRAPPERS[which]
    fake = _make_fake_provider(tmp_path, provider_exit)
    item = _make_work_item(tmp_path)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("dummy prompt\n", encoding="utf-8")
    outdir = tmp_path / "prompt-outputs"

    env = os.environ.copy()
    env[BIN_ENV[which]] = _to_posix(fake)
    env[PROMPTS_DIR_ENV[which]] = _to_posix(outdir)

    result = subprocess.run(
        [_bash(), _to_posix(wrapper), "oracle-fixture",
         "--prompt-file", _to_posix(prompt),
         "--ledger", _to_posix(item),
         "--ledger-role", "architecture-reviewer",
         "--ledger-lane", "fixture-lane",
         "--ledger-artifact", "design.md"],
        capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=120,
    )

    assert result.returncode == provider_exit, (
        f"wrapper must propagate provider exit {provider_exit}; "
        f"got {result.returncode}; stderr:\n{result.stderr}"
    )
    paths = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(paths) == 3, (
        "wrapper must print the three artifact paths even on a failed run; "
        f"stdout was:\n{result.stdout}\nstderr:\n{result.stderr}"
    )

    ledger = item / "agent-runs.jsonl"
    events = [json.loads(ln) for ln in
              ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
    launches = [e for e in events if e.get("eventKind") == "launch"]
    terminals = [e for e in events if e.get("eventKind") == "terminal"]
    assert len(launches) == 1
    assert len(terminals) == 1, (
        "failed/empty run left an UNSETTLED launch — oracle died before the "
        f"terminal append. Events: {events}"
    )
    term = terminals[0]
    assert term["launchRunId"] == launches[0]["runId"]
    assert term["gate"] == "none"
    assert term.get("status") == "blocked"
    expected_note = "nonzero exit" if provider_exit != 0 else "empty .out"
    assert expected_note in term.get("notes", ""), term
