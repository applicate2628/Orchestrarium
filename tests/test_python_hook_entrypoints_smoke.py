"""Smoke contracts for the direct Python hook and publication entrypoints.

This is the live successor to ``test_powershell_wrappers_smoke.py``.  The
PowerShell/Git-Bash locator mechanics were retired with the wrappers; the
host-visible decisions, fail-open behavior, structured context, and
foreign-working-directory behavior remain production contracts.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLAUDE_SCRIPTS = ROOT / "src.claude" / "agents" / "scripts"
CLAUDE_HOOKS = ROOT / "src.claude" / "agents" / "hooks"
CODEX_SCRIPTS = ROOT / "src.codex" / "skills" / "lead" / "scripts"
CODEX_HOOKS = ROOT / "src.codex" / "skills" / "lead" / "hooks"

HOOK_PYTHON_ENTRYPOINTS = (
    CLAUDE_SCRIPTS / "check-bugfix-discipline.py",
    CLAUDE_SCRIPTS / "check-git-push-gate.py",
    CLAUDE_SCRIPTS / "check-passive-polling-stop.py",
    CLAUDE_HOOKS / "check-machine-local-path.py",
    CLAUDE_HOOKS / "check-no-trash-in-repo.py",
    CLAUDE_HOOKS / "check-stale-relation-residue.py",
    CLAUDE_HOOKS / "check-repository-orientation.py",
    CLAUDE_HOOKS / "check-mcp-momentum.py",
    CODEX_SCRIPTS / "check-bugfix-discipline.py",
    CODEX_SCRIPTS / "check-git-push-gate.py",
    CODEX_SCRIPTS / "check-passive-polling-stop.py",
    CODEX_HOOKS / "check-machine-local-path.py",
    CODEX_HOOKS / "check-no-trash-in-repo.py",
    CODEX_HOOKS / "check-stale-relation-residue.py",
    CODEX_HOOKS / "check-repository-orientation.py",
    CODEX_HOOKS / "check-mcp-momentum.py",
)

MCP_REMINDERS = (
    CLAUDE_SCRIPTS / "mcp-usage-reminder.py",
    CODEX_SCRIPTS / "mcp-usage-reminder.py",
)
AGENTS_MODE_REMINDERS = (
    (CLAUDE_SCRIPTS / "agents-mode-reminder.py", ".claude"),
    (CODEX_SCRIPTS / "agents-mode-reminder.py", ".agents"),
)
SCRATCH_WATCHDOGS = (
    CLAUDE_SCRIPTS / "check-scratch-valuables.py",
    CODEX_SCRIPTS / "check-scratch-valuables.py",
)
PUBLICATION_SCANNERS = (
    ROOT / "scripts" / "universal-hooks" / "scripts" / "check-publication-safety.py",
    CLAUDE_SCRIPTS / "check-publication-safety.py",
    CODEX_SCRIPTS / "check-publication-safety.py",
)
PUBLICATION_GATE = ROOT / "scripts" / "check-publication-gate.py"

MALFORMED_JSON = "not json at all " + "{" * 3
GIT = shutil.which("git")

_MACHINE_PATH_FIXTURE = "see C:/" + "Use" + "rs/realuser/.claude/x"
AUDIT_HIT_CASES = (
    (
        "check-machine-local-path.py",
        {
            "tool_input": {
                "file_path": "README.md",
                "content": _MACHINE_PATH_FIXTURE,
            }
        },
    ),
    (
        "check-no-trash-in-repo.py",
        {"tool_input": {"command": "git worktree add ../wt"}},
    ),
    (
        "check-stale-relation-residue.py",
        {
            "tool_input": {
                "file_path": "docs/live-doc.md",
                "content": "this helper is a deprecated alias for the new one",
            }
        },
    ),
)


def _run_python(
    script: Path,
    *,
    stdin: str = "",
    cwd: str | Path | None = None,
    env: dict[str, str] | None = None,
    args: tuple[str, ...] = (),
) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), *args],
        input=stdin,
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _decode_context(stdout: str, expected_event: str) -> str:
    payload = json.loads(stdout)
    if set(payload) != {"hookSpecificOutput"}:
        raise AssertionError(f"unexpected top-level payload: {payload!r}")
    specific = payload["hookSpecificOutput"]
    if set(specific) != {"hookEventName", "additionalContext"}:
        raise AssertionError(f"unexpected hookSpecificOutput: {specific!r}")
    if specific["hookEventName"] != expected_event:
        raise AssertionError(f"unexpected event: {specific!r}")
    context = specific["additionalContext"]
    if not isinstance(context, str):
        raise AssertionError(f"additionalContext must be text: {specific!r}")
    return context


def _load_module(script: Path, stem: str):
    spec = importlib.util.spec_from_file_location(stem, script)
    if spec is None or spec.loader is None:
        raise AssertionError(f"cannot load Python owner: {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class DirectPythonHookSmokeTests(unittest.TestCase):
    def test_empty_and_malformed_stdin_fail_open_from_foreign_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            for script in HOOK_PYTHON_ENTRYPOINTS:
                self.assertTrue(script.is_file(), f"missing Python owner: {script}")
                for stdin in ("", MALFORMED_JSON):
                    with self.subTest(
                        script=str(script.relative_to(ROOT)), stdin=stdin[:8]
                    ):
                        result = _run_python(script, stdin=stdin, cwd=td)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stdout, "")
                        self.assertEqual(result.stderr, "")

    def test_warn_only_hooks_emit_stdout_advisory_from_foreign_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            for name, envelope in AUDIT_HIT_CASES:
                for hooks_dir in (CLAUDE_HOOKS, CODEX_HOOKS):
                    script = hooks_dir / name
                    with self.subTest(script=str(script.relative_to(ROOT))):
                        result = _run_python(
                            script,
                            stdin=json.dumps(envelope, ensure_ascii=False),
                            cwd=td,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stderr, "")
                        context = _decode_context(result.stdout, "PreToolUse")
                        self.assertTrue(context.strip(), "expected non-empty advisory")


class SessionStartPythonSmokeTests(unittest.TestCase):
    def test_mcp_reminders_emit_policy_owned_context_from_foreign_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            for index, script in enumerate(MCP_REMINDERS):
                policy = _load_module(
                    script.with_name("mcp_continuity_policy.py"),
                    f"python_smoke_mcp_policy_{index}",
                )
                with self.subTest(script=str(script.relative_to(ROOT))):
                    result = _run_python(script, cwd=td)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stderr, "")
                    self.assertEqual(
                        _decode_context(result.stdout, "SessionStart"),
                        policy.SESSION_START_CONTEXT,
                    )

    def test_agents_mode_force_auto_emit_exact_context_manual_is_silent(self) -> None:
        for index, (script, config_dirname) in enumerate(AGENTS_MODE_REMINDERS):
            owner = _load_module(script, f"python_smoke_agents_mode_{index}")
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                config_dir = root / config_dirname
                config_dir.mkdir()
                home = root / "home"
                home.mkdir()
                env = os.environ.copy()
                env["USERPROFILE"] = str(home)
                env["HOME"] = str(home)
                config = config_dir / ".agents-mode.yaml"
                for mode, expected in (
                    ("force", owner.FORCE_CONTEXT),
                    ("auto", owner.AUTO_CONTEXT),
                ):
                    config.write_text(
                        f"delegationMode: {mode}\n", encoding="utf-8"
                    )
                    with self.subTest(
                        script=str(script.relative_to(ROOT)), mode=mode
                    ):
                        result = _run_python(script, cwd=root, env=env)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stderr, "")
                        self.assertEqual(
                            _decode_context(result.stdout, "SessionStart"),
                            expected,
                        )

                config.write_text("delegationMode: manual\n", encoding="utf-8")
                result = _run_python(script, cwd=root, env=env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertEqual(result.stderr, "")

    def test_agents_mode_missing_config_is_silent_from_foreign_cwd(self) -> None:
        for script, _config_dirname in AGENTS_MODE_REMINDERS:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                home = root / "home"
                home.mkdir()
                env = os.environ.copy()
                env["USERPROFILE"] = str(home)
                env["HOME"] = str(home)
                with self.subTest(script=str(script.relative_to(ROOT))):
                    result = _run_python(script, cwd=root, env=env)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, "")

    def test_scratch_watchdog_emits_context_for_unique_file(self) -> None:
        if GIT is None:
            self.skipTest("git is required for the uniqueness oracle")
        for script in SCRATCH_WATCHDOGS:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                repo = root / "repo"
                foreign_cwd = root / "foreign"
                repo.mkdir()
                foreign_cwd.mkdir()
                subprocess.run(
                    [GIT, "init", "-q", str(repo)],
                    check=True,
                    capture_output=True,
                )
                scratch = repo / ".scratch"
                scratch.mkdir()
                (scratch / "unique.md").write_text(
                    "genuinely unique content, never committed",
                    encoding="utf-8",
                )
                with self.subTest(script=str(script.relative_to(ROOT))):
                    result = _run_python(
                        script,
                        stdin=json.dumps({"cwd": str(repo)}),
                        cwd=foreign_cwd,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stderr, "")
                    context = _decode_context(result.stdout, "SessionStart")
                    self.assertIn("scratch watchdog", context)
                    named_unique_file = "unique.md" in context
                    disclosed_budget_limit = (
                        "[scratch watchdog budget]" in context
                        and (
                            "1 candidate file(s) exceeded this run's "
                            "git-verification budget"
                        )
                        in context
                        and (
                            "graded by file age instead of "
                            "git-content-uniqueness"
                        )
                        in context
                    )
                    self.assertNotEqual(
                        named_unique_file,
                        disclosed_budget_limit,
                        "CLI must name the git-unique file or disclose the exact "
                        "budget-limited fallback, but never produce a third or "
                        "ambiguous outcome",
                    )

    def test_scratch_watchdog_owner_selects_unique_file_with_expanded_budget(
        self,
    ) -> None:
        if GIT is None:
            self.skipTest("git is required for the uniqueness oracle")
        for index, script in enumerate(SCRATCH_WATCHDOGS):
            owner = _load_module(script, f"python_smoke_scratch_owner_{index}")
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                subprocess.run(
                    [GIT, "init", "-q", str(root)],
                    check=True,
                    capture_output=True,
                )
                scratch = root / ".scratch"
                scratch.mkdir()
                (scratch / "unique.md").write_text(
                    "genuinely unique content, never committed",
                    encoding="utf-8",
                )
                report = owner.ScanReport()
                with self.subTest(script=str(script.relative_to(ROOT))):
                    valuables = owner._scan_valuables(
                        scratch,
                        time_budget_seconds=30.0,
                        report=report,
                    )
                    self.assertEqual(
                        [item["path"] for item in valuables],
                        ["unique.md"],
                    )
                    self.assertEqual(report.candidates_found, 1)
                    self.assertEqual(report.candidates_git_verified, 1)
                    self.assertEqual(report.candidates_budget_age_gated, 0)
                    self.assertFalse(report.budget_limited)

    def test_scratch_watchdog_is_silent_without_candidates_or_directory(self) -> None:
        for script in SCRATCH_WATCHDOGS:
            for create_scratch in (True, False):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    if create_scratch:
                        (root / ".scratch").mkdir()
                    with self.subTest(
                        script=str(script.relative_to(ROOT)),
                        scratch=create_scratch,
                    ):
                        result = _run_python(
                            script,
                            stdin=json.dumps({"cwd": str(root)}),
                            cwd=root,
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)
                        self.assertEqual(result.stdout, "")
                        self.assertEqual(result.stderr, "")

    def test_scratch_watchdog_fails_open_on_malformed_input(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            for script in SCRATCH_WATCHDOGS:
                with self.subTest(script=str(script.relative_to(ROOT))):
                    result = _run_python(
                        script, stdin=MALFORMED_JSON, cwd=td
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, "")


@unittest.skipIf(GIT is None, "git is required for publication scanner smoke")
class PublicationSafetyPythonSmokeTests(unittest.TestCase):
    def _staged_repo(self, root: Path, content: str) -> None:
        assert GIT is not None
        subprocess.run(
            [GIT, "init", "-q", str(root)], check=True, capture_output=True
        )
        fixture = root / "fixture.txt"
        fixture.write_text(content, encoding="utf-8")
        subprocess.run(
            [GIT, "-C", str(root), "add", fixture.name],
            check=True,
            capture_output=True,
        )

    def test_clean_staged_repo_exits_zero_from_foreign_cwd(self) -> None:
        for script in PUBLICATION_SCANNERS:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                self._staged_repo(root, "nothing machine-local here\n")
                with self.subTest(script=str(script.relative_to(ROOT))):
                    result = _run_python(script, cwd=root)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stderr, "")
                    self.assertIn(
                        "publication-safety: clean (tracked, examined 1 file)",
                        result.stdout,
                    )

    def test_staged_leak_exits_one_from_foreign_cwd(self) -> None:
        leak = "pass" + "word" + ": hunter2\n"
        for script in PUBLICATION_SCANNERS:
            with tempfile.TemporaryDirectory() as td:
                root = Path(td)
                self._staged_repo(root, leak)
                with self.subTest(script=str(script.relative_to(ROOT))):
                    result = _run_python(script, cwd=root)
                    self.assertEqual(result.returncode, 1, result.stdout)
                    self.assertEqual(result.stdout, "")
                    self.assertIn(
                        "publication-safety scan found potential tracked-content leak markers",
                        result.stderr,
                    )

    def test_nonrepo_cwd_fails_closed_without_interpreter_crash(self) -> None:
        for script in (*PUBLICATION_SCANNERS, PUBLICATION_GATE):
            with tempfile.TemporaryDirectory() as td:
                with self.subTest(script=str(script.relative_to(ROOT))):
                    result = _run_python(script, cwd=td)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, "")
                    self.assertIn("not inside a git repository", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
