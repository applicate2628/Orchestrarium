"""Regression tests for the stray-artifact PreToolUse hook (AUDIT mode).

The hook lives in `check-no-trash-in-repo.py` (filename retained for install-marker
continuity; a rename to check-stray-artifact is a tracked follow-up). It warns on a
confident `git worktree add` Bash command — the unrequested-worktree side effect —
EXCEPT one add whose command ends with the exact command-local marker
`# orchestrarium:requested-isolation-worktree` (a protocol-requested isolation
worktree per the parallel-isolation protocol). A missing/near-match/quoted/not-final
marker, or two-or-more adds with one marker, still warns — one marker never
suppresses a batch. `git worktree list/remove/prune`, `git add` (not `git worktree
add`), other git commands, `git` inside a quoted string, non-git commands, and file
writes never warn. AUDIT mode: always exits 0; a hit emits one line of JSON to
stdout -- `{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":
"..."}}` -- the model-visible delivery channel (see `hook_common.emit_advisory`);
silent otherwise. This replaced a stderr-plus-exit-1 form measured to reach
nobody on either provider line (see
work-items/bugs/2026-07-26-mcp-reminder-uses-the-once-per-session-form-its-
sibling-calls-broken.md). Tested against BOTH the Claude and Codex hook copies.
"""

from __future__ import annotations

import json
import shutil
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

# Two real directories standing in for the two CWD shapes the root-destined
# triggers discriminate between. The repo-root probe is `(cwd/".git").exists()`,
# so these must exist on disk — a synthetic path string cannot exercise it.
#   ROOT_CWD     -- contains a `.git` entry -> IS a repository root
#   NON_ROOT_CWD -- no `.git` -> not a root, so root-destined triggers stay silent
# `_TMP_ROOTS` holds them for tearDownModule.
ROOT_CWD = ""
NON_ROOT_CWD = ""
_TMP_ROOTS: list[str] = []


def setUpModule() -> None:
    global ROOT_CWD, NON_ROOT_CWD
    ROOT_CWD = tempfile.mkdtemp(prefix="orch-hook-root-")
    NON_ROOT_CWD = tempfile.mkdtemp(prefix="orch-hook-sub-")
    _TMP_ROOTS.extend((ROOT_CWD, NON_ROOT_CWD))
    # A worktree/submodule checkout has `.git` as a FILE, a normal clone as a
    # DIRECTORY; the probe accepts either, so a directory is enough here.
    (Path(ROOT_CWD) / ".git").mkdir()


def tearDownModule() -> None:
    for path in _TMP_ROOTS:
        shutil.rmtree(path, ignore_errors=True)


def run_hook(
    script: Path,
    tool_input: object,
    raw: str | None = None,
    cwd: str = "/tmp",
) -> subprocess.CompletedProcess:
    envelope = {"cwd": cwd, "tool_input": tool_input}
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
                # AUDIT never BLOCKS (never exit 2) and never uses a non-zero exit
                # for a hit either -- the advisory travels via stdout JSON, always
                # exit 0 (see hook_common.emit_advisory).
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(p.stderr, "")
                self.assertEqual(bool(p.stdout.strip()), should_warn, f"stdout={p.stdout!r}")

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
                self.assertEqual(p.stdout.strip(), "")

    def test_no_tool_input_fails_open(self) -> None:
        for script in HOOKS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(script, None, raw=json.dumps({"cwd": "/tmp"}))
                self.assertEqual(p.returncode, 0)
                self.assertEqual(p.stderr.strip(), "")
                self.assertEqual(p.stdout.strip(), "")


