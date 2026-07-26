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

PowerShell CLI note, UPDATED (bug
work-items/bugs/2026-07-26-powershell-flag-abbreviation-collision-blocks-provider-overrides.md,
now fixed): a bare `-c` (Codex's own config-override flag) or `-p` (Claude's own
print flag), passed as trailing tokens via `-File`, used to collide with
PowerShell's own unique-prefix parameter-name abbreviation ("-c" uniquely
abbreviated "-CodexFlags", "-p" uniquely abbreviated "-PromptFile") and got
silently swallowed as an attempt to (re)bind THAT parameter instead of landing in
the flags array. Both `.ps1` wrappers now declare NO `param()` block at all --
a script with zero declared parameters gets none of PowerShell's automatic
name-matching (not even the built-in common parameters like `-PipelineVariable`,
which "-p" ALSO collided with once `[Parameter(ValueFromRemainingArguments=$true)]`
made the old param() block "advanced") -- and instead parse the raw `$args` array
by hand, exactly like the Bash sibling's `case "$1" in ...` loop. `-File` and
`-Command` now behave identically, and a bare `-c`/`-p` survives byte-for-byte via
either. The PowerShell tests below exercise BOTH invocation styles directly with
the real colliding short flags -- no array-literal workaround needed or supported
any more (the old `-CodexFlags @(...)` named-splat shape no longer parses, since
that parameter no longer exists).
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
    """Fake stand-in for the real `codex`/`claude` binary.

    Deliberately declares NO `param()` block -- an EARLIER version of this
    fixture used `param([Parameter(ValueFromRemainingArguments=$true)]
    [string[]]$Arguments)`, which (empirically, discovered this session while
    building the regression test for the collision bug below) made the FIXTURE
    ITSELF swallow a leading `-p` token via the exact same PowerShell
    common-parameter collision (`-p` uniquely abbreviates the built-in
    `-PipelineVariable`, present on any script with an advanced/`[Parameter()]`
    param block) that this whole bug is about -- masking the wrapper's own
    behavior rather than proving it, since the assertion would still have
    passed (wrong reason: the fixture ate the token, not the wrapper). A real
    provider CLI is a compiled/Node binary with no PowerShell parameter binder
    at all; reading the classic `$args` array (no param() block, so this
    script is never "advanced") is the faithful stand-in, and it also echoes
    every token it actually received to stdout (`ARGRECV[i]=<token>`, captured
    in the wrapper's `.out` file) so a test can prove byte-for-byte argument
    fidelity, not just infer it from the A12 guard's pass/fail verdict.
    """
    fake = tmp_path / f"fake-{which}.ps1"
    if which == "codex":
        body = (
            "$lastmsg = ''\n"
            "for ($i = 0; $i -lt $args.Count; $i++) {\n"
            "  Write-Output \"ARGRECV[$i]=<$($args[$i])>\"\n"
            "  if ($args[$i] -eq '--output-last-message') { $lastmsg = $args[$i + 1] }\n"
            "}\n"
            "$input | Out-Null\n"
            "if ($lastmsg) { [System.IO.File]::WriteAllText($lastmsg, \"GATE: PASS`n\", [System.Text.UTF8Encoding]::new($false)) }\n"
            "exit 0\n"
        )
    else:
        body = (
            "for ($i = 0; $i -lt $args.Count; $i++) { Write-Output \"ARGRECV[$i]=<$($args[$i])>\" }\n"
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
    """Invoke via `-Command`/the call operator (`&`) with bare trailing tokens --
    see the comment on `parts` below for why this no longer uses the old
    named-parameter array-literal splat."""
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

    # Bare tokens, exactly like `_run_ps_file` -- the fix removed the named
    # `-CodexFlags`/`-ClaudeFlags` parameter entirely, so the old array-literal
    # splat (`-CodexFlags @(...)`) no longer parses (with no such parameter left
    # to bind, it now lands as two unrelated literal tokens: the wrapper's manual
    # `$args` parser would take "-CodexFlags" as the topic-slug-if-unset-else-a-
    # stray-provider-flag, and the array value collapses to one ToString()-joined
    # string -- see the bug work-item for the measured repro). Kept as a
    # SEPARATE helper from `_run_ps_file` (rather than deleting it) specifically
    # to prove `-Command`/the call operator behaves identically to `-File` now,
    # which is the fix's central claim.
    parts = [f"& {_ps_quote(str(wrapper))}", _ps_quote(topic), "-PromptFile", _ps_quote(str(prompt))]
    if flag_array is not None:
        parts += [_ps_quote(v) for v in flag_array]
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

    Uses bare trailing tokens via `-File` -- the ACTUAL shape the collision bug
    was reported against, and now safe to use directly since the fix (removing
    the wrapper's own named parameters in favor of manual `$args` parsing) means
    a bare `-c`/`-p` no longer collides with anything. Before the fix, this exact
    invocation could not isolate "guard rejects a partial override" from "the
    collision ate the `-c` marker" -- both produced `returncode != 0`, for
    different reasons (see the module docstring and the fixed
    `_make_fake_provider_ps1` above, which used to mask this the same way). This
    now reproduces the reported bug shape directly rather than working around
    it."""
    partial_args = (
        ["-c", "model_reasoning_effort=xhigh"] if which == "codex" else ["--effort", "xhigh"]
    )
    result = _run_ps_file(tmp_path, which, "a12-ps-partial", partial_args)

    assert result.returncode != 0, (
        f"partial override must fail closed; stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert "A12" in result.stderr
    assert "--model" in result.stderr


@pytestmark_ps
@pytest.mark.parametrize("which", ["codex", "claude"])
def test_ps_full_profile_override_still_launches(tmp_path: Path, which: str) -> None:
    """Full per-profile override via bare `-File` trailing tokens -- the same
    invocation shape as the test above, now exercised on the success path."""
    full_args = (
        ["--model", "gpt-5.6-sol", "-c", "model_reasoning_effort=xhigh"]
        if which == "codex"
        else ["-p", "--output-format", "text", "--model", "opus", "--effort", "xhigh"]
    )
    result = _run_ps_file(tmp_path, which, "a12-ps-full", full_args)

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


@pytestmark_ps
@pytest.mark.parametrize("which", ["codex", "claude"])
def test_ps_file_bare_args_forward_the_actual_colliding_short_flag(tmp_path: Path, which: str) -> None:
    """Direct end-to-end reproduction of
    2026-07-26-powershell-flag-abbreviation-collision-blocks-provider-overrides,
    NOT the guard-inferred proxy the tests above rely on. This invokes the real
    `.ps1` wrapper via `-File` with BARE trailing tokens -- the wrapper's own
    documented usage shape, and the exact shape the bug report reproduced against
    -- carrying codex's real `-c` config-override flag / claude's real `-p` print
    flag as the FIRST token of a full per-profile override, mixed with a
    `-Ledger`/... block so provenance is checked too.

    Before the fix: PowerShell's automatic parameter-name abbreviation intercepted
    `-c`/`-p` as an attempt to (re)bind the wrapper's own `-CodexFlags`/
    `-PromptFile` parameter (or, for `-p`, the always-present common parameter
    `-PipelineVariable` once `-PromptFile` alone did not exist to collide with --
    see the module docstring) -- corrupting the array or hard-erroring -- so this
    exact invocation could not succeed via `-File` at all.

    This asserts three independent things, each closing a different way the fix
    could be wrong for the right-looking reason:
      1. the launch succeeds (proves no collision/hard-error occurred);
      2. the ledger's recorded model/effort match the override exactly (proves
         the override -- not a corrupted array that happened to still satisfy
         the guard some other way -- is what actually resolved);
      3. the fake provider's OWN echoed argv (captured in its `.out` file)
         contains the literal colliding token AND `--model`, in order -- direct
         proof the provider received it byte-for-byte, not an inference from the
         guard's verdict (which the module docstring's `_make_fake_provider_ps1`
         history shows can itself mask a swallowed token)."""
    item = _make_work_item(tmp_path, name=f"2026-01-01-a12-ps-collision-{which}-fixture")
    full_args = (
        ["-c", "model_reasoning_effort=xhigh", "--model", "gpt-5.6-sol"]
        if which == "codex"
        else ["-p", "--output-format", "text", "--model", "sonnet", "--effort", "high"]
    )
    ledger_args = ["-Ledger", str(item), "-LedgerRole", "architecture-reviewer",
                   "-LedgerLane", "a12-collision-fixture", "-LedgerArtifact", "design.md"]
    topic = "a12-ps-collision"
    result = _run_ps_file(tmp_path, which, topic, [*ledger_args, *full_args])

    colliding_flag = "-c" if which == "codex" else "-p"
    assert result.returncode == 0, (
        f"a full override carrying the provider's own colliding short flag "
        f"({colliding_flag!r}) as its first token must launch cleanly via -File; "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )

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

    outdir = tmp_path / "prompt-outputs"
    out_files = sorted(outdir.glob(f"{topic}-*.out"))
    assert len(out_files) == 1, out_files
    received = out_files[0].read_text(encoding="utf-8")
    assert f"<{colliding_flag}>" in received, (
        f"the fake provider's own echoed argv must contain the literal "
        f"{colliding_flag!r} token unmodified; received={received!r}"
    )
    assert "<--model>" in received, received
