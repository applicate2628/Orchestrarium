"""Smoke tests for the PowerShell (.ps1) hook + scanner wrappers.

The installer registers a .ps1 entry point as the WINDOWS hook command for the
 eight structural/audit hooks (check-bugfix-discipline, check-git-push-gate,
 check-passive-polling-stop, check-work-items-archival-stop,
check-machine-local-path, check-no-trash-in-repo, check-stale-relation-residue,
check-repository-orientation),
the two informational SessionStart reminders
(mcp-usage-reminder, agents-mode-reminder), and ships a .ps1 for the publication
scanner — yet NO test executed any .ps1, so a syntax error, a broken fail-open
path, or a regressed stdin pipe in the Windows entry point would have shipped
green (every other hook test drives the .py helper via sys.executable, never the
.ps1 the OS actually runs). These tests close that gap for BOTH the Claude
(src.claude/agents/{scripts,hooks}/) and Codex
(src.codex/skills/lead/{scripts,hooks}/) copies.

Three wrapper shapes, three contracts:

  * The eight structural/audit HOOK wrappers are thin stdin pipes around their .py helper. Contract:
    FAIL OPEN — on empty stdin AND on malformed JSON they must exit 0 with no
    stdout and no stderr (AUDIT/decision hooks never crash the host; the helper's
    own fail-open swallows bad input). Verified under every available interpreter.

  * The mcp-usage-reminder SessionStart wrapper is informational and always emits
    its checkpoint text; agents-mode-reminder is CONDITIONAL — it reads the
    effective delegationMode and emits an imperative directive on force/auto but
    is SILENT on manual and on the no-file/unresolved state. Each has its own
    contract test below.

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

import json
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

# The eight stdin-piping structural/audit hook wrappers, in BOTH install trees (16 files).
HOOK_WRAPPERS = (
    CLAUDE_SCRIPTS / "check-bugfix-discipline.ps1",
    CLAUDE_SCRIPTS / "check-git-push-gate.ps1",
    CLAUDE_SCRIPTS / "check-passive-polling-stop.ps1",
    CLAUDE_SCRIPTS / "check-work-items-archival-stop.ps1",
    CLAUDE_HOOKS / "check-machine-local-path.ps1",
    CLAUDE_HOOKS / "check-no-trash-in-repo.ps1",
    CLAUDE_HOOKS / "check-stale-relation-residue.ps1",
    CLAUDE_HOOKS / "check-repository-orientation.ps1",
    CODEX_SCRIPTS / "check-bugfix-discipline.ps1",
    CODEX_SCRIPTS / "check-git-push-gate.ps1",
    CODEX_SCRIPTS / "check-passive-polling-stop.ps1",
    CODEX_SCRIPTS / "check-work-items-archival-stop.ps1",
    CODEX_HOOKS / "check-machine-local-path.ps1",
    CODEX_HOOKS / "check-no-trash-in-repo.ps1",
    CODEX_HOOKS / "check-stale-relation-residue.ps1",
    CODEX_HOOKS / "check-repository-orientation.ps1",
)

# The always-emitting informational SessionStart reminder (mcp-usage-reminder), in
# BOTH install trees (2 files). agents-mode-reminder is a SECOND SessionStart
# reminder but has a CONDITIONAL contract (force/auto emit, manual silent), so it
# is covered by its own test class below, not this always-emit list.
REMINDER_WRAPPERS = (
    CLAUDE_SCRIPTS / "mcp-usage-reminder.ps1",
    CODEX_SCRIPTS / "mcp-usage-reminder.ps1",
)

# The conditional delegation-posture reminder, per pack, with the pack-specific
# top-level .agents-mode.yaml dir the wrapper reads from cwd. Both packs emit the
# SessionStart JSON envelope since the claude alignment (5f9d5907); the expected
# directive text stays pack-specific (conversation/Agent-tool vs session/role-skill,
# and the pack-correct external-dispatch contract path).
AGENTS_MODE_REMINDERS = (
    (CLAUDE_SCRIPTS / "agents-mode-reminder.ps1", ".claude", "claude"),
    (CODEX_SCRIPTS / "agents-mode-reminder.ps1", ".agents", "codex"),
)

# The conditional scratch-valuables watchdog reminder, in BOTH install trees
# (2 files). Reads `cwd` from the stdin JSON envelope (not the process cwd),
# so it is driven via stdin like the structural/audit hook wrappers rather
# than the cwd= kwarg the agents-mode-reminder tests use.
SCRATCH_VALUABLES_WRAPPERS = (
    CLAUDE_SCRIPTS / "check-scratch-valuables.ps1",
    CODEX_SCRIPTS / "check-scratch-valuables.ps1",
)

MCP_REMINDER_CONTEXT = "\n".join((
    "[MCP / tools reminder - re-shown at session start and after every compaction]",
    "MCP servers may be connected in this environment. For codebase, architecture, API/docs, search, browser, debugger, profiler, or repository-understanding tasks, make MCP/tool-discovery an explicit checkpoint before falling back to ad-hoc shell reads.",
    "MCP tools load on demand: use the platform's tool discovery (e.g. ToolSearch) to see the connected servers and load a tool's schema, then call the relevant tool. If a relevant MCP is unavailable or broken, say so briefly instead of silently substituting a weaker path.",
    "When mcpMode: force is active, relevant MCP use is a standing instruction. Under mcpMode: auto, still consider MCP first when it fits the task and record why it was skipped if the task explicitly asked for MCP.",
    "High-value categories when present: semantic code navigation and code-graph, Repomix or repository packers, language-server / LSP, current library / framework / API docs (use these instead of answering API questions from memory), debuggers and profilers, browser automation, memory, search, and fetch utilities.",
    "This STILL APPLIES AFTER COMPACTION - do not forget MCP just because the context was summarized.",
    "SUBAGENTS: dispatched agents inherit the runtime tool surface. In the dispatch prompt, explicitly allow relevant MCP discovery/use within the assigned role, scope, and safety limits; do not accidentally hide MCP availability, but keep any deliberate tool limits honest.",
))

DELEGATION_HEADING = (
    "[Delegation posture - re-shown at session start and after every compaction]"
)
CODEX_DELEGATION_CONTEXTS = {
    "force": DELEGATION_HEADING + "\n" + (
        "Effective delegationMode: FORCE. STANDING INSTRUCTION, not advisory: at the FIRST decision point of any non-trivial task (multi-step implementation, design, research, review, bug-fix), STOP - hold the $lead orchestration role in THIS session, classify the task, pick the team template, and activate the matching specialist role/skill per stage ($lead is the role you hold, not a subagent you spawn). Doing substantial work inline when a matching specialist and a viable tool path exist violates the active posture. When you launch any external provider (consultant / Codex / Claude) as $lead, take the launch flags from skills/lead/external-dispatch.md - file-based prompt, explicit model+effort, run-completion oracle, stall policy - never improvise them from memory. Maintain work-items/ recovery state for multi-stage chains. This STILL APPLIES AFTER COMPACTION."
    ),
    "auto": DELEGATION_HEADING + "\n" + (
        "Effective delegationMode: AUTO. Holding the $lead orchestration role in THIS session and activating the matching specialist role/skill per stage is the DEFAULT for any non-trivial task (multi-step implementation, design, research, review, bug-fix) - do it unless the task is trivial or you record why inline is better. $lead is the role you hold, not a subagent you spawn. When you launch any external provider (consultant / Codex / Claude) as $lead, take the launch flags from skills/lead/external-dispatch.md - file-based prompt, explicit model+effort, run-completion oracle, stall policy - never improvise them from memory. Maintain work-items/ recovery state for multi-stage chains. This STILL APPLIES AFTER COMPACTION."
    ),
}
CLAUDE_DELEGATION_CONTEXTS = {
    "force": DELEGATION_HEADING + "\n" + (
        "Effective delegationMode: FORCE. STANDING INSTRUCTION, not advisory: at the FIRST decision point of any non-trivial task (multi-step implementation, design, research, review, bug-fix), STOP - hold the $lead orchestration role in THIS conversation, classify the task, pick the team template, and route it via the Agent tool to the matching specialist subagents ($lead is the role you hold, not a subagent you spawn). Doing substantial work inline when a matching specialist and a viable tool path exist violates the active posture. When you launch any external provider (consultant / Codex / Claude) as $lead, take the launch flags from contracts/external-dispatch.md - file-based prompt, explicit model+effort, run-completion oracle, stall policy - never improvise them from memory. Maintain work-items/ recovery state for multi-stage chains. This STILL APPLIES AFTER COMPACTION."
    ),
    "auto": DELEGATION_HEADING + "\n" + (
        "Effective delegationMode: AUTO. Holding the $lead orchestration role in THIS conversation and delegating to the matching specialist subagents via the Agent tool is the DEFAULT for any non-trivial task (multi-step implementation, design, research, review, bug-fix) - do it unless the task is trivial or you record why inline is better. $lead is the role you hold, not a subagent you spawn. When you launch any external provider (consultant / Codex / Claude) as $lead, take the launch flags from contracts/external-dispatch.md - file-based prompt, explicit model+effort, run-completion oracle, stall policy - never improvise them from memory. Maintain work-items/ recovery state for multi-stage chains. This STILL APPLIES AFTER COMPACTION."
    ),
}
DELEGATION_CONTEXTS_BY_PACK = {
    "codex": CODEX_DELEGATION_CONTEXTS,
    "claude": CLAUDE_DELEGATION_CONTEXTS,
}

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


def _decode_sessionstart_context(stdout: str) -> str:
    payload = json.loads(stdout)
    if set(payload) != {"hookSpecificOutput"}:
        raise AssertionError(f"unexpected SessionStart top-level shape: {payload!r}")
    specific = payload["hookSpecificOutput"]
    if set(specific) != {"hookEventName", "additionalContext"}:
        raise AssertionError(f"unexpected hookSpecificOutput shape: {specific!r}")
    if specific["hookEventName"] != "SessionStart":
        raise AssertionError(f"unexpected hookEventName: {specific!r}")
    if not isinstance(specific["additionalContext"], str):
        raise AssertionError(f"additionalContext must be a string: {specific!r}")
    return specific["additionalContext"]


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
    """All seven hook wrappers, in both trees, must FAIL OPEN under every available
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
                    self.assertEqual(_decode_sessionstart_context(p.stdout), MCP_REMINDER_CONTEXT)