class TestRequestedIsolationMarker(unittest.TestCase):
    """A2 marker discriminator: exactly one `git worktree add` whose command ends
    with the exact `# orchestrarium:requested-isolation-worktree` marker is a
    protocol-requested isolation worktree and is NOT warned; every other shape
    (missing/near-match/quoted/not-final marker, or a batch of adds) still warns."""

    MARKER = "# orchestrarium:requested-isolation-worktree"

    def assert_outcome(self, tool_input: object, should_warn: bool, raw: str | None = None) -> None:
        for script in HOOKS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(script, tool_input, raw)
                # AUDIT never BLOCKS (never exit 2) and never uses a non-zero exit
                # for a hit either -- the advisory travels via stdout JSON, always
                # exit 0 (see hook_common.emit_advisory).
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(p.stderr, "")
                self.assertEqual(bool(p.stdout.strip()), should_warn, f"stdout={p.stdout!r}")

    # --- silent: exactly one add + exact end-of-command marker ---
    def test_single_add_with_exact_marker_no_warn(self) -> None:
        self.assert_outcome(
            {"command": f"git worktree add .scratch/worktrees/lane-a {self.MARKER}"}, False
        )

    def test_single_add_with_marker_cd_chained_no_warn(self) -> None:
        self.assert_outcome(
            {"command": f"cd repo && git worktree add ../wt {self.MARKER}"}, False
        )

    def test_single_add_with_marker_trailing_whitespace_no_warn(self) -> None:
        # `command.rstrip()` tolerates trailing whitespace before the check.
        self.assert_outcome(
            {"command": f"git worktree add ../wt {self.MARKER}   \n"}, False
        )

    # --- WARN: marker present but not the exact requested shape ---
    def test_add_without_marker_warns(self) -> None:
        # (already covered by the bare case, restated for the matrix)
        self.assert_outcome({"command": "git worktree add ../wt"}, True)

    def test_add_with_near_match_marker_warns(self) -> None:
        # one character short of the exact marker
        self.assert_outcome(
            {"command": "git worktree add ../wt # orchestrarium:requested-isolation-worktre"}, True
        )

    def test_add_with_marker_in_quoted_arg_warns(self) -> None:
        # marker inside a quoted argument is not the end-of-command marker
        self.assert_outcome(
            {"command": f'git worktree add ../wt "{self.MARKER}"'}, True
        )

    def test_add_with_marker_not_final_warns(self) -> None:
        # marker followed by another command -> not at absolute command end
        self.assert_outcome(
            {"command": f"git worktree add ../wt {self.MARKER} && echo done"}, True
        )

    def test_two_adds_one_marker_warns(self) -> None:
        # one marker never suppresses a batch of adds
        self.assert_outcome(
            {"command": f"git worktree add ../a && git worktree add ../b {self.MARKER}"}, True
        )

    def test_marker_alone_without_add_no_warn(self) -> None:
        # a non-add command that merely ends with the marker is not a worktree add
        self.assert_outcome({"command": f"echo hi {self.MARKER}"}, False)


class _CwdAwareHookCase(unittest.TestCase):
    """Shared outcome assertion for the root-destined triggers, which need a REAL
    `cwd` on disk (the repo-root probe stats `cwd/".git"`)."""

    def assert_outcome(
        self, tool_input: object, should_warn: bool, cwd: str = "/tmp"
    ) -> None:
        for script in HOOKS:
            with self.subTest(script=script.parent.parent.name):
                p = run_hook(script, tool_input, cwd=cwd)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(p.stderr, "")
                self.assertEqual(bool(p.stdout.strip()), should_warn, f"stdout={p.stdout!r}")


class TestMangledRedirectTarget(_CwdAwareHookCase):
    """Mechanism 2 — Git Bash eats the backslashes of a Windows redirect target,
    so `> r:\\Temp\\x\\build.log` becomes ONE file literally named
    `r:Tempxbuild.log` and the command reports success. A single-letter drive
    prefix followed by a colon in a target carrying NO path separator at all is
    always this mistake, so it warns on its own merits — independent of the
    artifact-extension list and independent of where the process is running."""

    def test_mangled_drive_prefix_warns(self) -> None:
        self.assert_outcome({"command": "ifx probe.f90 > r:Tempxbuild.log"}, True)

    def test_mangled_drive_prefix_warns_outside_repo_root(self) -> None:
        # ALWAYS a mistake -> not gated on the repo-root probe.
        self.assert_outcome(
            {"command": "make > c:Usersdimalog.txt"}, True, cwd=NON_ROOT_CWD
        )

    def test_mangled_drive_prefix_append_warns(self) -> None:
        self.assert_outcome({"command": "echo hi >> d:builddiag.log"}, True)

    # --- silent: a well-formed path that merely contains a drive letter ---
    def test_wellformed_windows_path_no_warn(self) -> None:
        # separators intact -> the redirect lands where it was aimed
        self.assert_outcome({"command": "make > r:/Temp/x/build.log"}, False)

    def test_wellformed_backslash_path_no_warn(self) -> None:
        self.assert_outcome({"command": r"make > r:\Temp\x\build.log"}, False)

    def test_stderr_dup_not_a_mangled_target(self) -> None:
        # `2>&1` tokenizes to a `>&` operator whose target is `1` — not a path.
        self.assert_outcome({"command": "make > .scratch/t/o.log 2>&1"}, False)


