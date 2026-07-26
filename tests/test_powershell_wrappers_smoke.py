"""Smoke tests for the PowerShell (.ps1) hook + scanner wrappers.

The installer registers a .ps1 entry point as the WINDOWS hook command for the
 nine shared structural/audit hooks (check-bugfix-discipline, check-git-push-gate,
 check-passive-polling-stop, check-work-items-archival-stop,
check-machine-local-path, check-no-trash-in-repo, check-stale-relation-residue,
check-repository-orientation, check-mcp-momentum; the Claude line adds a tenth, the Claude-only check-typed-routing audit, covered by test_typed_routing_hook.py),
the two informational SessionStart reminders
(mcp-usage-reminder, agents-mode-reminder), and ships a .ps1 for the publication
scanner — yet NO test executed any .ps1, so a syntax error, a broken fail-open
path, or a regressed stdin pipe in the Windows entry point would have shipped
green (every other hook test drives the .py helper via sys.executable, never the
.ps1 the OS actually runs). These tests close that gap for BOTH the Claude
(src.claude/agents/{scripts,hooks}/) and Codex
(src.codex/skills/lead/{scripts,hooks}/) copies.

Three wrapper shapes, three contracts:

  * The nine shared structural/audit HOOK wrappers are thin stdin pipes around their .py helper. Contract:
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
import string
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CLAUDE_SCRIPTS = REPO_ROOT / "src.claude" / "agents" / "scripts"
CLAUDE_HOOKS = REPO_ROOT / "src.claude" / "agents" / "hooks"
CODEX_SCRIPTS = REPO_ROOT / "src.codex" / "skills" / "lead" / "scripts"
CODEX_HOOKS = REPO_ROOT / "src.codex" / "skills" / "lead" / "hooks"
PACK_VALIDATORS = (
    CLAUDE_SCRIPTS / "validate-skill-pack.ps1",
    CODEX_SCRIPTS / "validate-skill-pack.ps1",
)

# The nine stdin-piping structural/audit hook wrappers, in BOTH install trees (18 files).
HOOK_WRAPPERS = (
    CLAUDE_SCRIPTS / "check-bugfix-discipline.ps1",
    CLAUDE_SCRIPTS / "check-git-push-gate.ps1",
    CLAUDE_SCRIPTS / "check-passive-polling-stop.ps1",
    CLAUDE_SCRIPTS / "check-work-items-archival-stop.ps1",
    CLAUDE_HOOKS / "check-machine-local-path.ps1",
    CLAUDE_HOOKS / "check-no-trash-in-repo.ps1",
    CLAUDE_HOOKS / "check-stale-relation-residue.ps1",
    CLAUDE_HOOKS / "check-repository-orientation.ps1",
    CLAUDE_HOOKS / "check-mcp-momentum.ps1",
    CODEX_SCRIPTS / "check-bugfix-discipline.ps1",
    CODEX_SCRIPTS / "check-git-push-gate.ps1",
    CODEX_SCRIPTS / "check-passive-polling-stop.ps1",
    CODEX_SCRIPTS / "check-work-items-archival-stop.ps1",
    CODEX_HOOKS / "check-machine-local-path.ps1",
    CODEX_HOOKS / "check-no-trash-in-repo.ps1",
    CODEX_HOOKS / "check-stale-relation-residue.ps1",
    CODEX_HOOKS / "check-repository-orientation.ps1",
    CODEX_HOOKS / "check-mcp-momentum.ps1",
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
    "CONNECTED but uninitialized is not unavailable: do NOT skip a connected MCP reporting \"not initialized\", \"no index\", \"empty\", or \"no data yet\". Many servers require or build their own index/state on first use — when they report no index, INITIALIZE them per the server's own instructions (e.g. run a code-graph server's init / check its status; codegraph builds its initial index via `codegraph init`, then a file-watcher keeps it fresh) and use or await the result — never silently substitute ad-hoc shell/grep. Only a genuinely absent server (not connected, not installed, or absent from tool discovery) may be skipped with an explanation.",
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

# All four publication-gate/scanner PowerShell launchers that derive their
# bundled-bash search root from `git.exe`'s own install location: the two
# pack-mirrored check-publication-safety.ps1 copies above, the pack-neutral
# canon copy under scripts/universal-hooks/, and the standalone top-level
# check-publication-gate.ps1 convenience entrypoint. See
# work-items/bugs/2026-07-19-publication-gate-powershell-bash-resolution.md.
PUBLICATION_WRAPPERS = SCANNER_WRAPPERS + (
    REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "check-publication-safety.ps1",
    REPO_ROOT / "scripts" / "check-publication-gate.ps1",
)

# Runtime-assembled malformed-JSON probe (kept off one source line as a bare
# literal only for tidiness; it is plain ASCII junk that is not valid JSON).
MALFORMED_JSON = "not json at all " + "{" * 3

# Markers that prove the wrapper threw its OWN guarded diagnostic rather than
# crashing at the interpreter level. Any of these (or a clean delegate) is an
# acceptable deterministic outcome; a PowerShell ParserError is not.
_GUARDED_THROW_MARKERS = (
    "bundled bash",          # "Unable to locate a non-WSL bundled bash.exe or sh.exe ..."
    "Unable to resolve git",
    "Unable to determine repository root",
    "Unable to locate sibling check-publication-safety.sh",
)
# Substrings that indicate an UNHANDLED interpreter-level failure (a real bug in
# the wrapper source, not a guarded environment throw). The two binding-error
# markers catch the drive-root regression: when git.exe resolves two levels below
# a drive root, Split-Path -Parent of the install root is '' and an unguarded
# `Join-Path '' ...` for the grandparent candidates threw a
# ParameterBindingValidationException before any candidate/PATH-fallback probe.
_INTERPRETER_CRASH_MARKERS = (
    "ParserError",
    "is not recognized as the name of a cmdlet",
    "Missing closing",
    "Unexpected token",
    "CommandNotFoundException",
    "Cannot bind argument to parameter",
    "ParameterBindingValidationException",
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
        encoding="utf-8",
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


def _grandparent_bash_git() -> str | None:
    r"""A PATH git.exe whose 2-up install root has NO bundled bash but whose
    grandparent (3-up) DOES -- i.e. the .../Git/mingw64/bin/git.exe layout the
    root fix targets. parent(parent(git.exe)) yields .../Git/mingw64 (which has
    no bundled bash), whose parent .../Git carries bin/bash.exe. Returns None if
    no such git is on PATH (e.g. only a .../Git/cmd/git.exe whose 2-up root
    already has the bundled bash, which _bash_locatable_git() covers)."""
    sub = ("bin/bash.exe", "usr/bin/bash.exe", "usr/bin/sh.exe")
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if not d:
            continue
        g = Path(d) / "git.exe"
        if g.is_file():
            inst = g.parent.parent
            gp = inst.parent
            if (not any((inst / c).is_file() for c in sub)
                    and any((gp / c).is_file() for c in sub)):
                return str(g)
    return None


def _standalone_bundled_bash() -> Path | None:
    r"""A real Git-for-Windows MSYS2 bash that runs STANDALONE when copied with
    only its ``msys-2.0.dll``: a ``.../usr/bin/bash.exe`` (or ``sh.exe``) whose
    sibling ``msys-2.0.dll`` exists. The thin ``.../bin/bash.exe`` STUB is
    deliberately excluded -- it re-execs ``..\usr\bin\bash.exe`` and fails when
    copied alone, so it cannot back a synthetic grandparent fixture. Scans git.exe
    on PATH, checking the 2-up install root and its grandparent. Returns the
    bash.exe Path, or None when no standalone MSYS2 bash exists on the host (the
    synthetic root-fix test then skips -- there is nothing runnable to copy)."""
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if not d:
            continue
        g = Path(d) / "git.exe"
        if not g.is_file():
            continue
        for base in (g.parent.parent, g.parent.parent.parent):
            for name in ("bash.exe", "sh.exe"):
                cand = base / "usr" / "bin" / name
                if cand.is_file() and (cand.parent / "msys-2.0.dll").is_file():
                    return cand
    return None


# A real standalone MSYS2 bash to copy into the synthetic grandparent fixture
# (test_grandparent_bundled_bash_found_synthetic). None -> that test skips.
_STANDALONE_BASH = _standalone_bundled_bash()

# `subst` maps a free drive letter to a real dir WITHOUT admin, letting the
# drive-root crash test (test_drive_root_git_does_not_crash) synthesize a git.exe
# two levels below a REAL drive root -- the only way Split-Path -Parent of the
# install root returns ''. None on non-Windows / when subst is unavailable.
_SUBST = shutil.which("subst") if os.name == "nt" else None


def _free_drive_letter() -> str | None:
    """First unused drive letter (Z down to G) for a `subst` mapping, or None if
    every letter in that range is taken (a stale subst also reads as taken and is
    skipped). Windows-only helper for the drive-root crash-regression test."""
    for letter in reversed(string.ascii_uppercase[6:]):  # Z .. G
        if not Path(letter + ":" + chr(92)).exists():
            return letter
    return None


# The generalized WSL-reject filter has two INDEPENDENT arms; each genuineness
# helper below DISABLES one arm (byte level, LF preserved) in a copy of a
# launcher so a test can prove that arm is load-bearing, not a tautology of the
# other. The exact source-byte fragments are built via chr(92) so this test
# source carries no literal-backslash ambiguity of its own.
#   * _WINDOWSAPPS_ARM -- the `-match '[\\/]Microsoft[\\/]WindowsApps[\\/]'`
#     Store-alias regex. Neutralizing it to a never-match `(?!)` leaves only the
#     Windows-dir PREFIX arm, so a WindowsApps alias planted OUTSIDE the Windows
#     dir is then selected (proving the WindowsApps arm rejected it).
#   * _WINDIR_SEED -- the `@($env:SystemRoot, $env:windir, 'C:\Windows')` seed of
#     the Windows-dir prefix set. Replacing it with `@()` leaves only the
#     WindowsApps arm, so a Sysnative launcher under the (windir-pointed) Windows
#     dir is then selected -- proving the PREFIX arm, not a System32 substring,
#     is what rejects Sysnative.
_BS = chr(92)
_WINDOWSAPPS_ARM = ("'[" + _BS + _BS + "/]Microsoft[" + _BS + _BS
                    + "/]WindowsApps[" + _BS + _BS + "/]'").encode("utf-8")
_WINDOWSAPPS_ARM_DISABLED = "'(?!)'".encode("utf-8")
_WINDIR_SEED = ("@($env:SystemRoot, $env:windir, 'C:" + _BS + "Windows')").encode("utf-8")
_WINDIR_SEED_DISABLED = "@()".encode("utf-8")


def _disable_windowsapps_arm(src: Path, dst: Path) -> None:
    """Copy `src` to `dst` with the WindowsApps-alias reject arm neutralized to a
    never-matching regex, leaving the Windows-dir prefix arm intact. Asserts the
    arm is present exactly once so genuineness fails loudly on filter drift."""
    b = src.read_bytes()
    assert b.count(_WINDOWSAPPS_ARM) == 1, f"WindowsApps arm not found once in {src}"
    dst.write_bytes(b.replace(_WINDOWSAPPS_ARM, _WINDOWSAPPS_ARM_DISABLED))


def _disable_windows_dir_arm(src: Path, dst: Path) -> None:
    """Copy `src` to `dst` with the Windows-dir prefix arm neutralized (its
    prefix-seed replaced by an empty set), leaving the WindowsApps arm intact.
    Asserts the seed is present exactly once so genuineness fails loudly on
    filter drift."""
    b = src.read_bytes()
    assert b.count(_WINDIR_SEED) == 1, f"Windows-dir seed not found once in {src}"
    dst.write_bytes(b.replace(_WINDIR_SEED, _WINDIR_SEED_DISABLED))


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


# Fragment-assembled so this tracked source carries no literal machine-path
# token (mirrors the gate-safe fixture pattern in test_machine_local_path_hook.py).
_MLP_USERS_FRAGMENT = "Use" + "rs"

# The three AUDIT hooks (machine-local-path, no-trash-in-repo, stale-relation-residue)
# live in the typed hooks/ dir, each with an envelope that reliably trips a HIT.
AUDIT_HOOK_HIT_CASES = (
    ("check-machine-local-path.ps1", {"tool_input": {
        "file_path": "README.md", "content": f"see C:/{_MLP_USERS_FRAGMENT}/realuser/.claude/x",
    }}),
    ("check-no-trash-in-repo.ps1", {"tool_input": {"command": "git worktree add ../wt"}}),
    ("check-stale-relation-residue.ps1", {"tool_input": {
        "file_path": "docs/live-doc.md", "content": "this helper is a deprecated alias for the new one",
    }}),
)


@unittest.skipIf(not INTERPRETERS, "no PowerShell host (pwsh/powershell) on PATH")
class TestAuditHookWrappersExitOneOnHit(unittest.TestCase):
    """Regression coverage for the AUDIT hook wrappers' hit path, driven through
    the ACTUAL .ps1 entry point (a .py-only test would not catch a wrapper-level
    regression). A prior BLOCKER had these wrappers hard-code `exit 0`
    unconditionally, discarding the Python helper's real exit code; the fix at
    that time was to propagate exit 1 on a hit. That exit-1-plus-stderr channel
    was ITSELF later measured to reach nobody -- neither Claude Code 2.1.220
    (transcript-only, model-invisible) nor Codex CLI 0.145.0 (discarded
    entirely) -- so the delivery channel changed again: a hit now emits one line
    of JSON to stdout, `{"hookSpecificOutput":{"hookEventName":"PreToolUse",
    "additionalContext":"..."}}`, and the helper always exits 0 (see
    `hook_common.emit_advisory` and
    work-items/bugs/2026-07-26-mcp-reminder-uses-the-once-per-session-form-its-
    sibling-calls-broken.md). The wrapper's job is unchanged -- propagate
    whatever the Python helper returns/prints -- so this class now asserts exit
    0 plus a non-empty, well-formed stdout JSON advisory instead of exit 1 plus
    stderr. Fail-open (missing python/helper -> exit 0, silent) stays covered by
    TestHookWrappersFailOpen above."""

    def test_wrapper_exits_zero_and_warns_via_stdout_on_a_real_hit(self) -> None:
        for interp in INTERPRETERS:
            for name, envelope in AUDIT_HOOK_HIT_CASES:
                for wrapper in (CLAUDE_HOOKS / name, CODEX_HOOKS / name):
                    self.assertTrue(wrapper.is_file(), f"missing wrapper: {wrapper}")
                    with self.subTest(interp=Path(interp).stem, wrapper=str(wrapper.relative_to(REPO_ROOT))):
                        p = _run_ps1(interp, wrapper, stdin=json.dumps(envelope, ensure_ascii=False))
                        self.assertEqual(
                            p.returncode, 0,
                            f"expected exit 0 on a hit; stdout={p.stdout!r} stderr={p.stderr!r}",
                        )
                        self.assertEqual(p.stderr.strip(), "", "expected no stderr on a hit")
                        payload = json.loads(p.stdout)
                        specific = payload["hookSpecificOutput"]
                        self.assertEqual(specific["hookEventName"], "PreToolUse")
                        self.assertTrue(specific["additionalContext"].strip(), "expected a non-empty advisory")


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
        # The class-level skipIf guarantees GIT is not None whenever this runs;
        # the assert narrows the type for pyright the same way _bash_locatable_git()
        # callers already do below, rather than leaving `GIT: str | None` unguarded
        # in a subprocess.run() arg list.
        assert GIT is not None
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
        # See TestScannerWrapperNoCrash._clean_repo: the class-level skipIf
        # guarantees GIT is not None whenever this runs.
        assert GIT is not None
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


def _write_fake_cmd(path: Path, body: str) -> None:
    """Write a fake `.cmd` executable (mirrors the per-class `_write_cmd` helpers)
    that Get-Command -CommandType Application resolves on PATH."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("@echo off\r\n" + body, encoding="utf-8", newline="")