@unittest.skipIf(not INTERPRETERS, "no PowerShell host (pwsh/powershell) on PATH")
class TestAgentsModeReminderWrapper(unittest.TestCase):
    """The agents-mode-reminder SessionStart wrapper is CONDITIONAL: it reads the
    effective delegationMode from the pack-specific .agents-mode.yaml read-order
    (relative to cwd, with an isolated USERPROFILE so no ambient home file leaks
    in) and must emit an imperative FORCE directive on force, be SILENT on manual,
    and always exit 0 (fail-open). This locks the parser hardening (case-sensitive
    key match, whitespace-only comment strip, end-only trim, key-line ownership)
    into a durable Windows-entry-point regression, per the external review."""

    def test_force_and_auto_emit_directive_json_and_manual_is_silent(self) -> None:
        for interp in INTERPRETERS:
            for wrapper, sub, pack_key in AGENTS_MODE_REMINDERS:
                self.assertTrue(wrapper.is_file(), f"missing wrapper: {wrapper}")
                with tempfile.TemporaryDirectory() as td:
                    cfg_dir = Path(td) / sub
                    cfg_dir.mkdir(parents=True, exist_ok=True)
                    home = Path(td) / "home"
                    home.mkdir(exist_ok=True)
                    cfg = cfg_dir / ".agents-mode.yaml"

                    env = os.environ.copy()
                    env["USERPROFILE"] = str(home)

                    for mode in ("force", "auto"):
                        cfg.write_text(f"delegationMode: {mode}\n", encoding="utf-8")
                        with self.subTest(interp=Path(interp).stem, pack=sub, mode=mode):
                            p = _run_ps1(interp, wrapper, cwd=td, env=env)
                            self.assertEqual(p.returncode, 0, p.stderr)
                            context = _decode_sessionstart_context(p.stdout)
                            self.assertEqual(context.splitlines()[0], DELEGATION_HEADING)
                            self.assertIn(f"delegationMode: {mode.upper()}", context)
                            self.assertEqual(
                                context, DELEGATION_CONTEXTS_BY_PACK[pack_key][mode]
                            )

                    cfg.write_text("delegationMode: manual\n", encoding="utf-8")
                    with self.subTest(interp=Path(interp).stem, pack=sub, mode="manual"):
                        p = _run_ps1(interp, wrapper, cwd=td, env=env)
                        self.assertEqual(p.returncode, 0, p.stderr)
                        self.assertEqual(p.stdout.strip(), "",
                                         f"manual must be silent; got {p.stdout!r}")

    def test_no_file_is_silent(self) -> None:
        # No .agents-mode.yaml anywhere in the read-order (a fresh cwd with no
        # pack config, and an isolated empty USERPROFILE so no ambient home file
        # leaks in) must resolve to the `unresolved` sentinel and stay SILENT
        # (fail-safe), exit 0. A directory where the pack is not installed / the
        # config was removed must never surface a standing delegation directive.
        for interp in INTERPRETERS:
            for wrapper, sub, _emits_json in AGENTS_MODE_REMINDERS:
                self.assertTrue(wrapper.is_file(), f"missing wrapper: {wrapper}")
                with tempfile.TemporaryDirectory() as td:
                    home = Path(td) / "home"
                    home.mkdir(exist_ok=True)
                    env = os.environ.copy()
                    env["USERPROFILE"] = str(home)
                    with self.subTest(interp=Path(interp).stem, pack=sub, mode="no-file"):
                        p = _run_ps1(interp, wrapper, cwd=td, env=env)
                        self.assertEqual(p.returncode, 0, p.stderr)
                        self.assertEqual(p.stdout.strip(), "",
                                         f"no-file/unresolved must be silent; got {p.stdout!r}")


