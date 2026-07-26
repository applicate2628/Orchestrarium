"""Falsifier for the A12 model/effort guard added to all four prompt wrappers.

Bug (work-items/bugs/2026-07-25-codex-wrapper-partial-flag-block-silently-drops-model-pin.md):
an explicit `--` block (Bash) / non-empty remaining-argument block (PowerShell)
REPLACES the wrapper's default flags wholesale, including `--model`. A caller who
passes a partial override (only changing effort or toggling a feature) silently
drops the model pin and the run falls back to whatever model the ambient provider
config selects -- exactly what A12 ("every provider-backed run must carry an
explicit model AND effort, never an ambient one") forbids. Reproduced live: a
dispatch with `-- -c model_reasoning_effort=xhigh --disable fast_mode` resolved
`gpt-5.6-sol` only because the operator's `~/.codex/config.toml` happened to match
the wrapper default -- on a differently configured machine it would have silently
run a different model.

The fix makes each wrapper validate its FINAL resolved flag array (whichever
source produced it -- the shipped default, or a caller override) for an explicit
model AND an explicit effort tier, refusing to launch otherwise, and records both
values in the ledger. This file proves:
  1. a partial override (effort/feature-toggle only, no --model) fails closed;
  2. a full per-profile override (both --model and effort) still launches;
  3. the shipped default (no override at all) still launches;
  4. the "no default pin at all" historical shape (60/97 audited .scratch
     snapshots carried this shape, distinct from the 37 partial-override
     snapshots) ALSO fails closed -- the guard checks the final resolved array
     regardless of how it got that way, not just "did the override look partial";
  5. the ledger records the resolved --model alongside --effort in both the
     launch and terminal events, so provenance is backed by data.

PowerShell CLI note (see the adjacent-finding bug this session also filed): a
bare `-c` (Codex's own reasoning-effort flag) or `-p` (Claude's own print flag),
passed as trailing remaining-argument tokens via `-File`, collides with
PowerShell's own unique-prefix parameter-name abbreviation ("-c" uniquely
abbreviates "-CodexFlags", "-p" uniquely abbreviates "-PromptFile") and gets
silently swallowed as an attempt to (re)bind THAT parameter instead of landing in
the flags array -- a pre-existing defect independent of this fix. The PowerShell
"full profile" tests below therefore use a genuine PowerShell array literal via
`-Command` (`-CodexFlags @('--model', ...)`), which is unambiguous and exercises
the real end-to-end script rather than working around the collision.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "src.claude" / "agents" / "scripts"

BASH_WRAPPERS = {
    "codex": SCRIPTS / "invoke-codex-prompt.sh",
    "claude": SCRIPTS / "invoke-claude-prompt.sh",
}
PS_WRAPPERS = {
    "codex": SCRIPTS / "invoke-codex-prompt.ps1",
    "claude": SCRIPTS / "invoke-claude-prompt.ps1",
}
BIN_ENV = {"codex": "CODEX_BIN", "claude": "CLAUDE_BIN"}
PROMPTS_DIR_ENV = {"codex": "CODEX_PROMPTS_DIR", "claude": "CLAUDE_PROMPTS_DIR"}
LEDGER_HELPER = ROOT / "scripts" / "agent-run-ledger.py"


def test_effort_tier_enum_matches_across_all_five_hardcoded_owners() -> None:
    """Five independent files each hardcode the same 5-tier reasoning-effort
    enum (low/medium/high/xhigh/max), with no single shared source: the two
    Bash wrappers, the two PowerShell wrappers, and
    scripts/agent-run-ledger.py's own `--effort` argparse `choices`. A change
    to one of these (e.g. adding a new tier) that is not mirrored in the other
    four is a silent C1 (single-owner-invariant) violation: the guard could
    accept a tier the ledger helper then refuses to record (or vice versa),
    reproducing the exact "the stated invariant and the mechanism differ"
    defect class this whole fix exists to close. These five owners cross a
    real process/language boundary (Bash, PowerShell, Python) where unifying
    them behind one physical source is impractical, so this drift-gated
    equality test -- pinning each owner's own literal syntax for the same
    ordered tier list -- is the sanctioned substitute for a single owner."""
    codex_sh_text = BASH_WRAPPERS["codex"].read_text(encoding="utf-8")
    claude_sh_text = BASH_WRAPPERS["claude"].read_text(encoding="utf-8")
    codex_ps1_text = PS_WRAPPERS["codex"].read_text(encoding="utf-8")
    claude_ps1_text = PS_WRAPPERS["claude"].read_text(encoding="utf-8")
    ledger_text = LEDGER_HELPER.read_text(encoding="utf-8")

    assert "(low|medium|high|xhigh|max)" in codex_sh_text, (
        f"canonical tier list missing/drifted in {BASH_WRAPPERS['codex']}"
    )
    assert "low|medium|high|xhigh|max)" in claude_sh_text, (
        f"canonical tier list missing/drifted in {BASH_WRAPPERS['claude']}"
    )
    assert "(low|medium|high|xhigh|max)" in codex_ps1_text, (
        f"canonical tier list missing/drifted in {PS_WRAPPERS['codex']}"
    )
    assert "'low', 'medium', 'high', 'xhigh', 'max'" in claude_ps1_text, (
        f"canonical tier list missing/drifted in {PS_WRAPPERS['claude']}"
    )
    assert '"low", "medium", "high", "xhigh", "max"' in ledger_text, (
        f"canonical tier list missing/drifted in {LEDGER_HELPER}"
    )


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
    return shutil.which("powershell") or shutil.which("pwsh")


def _to_posix(p: Path) -> str:
    s = str(p).replace("\\", "/")
    if len(s) > 1 and s[1] == ":":
        s = "/" + s[0].lower() + s[2:]
    return s


def _make_work_item(tmp_path: Path, name: str = "2026-01-01-a12-guard-fixture") -> Path:
    item = tmp_path / "work-items" / "active" / name
    item.mkdir(parents=True)
    (item / "design.md").write_text("fixture artifact\n", encoding="utf-8")
    (item / "status.md").write_text(
        "# Status\n\n- state: open\n\n## Current state\n\nFixture item for the"
        " A12 guard falsifier.\n\n## Active agents\n\n- none\n\n"
        "## Completed agents\n\n- none\n\n## Next action\n\n- none\n",
        encoding="utf-8")
    return item


def _read_ledger(item: Path) -> list[dict]:
    ledger = item / "agent-runs.jsonl"
    return [json.loads(ln) for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]


# ---------------------------------------------------------------------------
# Bash wrappers
# ---------------------------------------------------------------------------

def _make_fake_provider_sh(tmp_path: Path, which: str) -> Path:
    fake = tmp_path / f"fake-{which}.sh"
    if which == "codex":
        body = (
            "#!/usr/bin/env bash\n"
            "lastmsg=\"\"\n"
            "while [[ $# -gt 0 ]]; do\n"
            "  case \"$1\" in\n"
            "    --output-last-message) lastmsg=\"$2\"; shift 2 ;;\n"
            "    *) shift ;;\n"
            "  esac\n"
            "done\n"
            "cat >/dev/null\n"
            "[[ -n \"$lastmsg\" ]] && printf 'GATE: PASS\\n' > \"$lastmsg\"\n"
            "exit 0\n"
        )
    else:
        body = "#!/usr/bin/env bash\ncat >/dev/null\nprintf 'GATE: PASS\\n'\nexit 0\n"
    fake.write_text(body, encoding="utf-8", newline="\n")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return fake


def _run_sh(tmp_path: Path, which: str, args: list[str], *, extra_env: dict | None = None) -> subprocess.CompletedProcess:
    wrapper = BASH_WRAPPERS[which]
    fake = _make_fake_provider_sh(tmp_path, which)
    outdir = tmp_path / "prompt-outputs"
    prompt = tmp_path / "prompt.md"
    prompt.write_text("dummy prompt\n", encoding="utf-8")

    env = os.environ.copy()
    env[BIN_ENV[which]] = _to_posix(fake)
    env[PROMPTS_DIR_ENV[which]] = _to_posix(outdir)
    if which == "claude":
        env["ANTHROPIC_API_KEY"] = "a12-guard-fixture-key"
    if extra_env:
        env.update(extra_env)

    return subprocess.run(
        [_bash(), _to_posix(wrapper), "a12-guard-fixture",
         "--prompt-file", _to_posix(prompt), *args],
        capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=120,
    )


@pytest.mark.parametrize("which", ["codex", "claude"])
def test_sh_partial_override_missing_model_fails_closed(tmp_path: Path, which: str) -> None:
    """Reproduces the live incident: a `--` block that changes only effort (or a
    feature toggle) and never mentions --model must be refused, not silently
    launched against an ambient model."""
    partial_args = (
        ["--", "-c", "model_reasoning_effort=xhigh", "--disable", "fast_mode"]
        if which == "codex"
        else ["--", "--effort", "xhigh"]
    )
    result = _run_sh(tmp_path, which, partial_args)

    assert result.returncode != 0, (
        f"partial override must fail closed; stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "A12" in result.stderr
    assert "--model" in result.stderr
    assert result.stdout == "", "a refused launch must not print artifact paths"


@pytest.mark.parametrize("which", ["codex", "claude"])
def test_sh_full_profile_override_still_launches(tmp_path: Path, which: str) -> None:
    full_args = (
        ["--", "--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=xhigh"]
        if which == "codex"
        else ["--", "-p", "--output-format", "text", "--model", "opus", "--effort", "xhigh"]
    )
    result = _run_sh(tmp_path, which, full_args)

    assert result.returncode == 0, (
        f"full per-profile override must still launch; stderr={result.stderr!r}"
    )
    assert result.stdout.strip() != ""


@pytest.mark.parametrize("which", ["codex", "claude"])
def test_sh_default_no_override_still_launches(tmp_path: Path, which: str) -> None:
    result = _run_sh(tmp_path, which, [])

    assert result.returncode == 0, f"shipped default must still launch; stderr={result.stderr!r}"


@pytest.mark.parametrize("which", ["codex", "claude"])
def test_sh_empty_override_no_default_pin_shape_fails_closed(tmp_path: Path, which: str) -> None:
    """The second historical shape the audit found (60 of 97 .scratch snapshots):
    a resolved flag array with NO model/effort pin at all, regardless of how it
    got that way. A literal `--` followed by nothing reproduces that shape on the
    CURRENT wrapper (Bash's `--` always wholesale-replaces the default, even with
    zero subsequent tokens), proving the guard checks the final array rather than
    trusting that a default was ever assigned."""
    result = _run_sh(tmp_path, which, ["--"])

    assert result.returncode != 0, (
        f"an empty resolved flag set must fail closed exactly like a partial one; "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "A12" in result.stderr


@pytest.mark.parametrize("which", ["codex", "claude"])
def test_sh_ledger_records_resolved_model_alongside_effort(tmp_path: Path, which: str) -> None:
    item = _make_work_item(tmp_path)
    full_args = (
        ["--ledger", _to_posix(item), "--ledger-role", "architecture-reviewer",
         "--ledger-lane", "a12-fixture", "--ledger-artifact", "design.md",
         "--", "--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=xhigh"]
        if which == "codex"
        else ["--ledger", _to_posix(item), "--ledger-role", "architecture-reviewer",
              "--ledger-lane", "a12-fixture", "--ledger-artifact", "design.md",
              "--", "-p", "--output-format", "text", "--model", "sonnet", "--effort", "high"]
    )
    result = _run_sh(tmp_path, which, full_args)
    assert result.returncode == 0, result.stderr

    events = _read_ledger(item)
    launches = [e for e in events if e.get("eventKind") == "launch"]
    terminals = [e for e in events if e.get("eventKind") == "terminal"]
    assert len(launches) == 1
    assert len(terminals) == 1

    expected_model = "gpt-5.6-sol" if which == "codex" else "sonnet"
    expected_effort = "xhigh" if which == "codex" else "high"
    for event in (launches[0], terminals[0]):
        assert event.get("model") == expected_model, event
        assert event.get("effort") == expected_effort, event


# ---------------------------------------------------------------------------
# PowerShell wrappers
# ---------------------------------------------------------------------------

INTERPRETER = _powershell()
pytestmark_ps = pytest.mark.skipif(INTERPRETER is None, reason="no PowerShell host (pwsh/powershell) on PATH")


def _make_fake_provider_ps1(tmp_path: Path, which: str) -> Path:
    fake = tmp_path / f"fake-{which}.ps1"
    if which == "codex":
        body = (
            "param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)\n"
            "$lastmsg = ''\n"
            "for ($i = 0; $i -lt $Arguments.Count; $i++) {\n"
            "  if ($Arguments[$i] -eq '--output-last-message') { $lastmsg = $Arguments[$i + 1] }\n"
            "}\n"
            "$input | Out-Null\n"
            "if ($lastmsg) { [System.IO.File]::WriteAllText($lastmsg, \"GATE: PASS`n\", [System.Text.UTF8Encoding]::new($false)) }\n"
            "exit 0\n"
        )
    else:
        body = (
            "param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Arguments)\n"
            "$input | Out-Null\n"
            "Write-Output 'GATE: PASS'\n"
            "exit 0\n"
        )
    fake.write_text(body, encoding="utf-8", newline="\n")
    return fake


def _run_ps_file(tmp_path: Path, which: str, topic: str, extra_args: list[str]) -> subprocess.CompletedProcess:
    """Invoke via `-File` with bare trailing tokens (works as long as no token
    collides with a wrapper parameter's unique-abbreviation prefix -- see the
    module docstring)."""
    wrapper = PS_WRAPPERS[which]
    fake = _make_fake_provider_ps1(tmp_path, which)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("dummy prompt\n", encoding="utf-8")
    outdir = tmp_path / "prompt-outputs"

    env = os.environ.copy()
    env[BIN_ENV[which]] = str(fake)
    env[PROMPTS_DIR_ENV[which]] = str(outdir)
    if which == "claude":
        env["ANTHROPIC_API_KEY"] = "a12-guard-fixture-key"

    cmd = [INTERPRETER, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
           "-File", str(wrapper), topic, "-PromptFile", str(prompt), *extra_args]
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=120)


def _ps_quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _run_ps_command(tmp_path: Path, which: str, topic: str, flag_array: list[str] | None,
                     *, ledger_item: Path | None = None) -> subprocess.CompletedProcess:
    """Invoke via `-Command` using an explicit named parameter with a genuine
    PowerShell array literal (`-CodexFlags @('a','b',...)`), which unambiguously
    constructs a multi-element array regardless of any token's shape -- the
    collision-free path used for cases that need Codex's own `-c` or Claude's own
    `-p` flag."""
    wrapper = PS_WRAPPERS[which]
    fake = _make_fake_provider_ps1(tmp_path, which)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("dummy prompt\n", encoding="utf-8")
    outdir = tmp_path / "prompt-outputs"

    env = os.environ.copy()
    env[BIN_ENV[which]] = str(fake)
    env[PROMPTS_DIR_ENV[which]] = str(outdir)
    if which == "claude":
        env["ANTHROPIC_API_KEY"] = "a12-guard-fixture-key"

    flags_param = "CodexFlags" if which == "codex" else "ClaudeFlags"
    parts = [f"& {_ps_quote(str(wrapper))}", _ps_quote(topic), "-PromptFile", _ps_quote(str(prompt))]
    if flag_array is not None:
        literal = "@(" + ",".join(_ps_quote(v) for v in flag_array) + ")"
        parts += [f"-{flags_param}", literal]
    if ledger_item is not None:
        parts += ["-Ledger", _ps_quote(str(ledger_item)),
                  "-LedgerRole", "architecture-reviewer",
                  "-LedgerLane", "a12-fixture", "-LedgerArtifact", "design.md"]
    ps_cmd = " ".join(parts)

    cmd = [INTERPRETER, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd]
    return subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=120)


@pytestmark_ps
@pytest.mark.parametrize("which", ["codex", "claude"])
def test_ps_partial_override_missing_model_fails_closed(tmp_path: Path, which: str) -> None:
    """Effort-only override, no --model: must fail closed.

    Uses the array-literal `-Command` invocation (`_run_ps_command`), NOT bare
    trailing args via `-File`. A bare `-c` token passed as a trailing arg to the
    Codex wrapper collides with PowerShell's own unique-prefix abbreviation of
    `-CodexFlags` (see the module docstring) and collapses to a one-element
    array with the `-c` marker itself silently stripped -- a genuinely different
    failure mechanism than "effort given, model omitted". An earlier version of
    this test used that bare-args shape and got a `returncode != 0` for the
    wrong reason (the collision, not the A12 guard's own model-presence check),
    which a caught review correctly flagged: a passing assertion that does not
    exercise its stated scenario is worse than no test at all. The array literal
    constructs the intended two-element `-c model_reasoning_effort=xhigh` (or,
    for Claude, `--effort xhigh`) array exactly, isolating the guard's own
    behavior from that unrelated collision."""
    partial_array = ["-c", "model_reasoning_effort=xhigh"] if which == "codex" else ["--effort", "xhigh"]
    result = _run_ps_command(tmp_path, which, "a12-ps-partial", partial_array)

    assert result.returncode != 0, (
        f"partial override must fail closed; stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "A12" in result.stderr
    assert "--model" in result.stderr


@pytestmark_ps
@pytest.mark.parametrize("which", ["codex", "claude"])
def test_ps_full_profile_override_still_launches(tmp_path: Path, which: str) -> None:
    full_array = (
        ["--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=xhigh"]
        if which == "codex"
        else ["-p", "--output-format", "text", "--model", "opus", "--effort", "xhigh"]
    )
    result = _run_ps_command(tmp_path, which, "a12-ps-full", full_array)

    assert result.returncode == 0, (
        f"full per-profile override must still launch; stderr={result.stderr!r}"
    )


@pytestmark_ps
@pytest.mark.parametrize("which", ["codex", "claude"])
def test_ps_default_no_override_still_launches(tmp_path: Path, which: str) -> None:
    result = _run_ps_file(tmp_path, which, "a12-ps-default", [])

    assert result.returncode == 0, f"shipped default must still launch; stderr={result.stderr!r}"


@pytestmark_ps
@pytest.mark.parametrize("which", ["codex", "claude"])
def test_ps_no_default_pin_shape_fails_closed(tmp_path: Path, which: str) -> None:
    """The second historical shape (60/97 audited snapshots): a variant that
    ships no default flags at all, so an unpinned run would otherwise reach the
    provider. Simulated by neutralizing the shipped default's own guard
    condition (`if (-not $CodexFlags -or $CodexFlags.Count -eq 0)` ->
    `if ($false)`) in a throwaway copy, then invoking with zero override flags:
    the A12 guard below it must still catch the resulting empty array,
    independent of whether the default-assignment branch ever ran."""
    wrapper = PS_WRAPPERS[which]
    src = wrapper.read_bytes()
    param_name = "CodexFlags" if which == "codex" else "ClaudeFlags"
    needle = f"if (-not ${param_name} -or ${param_name}.Count -eq 0) {{".encode("utf-8")
    assert src.count(needle) == 1, f"default-guard condition not found exactly once in {wrapper}"
    patched = src.replace(needle, b"if ($false) {")

    copy_path = tmp_path / wrapper.name
    copy_path.write_bytes(patched)

    fake = _make_fake_provider_ps1(tmp_path, which)
    prompt = tmp_path / "prompt.md"
    prompt.write_text("dummy prompt\n", encoding="utf-8")
    outdir = tmp_path / "prompt-outputs"

    env = os.environ.copy()
    env[BIN_ENV[which]] = str(fake)
    env[PROMPTS_DIR_ENV[which]] = str(outdir)
    if which == "claude":
        env["ANTHROPIC_API_KEY"] = "a12-guard-fixture-key"

    cmd = [INTERPRETER, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
           "-File", str(copy_path), "a12-ps-nodefault", "-PromptFile", str(prompt)]
    result = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=120)

    assert result.returncode != 0, (
        f"a variant with no default pin, given zero override flags, must still fail closed; "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "A12" in result.stderr


@pytestmark_ps
@pytest.mark.parametrize("which", ["codex", "claude"])
def test_ps_ledger_records_resolved_model_alongside_effort(tmp_path: Path, which: str) -> None:
    item = _make_work_item(tmp_path, name=f"2026-01-01-a12-ps-{which}-fixture")
    full_array = (
        ["--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=xhigh"]
        if which == "codex"
        else ["-p", "--output-format", "text", "--model", "sonnet", "--effort", "high"]
    )
    result = _run_ps_command(tmp_path, which, "a12-ps-ledger", full_array, ledger_item=item)
    assert result.returncode == 0, result.stderr

    events = _read_ledger(item)
    launches = [e for e in events if e.get("eventKind") == "launch"]
    terminals = [e for e in events if e.get("eventKind") == "terminal"]
    assert len(launches) == 1
    assert len(terminals) == 1

    expected_model = "gpt-5.6-sol" if which == "codex" else "sonnet"
    expected_effort = "xhigh" if which == "codex" else "high"
    for event in (launches[0], terminals[0]):
        assert event.get("model") == expected_model, event
        assert event.get("effort") == expected_effort, event
