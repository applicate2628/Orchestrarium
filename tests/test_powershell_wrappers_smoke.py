"""Smoke tests for the PowerShell (.ps1) hook + scanner wrappers.

The installer registers a .ps1 entry point as the WINDOWS hook command for the
five structural/audit hooks (check-bugfix-discipline, check-passive-polling-stop,
check-work-items-archival-stop, check-machine-local-path, check-no-trash-in-repo),
the informational mcp-usage-reminder SessionStart hook, and ships a .ps1 for the
publication scanner — yet NO test executed any .ps1, so a syntax error, a broken
fail-open path, or a regressed stdin pipe in the Windows entry point would have
shipped green (every other hook test drives the .py helper via sys.executable,
never the .ps1 the OS actually runs). These tests close that gap for BOTH the
Claude (src.claude/agents/{scripts,hooks}/) and Codex
(src.codex/skills/lead/{scripts,hooks}/) copies.

Two wrapper shapes, two contracts:

  * The five structural/audit HOOK wrappers are thin stdin pipes around their .py helper. Contract:
    FAIL OPEN — on empty stdin AND on malformed JSON they must exit 0 with no
    stdout and no stderr (AUDIT/decision hooks never crash the host; the helper's
    own fail-open swallows bad input). Verified under every available interpreter.

  * The publication SCANNER wrapper does not read stdin; it resolves git, locates
    the bundled bash next to that git, cd's to the repo root, and delegates to
    check-publication-safety.sh. Its environment coupling (which git is first on
    PATH determines whether bundled bash is locatable) is real and deterministic,
    so the smoke contract is: it must reach a DETERMINISTIC DECISION without an
    INTERPRETER-LEVEL crash (a guarded `throw` with a clear message is fine; a
    PowerShell ParserError / unhandled native traceback is not). Additionally,
    WHEN a bash-locatable git is available, a clean staged repo must exit 0 (the
    real clean-pass contract) and a staged leak must exit 1 (proving the
    delegation to the .sh is live, not a no-op).

POSIX-only CI safety: if neither `pwsh` nor `powershell` is on PATH, the whole
module is SKIPPED (pytest skip), so the suite stays green where PowerShell does
not exist.

Gate safety: this file contains NO machine-local-path literal and NO real secret
literal. The malformed-JSON probe and the leak fixture are ASSEMBLED AT RUNTIME
from fragments, so the publication scanner never flags this tracked test source.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CLAUDE_SCRIPTS = REPO_ROOT / "src.claude" / "agents" / "scripts"
CLAUDE_HOOKS = REPO_ROOT / "src.claude" / "agents" / "hooks"
CODEX_SCRIPTS = REPO_ROOT / "src.codex" / "skills" / "lead" / "scripts"
CODEX_HOOKS = REPO_ROOT / "src.codex" / "skills" / "lead" / "hooks"

# The five stdin-piping structural/audit hook wrappers, in BOTH install trees (10 files).
HOOK_WRAPPERS = (
    CLAUDE_SCRIPTS / "check-bugfix-discipline.ps1",
    CLAUDE_SCRIPTS / "check-passive-polling-stop.ps1",
    CLAUDE_SCRIPTS / "check-work-items-archival-stop.ps1",
    CLAUDE_HOOKS / "check-machine-local-path.ps1",
    CLAUDE_HOOKS / "check-no-trash-in-repo.ps1",
    CODEX_SCRIPTS / "check-bugfix-discipline.ps1",
    CODEX_SCRIPTS / "check-passive-polling-stop.ps1",
    CODEX_SCRIPTS / "check-work-items-archival-stop.ps1",
    CODEX_HOOKS / "check-machine-local-path.ps1",
    CODEX_HOOKS / "check-no-trash-in-repo.ps1",
)

# The informational SessionStart reminder wrappers, in BOTH install trees (2 files).
REMINDER_WRAPPERS = (
    CLAUDE_SCRIPTS / "mcp-usage-reminder.ps1",
    CODEX_SCRIPTS / "mcp-usage-reminder.ps1",
)

# The publication scanner wrapper, in BOTH install trees (2 files).
SCANNER_WRAPPERS = (
    CLAUDE_SCRIPTS / "check-publication-safety.ps1",
    CODEX_SCRIPTS / "check-publication-safety.ps1",
)

# Runtime-assembled malformed-JSON probe (kept off one source line as a bare
# literal only for tidiness; it is plain ASCII junk that is not valid JSON).
MALFORMED_JSON = "not json at all " + "{" * 3

# Markers that prove the wrapper threw its OWN guarded diagnostic rather than
# crashing at the interpreter level. Any of these (or a clean delegate) is an
# acceptable deterministic outcome; a PowerShell ParserError is not.
_GUARDED_THROW_MARKERS = (
    "bundled bash",          # "Unable to locate bundled bash.exe or sh.exe ..."
    "Unable to resolve git",
    "Unable to determine repository root",
    "Unable to locate sibling check-publication-safety.sh",
)
# Substrings that indicate an UNHANDLED interpreter-level failure (a real bug in
# the wrapper source, not a guarded environment throw).
_INTERPRETER_CRASH_MARKERS = (
    "ParserError",
    "is not recognized as the name of a cmdlet",
    "Missing closing",
    "Unexpected token",
    "CommandNotFoundException",
)


def _interpreters() -> list[str]:
    """Absolute paths to whichever PowerShell hosts exist on PATH (pwsh 7+ first,
    then Windows PowerShell 5.1). Empty list -> POSIX-only runner -> skip."""
    found: list[str] = []
    for name in ("pwsh", "powershell"):
        exe = shutil.which(name)
        if exe:
            found.append(exe)
    return found


INTERPRETERS = _interpreters()
GIT = shutil.which("git")


def _run_ps1(interp: str, script: Path, *, stdin: str | None = None,
             cwd: str | None = None, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [interp, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        input=stdin,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
    )


def _bash_locatable_git() -> str | None:
    """Return a git.exe path on PATH whose grandparent dir contains the bundled
    bash/sh the scanner wrapper looks for, so the wrapper can delegate to the .sh.

    The wrapper computes git_root = parent(parent(git.exe)) and probes
    git_root/{bin,usr/bin}/bash.exe and git_root/usr/bin/sh.exe. A mingw64 shim
    (…/Git/mingw64/bin/git.exe) yields git_root=…/Git/mingw64, which has NO
    bundled bash; the top-level …/Git/cmd/git.exe yields git_root=…/Git, which
    does. We return the first PATH git that satisfies the wrapper's own probe."""
    sub = ("bin/bash.exe", "usr/bin/bash.exe", "usr/bin/sh.exe")
    seen: list[Path] = []
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if not d:
            continue
        g = Path(d) / "git.exe"
        if g.is_file():
            seen.append(g)
            root = g.parent.parent
            if any((root / c).is_file() for c in sub):
                return str(g)
    return None