def _make_wsl_fixture_env(root: Path, *, include_path_shell: bool) -> tuple[dict, Path]:
    r"""Build a fully PATH-controlled env for the WSL-rejection tests.

    Plants a fake git whose derived install root (and its grandparent) have NO
    bundled bash (forcing the PATH fallback), plus the TWO real WSL launcher
    locations the generalized filter must reject:

      * ``<winsysroot>\System32\bash.cmd`` + ``sh.cmd`` -- the legacy WSL launcher
        UNDER the Windows dir. ``$env:windir`` is pointed at ``<winsysroot>`` (see
        below) so the launcher's Windows-dir PREFIX arm rejects it exactly as it
        would a real ``C:\Windows\System32`` one -- no ``\System32\`` substring
        rule involved.
      * ``<localappdata>\Microsoft\WindowsApps\bash.cmd`` + ``sh.cmd`` -- the
        Store-WSL execution alias, planted OUTSIDE ``<winsysroot>`` (its real home
        is the user profile, not the Windows dir), so ONLY the WindowsApps arm can
        reject it -- which keeps the WindowsApps-arm genuineness test honest.

    When include_path_shell is True, also plants a legitimate NON-WSL
    ``bash.cmd``/``sh.cmd`` on PATH AFTER both WSL dirs, so the launcher must SKIP
    both WSL candidates and select the legitimate one.

    ``$env:windir`` (NOT ``$env:SystemRoot``) is repointed at ``<winsysroot>``:
    overriding ``SystemRoot`` crashes Windows PowerShell 5.1 startup (it loads its
    managed runtime relative to it), whereas overriding only ``windir`` is
    tolerated by both hosts, and the launcher's prefix arm reads both -- so this
    exercises the real prefix code path on a synthetic Windows dir without
    touching the real one.

    PATH is FULLY REPLACED (no ambient dirs appended): the host's own real
    ``System32\bash.exe`` (WSL launcher) and its WindowsApps ``bash.exe`` execution
    alias would otherwise leak into ``Get-Command -All`` and make the outcome
    nondeterministic. The fake git echoes ``root`` so the publication wrappers'
    ``git rev-parse --show-toplevel`` resolves without a real repo (mirrors the
    existing PATH-fallback fixtures)."""
    marker = root / "shell.marker"
    git_dir = root / "fake-git" / "mingw64" / "bin"
    _write_fake_cmd(git_dir / "git.cmd", f"echo {root}\r\nexit /b 0\r\n")
    winsysroot = root / "winsysroot"
    system32_dir = winsysroot / "System32"
    _write_fake_cmd(
        system32_dir / "bash.cmd",
        ">>\"%ORCHESTRARIUM_SHELL_PROBE%\" echo system32-bash\r\nexit /b 0\r\n",
    )
    _write_fake_cmd(
        system32_dir / "sh.cmd",
        ">>\"%ORCHESTRARIUM_SHELL_PROBE%\" echo system32-sh\r\nexit /b 0\r\n",
    )
    # The Store-WSL execution alias's real home is the user profile
    # (...\AppData\Local\Microsoft\WindowsApps), NOT the Windows dir, so it is
    # planted OUTSIDE winsysroot: only the WindowsApps arm can catch it, which is
    # what makes the WindowsApps genuineness revert meaningful. Plant it right
    # AFTER the System32 dir so the filter must reject BOTH before reaching any
    # legitimate shell.
    windowsapps_dir = root / "localappdata" / "Microsoft" / "WindowsApps"
    _write_fake_cmd(
        windowsapps_dir / "bash.cmd",
        ">>\"%ORCHESTRARIUM_SHELL_PROBE%\" echo windowsapps-bash\r\nexit /b 0\r\n",
    )
    _write_fake_cmd(
        windowsapps_dir / "sh.cmd",
        ">>\"%ORCHESTRARIUM_SHELL_PROBE%\" echo windowsapps-sh\r\nexit /b 0\r\n",
    )
    path_entries = [str(git_dir), str(system32_dir), str(windowsapps_dir)]
    if include_path_shell:
        path_shells = root / "path-shells"
        _write_fake_cmd(
            path_shells / "bash.cmd",
            ">>\"%ORCHESTRARIUM_SHELL_PROBE%\" echo path-bash\r\nexit /b 0\r\n",
        )
        _write_fake_cmd(
            path_shells / "sh.cmd",
            ">>\"%ORCHESTRARIUM_SHELL_PROBE%\" echo path-sh\r\nexit /b 0\r\n",
        )
        path_entries.append(str(path_shells))
    env = dict(os.environ)
    env["ORCHESTRARIUM_SHELL_PROBE"] = str(marker)
    env["windir"] = str(winsysroot)
    env["PATH"] = os.pathsep.join(path_entries)
    return env, marker


