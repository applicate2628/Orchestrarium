"""Regression tests for the stray-artifact PreToolUse hook (AUDIT mode).

The hook lives in `check-no-trash-in-repo.py` (filename retained for install-marker
continuity; a rename to check-stray-artifact is a tracked follow-up). It warns ONLY
on a confident `git worktree add` Bash command — the unrequested-worktree side
effect. `git worktree list/remove/prune`, `git add` (not `git worktree add`), other
git commands, `git` inside a quoted string, non-git commands, and file writes never
warn. AUDIT mode: always exit 0; a hit warns to stderr. The earlier name-based
no-trash detection it replaced was useless — the agent never created dirs named
`kosyaks`/`mistake-log` (those are the user's vocabulary, not agent output), so it
never fired. Tested against BOTH the Claude and Codex hook copies.
"""

from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS = (
    REPO_ROOT / "src.claude" / "agents" / "hooks" / "check-no-trash-in-repo.py",
    REPO_ROOT / "src.codex" / "skills" / "lead" / "hooks" / "check-no-trash-in-repo.py",
)


def run_hook(script: Path, tool_input: object, raw: str | None = None) -> subprocess.CompletedProcess:
    envelope = {"cwd": "/tmp", "tool_input": tool_input}
    stdin = raw if raw is not None else json.dumps(envelope, ensure_ascii=False)
    return subprocess.run(
        [sys.executable, str(script)],
        input=stdin, capture_output=True, text=True, encoding="utf-8",
    )


class TestStrayArtifactHook(unittest.TestCase):
    def assert_outcome(self, tool_input: object, should_warn: bool, raw: str | None = None) -> None:
        for script in HOOKS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(script, tool_input, raw)
                self.assertEqual(p.returncode, 0, p.stderr)  # AUDIT never blocks
                self.assertEqual(bool(p.stderr.strip()), should_warn, f"stderr={p.stderr!r}")

    # --- WARN: confident `git worktree add` ---
    def test_worktree_add_bare(self) -> None:
        self.assert_outcome({"command": "git worktree add ../wt"}, True)

    def test_worktree_add_with_branch(self) -> None:
        self.assert_outcome({"command": "git worktree add /tmp/wt feature"}, True)

    def test_worktree_add_cd_chained(self) -> None:
        self.assert_outcome({"command": "cd repo && git worktree add ../wt"}, True)

    def test_worktree_add_global_value_opt(self) -> None:
        # `git -C <path> worktree add` — the value-taking global option's value must
        # be skipped, not mistaken for the subcommand.
        self.assert_outcome({"command": "git -C /x worktree add ../wt"}, True)

    def test_worktree_add_env_prefix(self) -> None:
        # An env-var assignment prefix does not consume the command slot.
        self.assert_outcome({"command": "FOO=bar git worktree add x"}, True)

    def test_worktree_add_subshell(self) -> None:
        self.assert_outcome({"command": "( git worktree add x )"}, True)

    def test_worktree_add_absolute_git(self) -> None:
        self.assert_outcome({"command": "/usr/bin/git worktree add x"}, True)

    def test_worktree_add_with_b_flag(self) -> None:
        self.assert_outcome({"command": "git worktree add -b feat ../wt"}, True)

    def test_worktree_add_in_for_loop(self) -> None:
        # An agent scripting a loop of worktree creates: the `do` shell keyword is
        # command-slot-transparent, so `git` after it is still seen.
        self.assert_outcome({"command": "for d in a b; do git worktree add $d; done"}, True)

    def test_worktree_add_in_if_branch(self) -> None:
        # `then` is command-slot-transparent.
        self.assert_outcome({"command": "if true; then git worktree add x; fi"}, True)

    def test_worktree_add_if_condition(self) -> None:
        # `if` is command-slot-transparent (the condition command follows it).
        self.assert_outcome({"command": "if git worktree add x; then echo hi; fi"}, True)

    # --- silent: other worktree subcommands, other git commands, non-git ---
    def test_worktree_list_no_warn(self) -> None:
        self.assert_outcome({"command": "git worktree list"}, False)

    def test_worktree_remove_no_warn(self) -> None:
        self.assert_outcome({"command": "git worktree remove ../wt"}, False)

    def test_worktree_prune_no_warn(self) -> None:
        self.assert_outcome({"command": "git worktree prune"}, False)

    def test_git_status_no_warn(self) -> None:
        self.assert_outcome({"command": "git status"}, False)

    def test_git_add_not_confused_with_worktree_add(self) -> None:
        # `git add` is NOT `git worktree add` — the subcommand is `add`, not
        # `worktree`, so it must stay silent.
        self.assert_outcome({"command": "git add -A"}, False)

    def test_worktree_inside_quoted_string_no_warn(self) -> None:
        # `git worktree add` inside a quoted string is not a command.
        self.assert_outcome({"command": 'echo "git worktree add x"'}, False)

    def test_git_as_argument_no_warn(self) -> None:
        # `git` as an argument of another command is not a git invocation.
        self.assert_outcome({"command": "echo git worktree add x"}, False)

    def test_non_git_command_no_warn(self) -> None:
        # Name-based no-trash detection is gone: an ordinary dir creation is silent.
        self.assert_outcome({"command": "mkdir kosyaks"}, False)

    def test_file_write_no_warn(self) -> None:
        self.assert_outcome({"file_path": "src/main.py"}, False)

    # --- fail-open ---
    def test_malformed_envelope_fails_open(self) -> None:
        for script in HOOKS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(script, None, raw="not json {{{")
                self.assertEqual(p.returncode, 0)
                self.assertEqual(p.stderr.strip(), "")

    def test_no_tool_input_fails_open(self) -> None:
        for script in HOOKS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(script, None, raw=json.dumps({"cwd": "/tmp"}))
                self.assertEqual(p.returncode, 0)
                self.assertEqual(p.stderr.strip(), "")


if __name__ == "__main__":
    unittest.main()