@unittest.skipIf(not INTERPRETERS, "no PowerShell host (pwsh/powershell) on PATH")
class TestScratchValuablesWrapper(unittest.TestCase):
    """The scratch-valuables SessionStart wrapper is CONDITIONAL, like
    agents-mode-reminder, but on `.scratch/` content instead of
    delegationMode: silent when there is nothing to flag, and emits a
    hookSpecificOutput context block when there is. It reads `cwd` from the
    stdin JSON envelope (not the process cwd), so it is driven via stdin
    rather than the `cwd=` kwarg the agents-mode-reminder tests use.

    A bare `git init` (no commits) is used to make the git-uniqueness
    predicate deterministic regardless of the test host's ambient state: an
    empty object database reports every blob as missing, so any non-junk,
    non-empty file is a candidate independent of its age -- this locks in
    the junction/reparse fix and the git-mode code path as an actual
    Windows PowerShell entry-point regression test, not just a .py unit
    test."""

    def _init_git_repo(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)

    def test_emits_context_when_a_unique_valuable_is_present(self) -> None:
        for interp in INTERPRETERS:
            for wrapper in SCRATCH_VALUABLES_WRAPPERS:
                self.assertTrue(wrapper.is_file(), f"missing wrapper: {wrapper}")
                with self.subTest(interp=Path(interp).stem, wrapper=str(wrapper.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        self._init_git_repo(root)
                        scratch = root / ".scratch"
                        scratch.mkdir()
                        (scratch / "unique.md").write_text(
                            "genuinely unique content, never committed", encoding="utf-8"
                        )
                        envelope = json.dumps({"cwd": str(root)})
                        p = _run_ps1(interp, wrapper, stdin=envelope)
                        self.assertEqual(p.returncode, 0, p.stderr)
                        context = _decode_sessionstart_context(p.stdout)
                        self.assertIn("scratch watchdog", context)
                        self.assertIn("unique.md", context)

    def test_silent_when_scratch_has_no_candidates(self) -> None:
        for interp in INTERPRETERS:
            for wrapper in SCRATCH_VALUABLES_WRAPPERS:
                self.assertTrue(wrapper.is_file(), f"missing wrapper: {wrapper}")
                with self.subTest(interp=Path(interp).stem, wrapper=str(wrapper.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        (root / ".scratch").mkdir()
                        envelope = json.dumps({"cwd": str(root)})
                        p = _run_ps1(interp, wrapper, stdin=envelope)
                        self.assertEqual(p.returncode, 0, p.stderr)
                        self.assertEqual(p.stdout.strip(), "",
                                         f"clean .scratch/ must be silent; got {p.stdout!r}")

    def test_silent_when_no_scratch_dir_exists(self) -> None:
        for interp in INTERPRETERS:
            for wrapper in SCRATCH_VALUABLES_WRAPPERS:
                with self.subTest(interp=Path(interp).stem, wrapper=str(wrapper.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        envelope = json.dumps({"cwd": td})
                        p = _run_ps1(interp, wrapper, stdin=envelope)
                        self.assertEqual(p.returncode, 0, p.stderr)
                        self.assertEqual(p.stdout.strip(), "",
                                         f"missing .scratch/ must be silent; got {p.stdout!r}")


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
