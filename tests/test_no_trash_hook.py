"""Regression tests for the redesigned no-trash-in-repo PreToolUse hook (AUDIT).

The redesign (Task 9) warns ONLY when an operation CREATES A NEW directory
inside the repo whose newly-created name is high-signal author-process
vocabulary (kosyaks, journal, diary, mistakes, mistake-log, personal, private,
mine). It must NOT warn on ordinary project dirs (dev/, notes/, docs/, tools/),
on writes under EXISTING dirs, on `.scratch/`, on paths outside the repo, or on
unconfident `mkdir` (variables/globs). AUDIT mode: always exit 0; a hit warns to
stderr. Tested against BOTH the Claude and Codex copies, on a real temp repo
(the new-directory check inspects the filesystem).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS = (
    REPO_ROOT / "src.claude" / "agents" / "hooks" / "check-no-trash-in-repo.py",
    REPO_ROOT / "src.codex" / "skills" / "lead" / "hooks" / "check-no-trash-in-repo.py",
)

# Directories that already exist in the synthetic repo for each test.
EXISTING_DIRS = ("dev", "notes", "src", "docs", "tools/dev")


def run_hook(script: Path, tool_input: object, cwd: str, raw: str | None = None) -> subprocess.CompletedProcess:
    envelope = {"cwd": cwd, "tool_input": tool_input}
    stdin = raw if raw is not None else json.dumps(envelope, ensure_ascii=False)
    return subprocess.run(
        [sys.executable, str(script)],
        input=stdin, capture_output=True, text=True, encoding="utf-8",
    )


class TestNoTrashHook(unittest.TestCase):
    def assert_outcome(self, tool_input: object, should_warn: bool, raw: str | None = None) -> None:
        for script in HOOKS:
            with self.subTest(script=script.parent.parent.name):
                with tempfile.TemporaryDirectory() as tmp:
                    tmp = tmp.replace("\\", "/")
                    for d in EXISTING_DIRS:
                        os.makedirs(os.path.join(tmp, d), exist_ok=True)
                    p = run_hook(script, tool_input, tmp, raw)
                    self.assertEqual(p.returncode, 0, p.stderr)  # AUDIT never blocks
                    self.assertEqual(bool(p.stderr.strip()), should_warn, f"stderr={p.stderr!r}")

    # --- WARN: new high-signal personal dir created inside the repo ---
    def test_mkdir_dev_kosyaks_warns(self) -> None:
        self.assert_outcome({"command": "mkdir -p dev/kosyaks"}, True)

    def test_mkdir_personal_at_root_warns(self) -> None:
        self.assert_outcome({"command": "mkdir personal"}, True)

    def test_write_into_new_journal_dir_warns(self) -> None:
        self.assert_outcome({"file_path": "journal/2026-05-29.md"}, True)

    def test_mkdir_private_warns(self) -> None:
        self.assert_outcome({"command": "mkdir -p notes/private"}, True)  # private is high-signal; notes exists, private is new

    # --- NO WARN: ambiguous names, existing dirs, .scratch, outside repo ---
    def test_mkdir_ambiguous_dev_no_warn(self) -> None:
        self.assert_outcome({"command": "mkdir dev"}, False)

    def test_mkdir_notes_api_no_warn(self) -> None:
        self.assert_outcome({"command": "mkdir notes/api"}, False)

    def test_mkdir_tools_dev_no_warn(self) -> None:
        self.assert_outcome({"command": "mkdir -p tools/dev/bootstrap"}, False)

    def test_write_under_existing_dir_no_warn(self) -> None:
        self.assert_outcome({"file_path": "src/module.py"}, False)

    def test_scratch_dir_always_allowed(self) -> None:
        self.assert_outcome({"command": "mkdir -p .scratch/kosyaks"}, False)

    def test_absolute_path_outside_repo_no_warn(self) -> None:
        self.assert_outcome({"command": "mkdir D:/dev/other-project/kosyaks"}, False)

    def test_unconfident_mkdir_variable_no_warn(self) -> None:
        self.assert_outcome({"command": "mkdir $HOME/kosyaks"}, False)

    def test_unconfident_mkdir_glob_no_warn(self) -> None:
        self.assert_outcome({"command": "mkdir build/*/kosyaks"}, False)

    # --- fail-open ---
    def test_malformed_envelope_fails_open(self) -> None:
        for script in HOOKS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(script, None, "", raw="not json {{{")
                self.assertEqual(p.returncode, 0)
                self.assertEqual(p.stderr.strip(), "")

    def test_no_tool_input_fails_open(self) -> None:
        for script in HOOKS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(script, None, "", raw=json.dumps({"cwd": "/tmp"}))
                self.assertEqual(p.returncode, 0)
                self.assertEqual(p.stderr.strip(), "")

    # --- path / shell-parsing edges (Codex Task-9 review) ---
    def test_relative_dotdot_escape_no_warn(self) -> None:
        # `../personal/...` resolves OUTSIDE the repo -> must not warn (normpath
        # rejects the lexical in-repo prefix).
        self.assert_outcome({"file_path": "../personal/outside.md"}, False)

    def test_quoted_space_dir_no_warn(self) -> None:
        # `mkdir "journal notes"` is ONE dir literally named "journal notes",
        # not the high-signal "journal" -> no warn (shlex keeps it one token).
        self.assert_outcome({"command": 'mkdir "journal notes"'}, False)

    def test_mkdir_inside_echo_string_no_warn(self) -> None:
        # `mkdir` inside a quoted string is not a command -> no warn.
        self.assert_outcome({"command": 'echo "mkdir personal"'}, False)

    def test_embedded_quotes_warns(self) -> None:
        # `mkdir dev/"kosyaks"` resolves to dev/kosyaks in bash -> warn.
        self.assert_outcome({"command": 'mkdir dev/"kosyaks"'}, True)

    def test_cd_chain_under_warns(self) -> None:
        # FP-safe model: ANY `cd` makes the mkdir's cwd and whether it even runs
        # runtime-dependent, so the hook under-warns rather than risk a false
        # positive. `cd dev && mkdir kosyaks` would create dev/kosyaks but is now
        # silent (acceptable fail-open; the common `mkdir -p dev/kosyaks` form
        # carries no cd and still warns).
        self.assert_outcome({"command": "cd dev && mkdir kosyaks"}, False)

    def test_mkdir_as_argument_no_warn(self) -> None:
        # `mkdir` as an ARGUMENT of another command (not the command word) must
        # not warn — bash creates no directory (Sonnet Task-9 confirmation FP).
        self.assert_outcome({"command": "echo mkdir personal"}, False)
        self.assert_outcome({"command": "grep mkdir personal"}, False)
        self.assert_outcome({"command": "echo /usr/bin/mkdir personal"}, False)

    def test_env_prefixed_mkdir_warns(self) -> None:
        # An env-var assignment prefix does not consume the command slot: mkdir
        # IS the command here, so a new high-signal dir must still warn.
        self.assert_outcome({"command": "FOO=bar mkdir personal"}, True)

    def test_mkdir_with_redirection_still_warns(self) -> None:
        # A redirection does not end the command: `personal` is still mkdir's
        # operand (Codex Task-9 confirmation under-warn).
        self.assert_outcome({"command": "mkdir > out personal"}, True)
        self.assert_outcome({"command": "mkdir 2>err personal"}, True)

    def test_redirect_target_named_mkdir_no_warn(self) -> None:
        # `echo > mkdir personal`: bash redirects echo's stdout to a file named
        # "mkdir"; mkdir is NOT run, so no warn (Codex Task-9 confirmation FP).
        self.assert_outcome({"command": "echo > mkdir personal"}, False)

    def test_cd_into_scratch_then_mkdir_no_warn(self) -> None:
        # `cd .scratch && mkdir personal` creates .scratch/personal in bash, which
        # is the exempt evidence area; the hook must resolve the operand against
        # the post-cd cwd, not the repo root (full-repo-review cd-handling FP).
        self.assert_outcome({"command": "cd .scratch && mkdir personal"}, False)

    def test_cd_absolute_then_mkdir_no_warn(self) -> None:
        # `cd /tmp && mkdir kosyaks` creates kosyaks OUTSIDE the repo; an absolute
        # cd makes the cwd unresolvable, so the hook under-warns (fails open).
        self.assert_outcome({"command": "cd /tmp && mkdir kosyaks"}, False)

    def test_cd_or_then_mkdir_under_warns(self) -> None:
        # `cd .scratch || mkdir personal`: whether mkdir runs (and in which cwd)
        # depends on whether .scratch exists at runtime; the FP-safe model
        # under-warns rather than guess. (A prior cwd-modelling attempt warned
        # here but then false-positived on the guard-chain form below.)
        self.assert_outcome({"command": "cd .scratch || mkdir personal"}, False)

    def test_cd_guard_chain_no_false_positive(self) -> None:
        # `cd .scratch || exit; mkdir personal` is a cd-or-die guard: with .scratch
        # present bash makes .scratch/personal (exempt); without it the shell exits
        # before mkdir. Either way no repo-root personal/ is created, so it must
        # NOT warn (this was a real FP in the cwd-revert modelling attempt).
        self.assert_outcome({"command": "cd .scratch || exit; mkdir personal"}, False)

    def test_cd_pipe_then_mkdir_under_warns(self) -> None:
        # `cd .scratch | mkdir personal`: pipe subshell; FP-safe model under-warns.
        self.assert_outcome({"command": "cd .scratch | mkdir personal"}, False)

    def test_cd_semicolon_then_mkdir_under_warns(self) -> None:
        # `cd .scratch ; mkdir personal`: any cd present -> under-warn (FP-safe).
        self.assert_outcome({"command": "cd .scratch ; mkdir personal"}, False)

    def test_git_tracked_high_signal_dir_suppressed(self) -> None:
        # git suppressor: a high-signal dir that git still tracks (tracked then
        # deleted on disk) is an established dir -> suppress even on re-create.
        import shutil
        git = shutil.which("git")
        if not git:
            self.skipTest("git not available")
        for script in HOOKS:
            with self.subTest(script=script.parent.parent.name):
                with tempfile.TemporaryDirectory() as tmp:
                    tmp = tmp.replace("\\", "/")
                    def g(*a):
                        subprocess.run([git, "-C", tmp, *a], capture_output=True, text=True)
                    g("init")
                    g("config", "user.email", "t@t")
                    g("config", "user.name", "t")
                    os.makedirs(os.path.join(tmp, "personal"))
                    Path(tmp, "personal", "f.md").write_text("x", encoding="utf-8")
                    g("add", "-A")
                    g("commit", "-m", "x")
                    shutil.rmtree(os.path.join(tmp, "personal"))  # tracked but gone on disk
                    p = run_hook(script, {"command": "mkdir personal"}, tmp)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertEqual(p.stderr.strip(), "", "git-tracked dir should be suppressed")


if __name__ == "__main__":
    unittest.main()
