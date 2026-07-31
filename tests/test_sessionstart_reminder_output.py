"""POSIX SessionStart reminders emit the structured host context contract."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.bash_runtime import resolve_bash


ROOT = Path(__file__).resolve().parents[1]
BASH = resolve_bash()

MCP_SCRIPTS = (
    ROOT / "scripts" / "universal-hooks" / "scripts" / "mcp-usage-reminder.sh",
    ROOT / "src.codex" / "skills" / "lead" / "scripts" / "mcp-usage-reminder.sh",
    ROOT / "src.claude" / "agents" / "scripts" / "mcp-usage-reminder.sh",
)
CODEX_AGENTS_MODE = (
    ROOT / "src.codex" / "skills" / "lead" / "scripts" / "agents-mode-reminder.sh"
)
SCRATCH_VALUABLES_SCRIPTS = (
    ROOT / "scripts" / "universal-hooks" / "scripts" / "check-scratch-valuables.sh",
    ROOT / "src.codex" / "skills" / "lead" / "scripts" / "check-scratch-valuables.sh",
    ROOT / "src.claude" / "agents" / "scripts" / "check-scratch-valuables.sh",
)

MCP_CONTEXT = "\n".join((
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
DELEGATION_CONTEXTS = {
    "force": DELEGATION_HEADING + "\n" + (
        "Effective delegationMode: FORCE. STANDING INSTRUCTION, not advisory: at the FIRST decision point of any non-trivial task (multi-step implementation, design, research, review, bug-fix), STOP - hold the $lead orchestration role in THIS session, classify the task, pick the team template, and activate the matching specialist role/skill per stage ($lead is the role you hold, not a subagent you spawn). Doing substantial work inline when a matching specialist and a viable tool path exist violates the active posture. When you launch any external provider (consultant / Codex / Claude) as $lead, take the launch flags from skills/lead/external-dispatch.md - file-based prompt, explicit model+effort, run-completion oracle, stall policy - never improvise them from memory. Maintain work-items/ recovery state for multi-stage chains. This STILL APPLIES AFTER COMPACTION."
    ),
    "auto": DELEGATION_HEADING + "\n" + (
        "Effective delegationMode: AUTO. Holding the $lead orchestration role in THIS session and activating the matching specialist role/skill per stage is the DEFAULT for any non-trivial task (multi-step implementation, design, research, review, bug-fix) - do it unless the task is trivial or you record why inline is better. $lead is the role you hold, not a subagent you spawn. When you launch any external provider (consultant / Codex / Claude) as $lead, take the launch flags from skills/lead/external-dispatch.md - file-based prompt, explicit model+effort, run-completion oracle, stall policy - never improvise them from memory. Maintain work-items/ recovery state for multi-stage chains. This STILL APPLIES AFTER COMPACTION."
    ),
}


def _run(script: Path, *, cwd: Path | None = None,
         env: dict[str, str] | None = None,
         input: str | None = None) -> subprocess.CompletedProcess[str]:
    assert BASH is not None
    return subprocess.run(
        [BASH, script.as_posix()],
        cwd=cwd,
        env=env,
        input=input,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _decode_context(stdout: str) -> str:
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


@unittest.skipIf(BASH is None, "bash is not available")
class SessionStartReminderOutputTest(unittest.TestCase):
    def test_mcp_reminders_emit_one_compact_json_object_with_exact_context(self) -> None:
        for script in MCP_SCRIPTS:
            with self.subTest(script=str(script.relative_to(ROOT))):
                result = _run(script)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                self.assertEqual(len(result.stdout.splitlines()), 1)
                self.assertEqual(_decode_context(result.stdout), MCP_CONTEXT)

    def test_codex_agents_mode_force_and_auto_emit_exact_json_context(self) -> None:
        for mode, expected in DELEGATION_CONTEXTS.items():
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                config_dir = root / ".agents"
                config_dir.mkdir()
                (config_dir / ".agents-mode.yaml").write_text(
                    f"delegationMode: {mode}\n", encoding="utf-8"
                )
                home = root / "home"
                home.mkdir()
                env = dict(os.environ)
                env["HOME"] = str(home)

                result = _run(CODEX_AGENTS_MODE, cwd=root, env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                self.assertEqual(len(result.stdout.splitlines()), 1)
                self.assertEqual(_decode_context(result.stdout), expected)

    def test_codex_agents_mode_non_actionable_values_are_byte_silent(self) -> None:
        fixtures = {
            "manual": "delegationMode: manual\n",
            "empty": "delegationMode:\n",
            "unrecognized": "delegationMode: maybe\n",
            "inline-hash": "delegationMode: force#x\n",
            "case-sensitive-key": "DelegationMode: force\n",
        }
        for name, config in fixtures.items():
            with self.subTest(fixture=name), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                config_dir = root / ".agents"
                config_dir.mkdir()
                (config_dir / ".agents-mode.yaml").write_text(config, encoding="utf-8")
                home = root / "home"
                home.mkdir()
                env = dict(os.environ)
                env["HOME"] = str(home)

                result = _run(CODEX_AGENTS_MODE, cwd=root, env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")

    def test_codex_agents_mode_no_file_is_byte_silent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            home = root / "home"
            home.mkdir()
            env = dict(os.environ)
            env["HOME"] = str(home)

            result = _run(CODEX_AGENTS_MODE, cwd=root, env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "")

    def test_codex_agents_mode_first_defining_file_owns_the_value(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            config_dir = root / ".agents"
            config_dir.mkdir()
            home = root / "home"
            global_dir = home / ".codex"
            global_dir.mkdir(parents=True)
            (global_dir / ".agents-mode.yaml").write_text(
                "delegationMode: force\n", encoding="utf-8"
            )
            env = dict(os.environ)
            env["HOME"] = str(home)

            local = config_dir / ".agents-mode.yaml"
            local.write_text("delegationMode:\n", encoding="utf-8")
            owned_silence = _run(CODEX_AGENTS_MODE, cwd=root, env=env)
            self.assertEqual(owned_silence.returncode, 0, owned_silence.stderr)
            self.assertEqual(owned_silence.stdout, "")
            self.assertEqual(owned_silence.stderr, "")

            local.write_text("externalProvider: auto\n", encoding="utf-8")
            fallback = _run(CODEX_AGENTS_MODE, cwd=root, env=env)
            self.assertEqual(fallback.returncode, 0, fallback.stderr)
            self.assertEqual(fallback.stderr, "")
            self.assertEqual(
                _decode_context(fallback.stdout), DELEGATION_CONTEXTS["force"]
            )


@unittest.skipIf(BASH is None, "bash is not available")
class ScratchValuablesReminderOutputTest(unittest.TestCase):
    """The scratch-valuables watchdog is CONDITIONAL (silent when `.scratch/`
    has nothing to flag, emits a hookSpecificOutput block when it does), and
    reads `cwd` from the stdin JSON envelope rather than the process cwd. A
    bare `git init` (no commits) makes the git-uniqueness predicate
    deterministic regardless of the test host's ambient state: an empty
    object database reports every blob as missing, so any non-junk,
    non-empty file is a candidate independent of its age."""

    def _init_git_repo(self, root: Path) -> None:
        subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)

    def test_emits_context_when_a_unique_valuable_is_present(self) -> None:
        for script in SCRATCH_VALUABLES_SCRIPTS:
            with self.subTest(script=str(script.relative_to(ROOT))), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                self._init_git_repo(root)
                scratch = root / ".scratch"
                scratch.mkdir()
                (scratch / "unique.md").write_text(
                    "genuinely unique content, never committed", encoding="utf-8"
                )
                envelope = json.dumps({"cwd": str(root)})

                result = _run(script, input=envelope)

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                context = _decode_context(result.stdout)
                self.assertIn("scratch watchdog", context)
                self.assertIn("unique.md", context)

    def test_silent_when_scratch_has_no_candidates(self) -> None:
        for script in SCRATCH_VALUABLES_SCRIPTS:
            with self.subTest(script=str(script.relative_to(ROOT))), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                (root / ".scratch").mkdir()
                envelope = json.dumps({"cwd": str(root)})

                result = _run(script, input=envelope)

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")

    def test_silent_when_no_scratch_dir_exists(self) -> None:
        for script in SCRATCH_VALUABLES_SCRIPTS:
            with self.subTest(script=str(script.relative_to(ROOT))), tempfile.TemporaryDirectory() as td:
                envelope = json.dumps({"cwd": td})

                result = _run(script, input=envelope)

                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