class TestRootArtifactRedirect(_CwdAwareHookCase):
    """Mechanism 1 — a bare `> foo.log` redirect writes to the process CWD, which
    for a tool-run command is the repository root. Closed on both axes: the
    destination is one directory (a CONFIRMED repo root) and the name must match
    an enumerated build/log artifact extension."""

    def test_bare_log_redirect_into_root_warns(self) -> None:
        self.assert_outcome({"command": "make > build.log"}, True, cwd=ROOT_CWD)

    def test_bare_log_append_into_root_warns(self) -> None:
        self.assert_outcome({"command": "make >> build.log"}, True, cwd=ROOT_CWD)

    def test_dot_slash_log_redirect_into_root_warns(self) -> None:
        # `./x.log` has no real directory component — same destination.
        self.assert_outcome({"command": "make > ./build.log"}, True, cwd=ROOT_CWD)

    def test_bare_obj_redirect_into_root_warns(self) -> None:
        self.assert_outcome({"command": "cat x > probe.obj"}, True, cwd=ROOT_CWD)

    # --- silent: the false-positive side ---
    def test_redirect_into_scratch_subdir_no_warn(self) -> None:
        # A legitimate capture under a scratch subdirectory — the whole point of
        # the rule the guard enforces. Must stay silent.
        self.assert_outcome(
            {"command": "make > .scratch/build/build.log"}, False, cwd=ROOT_CWD
        )

    def test_redirect_from_non_root_cwd_no_warn(self) -> None:
        # Same bare target, but the process is NOT at a repository root.
        self.assert_outcome({"command": "make > build.log"}, False, cwd=NON_ROOT_CWD)

    def test_redirect_after_cd_no_warn(self) -> None:
        # A `cd` moves the CWD, so the destination is no longer decidable ->
        # fail open. This is the documented "run the tool from inside its own
        # scratch output dir" pattern.
        self.assert_outcome(
            {"command": "cd .scratch/t && make > build.log"}, False, cwd=ROOT_CWD
        )

    def test_non_artifact_extension_no_warn(self) -> None:
        # A root write of a non-artifact name is ordinary authoring, not trash.
        self.assert_outcome({"command": "make > CHANGELOG.md"}, False, cwd=ROOT_CWD)

    def test_absolute_redirect_elsewhere_no_warn(self) -> None:
        self.assert_outcome({"command": "make > /tmp/build.log"}, False, cwd=ROOT_CWD)


class TestRootCompilerOutput(_CwdAwareHookCase):
    """Mechanism 3 — `ifx`/`cl`/`gcc` write `.obj`/`.o`/`.pdb` beside the
    invocation unless directed elsewhere, and the compile succeeds silently.
    This is the mechanism behind all 54 artifacts in the recorded cleanup."""

    def test_ifx_compile_in_root_warns(self) -> None:
        self.assert_outcome({"command": "ifx probe.f90"}, True, cwd=ROOT_CWD)

    def test_ifx_compile_only_in_root_warns(self) -> None:
        self.assert_outcome({"command": "ifx -c probe.f90"}, True, cwd=ROOT_CWD)

    def test_cl_compile_in_root_warns(self) -> None:
        self.assert_outcome({"command": "cl /c probe.cpp"}, True, cwd=ROOT_CWD)

    def test_gfortran_compile_in_root_warns(self) -> None:
        self.assert_outcome({"command": "gfortran oracle.f90"}, True, cwd=ROOT_CWD)

    def test_gcc_compile_in_root_warns(self) -> None:
        self.assert_outcome({"command": "gcc falsifier.c"}, True, cwd=ROOT_CWD)

    def test_compiler_absolute_path_in_root_warns(self) -> None:
        self.assert_outcome({"command": "/usr/bin/gcc qa_probe.c"}, True, cwd=ROOT_CWD)

    # --- silent: the false-positive side ---
    def test_compile_with_explicit_output_no_warn(self) -> None:
        self.assert_outcome(
            {"command": "gcc -o .scratch/t/probe probe.c"}, False, cwd=ROOT_CWD
        )

    def test_compile_with_msvc_fo_no_warn(self) -> None:
        self.assert_outcome(
            {"command": "cl /c /Fo.scratch\\t\\ probe.cpp"}, False, cwd=ROOT_CWD
        )

    def test_compile_after_cd_no_warn(self) -> None:
        self.assert_outcome(
            {"command": "cd .scratch/t && ifx probe.f90"}, False, cwd=ROOT_CWD
        )

    def test_compile_from_non_root_cwd_no_warn(self) -> None:
        self.assert_outcome({"command": "ifx probe.f90"}, False, cwd=NON_ROOT_CWD)

    def test_compiler_version_probe_no_warn(self) -> None:
        # No source operand -> nothing is compiled, nothing is written.
        self.assert_outcome({"command": "gcc --version"}, False, cwd=ROOT_CWD)

    def test_non_compiler_command_no_warn(self) -> None:
        self.assert_outcome({"command": "python probe.py"}, False, cwd=ROOT_CWD)

    def test_compiler_mentioned_in_quoted_string_no_warn(self) -> None:
        self.assert_outcome({"command": 'echo "ifx probe.f90"'}, False, cwd=ROOT_CWD)


if __name__ == "__main__":
    unittest.main()
