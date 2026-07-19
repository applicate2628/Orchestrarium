"""Falsifier for the prompt-wrapper completion oracle's failure path.

Live incident (2026-07-16): two codex dispatches hit the provider usage limit,
producing an EMPTY .out and a nonzero exit. Under `set -euo pipefail` the
oracle's FINAL_LINE extraction (`grep | tail | tr`) aborted the wrapper —
grep exits 1 on an empty file and pipefail propagates it — BEFORE the blocked
terminal event was appended and before the three output paths were printed.
Result: permanently unsettled launch events, the exact defect class the
completion oracle exists to prevent.

Contract under test: a provider run that fails or emits nothing must still
append a linked terminal event, print every artifact path, and propagate the
provider's exit code. The Codex wrapper additionally passes
`--output-last-message`, prints the fourth `.lastmsg` path, and uses that
dedicated final message instead of an empty stdout trace when available.
"""

from __future__ import annotations

import json
import os
import shlex
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


def _powershell() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def _to_posix(p: Path) -> str:
    s = str(p).replace("\\", "/")
    if len(s) > 1 and s[1] == ":":
        s = "/" + s[0].lower() + s[2:]
    return s


def _make_fake_provider(
    tmp_path: Path,
    which: str,
    exit_code: int,
    *,
    write_lastmsg: bool = True,
) -> Path:
    """A provider stand-in with an empty stdout trace.

    The Codex shape requires `--output-last-message` and writes a PASS verdict
    there, so the test distinguishes reliable final-message capture from the
    trace-only failure mode. The Claude shape preserves its existing behavior.
    """
    fake = tmp_path / "fake-provider.sh"
    if which == "codex":
        lastmsg_write = "printf 'GATE: PASS\\n' > \"$lastmsg\"" if write_lastmsg else ":"
        body = f"""#!/usr/bin/env bash
lastmsg=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --output-last-message) lastmsg="$2"; shift 2 ;;
    *) shift ;;
  esac
done
cat >/dev/null
[[ -n "$lastmsg" ]] || exit 97
{lastmsg_write}
exit {exit_code}
"""
    else:
        body = f"#!/usr/bin/env bash\ncat >/dev/null\nexit {exit_code}\n"
    fake.write_text(body, encoding="utf-8", newline="\n")
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
def test_empty_trace_still_settles_terminal(tmp_path, which, provider_exit):
    """An empty trace still settles the launch and propagates the provider
    exit; Codex uses its dedicated final-message artifact when available."""
    wrapper = WRAPPERS[which]
    fake = _make_fake_provider(tmp_path, which, provider_exit)
    item = _make_work_item(tmp_path)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("dummy prompt\n", encoding="utf-8")
    outdir = tmp_path / "prompt-outputs"

    env = os.environ.copy()
    env[BIN_ENV[which]] = _to_posix(fake)
    env[PROMPTS_DIR_ENV[which]] = _to_posix(outdir)
    if which == "claude":
        env["ANTHROPIC_API_KEY"] = "oracle-fixture-commercial-key"

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
    output_lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    if which == "codex":
        assert output_lines[-2] == "# actively await this dispatch (do NOT passively wait for a notification):"
        watcher = _to_posix(wrapper.parent / "await-codex-dispatch.sh")
        assert output_lines[-1].startswith(f"bash {shlex.quote(watcher)}")
        paths = output_lines[:4]
    else:
        paths = output_lines
    expected_path_count = 4 if which == "codex" else 3
    assert len(paths) == expected_path_count, (
        f"wrapper must print {expected_path_count} artifact paths even on a failed run; "
        f"stdout was:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    if which == "codex":
        assert paths[3].endswith(".lastmsg"), paths

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
    codex_success = which == "codex" and provider_exit == 0
    assert term["gate"] == ("PASS" if codex_success else "none")
    assert term.get("status") == ("completed" if codex_success else "blocked")
    expected_note = (
        "nonzero exit"
        if provider_exit != 0
        else "final-line GATE: PASS"
        if codex_success
        else "empty .out"
    )
    assert expected_note in term.get("notes", ""), term
    expected_evidence_ref = paths[3] if which == "codex" else paths[1]
    assert term.get("evidence") == [{"kind": "review", "ref": expected_evidence_ref}]


def test_codex_empty_lastmsg_and_out_exit_zero_records_blocked_terminal(tmp_path: Path) -> None:
    """An exit-zero Codex run with no final message or stdout still settles as blocked."""
    wrapper = WRAPPERS["codex"]
    fake = _make_fake_provider(tmp_path, "codex", 0, write_lastmsg=False)
    item = _make_work_item(tmp_path)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("dummy prompt\n", encoding="utf-8")
    outdir = tmp_path / "prompt-outputs"

    env = os.environ.copy()
    env[BIN_ENV["codex"]] = _to_posix(fake)
    env[PROMPTS_DIR_ENV["codex"]] = _to_posix(outdir)
    result = subprocess.run(
        [_bash(), _to_posix(wrapper), "oracle-empty-codex",
         "--prompt-file", _to_posix(prompt),
         "--ledger", _to_posix(item),
         "--ledger-role", "architecture-reviewer",
         "--ledger-lane", "fixture-lane",
         "--ledger-artifact", "design.md"],
        capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=120,
    )

    assert result.returncode == 0, result.stderr
    output_lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    paths = output_lines[:4]
    assert paths[3].endswith(".lastmsg")
    events = [json.loads(ln) for ln in
              (item / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    terminal = next(e for e in events if e.get("eventKind") == "terminal")
    assert terminal["gate"] == "none"
    assert terminal["status"] == "blocked"
    assert "empty .out" in terminal["notes"]
    assert terminal["evidence"] == [{"kind": "review", "ref": paths[1]}]


def test_powershell_codex_oracle_prefers_lastmsg(tmp_path: Path) -> None:
    powershell = _powershell()
    if not powershell:
        pytest.skip("PowerShell is unavailable")

    fake = tmp_path / "fake-codex.ps1"
    fake.write_text(
        "param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)\n"
        "$lastmsg = ''\n"
        "for ($i = 0; $i -lt $Arguments.Count; $i++) {\n"
        "  if ($Arguments[$i] -eq '--output-last-message') { $lastmsg = $Arguments[$i + 1] }\n"
        "}\n"
        "if (-not $lastmsg) { exit 97 }\n"
        "[System.IO.File]::WriteAllText($lastmsg, \"GATE: PASS`n\", [System.Text.UTF8Encoding]::new($false))\n"
        "exit 0\n",
        encoding="utf-8",
        newline="\n",
    )
    item = _make_work_item(tmp_path)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("dummy prompt\n", encoding="utf-8")
    outdir = tmp_path / "prompt-outputs"
    env = os.environ.copy()
    env["CODEX_BIN"] = str(fake)
    env["CODEX_PROMPTS_DIR"] = str(outdir)

    result = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
         "-File", str(ROOT / "src.claude" / "agents" / "scripts" / "invoke-codex-prompt.ps1"),
         "oracle-ps1", "-PromptFile", str(prompt), "-Ledger", str(item),
         "-LedgerRole", "architecture-reviewer", "-LedgerLane", "fixture-lane",
         "-LedgerArtifact", "design.md"],
        capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=120,
    )

    assert result.returncode == 0, result.stderr
    paths = [line for line in result.stdout.splitlines() if line.strip()][:4]
    events = [json.loads(line) for line in
              (item / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    terminal = next(event for event in events if event.get("eventKind") == "terminal")
    assert terminal["gate"] == "PASS"
    assert terminal["status"] == "completed"
    assert terminal["evidence"] == [{"kind": "review", "ref": paths[3]}]