def _make_sysnative_fixture_env(root: Path, *, include_path_shell: bool) -> tuple[dict, Path]:
    r"""Windows-dir PREFIX-arm fixture. Plants a single WSL launcher under
    ``<winsysroot>\Sysnative\`` (the 32-bit-process view of System32) with
    ``$env:windir`` -> ``<winsysroot>``, so the launcher's Windows-dir prefix arm
    must reject it EVEN THOUGH its path carries no ``\System32\`` segment -- the
    exact case the pre-fix per-alias filter kept missing. A single Windows-dir
    launcher (no competing System32) means a genuineness revert that disables the
    prefix arm selects ``sysnative-bash``, proving the prefix arm -- not a
    System32 substring -- is what rejects it. Mirrors ``_make_wsl_fixture_env``;
    PATH is fully replaced and the fake git echoes ``root``."""
    marker = root / "shell.marker"
    git_dir = root / "fake-git" / "mingw64" / "bin"
    _write_fake_cmd(git_dir / "git.cmd", f"echo {root}\r\nexit /b 0\r\n")
    winsysroot = root / "winsysroot"
    sysnative_dir = winsysroot / "Sysnative"
    _write_fake_cmd(
        sysnative_dir / "bash.cmd",
        ">>\"%ORCHESTRARIUM_SHELL_PROBE%\" echo sysnative-bash\r\nexit /b 0\r\n",
    )
    _write_fake_cmd(
        sysnative_dir / "sh.cmd",
        ">>\"%ORCHESTRARIUM_SHELL_PROBE%\" echo sysnative-sh\r\nexit /b 0\r\n",
    )
    path_entries = [str(git_dir), str(sysnative_dir)]
    if include_path_shell:
        path_shells = root / "path-shells"
        _write_fake_cmd(
            path_shells / "bash.cmd",
            ">>\"%ORCHESTRARIUM_SHELL_PROBE%\" echo path-bash\r\nexit /b 0\r\n",
        )
        _write_fake_cmd(
            path_shells / "sh.cmd",
            ">>\"%ORCHESTRARIUM_SHELL_PROBE%\" echo path-sh\r\nexit /b 0\r\n",
        )
        path_entries.append(str(path_shells))
    env = dict(os.environ)
    env["ORCHESTRARIUM_SHELL_PROBE"] = str(marker)
    env["windir"] = str(winsysroot)
    env["PATH"] = os.pathsep.join(path_entries)
    return env, marker


def _make_overreach_fixture_env(root: Path) -> tuple[dict, Path]:
    r"""Grandparent OVER-REACH fixture. A NONSTANDARD git layout whose 2-up
    install root leaf is NOT a mingw layer (``<root>\weird\tools\git.cmd`` ->
    install root ``<root>\weird``, leaf ``weird``), with an unrelated
    ``bash.exe`` planted at the grandparent bin (``<root>\bin\bash.exe``, the
    ``Join-Path $gitParentRoot 'bin\bash.exe'`` candidate). The leaf-gated
    grandparent probe must NOT add that candidate, so the launcher falls through
    to the legit PATH bash (marker == path-bash) instead of mis-selecting the
    unrelated grandparent bash. The grandparent bash.exe is an EMPTY file --
    enough for the pre-fix unconditional probe's Test-Path to select it, after
    which ``& <empty>.exe`` fails before any marker is written; so a path-bash
    marker proves the grandparent candidate was never even added. PATH is fully
    replaced and the fake git echoes ``root``."""
    marker = root / "shell.marker"
    git_dir = root / "weird" / "tools"
    _write_fake_cmd(git_dir / "git.cmd", f"echo {root}\r\nexit /b 0\r\n")
    grandparent_bash = root / "bin" / "bash.exe"
    grandparent_bash.parent.mkdir(parents=True, exist_ok=True)
    grandparent_bash.write_bytes(b"")
    path_shells = root / "path-shells"
    _write_fake_cmd(
        path_shells / "bash.cmd",
        ">>\"%ORCHESTRARIUM_SHELL_PROBE%\" echo path-bash\r\nexit /b 0\r\n",
    )
    _write_fake_cmd(
        path_shells / "sh.cmd",
        ">>\"%ORCHESTRARIUM_SHELL_PROBE%\" echo path-sh\r\nexit /b 0\r\n",
    )
    env = dict(os.environ)
    env["ORCHESTRARIUM_SHELL_PROBE"] = str(marker)
    env["PATH"] = os.pathsep.join((str(git_dir), str(path_shells)))
    return env, marker


