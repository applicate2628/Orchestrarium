"""Python-owned SessionStart reminders emit the structured host context.

Hook and reminder runtime behavior is Python-only and registered directly.
Retained POSIX launchers are limited to non-hook public commands.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

MCP_PY_SCRIPTS = (
    ROOT / "scripts" / "universal-hooks" / "scripts" / "mcp-usage-reminder.py",
    ROOT / "src.codex" / "skills" / "lead" / "scripts" / "mcp-usage-reminder.py",
    ROOT / "src.claude" / "agents" / "scripts" / "mcp-usage-reminder.py",
)
MCP_POLICY_SCRIPTS = (
    ROOT / "scripts" / "universal-hooks" / "scripts" / "mcp_continuity_policy.py",
    ROOT / "src.codex" / "skills" / "lead" / "scripts" / "mcp_continuity_policy.py",
    ROOT / "src.claude" / "agents" / "scripts" / "mcp_continuity_policy.py",
)

def _load_policy(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(policy)
    return policy


CANONICAL_MCP_POLICY = _load_policy(
    MCP_POLICY_SCRIPTS[0], "canonical_mcp_continuity_policy_test"
)
CANONICAL_SESSION_START_CONTEXT = CANONICAL_MCP_POLICY.SESSION_START_CONTEXT
CANONICAL_TURN_ANCHOR_CONTEXT = CANONICAL_MCP_POLICY.TURN_ANCHOR_CONTEXT

# (script, config subdir under cwd, expected-context-dict-key)
AGENTS_MODE_PY = (
    (ROOT / "src.codex" / "skills" / "lead" / "scripts" / "agents-mode-reminder.py", ".agents", "codex"),
    (ROOT / "src.claude" / "agents" / "scripts" / "agents-mode-reminder.py", ".claude", "claude"),
)

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
DELEGATION_CONTEXTS_BY_PACK = {"codex": CODEX_DELEGATION_CONTEXTS, "claude": CLAUDE_DELEGATION_CONTEXTS}

MALFORMED_JSON = "not json at all " + "{" * 3


def _run(script: Path, *, cwd: str | None = None, env: dict | None = None,
         stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script)],
        cwd=cwd,
        env=env,
        input=stdin,
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


class McpUsageReminderPythonHookTest(unittest.TestCase):
    def test_all_policy_projections_match_the_canonical_contexts(self) -> None:
        for index, policy_path in enumerate(MCP_POLICY_SCRIPTS[1:], start=1):
            with self.subTest(policy=str(policy_path.relative_to(ROOT))):
                policy = _load_policy(
                    policy_path, f"mcp_continuity_policy_projection_test_{index}"
                )
                self.assertEqual(
                    policy.SESSION_START_CONTEXT, CANONICAL_SESSION_START_CONTEXT
                )
                self.assertEqual(
                    policy.TURN_ANCHOR_CONTEXT, CANONICAL_TURN_ANCHOR_CONTEXT
                )

    def test_canonical_session_context_uses_runtime_discovery_and_non_normative_examples(self) -> None:
        for marker in (
            "runtime tool discovery",
            "Non-normative interface example only",
            "its name never selects a tool",
            "Non-normative workflow examples only",
            "These names never select a tool",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, CANONICAL_SESSION_START_CONTEXT)

    def test_all_three_adapters_emit_their_policy_owned_exact_context(self) -> None:
        for index, (script, policy_path) in enumerate(
            zip(MCP_PY_SCRIPTS, MCP_POLICY_SCRIPTS, strict=True)
        ):
            with self.subTest(script=str(script.relative_to(ROOT))):
                self.assertTrue(policy_path.is_file(), f"missing {policy_path}")
                policy = _load_policy(
                    policy_path, f"mcp_continuity_policy_adapter_test_{index}"
                )
                result = _run(script, stdin="")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    _decode_context(result.stdout), policy.SESSION_START_CONTEXT
                )

    def test_all_three_copies_emit_exact_context_with_no_stdin(self) -> None:
        for script in MCP_PY_SCRIPTS:
            with self.subTest(script=str(script.relative_to(ROOT))):
                self.assertTrue(script.is_file(), f"missing {script}")
                result = _run(script, stdin="")
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                self.assertEqual(len(result.stdout.splitlines()), 1)
                self.assertEqual(
                    _decode_context(result.stdout), CANONICAL_SESSION_START_CONTEXT
                )

    def test_malformed_stdin_does_not_change_the_unconditional_reminder(self) -> None:
        # mcp-usage-reminder never reads stdin; garbage input has zero effect.
        for script in MCP_PY_SCRIPTS:
            with self.subTest(script=str(script.relative_to(ROOT))):
                result = _run(script, stdin=MALFORMED_JSON)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stderr, "")
                self.assertEqual(
                    _decode_context(result.stdout), CANONICAL_SESSION_START_CONTEXT
                )

    def test_absent_stdin_still_exits_zero_with_the_reminder(self) -> None:
        for script in MCP_PY_SCRIPTS:
            with self.subTest(script=str(script.relative_to(ROOT))):
                result = subprocess.run(
                    [sys.executable, str(script)],
                    stdin=subprocess.DEVNULL,
                    capture_output=True, text=True, encoding="utf-8",
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    _decode_context(result.stdout), CANONICAL_SESSION_START_CONTEXT
                )


class AgentsModeReminderPythonHookTest(unittest.TestCase):
    """Drive the Python owner directly via sys.executable."""

    def test_force_and_auto_emit_exact_directive_manual_and_missing_are_silent(self) -> None:
        for script, sub, pack_key in AGENTS_MODE_PY:
            self.assertTrue(script.is_file(), f"missing {script}")
            with tempfile.TemporaryDirectory() as td:
                cfg_dir = Path(td) / sub
                cfg_dir.mkdir(parents=True, exist_ok=True)
                home = Path(td) / "home"
                home.mkdir(exist_ok=True)
                cfg = cfg_dir / ".agents-mode.yaml"

                import os
                env = os.environ.copy()
                env["USERPROFILE"] = str(home)
                env["HOME"] = str(home)

                for mode in ("force", "auto"):
                    cfg.write_text(f"delegationMode: {mode}\n", encoding="utf-8")
                    with self.subTest(pack=sub, mode=mode):
                        result = _run(script, cwd=td, env=env, stdin="")
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stderr, "")
                        context = _decode_context(result.stdout)
                        self.assertEqual(
                            context, DELEGATION_CONTEXTS_BY_PACK[pack_key][mode]
                        )

                cfg.write_text("delegationMode: manual\n", encoding="utf-8")
                with self.subTest(pack=sub, mode="manual"):
                    result = _run(script, cwd=td, env=env, stdin="")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, "")

    def test_no_file_anywhere_is_silent(self) -> None:
        import os
        for script, _sub, _pack_key in AGENTS_MODE_PY:
            with tempfile.TemporaryDirectory() as td:
                home = Path(td) / "home"
                home.mkdir(exist_ok=True)
                env = os.environ.copy()
                env["USERPROFILE"] = str(home)
                env["HOME"] = str(home)
                with self.subTest(script=str(script.relative_to(ROOT))):
                    result = _run(script, cwd=td, env=env, stdin="")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, "")

    def test_non_actionable_values_are_byte_silent(self) -> None:
        import os
        fixtures = {
            "empty": "delegationMode:\n",
            "unrecognized": "delegationMode: maybe\n",
            "inline-hash-no-space": "delegationMode: force#x\n",
            "case-sensitive-key": "DelegationMode: force\n",
        }
        for script, sub, _pack_key in AGENTS_MODE_PY:
            for name, config in fixtures.items():
                with tempfile.TemporaryDirectory() as td:
                    cfg_dir = Path(td) / sub
                    cfg_dir.mkdir(parents=True, exist_ok=True)
                    (cfg_dir / ".agents-mode.yaml").write_text(config, encoding="utf-8")
                    home = Path(td) / "home"
                    home.mkdir(exist_ok=True)
                    env = os.environ.copy()
                    env["USERPROFILE"] = str(home)
                    env["HOME"] = str(home)
                    with self.subTest(script=str(script.relative_to(ROOT)), fixture=name):
                        result = _run(script, cwd=td, env=env, stdin="")
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stdout, "")
                        self.assertEqual(result.stderr, "")

    def test_trailing_comment_is_stripped_but_glued_hash_is_literal(self) -> None:
        import os
        for script, sub, pack_key in AGENTS_MODE_PY:
            with tempfile.TemporaryDirectory() as td:
                cfg_dir = Path(td) / sub
                cfg_dir.mkdir(parents=True, exist_ok=True)
                cfg = cfg_dir / ".agents-mode.yaml"
                home = Path(td) / "home"
                home.mkdir(exist_ok=True)
                env = os.environ.copy()
                env["USERPROFILE"] = str(home)
                env["HOME"] = str(home)

                cfg.write_text("delegationMode: force  # trailing note\n", encoding="utf-8")
                with self.subTest(script=str(script.relative_to(ROOT)), case="trailing-comment"):
                    result = _run(script, cwd=td, env=env, stdin="")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(_decode_context(result.stdout), DELEGATION_CONTEXTS_BY_PACK[pack_key]["force"])

                cfg.write_text("delegationMode: force#nospace\n", encoding="utf-8")
                with self.subTest(script=str(script.relative_to(ROOT)), case="glued-hash"):
                    result = _run(script, cwd=td, env=env, stdin="")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, "")

    def test_legacy_extensionless_file_is_a_valid_fallback_candidate(self) -> None:
        import os
        for script, sub, pack_key in AGENTS_MODE_PY:
            with tempfile.TemporaryDirectory() as td:
                cfg_dir = Path(td) / sub
                cfg_dir.mkdir(parents=True, exist_ok=True)
                (cfg_dir / ".agents-mode").write_text("delegationMode: auto\n", encoding="utf-8")
                home = Path(td) / "home"
                home.mkdir(exist_ok=True)
                env = os.environ.copy()
                env["USERPROFILE"] = str(home)
                env["HOME"] = str(home)
                with self.subTest(script=str(script.relative_to(ROOT))):
                    result = _run(script, cwd=td, env=env, stdin="")
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(
                        _decode_context(result.stdout), DELEGATION_CONTEXTS_BY_PACK[pack_key]["auto"]
                    )

    def test_malformed_stdin_has_no_effect(self) -> None:
        # agents-mode-reminder never reads stdin either -- only the on-disk
        # .agents-mode.yaml drives its behavior.
        import os
        for script, sub, pack_key in AGENTS_MODE_PY:
            with tempfile.TemporaryDirectory() as td:
                cfg_dir = Path(td) / sub
                cfg_dir.mkdir(parents=True, exist_ok=True)
                (cfg_dir / ".agents-mode.yaml").write_text("delegationMode: force\n", encoding="utf-8")
                home = Path(td) / "home"
                home.mkdir(exist_ok=True)
                env = os.environ.copy()
                env["USERPROFILE"] = str(home)
                env["HOME"] = str(home)
                with self.subTest(script=str(script.relative_to(ROOT))):
                    result = _run(script, cwd=td, env=env, stdin=MALFORMED_JSON)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(
                        _decode_context(result.stdout), DELEGATION_CONTEXTS_BY_PACK[pack_key]["force"]
                    )


if __name__ == "__main__":
    unittest.main()