@unittest.skipIf(not INTERPRETERS, "no PowerShell host (pwsh/powershell) on PATH")
class TestHookWrappersFailOpen(unittest.TestCase):
    """All five hook wrappers, in both trees, must FAIL OPEN under every available
    PowerShell host: exit 0 with empty stdout+stderr on empty stdin and on
    malformed JSON."""

    def _assert_fail_open(self, stdin: str) -> None:
        for interp in INTERPRETERS:
            for wrapper in HOOK_WRAPPERS:
                self.assertTrue(wrapper.is_file(), f"missing wrapper: {wrapper}")
                with self.subTest(interp=Path(interp).stem, wrapper=str(wrapper.relative_to(REPO_ROOT))):
                    p = _run_ps1(interp, wrapper, stdin=stdin)
                    self.assertEqual(p.returncode, 0,
                                     f"expected fail-open exit 0; stderr={p.stderr!r}")
                    self.assertEqual(p.stdout.strip(), "",
                                     f"expected no stdout on fail-open; got {p.stdout!r}")
                    self.assertEqual(p.stderr.strip(), "",
                                     f"expected no stderr on fail-open; got {p.stderr!r}")

    def test_empty_stdin_fails_open(self) -> None:
        self._assert_fail_open("")

    def test_malformed_json_fails_open(self) -> None:
        self._assert_fail_open(MALFORMED_JSON)


@unittest.skipIf(not INTERPRETERS, "no PowerShell host (pwsh/powershell) on PATH")
class TestReminderWrappersEmitContext(unittest.TestCase):
    """The MCP reminder is informational, not stdin-driven. It must execute and
    emit the operational checkpoint text under every available PowerShell host."""

    def test_reminder_outputs_mcp_checkpoint(self) -> None:
        for interp in INTERPRETERS:
            for wrapper in REMINDER_WRAPPERS:
                self.assertTrue(wrapper.is_file(), f"missing reminder wrapper: {wrapper}")
                with self.subTest(interp=Path(interp).stem, wrapper=str(wrapper.relative_to(REPO_ROOT))):
                    p = _run_ps1(interp, wrapper, stdin="")
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertIn("MCP / tools reminder", p.stdout)
                    self.assertIn("tool discovery", p.stdout)
                    self.assertIn("mcpMode: force", p.stdout)


