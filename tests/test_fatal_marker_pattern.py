"""Regression coverage for the run-completion oracle's `.err` fatal-marker scan.

Bug: work-items/bugs/2026-07-26-oracle-err-marker-pattern-misses-timestamped-fatals.md

The oracle's ORIGINAL pattern (`^(ERROR|FATAL|API Error): `) required the
severity token at line start, immediately followed by `: `. The 2026-07-26
incident's real fatal line is a Rust `tracing`-crate default-formatter line --
timestamp-prefixed, with a module target between the severity token and its
message colon -- and the anchored pattern missed it entirely:

    2026-07-25T23:20:34.729085Z ERROR rmcp::transport::worker: worker quit
    with fatal: Transport channel closed, when Client(HttpRequest("http/
    request failed: error sending request for url (http://127.0.0.1:9401/mcp)"))

This file locks in the widened pattern two ways:
  1. A fixture-driven shape test (`TestFatalMarkerPatternShapes`) built from
     the REAL captured incident line plus a second real timestamped-ERROR line
     independently found in this repo's own `.scratch/codex-prompts/` corpus
     (`codex_core::tools::router`), run through the actual shipped pattern
     extracted from all four source files (both `.sh` grep -E and both `.ps1`
     Select-String twins), with falsifying controls -- lines that must be
     REJECTED -- so an empty non-match set is evidence, not an assumption.
  2. An end-to-end integration test (`TestOracleEndToEnd`) that runs the real
     `invoke-codex-prompt.sh` wrapper with a fake provider emitting the exact
     captured fatal line to `.err` (exit 0, GATE: PASS lastmsg) and asserts the
     ledger terminal event is `blocked`, not `completed` -- proving the fix
     closes the actual oracle gap, not just the regex in isolation.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The four wrappers that carry the fatal-marker scan (all under src.claude --
# no mirror copies exist elsewhere; verified via repo-wide grep for
# "ERR_MARKERS"/"errMarkers" during the fix).
CODEX_SH = ROOT / "src.claude" / "agents" / "scripts" / "invoke-codex-prompt.sh"
CODEX_PS1 = ROOT / "src.claude" / "agents" / "scripts" / "invoke-codex-prompt.ps1"
CLAUDE_SH = ROOT / "src.claude" / "agents" / "scripts" / "invoke-claude-prompt.sh"
CLAUDE_PS1 = ROOT / "src.claude" / "agents" / "scripts" / "invoke-claude-prompt.ps1"

# The exact pattern string shipped identically in all four files (bash
# single-quoted grep -E argument and PowerShell single-quoted Select-String
# -Pattern argument use the same regex text). Asserted present verbatim below
# so a future edit that silently narrows the pattern fails this test, not just
# a live incident.
SHIPPED_PATTERN = (
    r"^([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?Z? )?"
    r"(ERROR|FATAL|API Error)(: | [A-Za-z0-9_]+(::[A-Za-z0-9_]+)*: )"
)

# The ORIGINAL (pre-fix) pattern, kept here only for contrast so the test can
# demonstrate the actual defect empirically rather than asserting it from
# memory: it must match the plain shapes but MISS both real timestamped lines.
ORIGINAL_PATTERN = r"^(ERROR|FATAL|API Error): "

# The real captured incident line (bug registry, verbatim, joined to one
# physical line -- the bug's markdown code fence wrapped it for display width
# only; the raw .err bytes are one line, as confirmed against this repo's own
# .scratch/codex-prompts/sol-review-loop-audit-20260726-040336.err:93-95 which
# carries the byte-identical shape unwrapped).
REAL_INCIDENT_LINE = (
    '2026-07-25T23:20:34.729085Z ERROR rmcp::transport::worker: worker quit '
    'with fatal: Transport channel closed, when Client(HttpRequest('
    '"http/request failed: error sending request for url '
    '(http://127.0.0.1:9401/mcp)"))'
)

# A second real timestamped-ERROR line, independently found (not authored) in
# this repo's own .scratch/codex-prompts/sol-review-loop-audit-20260726-040336.err:5891,
# from a DIFFERENT module target -- proves the fix covers the class (any Rust
# tracing module path), not just the one incident string.
REAL_SECOND_LINE = (
    "2026-07-26T01:32:22.205989Z ERROR codex_core::tools::router: "
    "error=`\"C:\\Program Files\\PowerShell\\7\\pwsh.exe\" -Command"
)

POSITIVE_LINES = (
    "ERROR: plain anchored original shape",
    "FATAL: plain anchored original shape",
    "API Error: plain anchored original shape",
    REAL_INCIDENT_LINE,
    REAL_SECOND_LINE,
)

# Falsifying controls: shapes the pattern MUST reject. Each is either a real
# false-positive-risk line independently found in this repo's own .err corpus
# (the prompt/diff echo containing the word ERROR mid-prose) or a synthetic
# adversarial near-miss of the new shape.
NEGATIVE_LINES = (
    # Prose starting with the severity word but not followed by ": " or a
    # "module::path: " immediately -- the exact false-positive risk this
    # bug's own text names ("the prompt echo in stderr contains ERROR in
    # ordinary prose").
    "ERROR handling notes: see below",
    # "API Error" is a strict prefix of "API Errors" -- must not match on
    # the substring alone.
    "API Errors will be retried automatically",
    # A real line independently found in this repo's own
    # .scratch/codex-prompts/sol-review-loop-audit-20260726-040336.err:4122 --
    # the pattern definition itself echoed mid-prose, not at line start.
    "  fragment mentioning ^ERROR:|^FATAL: inside prose, not at line start",
    # INFO/WARN tracing lines: same shape as the real fatal, different
    # severity token. Must never count as fatal by design.
    "2026-07-26T01:00:00Z INFO codex_core::foo: error=None",
    "2026-07-26T01:00:00Z WARN codex_core::foo: something concerning but not fatal",
    # Severity token followed by a dash, not a colon or module path.
    "ERROR - transient issue, retrying",
    # "ERROR" appearing mid-line, not at line start.
    "this is a line that mentions ERROR in the middle of prose, not at line start",
)


class TestFatalMarkerPatternShapes(unittest.TestCase):
    """Pattern-level fixture test against the exact shipped regex."""

    def test_shipped_pattern_string_is_identical_across_all_four_wrappers(self) -> None:
        for path in (CODEX_SH, CODEX_PS1, CLAUDE_SH, CLAUDE_PS1):
            with self.subTest(wrapper=str(path.relative_to(ROOT))):
                text = path.read_text(encoding="utf-8")
                self.assertIn(
                    SHIPPED_PATTERN, text,
                    f"exact shipped fatal-marker pattern not found verbatim in {path}",
                )

    def test_positive_lines_all_match_the_shipped_pattern(self) -> None:
        for line in POSITIVE_LINES:
            with self.subTest(line=line[:60]):
                self.assertIsNotNone(
                    re.match(SHIPPED_PATTERN, line),
                    f"expected a fatal-marker match, got none: {line!r}",
                )

    def test_negative_lines_are_all_rejected_falsifying_controls(self) -> None:
        for line in NEGATIVE_LINES:
            with self.subTest(line=line[:60]):
                self.assertIsNone(
                    re.match(SHIPPED_PATTERN, line),
                    f"falsifying control must NOT match, but did: {line!r}",
                )

    def test_original_pattern_matches_plain_shapes_but_misses_both_real_timestamped_lines(self) -> None:
        """Empirical proof of the defect being fixed: the ORIGINAL anchored
        pattern (no timestamp support) matches the three plain shapes but
        misses both real incident-shaped lines -- exactly the gap the bug
        registry describes. Contrast case for the shipped pattern above,
        which matches all five."""
        for line in ("ERROR: plain anchored original shape",
                     "FATAL: plain anchored original shape",
                     "API Error: plain anchored original shape"):
            self.assertIsNotNone(re.match(ORIGINAL_PATTERN, line))
        for line in (REAL_INCIDENT_LINE, REAL_SECOND_LINE):
            with self.subTest(line=line[:60]):
                self.assertIsNone(
                    re.match(ORIGINAL_PATTERN, line),
                    "the pre-fix pattern was expected to MISS this real "
                    "timestamped fatal (that is the bug); if this now "
                    "matches, the ORIGINAL_PATTERN constant no longer "
                    "represents the pre-fix shape",
                )


def _bash() -> str | None:
    found = shutil.which("bash")
    if found and "System32" not in found:
        return found
    for candidate in (r"C:\Program Files\Git\bin\bash.exe",
                      r"C:\Program Files\Git\usr\bin\bash.exe"):
        if Path(candidate).exists():
            return candidate
    return found


def _powershell() -> str | None:
    return shutil.which("pwsh") or shutil.which("powershell")


def _to_posix(p: Path) -> str:
    s = str(p).replace("\\", "/")
    if len(s) > 1 and s[1] == ":":
        s = "/" + s[0].lower() + s[2:]
    return s


@unittest.skipIf(_powershell() is None, "no PowerShell host (pwsh/powershell) on PATH")
class TestFatalMarkerPatternShapesPowerShell(unittest.TestCase):
    """Same fixture set, run through the ACTUAL Select-String call the .ps1
    wrappers use, under every available PowerShell host (including Windows
    PowerShell 5.1 when present) -- .NET regex is a superset of the POSIX ERE
    subset used here, but this closes the "assumed, not verified" gap for the
    cross-engine port."""

    def _run_fixture(self, interp: str, lines: tuple[str, ...]) -> list[str]:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            fixture = Path(td) / "fixture.err"
            fixture.write_text("\n".join(lines) + "\n", encoding="utf-8")
            script = Path(td) / "probe.ps1"
            script.write_text(
                "param([string]$FixturePath)\n"
                f"$pattern = '{SHIPPED_PATTERN}'\n"
                "$m = @(Select-String -LiteralPath $FixturePath -Pattern $pattern -CaseSensitive -AllMatches)\n"
                "$m | ForEach-Object { $_.Line }\n",
                encoding="utf-8",
            )
            p = subprocess.run(
                [interp, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                 "-File", str(script), "-FixturePath", str(fixture)],
                capture_output=True, text=True, timeout=20,
            )
            self.assertEqual(p.returncode, 0, p.stderr)
            return [ln for ln in p.stdout.splitlines() if ln.strip()]

    def test_positive_and_negative_lines_under_every_powershell_host(self) -> None:
        for interp in filter(None, (shutil.which("pwsh"), shutil.which("powershell"))):
            with self.subTest(interp=Path(interp).stem):
                matched = self._run_fixture(interp, POSITIVE_LINES + NEGATIVE_LINES)
                self.assertEqual(
                    sorted(matched), sorted(POSITIVE_LINES),
                    f"Select-String under {interp} matched a different set than expected",
                )


def _make_fake_codex_provider(tmp_path: Path, *, err_content: str, exit_code: int = 0) -> Path:
    """A fake `codex` binary that writes a PASS lastmsg (so the ONLY reason a
    run should be blocked is the .err marker scan) and the given .err content,
    then exits with `exit_code`."""
    fake = tmp_path / "fake-codex.sh"
    # Bash single-quoted strings take every byte literally except the quote
    # character itself, which needs the '\'' close-escape-reopen trick.
    # Backslashes must NOT be doubled here -- they are not special inside
    # single quotes, and doubling would write different bytes than the real
    # captured line contains.
    err_literal = err_content.replace("'", "'\\''")
    fake.write_text(
        "#!/usr/bin/env bash\n"
        "lastmsg=''\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  case \"$1\" in\n"
        "    --output-last-message) lastmsg=\"$2\"; shift 2 ;;\n"
        "    *) shift ;;\n"
        "  esac\n"
        "done\n"
        "cat >/dev/null\n"
        f"printf '%s\\n' '{err_literal}' >&2\n"
        "printf 'GATE: PASS\\n' > \"$lastmsg\"\n"
        f"exit {exit_code}\n",
        encoding="utf-8", newline="\n",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return fake


def _make_work_item(tmp_path: Path) -> Path:
    item = tmp_path / "work-items" / "active" / "2026-01-01-fatal-marker-fixture"
    item.mkdir(parents=True)
    (item / "design.md").write_text("fixture artifact\n", encoding="utf-8")
    (item / "status.md").write_text(
        "# Status\n\n- state: open\n\n## Current state\n\nFixture item.\n\n"
        "## Active agents\n\n- none\n\n## Completed agents\n\n- none\n\n"
        "## Next action\n\n- none\n", encoding="utf-8",
    )
    return item


@unittest.skipIf(_bash() is None, "bash is unavailable")
class TestOracleEndToEnd(unittest.TestCase):
    """Integration-level proof: the real invoke-codex-prompt.sh wrapper, with a
    provider that reports GATE: PASS and exit 0 but whose .err carries the
    real captured fatal line, must NOT settle as a PASS."""

    def _run_wrapper(self, tmp_path: Path, err_content: str) -> dict:
        wrapper = CODEX_SH
        fake = _make_fake_codex_provider(tmp_path, err_content=err_content)
        item = _make_work_item(tmp_path)
        prompt = tmp_path / "prompt.md"
        prompt.write_text("dummy prompt\n", encoding="utf-8")
        outdir = tmp_path / "prompt-outputs"

        env = os.environ.copy()
        env["CODEX_BIN"] = _to_posix(fake)
        env["CODEX_PROMPTS_DIR"] = _to_posix(outdir)

        result = subprocess.run(
            [_bash(), _to_posix(wrapper), "fatal-marker-fixture",
             "--prompt-file", _to_posix(prompt),
             "--ledger", _to_posix(item),
             "--ledger-role", "architecture-reviewer",
             "--ledger-lane", "fixture-lane",
             "--ledger-artifact", "design.md"],
            capture_output=True, text=True, env=env, cwd=str(ROOT), timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)  # provider itself exits 0
        events = [json.loads(ln) for ln in
                  (item / "agent-runs.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
        terminal = next(e for e in events if e.get("eventKind") == "terminal")
        return terminal

    def test_real_captured_fatal_line_blocks_an_otherwise_passing_run(self) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            terminal = self._run_wrapper(Path(td), REAL_INCIDENT_LINE)
            self.assertEqual(
                terminal["status"], "blocked",
                f"a run whose .err carries the real captured fatal line must "
                f"NOT settle as completed/PASS despite exit 0 and a GATE: PASS "
                f"lastmsg; terminal event was: {terminal}",
            )
            self.assertEqual(terminal["gate"], "none")
            self.assertIn("err markers present", terminal.get("notes", ""))

    def test_control_clean_err_with_same_shape_run_settles_as_pass(self) -> None:
        """Falsifying control for the end-to-end test: an otherwise-identical
        run whose .err has NO fatal marker (just a benign INFO line of the
        same tracing shape) must settle as completed/PASS. This proves the
        blocked verdict above is caused by the marker, not by some other
        difference between this fixture and the real oracle tests."""
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            terminal = self._run_wrapper(
                Path(td), "2026-07-26T01:00:00Z INFO codex_core::foo: normal operation",
            )
            self.assertEqual(terminal["status"], "completed", terminal)
            self.assertEqual(terminal["gate"], "PASS", terminal)