@unittest.skipIf(not INTERPRETERS, "needs a PowerShell host on PATH")
class TestPackValidatorShellResolution(unittest.TestCase):
    @staticmethod
    def _write_cmd(path: Path, body: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("@echo off\r\n" + body, encoding="utf-8", newline="")

    @staticmethod
    def _copy_validator_fixture(root: Path, validator: Path) -> Path:
        scripts = root / "pack" / "scripts"
        scripts.mkdir(parents=True)
        copied = scripts / "validate-skill-pack.ps1"
        shutil.copy2(validator, copied)
        (scripts / "validate-skill-pack.sh").write_text(
            "#!/usr/bin/env bash\n"
            "printf 'derived-root\\n' >> \"$ORCHESTRARIUM_SHELL_PROBE\"\n"
            "exit 0\n",
            encoding="utf-8",
            newline="\n",
        )
        return copied

    def _path_shell_env(self, root: Path, git_dir: Path) -> tuple[dict, Path]:
        marker = root / "shell.marker"
        path_shells = root / "path-shells"
        self._write_cmd(
            path_shells / "bash.cmd",
            ">>\"%ORCHESTRARIUM_SHELL_PROBE%\" echo path-bash\r\nexit /b 0\r\n",
        )
        self._write_cmd(
            path_shells / "sh.cmd",
            ">>\"%ORCHESTRARIUM_SHELL_PROBE%\" echo path-sh\r\nexit /b 0\r\n",
        )
        env = dict(os.environ)
        env["ORCHESTRARIUM_SHELL_PROBE"] = str(marker)
        env["PATH"] = os.pathsep.join((str(git_dir), str(path_shells), env.get("PATH", "")))
        return env, marker

    def test_path_fallback_uses_bash_after_derived_root_candidates_miss(self) -> None:
        for interp in INTERPRETERS:
            for validator in PACK_VALIDATORS:
                with self.subTest(interp=Path(interp).stem, validator=str(validator.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_validator_fixture(root, validator)
                        git_dir = root / "fake-git" / "mingw64" / "bin"
                        self._write_cmd(
                            git_dir / "git.cmd",
                            f"echo {root}\r\nexit /b 0\r\n",
                        )
                        env, marker = self._path_shell_env(root, git_dir)

                        p = _run_ps1(interp, copied, cwd=str(root), env=env)

                        self.assertEqual(
                            p.returncode,
                            0,
                            "PATH bash fallback must run after all derived-root candidates miss; "
                            f"stdout={p.stdout!r} stderr={p.stderr!r}",
                        )
                        self.assertEqual(marker.read_text(encoding="utf-8").splitlines(), ["path-bash"])

    def test_derived_root_bash_precedes_path_bash(self) -> None:
        bashable_git = _bash_locatable_git()
        if bashable_git is None:
            self.skipTest("no PATH git whose derived install root contains bash/sh")
        git_dir = Path(bashable_git).parent

        for interp in INTERPRETERS:
            for validator in PACK_VALIDATORS:
                with self.subTest(interp=Path(interp).stem, validator=str(validator.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_validator_fixture(root, validator)
                        env, marker = self._path_shell_env(root, git_dir)

                        p = _run_ps1(interp, copied, cwd=str(root), env=env)

                        self.assertEqual(
                            p.returncode,
                            0,
                            "derived-root bash must run before PATH fallback; "
                            f"stdout={p.stdout!r} stderr={p.stderr!r}",
                        )
                        self.assertEqual(marker.read_text(encoding="utf-8").splitlines(), ["derived-root"])

    def test_system32_wsl_bash_is_skipped_for_non_system32_path_bash(self) -> None:
        r"""WSL-rejection regression: when the PATH fallback runs, a
        ``System32\bash.cmd`` (the WSL launcher, which cannot resolve
        ``C:\Users\...`` paths) placed AHEAD of a legitimate non-System32 PATH
        bash must be SKIPPED, not selected. Before the fix the fallback took the
        first Get-Command match, which on Windows is usually the System32 WSL
        bash (see the documented gotcha at scripts/install-codex.ps1). The fixture
        also plants a Microsoft\WindowsApps alias bash between System32 and the
        legitimate shell, so reaching path-bash proves BOTH WSL launchers are
        skipped (the dedicated WindowsApps genuineness test proves that arm)."""
        for interp in INTERPRETERS:
            for validator in PACK_VALIDATORS:
                with self.subTest(interp=Path(interp).stem, validator=str(validator.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_validator_fixture(root, validator)
                        env, marker = _make_wsl_fixture_env(root, include_path_shell=True)

                        p = _run_ps1(interp, copied, cwd=str(root), env=env)

                        self.assertEqual(
                            p.returncode,
                            0,
                            "non-System32 PATH bash must be selected over the System32 WSL bash; "
                            f"stdout={p.stdout!r} stderr={p.stderr!r}",
                        )
                        self.assertEqual(
                            marker.read_text(encoding="utf-8").splitlines(),
                            ["path-bash"],
                            "the System32 WSL bash must be skipped, never executed",
                        )

    def test_only_system32_bash_available_fails_closed(self) -> None:
        r"""When the ONLY bash/sh on PATH are WSL launchers (a System32 dir AND a
        Microsoft\WindowsApps alias, both now planted by the fixture), the
        fallback must FAIL CLOSED (throw the guarded bundled-bash diagnostic),
        never silently run WSL bash."""
        for interp in INTERPRETERS:
            for validator in PACK_VALIDATORS:
                with self.subTest(interp=Path(interp).stem, validator=str(validator.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_validator_fixture(root, validator)
                        env, marker = _make_wsl_fixture_env(root, include_path_shell=False)

                        p = _run_ps1(interp, copied, cwd=str(root), env=env)

                        self.assertNotEqual(
                            p.returncode,
                            0,
                            "only a System32 WSL bash present must FAIL, not run WSL bash; "
                            f"stdout={p.stdout!r} stderr={p.stderr!r}",
                        )
                        self.assertIn(
                            "bundled bash", p.stdout + p.stderr,
                            "expected the guarded bundled-bash throw",
                        )
                        self.assertFalse(
                            marker.exists(),
                            "the System32 WSL bash must never be executed",
                        )

    def test_grandparent_bundled_bash_found_for_mingw64_git(self) -> None:
        r"""Root fix: when git resolves via .../Git/mingw64/bin/git.exe, the 2-up
        install root (.../Git/mingw64) has NO bundled bash, but the grandparent
        (.../Git) does. The launcher must probe the grandparent and run that
        bundled bash (derived-root success), NOT fall through to the WSL-prone
        PATH fallback. A path-shells bash is planted so that WITHOUT the
        grandparent probe the marker would record 'path-bash'; asserting
        'derived-root' proves the grandparent candidate is what actually ran."""
        grandparent_git = _grandparent_bash_git()
        if grandparent_git is None:
            self.skipTest("no PATH git with a mingw64-style (2-up-miss / grandparent-hit) bundled bash")
        git_dir = Path(grandparent_git).parent
        for interp in INTERPRETERS:
            for validator in PACK_VALIDATORS:
                with self.subTest(interp=Path(interp).stem, validator=str(validator.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_validator_fixture(root, validator)
                        env, marker = self._path_shell_env(root, git_dir)

                        p = _run_ps1(interp, copied, cwd=str(root), env=env)

                        self.assertEqual(
                            p.returncode,
                            0,
                            "grandparent bundled bash must run for a mingw64-style git; "
                            f"stdout={p.stdout!r} stderr={p.stderr!r}",
                        )
                        self.assertEqual(
                            marker.read_text(encoding="utf-8").splitlines(),
                            ["derived-root"],
                            "the grandparent bundled bash must run, not the PATH fallback",
                        )

    def test_drive_root_git_does_not_crash(self) -> None:
        r"""Regression (de7aa1c0 follow-up): when git.exe resolves two levels below
        a DRIVE ROOT (e.g. X:\cmd\git.exe), Split-Path -Parent of the install root
        (X:\) is '', so the grandparent `Join-Path '' ...` candidate additions threw
        a ParameterBindingValidationException BEFORE any candidate or the PATH
        fallback was probed. Guarding those additions behind `if ($gitParentRoot)`
        must let the launcher reach a usable non-WSL PATH bash (marker == path-bash),
        never an interpreter binding error. A real drive root is synthesized with
        `subst`; skipped on non-Windows or when no drive letter is free."""
        if _SUBST is None:
            self.skipTest("subst unavailable (non-Windows host)")
        letter = _free_drive_letter()
        if letter is None:
            self.skipTest("no free drive letter for the subst drive-root fixture")
        for interp in INTERPRETERS:
            for validator in PACK_VALIDATORS:
                with self.subTest(interp=Path(interp).stem, validator=str(validator.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_validator_fixture(root, validator)
                        drive_dir = root / "driveroot"
                        # _write_cmd creates the parent dirs; git.cmd echoes a valid
                        # dir so the null-safe rev-parse resolves.
                        self._write_cmd(drive_dir / "cmd" / "git.cmd", f"echo {root}\r\nexit /b 0\r\n")
                        cp = subprocess.run([_SUBST, letter + ":", str(drive_dir)],
                                            capture_output=True, text=True)
                        if cp.returncode != 0:
                            self.skipTest(f"subst mapping failed: {cp.stderr.strip()}")
                        try:
                            env, marker = self._path_shell_env(root, Path(letter + ":" + chr(92) + "cmd"))
                            p = _run_ps1(interp, copied, cwd=str(root), env=env)
                            combined = p.stdout + p.stderr
                            for m in _INTERPRETER_CRASH_MARKERS:
                                self.assertNotIn(
                                    m, combined,
                                    f"drive-root git must not crash the interpreter ({m!r}):\n{combined}",
                                )
                            self.assertEqual(
                                p.returncode, 0,
                                f"drive-root git must reach the non-WSL PATH bash; {combined}",
                            )
                            self.assertEqual(
                                marker.read_text(encoding="utf-8").splitlines(), ["path-bash"],
                                "the guarded launcher must fall through to the PATH bash",
                            )
                        finally:
                            subprocess.run([_SUBST, letter + ":", "/d"], capture_output=True)

    def test_grandparent_bundled_bash_found_synthetic(self) -> None:
        r"""Root-fix coverage independent of the host git's natural layout: build a
        SYNTHETIC mingw64 git tree -- a fake .../mingw64/bin/git.cmd whose 2-up
        install root (.../mingw64) has NO bundled bash, over a REAL standalone MSYS2
        bash copied to the grandparent .../usr/bin/bash.exe. The launcher must probe
        the grandparent and run that bundled bash (marker == derived-root), NOT the
        WSL-prone PATH fallback (a planted path-shells bash would record path-bash).
        Unlike test_grandparent_bundled_bash_found_for_mingw64_git (which needs a
        naturally mingw64-layout git on PATH), this runs on ANY host with a
        standalone MSYS2 bash to copy; skipped only when none exists."""
        if _STANDALONE_BASH is None:
            self.skipTest("no standalone MSYS2 bash (usr/bin/bash.exe + msys-2.0.dll) on host to copy")
        for interp in INTERPRETERS:
            for validator in PACK_VALIDATORS:
                with self.subTest(interp=Path(interp).stem, validator=str(validator.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_validator_fixture(root, validator)
                        git_dir = root / "synth" / "mingw64" / "bin"
                        self._write_cmd(git_dir / "git.cmd", f"echo {root}\r\nexit /b 0\r\n")
                        gp_usr_bin = root / "synth" / "usr" / "bin"
                        gp_usr_bin.mkdir(parents=True)
                        shutil.copy2(_STANDALONE_BASH, gp_usr_bin / "bash.exe")
                        shutil.copy2(_STANDALONE_BASH.parent / "msys-2.0.dll", gp_usr_bin / "msys-2.0.dll")
                        env, marker = self._path_shell_env(root, git_dir)
                        p = _run_ps1(interp, copied, cwd=str(root), env=env)
                        self.assertEqual(
                            p.returncode, 0,
                            "synthetic grandparent bundled bash must run for a mingw64-style git; "
                            f"stdout={p.stdout!r} stderr={p.stderr!r}",
                        )
                        self.assertEqual(
                            marker.read_text(encoding="utf-8").splitlines(),
                            ["derived-root"],
                            "the copied grandparent bundled bash must run, not the PATH fallback",
                        )

    def test_windowsapps_alias_rejected_and_rejection_is_load_bearing(self) -> None:
        r"""WindowsApps rejection + genuineness in one. With the full filter a
        System32 (Windows-dir prefix arm) AND a Microsoft\WindowsApps (Store-alias
        arm) WSL launcher planted ahead of a legitimate PATH bash must BOTH be
        skipped (marker == path-bash). Genuineness: a copy whose WindowsApps arm
        is disabled does NOT reject the WindowsApps alias -- planted outside the
        Windows dir, the prefix arm cannot catch it either -- and selects it
        (marker == windowsapps-bash), proving the WindowsApps arm is load-bearing,
        not a tautology of the Windows-dir arm."""
        for interp in INTERPRETERS:
            for validator in PACK_VALIDATORS:
                with self.subTest(interp=Path(interp).stem, validator=str(validator.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_validator_fixture(root, validator)
                        env, marker = _make_wsl_fixture_env(root, include_path_shell=True)
                        p = _run_ps1(interp, copied, cwd=str(root), env=env)
                        self.assertEqual(
                            p.returncode, 0,
                            f"full filter must reach the legit PATH bash; stderr={p.stderr!r}",
                        )
                        self.assertEqual(
                            marker.read_text(encoding="utf-8").splitlines(),
                            ["path-bash"],
                            "System32 AND WindowsApps WSL launchers must both be skipped",
                        )
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_validator_fixture(root, validator)
                        _disable_windowsapps_arm(validator, copied)
                        env, marker = _make_wsl_fixture_env(root, include_path_shell=True)
                        p = _run_ps1(interp, copied, cwd=str(root), env=env)
                        self.assertEqual(
                            marker.read_text(encoding="utf-8").splitlines(),
                            ["windowsapps-bash"],
                            "disabling the WindowsApps arm selects the WindowsApps WSL alias -- "
                            "the WindowsApps arm is load-bearing",
                        )

    def test_sysnative_wsl_bash_rejected_and_rejection_is_load_bearing(self) -> None:
        r"""Sysnative rejection + genuineness (ends the per-alias chase). The
        Windows-dir PREFIX arm must reject a ...\winsysroot\Sysnative\bash.cmd
        (windir -> winsysroot) even though its path has NO \System32\ segment,
        selecting the legit PATH bash (marker == path-bash). Genuineness: a copy
        whose Windows-dir arm is disabled does NOT reject Sysnative and selects it
        (marker == sysnative-bash) -- proving the prefix arm, not a System32
        substring, catches Sysnative (it would slip a narrow \System32\-only
        filter, which is exactly round-4 of the blacklist chase this generalizes
        away)."""
        for interp in INTERPRETERS:
            for validator in PACK_VALIDATORS:
                with self.subTest(interp=Path(interp).stem, validator=str(validator.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_validator_fixture(root, validator)
                        env, marker = _make_sysnative_fixture_env(root, include_path_shell=True)
                        p = _run_ps1(interp, copied, cwd=str(root), env=env)
                        self.assertEqual(
                            p.returncode, 0,
                            f"Windows-dir prefix arm must reach the legit PATH bash; stderr={p.stderr!r}",
                        )
                        self.assertEqual(
                            marker.read_text(encoding="utf-8").splitlines(),
                            ["path-bash"],
                            "the Sysnative WSL launcher must be skipped",
                        )
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_validator_fixture(root, validator)
                        _disable_windows_dir_arm(validator, copied)
                        env, marker = _make_sysnative_fixture_env(root, include_path_shell=True)
                        p = _run_ps1(interp, copied, cwd=str(root), env=env)
                        self.assertEqual(
                            marker.read_text(encoding="utf-8").splitlines(),
                            ["sysnative-bash"],
                            "disabling the Windows-dir prefix arm selects Sysnative -- "
                            "the prefix arm (not a System32 substring) is load-bearing",
                        )

    def test_grandparent_not_probed_for_nonstandard_git_layout(self) -> None:
        r"""Over-reach fix: the grandparent bundled-bash probe is gated on
        $gitInstallRoot's leaf being a mingw layer, so a NONSTANDARD git layout
        (leaf 'weird') never mis-selects an unrelated <grandparent>\bin\bash.exe.
        The unrelated grandparent bash is present but must be skipped; the
        launcher falls through to the legit PATH bash (marker == path-bash).
        Genuine: under the pre-fix unconditional `if ($gitParentRoot)` probe that
        empty grandparent bash.exe would be Test-Path-selected and the run would
        never reach path-bash."""
        for interp in INTERPRETERS:
            for validator in PACK_VALIDATORS:
                with self.subTest(interp=Path(interp).stem, validator=str(validator.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_validator_fixture(root, validator)
                        env, marker = _make_overreach_fixture_env(root)
                        p = _run_ps1(interp, copied, cwd=str(root), env=env)
                        self.assertEqual(
                            p.returncode, 0,
                            "nonstandard-layout git must reach the legit PATH bash; "
                            f"stdout={p.stdout!r} stderr={p.stderr!r}",
                        )
                        self.assertEqual(
                            marker.read_text(encoding="utf-8").splitlines(),
                            ["path-bash"],
                            "the unrelated grandparent bash must not be probed or selected",
                        )


@unittest.skipIf(not INTERPRETERS, "needs a PowerShell host on PATH")
class TestPublicationWrapperShellResolution(unittest.TestCase):
    """PATH-fallback regression for the publication-safety/gate launchers.

    The derived-root-only bundled-shell resolution fixed for the two pack
    validators in commit 9d6afb88 (see TestPackValidatorShellResolution
    above) was duplicated verbatim in these four publication wrappers and
    needed the identical PATH-after-derived-root-miss fix: see
    work-items/bugs/2026-07-19-publication-gate-powershell-bash-resolution.md.
    Fixture shape mirrors TestPackValidatorShellResolution, generalized to
    each wrapper's own sibling .sh name (wrapper.stem + '.sh') since these
    four wrappers do not share one sibling script name."""

    @staticmethod
    def _write_cmd(path: Path, body: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("@echo off\r\n" + body, encoding="utf-8", newline="")

    @staticmethod
    def _copy_wrapper_fixture(root: Path, wrapper: Path) -> Path:
        scripts = root / "pack" / "scripts"
        scripts.mkdir(parents=True)
        copied = scripts / wrapper.name
        shutil.copy2(wrapper, copied)
        (scripts / f"{wrapper.stem}.sh").write_text(
            "#!/usr/bin/env bash\n"
            "printf 'derived-root\\n' >> \"$ORCHESTRARIUM_SHELL_PROBE\"\n"
            "exit 0\n",
            encoding="utf-8",
            newline="\n",
        )
        return copied

    def _path_shell_env(self, root: Path, git_dir: Path) -> tuple[dict, Path]:
        marker = root / "shell.marker"
        path_shells = root / "path-shells"
        self._write_cmd(
            path_shells / "bash.cmd",
            ">>\"%ORCHESTRARIUM_SHELL_PROBE%\" echo path-bash\r\nexit /b 0\r\n",
        )
        self._write_cmd(
            path_shells / "sh.cmd",
            ">>\"%ORCHESTRARIUM_SHELL_PROBE%\" echo path-sh\r\nexit /b 0\r\n",
        )
        env = dict(os.environ)
        env["ORCHESTRARIUM_SHELL_PROBE"] = str(marker)
        env["PATH"] = os.pathsep.join((str(git_dir), str(path_shells), env.get("PATH", "")))
        return env, marker

    def test_path_fallback_uses_bash_after_derived_root_candidates_miss(self) -> None:
        for interp in INTERPRETERS:
            for wrapper in PUBLICATION_WRAPPERS:
                with self.subTest(interp=Path(interp).stem, wrapper=str(wrapper.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_wrapper_fixture(root, wrapper)
                        git_dir = root / "fake-git" / "mingw64" / "bin"
                        self._write_cmd(
                            git_dir / "git.cmd",
                            f"echo {root}\r\nexit /b 0\r\n",
                        )
                        env, marker = self._path_shell_env(root, git_dir)

                        p = _run_ps1(interp, copied, cwd=str(root), env=env)

                        self.assertEqual(
                            p.returncode,
                            0,
                            "PATH bash fallback must run after all derived-root candidates miss; "
                            f"stdout={p.stdout!r} stderr={p.stderr!r}",
                        )
                        self.assertEqual(marker.read_text(encoding="utf-8").splitlines(), ["path-bash"])

    def test_derived_root_bash_precedes_path_bash(self) -> None:
        bashable_git = _bash_locatable_git()
        if bashable_git is None:
            self.skipTest("no PATH git whose derived install root contains bash/sh")
        git_dir = Path(bashable_git).parent

        for interp in INTERPRETERS:
            for wrapper in PUBLICATION_WRAPPERS:
                with self.subTest(interp=Path(interp).stem, wrapper=str(wrapper.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_wrapper_fixture(root, wrapper)
                        # These publication wrappers `git rev-parse --show-toplevel`
                        # before invoking their sibling .sh, so the fixture must be a
                        # real repo -- a non-repo cwd now hits the wrappers' own
                        # guarded `throw "Unable to determine repository root."`
                        # (null-safe rev-parse fixed 2026-07-26, mirroring the
                        # validators' pattern: validate-skill-pack.ps1:~101, `2>$null`
                        # + a $LASTEXITCODE guard) rather than the shell-precedence
                        # path this test targets. Without this init, the wrapper
                        # throws that clean error and the shell-precedence assertion
                        # can never be reached.
                        subprocess.run(
                            [bashable_git, "init", "-q", str(root)],
                            check=True, capture_output=True,
                        )
                        env, marker = self._path_shell_env(root, git_dir)

                        p = _run_ps1(interp, copied, cwd=str(root), env=env)

                        self.assertEqual(
                            p.returncode,
                            0,
                            "derived-root bash must run before PATH fallback; "
                            f"stdout={p.stdout!r} stderr={p.stderr!r}",
                        )
                        self.assertEqual(marker.read_text(encoding="utf-8").splitlines(), ["derived-root"])

    def test_system32_wsl_bash_is_skipped_for_non_system32_path_bash(self) -> None:
        r"""WSL-rejection regression for the publication launchers: a
        ``System32\bash.cmd`` placed ahead of a legitimate non-System32 PATH bash
        must be SKIPPED so the launcher selects the non-System32 one. The fixture
        also plants a Microsoft\WindowsApps alias bash between them, so reaching
        path-bash proves both WSL launchers are skipped. Mirrors the validator
        case in TestPackValidatorShellResolution; the fix is identical across all
        six shell-resolving launchers."""
        for interp in INTERPRETERS:
            for wrapper in PUBLICATION_WRAPPERS:
                with self.subTest(interp=Path(interp).stem, wrapper=str(wrapper.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_wrapper_fixture(root, wrapper)
                        # The fake git echoes root, so these wrappers'
                        # `git rev-parse --show-toplevel` resolves without a real
                        # repo (see test_path_fallback_uses_bash_after_derived_root_candidates_miss).
                        env, marker = _make_wsl_fixture_env(root, include_path_shell=True)

                        p = _run_ps1(interp, copied, cwd=str(root), env=env)

                        self.assertEqual(
                            p.returncode,
                            0,
                            "non-System32 PATH bash must be selected over the System32 WSL bash; "
                            f"stdout={p.stdout!r} stderr={p.stderr!r}",
                        )
                        self.assertEqual(
                            marker.read_text(encoding="utf-8").splitlines(),
                            ["path-bash"],
                            "the System32 WSL bash must be skipped, never executed",
                        )

    def test_only_system32_bash_available_fails_closed(self) -> None:
        r"""When the ONLY bash/sh on PATH are WSL launchers (a System32 dir AND a
        Microsoft\WindowsApps alias, both now planted by the fixture), the
        publication launchers must FAIL CLOSED (guarded bundled-bash throw),
        never silently run WSL bash."""
        for interp in INTERPRETERS:
            for wrapper in PUBLICATION_WRAPPERS:
                with self.subTest(interp=Path(interp).stem, wrapper=str(wrapper.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_wrapper_fixture(root, wrapper)
                        env, marker = _make_wsl_fixture_env(root, include_path_shell=False)

                        p = _run_ps1(interp, copied, cwd=str(root), env=env)

                        self.assertNotEqual(
                            p.returncode,
                            0,
                            "only a System32 WSL bash present must FAIL, not run WSL bash; "
                            f"stdout={p.stdout!r} stderr={p.stderr!r}",
                        )
                        self.assertIn(
                            "bundled bash", p.stdout + p.stderr,
                            "expected the guarded bundled-bash throw",
                        )
                        self.assertFalse(
                            marker.exists(),
                            "the System32 WSL bash must never be executed",
                        )

    def test_grandparent_bundled_bash_found_for_mingw64_git(self) -> None:
        r"""Root fix (publication launchers): a mingw64-style git
        (.../Git/mingw64/bin/git.exe) whose 2-up install root has no bundled bash
        but whose grandparent (.../Git) does must resolve the grandparent bundled
        bash, NOT the WSL-prone PATH fallback. Mirrors the validator case; these
        wrappers additionally rev-parse, so the fixture root is git-init'd."""
        grandparent_git = _grandparent_bash_git()
        if grandparent_git is None:
            self.skipTest("no PATH git with a mingw64-style (2-up-miss / grandparent-hit) bundled bash")
        git_dir = Path(grandparent_git).parent
        for interp in INTERPRETERS:
            for wrapper in PUBLICATION_WRAPPERS:
                with self.subTest(interp=Path(interp).stem, wrapper=str(wrapper.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_wrapper_fixture(root, wrapper)
                        # These wrappers rev-parse (null-safely, since 2026-07-26);
                        # a non-repo cwd would still throw a guarded error before
                        # shell resolution, so init a real repo (see
                        # test_derived_root_bash_precedes_path_bash).
                        subprocess.run(
                            [grandparent_git, "init", "-q", str(root)],
                            check=True, capture_output=True,
                        )
                        env, marker = self._path_shell_env(root, git_dir)

                        p = _run_ps1(interp, copied, cwd=str(root), env=env)

                        self.assertEqual(
                            p.returncode,
                            0,
                            "grandparent bundled bash must run for a mingw64-style git; "
                            f"stdout={p.stdout!r} stderr={p.stderr!r}",
                        )
                        self.assertEqual(
                            marker.read_text(encoding="utf-8").splitlines(),
                            ["derived-root"],
                            "the grandparent bundled bash must run, not the PATH fallback",
                        )

    def test_drive_root_git_does_not_crash(self) -> None:
        r"""Regression (de7aa1c0 follow-up) for the publication launchers: when
        git.exe resolves two levels below a DRIVE ROOT (e.g. X:\cmd\git.exe),
        Split-Path -Parent of the install root (X:\) is '', so the grandparent
        `Join-Path '' ...` candidate additions threw a
        ParameterBindingValidationException before any candidate or the PATH
        fallback was probed. Guarding those additions behind `if ($gitParentRoot)`
        must let the launcher reach a usable non-WSL PATH bash (marker == path-bash),
        never an interpreter binding error. A real drive root is synthesized with
        `subst`; skipped on non-Windows or when no drive letter is free."""
        if _SUBST is None:
            self.skipTest("subst unavailable (non-Windows host)")
        letter = _free_drive_letter()
        if letter is None:
            self.skipTest("no free drive letter for the subst drive-root fixture")
        for interp in INTERPRETERS:
            for wrapper in PUBLICATION_WRAPPERS:
                with self.subTest(interp=Path(interp).stem, wrapper=str(wrapper.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_wrapper_fixture(root, wrapper)
                        drive_dir = root / "driveroot"
                        # These wrappers rev-parse (null-safely, since 2026-07-26);
                        # the fake git echoes a valid dir with exit 0, so the
                        # null-safe capture resolves it and Set-Location succeeds
                        # without a real repo.
                        self._write_cmd(drive_dir / "cmd" / "git.cmd", f"echo {root}\r\nexit /b 0\r\n")
                        cp = subprocess.run([_SUBST, letter + ":", str(drive_dir)],
                                            capture_output=True, text=True)
                        if cp.returncode != 0:
                            self.skipTest(f"subst mapping failed: {cp.stderr.strip()}")
                        try:
                            env, marker = self._path_shell_env(root, Path(letter + ":" + chr(92) + "cmd"))
                            p = _run_ps1(interp, copied, cwd=str(root), env=env)
                            combined = p.stdout + p.stderr
                            for m in _INTERPRETER_CRASH_MARKERS:
                                self.assertNotIn(
                                    m, combined,
                                    f"drive-root git must not crash the interpreter ({m!r}):\n{combined}",
                                )
                            self.assertEqual(
                                p.returncode, 0,
                                f"drive-root git must reach the non-WSL PATH bash; {combined}",
                            )
                            self.assertEqual(
                                marker.read_text(encoding="utf-8").splitlines(), ["path-bash"],
                                "the guarded launcher must fall through to the PATH bash",
                            )
                        finally:
                            subprocess.run([_SUBST, letter + ":", "/d"], capture_output=True)

    def test_grandparent_bundled_bash_found_synthetic(self) -> None:
        r"""Root-fix coverage independent of the host git's natural layout, for the
        publication launchers: build a SYNTHETIC mingw64 git tree -- a fake
        .../mingw64/bin/git.cmd whose 2-up install root has NO bundled bash, over a
        REAL standalone MSYS2 bash copied to the grandparent .../usr/bin/bash.exe.
        The launcher must probe the grandparent and run that bundled bash
        (marker == derived-root), not the WSL-prone PATH fallback. Unlike
        test_grandparent_bundled_bash_found_for_mingw64_git (which needs a naturally
        mingw64-layout git on PATH), this runs on ANY host with a standalone MSYS2
        bash to copy; skipped only when none exists."""
        if _STANDALONE_BASH is None:
            self.skipTest("no standalone MSYS2 bash (usr/bin/bash.exe + msys-2.0.dll) on host to copy")
        for interp in INTERPRETERS:
            for wrapper in PUBLICATION_WRAPPERS:
                with self.subTest(interp=Path(interp).stem, wrapper=str(wrapper.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_wrapper_fixture(root, wrapper)
                        git_dir = root / "synth" / "mingw64" / "bin"
                        self._write_cmd(git_dir / "git.cmd", f"echo {root}\r\nexit /b 0\r\n")
                        gp_usr_bin = root / "synth" / "usr" / "bin"
                        gp_usr_bin.mkdir(parents=True)
                        shutil.copy2(_STANDALONE_BASH, gp_usr_bin / "bash.exe")
                        shutil.copy2(_STANDALONE_BASH.parent / "msys-2.0.dll", gp_usr_bin / "msys-2.0.dll")
                        env, marker = self._path_shell_env(root, git_dir)
                        p = _run_ps1(interp, copied, cwd=str(root), env=env)
                        self.assertEqual(
                            p.returncode, 0,
                            "synthetic grandparent bundled bash must run for a mingw64-style git; "
                            f"stdout={p.stdout!r} stderr={p.stderr!r}",
                        )
                        self.assertEqual(
                            marker.read_text(encoding="utf-8").splitlines(),
                            ["derived-root"],
                            "the copied grandparent bundled bash must run, not the PATH fallback",
                        )

    def test_windowsapps_alias_rejected_and_rejection_is_load_bearing(self) -> None:
        r"""WindowsApps rejection + genuineness for the publication launchers.
        Mirrors the validator case: the full filter skips a System32 (Windows-dir
        prefix arm) AND a Microsoft\WindowsApps (Store-alias arm) WSL launcher
        (marker == path-bash), while a copy whose WindowsApps arm is disabled
        selects the WindowsApps alias planted outside the Windows dir
        (marker == windowsapps-bash), proving the WindowsApps arm is
        load-bearing. The fake git echoes root, so no real repo is needed."""
        for interp in INTERPRETERS:
            for wrapper in PUBLICATION_WRAPPERS:
                with self.subTest(interp=Path(interp).stem, wrapper=str(wrapper.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_wrapper_fixture(root, wrapper)
                        env, marker = _make_wsl_fixture_env(root, include_path_shell=True)
                        p = _run_ps1(interp, copied, cwd=str(root), env=env)
                        self.assertEqual(
                            p.returncode, 0,
                            f"full filter must reach the legit PATH bash; stderr={p.stderr!r}",
                        )
                        self.assertEqual(
                            marker.read_text(encoding="utf-8").splitlines(),
                            ["path-bash"],
                            "System32 AND WindowsApps WSL launchers must both be skipped",
                        )
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_wrapper_fixture(root, wrapper)
                        _disable_windowsapps_arm(wrapper, copied)
                        env, marker = _make_wsl_fixture_env(root, include_path_shell=True)
                        p = _run_ps1(interp, copied, cwd=str(root), env=env)
                        self.assertEqual(
                            marker.read_text(encoding="utf-8").splitlines(),
                            ["windowsapps-bash"],
                            "disabling the WindowsApps arm selects the WindowsApps WSL alias -- "
                            "the WindowsApps arm is load-bearing",
                        )

    def test_sysnative_wsl_bash_rejected_and_rejection_is_load_bearing(self) -> None:
        r"""Sysnative rejection + genuineness for the publication launchers (ends
        the per-alias chase). The Windows-dir PREFIX arm must reject a
        ...\winsysroot\Sysnative\bash.cmd (windir -> winsysroot) even though its
        path has no \System32\ segment (marker == path-bash). Genuineness: a copy
        whose Windows-dir arm is disabled selects Sysnative (marker ==
        sysnative-bash), proving the prefix arm -- not a System32 substring --
        rejects it. The fake git echoes root, so no real repo is needed."""
        for interp in INTERPRETERS:
            for wrapper in PUBLICATION_WRAPPERS:
                with self.subTest(interp=Path(interp).stem, wrapper=str(wrapper.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_wrapper_fixture(root, wrapper)
                        env, marker = _make_sysnative_fixture_env(root, include_path_shell=True)
                        p = _run_ps1(interp, copied, cwd=str(root), env=env)
                        self.assertEqual(
                            p.returncode, 0,
                            f"Windows-dir prefix arm must reach the legit PATH bash; stderr={p.stderr!r}",
                        )
                        self.assertEqual(
                            marker.read_text(encoding="utf-8").splitlines(),
                            ["path-bash"],
                            "the Sysnative WSL launcher must be skipped",
                        )
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_wrapper_fixture(root, wrapper)
                        _disable_windows_dir_arm(wrapper, copied)
                        env, marker = _make_sysnative_fixture_env(root, include_path_shell=True)
                        p = _run_ps1(interp, copied, cwd=str(root), env=env)
                        self.assertEqual(
                            marker.read_text(encoding="utf-8").splitlines(),
                            ["sysnative-bash"],
                            "disabling the Windows-dir prefix arm selects Sysnative -- "
                            "the prefix arm (not a System32 substring) is load-bearing",
                        )

    def test_grandparent_not_probed_for_nonstandard_git_layout(self) -> None:
        r"""Over-reach fix for the publication launchers: the grandparent probe is
        gated on $gitInstallRoot's leaf being a mingw layer, so a NONSTANDARD git
        layout (leaf 'weird') never mis-selects an unrelated
        <grandparent>\bin\bash.exe. The unrelated grandparent bash is present but
        must be skipped; the launcher falls through to the legit PATH bash
        (marker == path-bash). Genuine: under the pre-fix unconditional probe that
        empty grandparent bash.exe would be Test-Path-selected and path-bash never
        reached. The fake git echoes root, so no real repo is needed."""
        for interp in INTERPRETERS:
            for wrapper in PUBLICATION_WRAPPERS:
                with self.subTest(interp=Path(interp).stem, wrapper=str(wrapper.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_wrapper_fixture(root, wrapper)
                        env, marker = _make_overreach_fixture_env(root)
                        p = _run_ps1(interp, copied, cwd=str(root), env=env)
                        self.assertEqual(
                            p.returncode, 0,
                            "nonstandard-layout git must reach the legit PATH bash; "
                            f"stdout={p.stdout!r} stderr={p.stderr!r}",
                        )
                        self.assertEqual(
                            marker.read_text(encoding="utf-8").splitlines(),
                            ["path-bash"],
                            "the unrelated grandparent bash must not be probed or selected",
                        )

    def test_nonrepo_cwd_fails_closed_with_clean_throw_not_crash(self) -> None:
        r"""Null-trim regression (work-items/bugs/2026-07-19-publication-wrapper-
        nonrepo-null-trim.md): outside a git repository, `git rev-parse
        --show-toplevel` exits nonzero with EMPTY stdout (git prints its error to
        stderr). Pre-fix, the wrapper called `.Trim()` directly on that $null
        result, and PowerShell threw `InvalidOperation: You cannot call a method
        on a null-valued expression` BEFORE the wrapper's own designed clean
        throw ("Unable to determine repository root.") could ever run --
        unreachable dead code for the real non-repo case. Post-fix (null-safe
        capture: `2>$null` + `$LASTEXITCODE` guard + try/catch, mirroring
        validate-skill-pack.ps1's pattern, WITHOUT that validator's
        fallback-root behavior -- these wrappers must keep hard-failing outside
        a repo), the same not-a-repo condition must reach the clean guarded
        throw with no interpreter-level crash and no null-method error, and the
        sibling .sh must never run."""
        for interp in INTERPRETERS:
            for wrapper in PUBLICATION_WRAPPERS:
                with self.subTest(interp=Path(interp).stem, wrapper=str(wrapper.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = self._copy_wrapper_fixture(root, wrapper)
                        git_dir = root / "fake-git" / "mingw64" / "bin"
                        # `rev-parse` fails (exit 128, like real git outside a
                        # repo, no stdout); any other invocation (e.g. resolving
                        # the executable) just echoes root and exits 0.
                        self._write_cmd(
                            git_dir / "git.cmd",
                            'if "%1"=="rev-parse" (exit /b 128)\r\n'
                            f"echo {root}\r\nexit /b 0\r\n",
                        )
                        env, marker = self._path_shell_env(root, git_dir)

                        p = _run_ps1(interp, copied, cwd=str(root), env=env)

                        combined = p.stdout + p.stderr
                        for m in _INTERPRETER_CRASH_MARKERS:
                            self.assertNotIn(
                                m, combined,
                                f"non-repo cwd must not crash the interpreter ({m!r}):\n{combined}",
                            )
                        self.assertNotIn(
                            "null-valued expression", combined,
                            f"the pre-fix null-.Trim() crash must not recur:\n{combined}",
                        )
                        self.assertNotEqual(
                            p.returncode, 0, f"a non-repo cwd must fail, not silently proceed: {combined}",
                        )
                        self.assertIn(
                            "Unable to determine repository root", combined,
                            f"expected the guarded clean throw:\n{combined}",
                        )
                        self.assertFalse(
                            marker.exists(), "the sibling .sh must never run outside a repo",
                        )


if __name__ == "__main__":
    unittest.main()