@unittest.skipIf(not INTERPRETERS or GIT is None, "needs a PowerShell host and git on PATH")
class TestScannerWrapperNoCrash(unittest.TestCase):
    """The publication scanner wrapper must reach a DETERMINISTIC decision without
    an interpreter-level crash under every available host, run inside a clean
    throwaway git repo. A guarded `throw` (e.g. bundled bash not locatable for the
    git first on PATH) is an acceptable deterministic outcome; a PowerShell
    ParserError / CommandNotFound is a wrapper bug."""

    def _clean_repo(self, td: str) -> None:
        subprocess.run([GIT, "init", "-q", td], check=True, capture_output=True)
        subprocess.run([GIT, "-C", td, "config", "user.email", "t@t"], check=True, capture_output=True)
        subprocess.run([GIT, "-C", td, "config", "user.name", "t"], check=True, capture_output=True)

    def test_scanner_runs_without_interpreter_crash(self) -> None:
        for interp in INTERPRETERS:
            for wrapper in SCANNER_WRAPPERS:
                self.assertTrue(wrapper.is_file(), f"missing scanner wrapper: {wrapper}")
                with self.subTest(interp=Path(interp).stem, wrapper=str(wrapper.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        self._clean_repo(td)
                        p = _run_ps1(interp, wrapper, cwd=td)
                        combined = p.stdout + p.stderr
                        for marker in _INTERPRETER_CRASH_MARKERS:
                            self.assertNotIn(
                                marker, combined,
                                f"interpreter-level crash marker {marker!r} in wrapper output:\n{combined}",
                            )
                        # Either it delegated cleanly (exit 0) or it threw its own
                        # guarded environment diagnostic. Anything else (a silent
                        # nonzero with no recognizable guarded message) is suspect.
                        if p.returncode != 0:
                            self.assertTrue(
                                any(m in combined for m in _GUARDED_THROW_MARKERS),
                                f"nonzero exit without a recognized guarded diagnostic:\n{combined}",
                            )


@unittest.skipIf(not INTERPRETERS or GIT is None or _bash_locatable_git() is None,
                 "needs a PowerShell host and a git whose bundled bash the wrapper can locate")
class TestScannerWrapperDelegatesWhenBashAvailable(unittest.TestCase):
    """When a bash-locatable git is on PATH, the scanner wrapper must delegate to
    check-publication-safety.sh: a clean staged repo exits 0 (the real clean-pass
    contract) and a staged leak exits 1 (proving the delegation is live)."""

    def _env_with_bashable_git_first(self) -> dict:
        bg = _bash_locatable_git()
        assert bg is not None
        env = dict(os.environ)
        env["PATH"] = str(Path(bg).parent) + os.pathsep + env.get("PATH", "")
        return env

    def _staged_repo(self, td: str, files: dict[str, str]) -> None:
        subprocess.run([GIT, "init", "-q", td], check=True, capture_output=True)
        subprocess.run([GIT, "-C", td, "config", "user.email", "t@t"], check=True, capture_output=True)
        subprocess.run([GIT, "-C", td, "config", "user.name", "t"], check=True, capture_output=True)
        for name, content in files.items():
            (Path(td) / name).write_text(content, encoding="utf-8")
            subprocess.run([GIT, "-C", td, "add", name], check=True, capture_output=True)

    def test_clean_staged_repo_exits_zero(self) -> None:
        env = self._env_with_bashable_git_first()
        for interp in INTERPRETERS:
            for wrapper in SCANNER_WRAPPERS:
                with self.subTest(interp=Path(interp).stem, wrapper=str(wrapper.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        self._staged_repo(td, {"clean.txt": "nothing machine-local here\n"})
                        p = _run_ps1(interp, wrapper, cwd=td, env=env)
                        self.assertEqual(p.returncode, 0,
                                         f"clean staged repo must PASS (exit 0); stderr={p.stderr!r}")

    def test_staged_leak_exits_one(self) -> None:
        # Leak fixture assembled at runtime so this tracked source has no real
        # secret literal of its own (gate safety).
        leak = "pass" + "word" + ": hunter2\n"
        env = self._env_with_bashable_git_first()
        for interp in INTERPRETERS:
            for wrapper in SCANNER_WRAPPERS:
                with self.subTest(interp=Path(interp).stem, wrapper=str(wrapper.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        self._staged_repo(td, {"leak.txt": leak})
                        p = _run_ps1(interp, wrapper, cwd=td, env=env)
                        self.assertEqual(p.returncode, 1,
                                         f"staged leak must BLOCK (exit 1); stdout={p.stdout!r} stderr={p.stderr!r}")


if __name__ == "__main__":
    unittest.main()
