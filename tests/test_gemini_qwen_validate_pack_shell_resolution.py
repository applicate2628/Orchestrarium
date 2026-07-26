r"""Regression coverage for
work-items/bugs/2026-07-19-gemini-qwen-validate-pack-ps1-shell-resolution.md.

Before this fix, `src.gemini/scripts/validate-pack.ps1` and
`src.qwen/scripts/validate-pack.ps1` (byte-identical to each other) carried
the PRE-9d6afb88 derived-root-only bundled-shell resolution: if git's derived
install root had no bundled bash/sh (e.g. git resolves under
`...\Git\mingw64\bin` with no bundled bash there), the wrapper threw "Unable
to locate bundled bash.exe or sh.exe" instead of falling back to a PATH
bash/sh -- exactly the bug class `9d6afb88` fixed for the claude/codex
`validate-skill-pack.ps1` pair. They also carried the same unguarded
`(& $gitExecutable rev-parse --show-toplevel).Trim()` pattern as
`2026-07-19-publication-wrapper-nonrepo-null-trim`: outside a git repo,
`rev-parse` prints nothing, PowerShell yields `$null`, and `.Trim()` throws
`InvalidOperation: You cannot call a method on a null-valued expression`
before the wrapper's own intended clean `throw` can run.

This module drives the ACTUAL .ps1 entry points (not a .py reimplementation)
under every available PowerShell host, mirroring the fixture shape already
proven for the claude/codex pair in test_powershell_wrappers_smoke.py's
TestPackValidatorShellResolution, scoped to just these two files so this
lane's change surface stays independent of that larger shared test module.

POSIX-only CI safety: if neither `pwsh` nor `powershell` is on PATH, the
whole module is SKIPPED, so the suite stays green where PowerShell does not
exist.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

VALIDATORS = (
    REPO_ROOT / "src.gemini" / "scripts" / "validate-pack.ps1",
    REPO_ROOT / "src.qwen" / "scripts" / "validate-pack.ps1",
)


def _interpreters() -> list[str]:
    found: list[str] = []
    for name in ("pwsh", "powershell"):
        exe = shutil.which(name)
        if exe:
            found.append(exe)
    return found


INTERPRETERS = _interpreters()
GIT = shutil.which("git")


def _run_ps1(interp: str, script: Path, *, cwd: str | None = None,
             env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [interp, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _write_cmd(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("@echo off\r\n" + body, encoding="utf-8", newline="")


def _copy_validator_fixture(root: Path, validator: Path) -> Path:
    """Copy the real validate-pack.ps1 alongside a dummy sibling
    validate-pack.sh (its content never runs in the PATH-fallback tests
    below, since the resolved "shell" there is a fake .cmd that ignores its
    arguments -- the sibling file only needs to EXIST for the wrapper's own
    Test-Path guard to pass)."""
    scripts = root / "pack" / "scripts"
    scripts.mkdir(parents=True)
    copied = scripts / "validate-pack.ps1"
    shutil.copy2(validator, copied)
    (scripts / "validate-pack.sh").write_text(
        "#!/usr/bin/env bash\n"
        "printf 'derived-root\\n' >> \"$ORCHESTRARIUM_SHELL_PROBE\"\n"
        "exit 0\n",
        encoding="utf-8",
        newline="\n",
    )
    return copied


def _path_shell_env(root: Path, git_dir: Path) -> tuple[dict, Path]:
    marker = root / "shell.marker"
    path_shells = root / "path-shells"
    _write_cmd(
        path_shells / "bash.cmd",
        ">>\"%ORCHESTRARIUM_SHELL_PROBE%\" echo path-bash\r\nexit /b 0\r\n",
    )
    _write_cmd(
        path_shells / "sh.cmd",
        ">>\"%ORCHESTRARIUM_SHELL_PROBE%\" echo path-sh\r\nexit /b 0\r\n",
    )
    env = dict(os.environ)
    env["ORCHESTRARIUM_SHELL_PROBE"] = str(marker)
    env["PATH"] = os.pathsep.join((str(git_dir), str(path_shells), env.get("PATH", "")))
    return env, marker


def _write_cwd_probe_script(scripts_dir: Path) -> None:
    """A REAL (non-fake) validate-pack.sh that reports whether its OWN
    process cwd is the fixture's designated 'correct root', by testing for a
    sentinel file placed there -- avoids Windows/POSIX/Git-Bash path-string
    translation entirely (bash's `pwd` under Git Bash prints a `/c/...`-style
    path that would need translating back to compare against a Windows
    Path). This script actually RUNS for real in the tests that use it (they
    do not fake the shell away), because we want to observe where
    Set-Location actually left the process, not just which binary got
    selected."""
    (scripts_dir / "validate-pack.sh").write_text(
        "#!/usr/bin/env bash\n"
        "if [ -f \"ORCHESTRARIUM_EXPECTED_ROOT.marker\" ]; then\n"
        "  printf 'CORRECT_ROOT\\n' >> \"$ORCHESTRARIUM_SHELL_PROBE\"\n"
        "else\n"
        "  printf 'WRONG_ROOT:%s\\n' \"$(pwd)\" >> \"$ORCHESTRARIUM_SHELL_PROBE\"\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
        newline="\n",
    )


def _bash_locatable_git() -> str | None:
    """First PATH git.exe whose derived install root (2-up) contains a
    bundled bash/sh -- mirrors the helper of the same name in
    test_powershell_wrappers_smoke.py."""
    sub = ("bin/bash.exe", "usr/bin/bash.exe", "usr/bin/sh.exe")
    for d in os.environ.get("PATH", "").split(os.pathsep):
        if not d:
            continue
        g = Path(d) / "git.exe"
        if g.is_file():
            root = g.parent.parent
            if any((root / c).is_file() for c in sub):
                return str(g)
    return None


@unittest.skipIf(not INTERPRETERS, "no PowerShell host (pwsh/powershell) on PATH")
class TestGeminiQwenValidatePackShellResolution(unittest.TestCase):
    def test_path_fallback_uses_bash_after_derived_root_candidates_miss(self) -> None:
        """Core regression: a git whose derived install root has no bundled
        bash/sh must fall back to a PATH bash/sh instead of throwing "Unable
        to locate bundled bash.exe or sh.exe" -- the pre-fix behavior."""
        for interp in INTERPRETERS:
            for validator in VALIDATORS:
                self.assertTrue(validator.is_file(), f"missing validator {validator}")
                with self.subTest(interp=Path(interp).stem, validator=str(validator.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = _copy_validator_fixture(root, validator)
                        git_dir = root / "fake-git" / "mingw64" / "bin"
                        _write_cmd(git_dir / "git.cmd", f"echo {root}\r\nexit /b 0\r\n")
                        env, marker = _path_shell_env(root, git_dir)

                        p = _run_ps1(interp, copied, cwd=str(root), env=env)

                        self.assertEqual(
                            p.returncode, 0,
                            "PATH bash fallback must run after all derived-root candidates miss; "
                            f"stdout={p.stdout!r} stderr={p.stderr!r}",
                        )
                        self.assertEqual(marker.read_text(encoding="utf-8").splitlines(), ["path-bash"])

    def test_derived_root_bash_precedes_path_bash(self) -> None:
        """When a bash-locatable git IS on PATH, the derived-root candidate
        must still win over the PATH fallback (fallback is a last resort,
        not a replacement)."""
        bashable_git = _bash_locatable_git()
        if bashable_git is None:
            self.skipTest("no PATH git whose derived install root contains bash/sh")
        git_dir = Path(bashable_git).parent

        for interp in INTERPRETERS:
            for validator in VALIDATORS:
                with self.subTest(interp=Path(interp).stem, validator=str(validator.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied = _copy_validator_fixture(root, validator)
                        env, marker = _path_shell_env(root, git_dir)

                        p = _run_ps1(interp, copied, cwd=str(root), env=env)

                        self.assertEqual(
                            p.returncode, 0,
                            "derived-root bash must run before PATH fallback; "
                            f"stdout={p.stdout!r} stderr={p.stderr!r}",
                        )
                        self.assertEqual(marker.read_text(encoding="utf-8").splitlines(), ["derived-root"])

    @unittest.skipIf(GIT is None, "needs git on PATH")
    def test_non_repo_directory_does_not_crash_with_null_trim(self) -> None:
        """Regression for the sibling null-.Trim() defect
        (2026-07-19-publication-wrapper-nonrepo-null-trim): running the
        validator outside any git repository must not raise
        'InvalidOperation: You cannot call a method on a null-valued
        expression'. A guarded rev-parse either falls back to the
        script-relative runtime root (this validator's role is not a
        repo-mandatory gate) or throws its OWN clean diagnostic -- either is
        acceptable; an interpreter-level null-method crash is not."""
        for interp in INTERPRETERS:
            for validator in VALIDATORS:
                with self.subTest(interp=Path(interp).stem, validator=str(validator.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        # Confirm this OS-temp directory is genuinely OUTSIDE
                        # any git repo before trusting the crash-absence
                        # assertion below -- if the temp root happens to be
                        # nested under a repo, rev-parse would succeed and the
                        # non-repo code path this test targets would never
                        # execute, making a pass meaningless.
                        assert GIT is not None
                        probe = subprocess.run(
                            [GIT, "-C", str(root), "rev-parse", "--show-toplevel"],
                            capture_output=True, text=True,
                        )
                        if probe.returncode == 0:
                            self.skipTest(
                                f"temp dir {root} is unexpectedly inside a git repo "
                                f"({probe.stdout.strip()!r}); cannot exercise the non-repo path"
                            )
                        copied = _copy_validator_fixture(root, validator)
                        # A real git on PATH, pointed at a directory with NO
                        # .git anywhere above it, so `rev-parse --show-toplevel`
                        # genuinely fails (non-repo case) rather than being
                        # faked -- this exercises the real git binary's null
                        # output, not a synthetic stand-in.
                        env = dict(os.environ)
                        p = _run_ps1(interp, copied, cwd=str(root), env=env)
                        combined = p.stdout + p.stderr
                        self.assertNotIn(
                            "You cannot call a method on a null-valued expression",
                            combined,
                            f"null-.Trim() crash reproduced outside a git repo:\n{combined}",
                        )

    def _require_nonrepo_dir(self, root: Path) -> None:
        assert GIT is not None
        probe = subprocess.run(
            [GIT, "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True, text=True,
        )
        if probe.returncode == 0:
            self.skipTest(
                f"temp dir {root} is unexpectedly inside a git repo "
                f"({probe.stdout.strip()!r}); cannot exercise the non-repo path"
            )

    @unittest.skipIf(GIT is None, "needs git on PATH")
    def test_nonrepo_fallback_resolves_literal_path_with_wildcard_chars_in_dir_name(self) -> None:
        """Finding 5 regression: Resolve-Path / Set-Location without
        -LiteralPath treat their argument as a WILDCARD pattern. A pack
        living under a directory whose name contains a glob-special
        character (e.g. 'pack[v1]') then resolves to $null -- reproduced
        directly this session: a hard PSArgumentNullException on Windows
        PowerShell 5.1, or a silent relocation to $HOME on pwsh 7 (Set-Location
        $null there succeeds and lands in the user's home directory) --
        either way never reaching the correct root.

        The bracket-named directory MUST be the directory that SURVIVES the
        '..\\..' navigation (i.e. the resolved 2-ups target itself), not an
        intermediate segment the '..' tokens cancel out: Resolve-Path
        collapses literal '..' segments lexically before any wildcard
        matching reaches the filesystem, so a bracket in a fully-cancelled
        segment never actually exercises the bug (confirmed empirically --
        an earlier draft of this fixture put the bracket one level too deep
        and the bug silently failed to reproduce even against the un-fixed
        code). Layout: <root>/pack[v1]/src.gemini/scripts/validate-pack.ps1
        -- 'src.gemini' and 'scripts' are cancelled by the two '..' tokens,
        leaving 'pack[v1]' as the directory Resolve-Path must actually
        resolve."""
        for interp in INTERPRETERS:
            for validator in VALIDATORS:
                with self.subTest(interp=Path(interp).stem, validator=str(validator.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        self._require_nonrepo_dir(root)

                        bracket_root = root / "pack[v1]"
                        scripts = bracket_root / "src.gemini" / "scripts"
                        scripts.mkdir(parents=True)
                        copied = scripts / "validate-pack.ps1"
                        shutil.copy2(validator, copied)
                        _write_cwd_probe_script(scripts)
                        (bracket_root / "ORCHESTRARIUM_EXPECTED_ROOT.marker").write_text("x", encoding="utf-8")

                        marker = root / "shell.marker"
                        env = dict(os.environ)
                        env["ORCHESTRARIUM_SHELL_PROBE"] = str(marker)

                        p = _run_ps1(interp, copied, cwd=str(root), env=env)
                        combined = p.stdout + p.stderr

                        self.assertNotIn(
                            "PSArgumentNullException", combined,
                            f"PowerShell 5.1-style null-argument crash on a wildcard-char "
                            f"directory name:\n{combined}",
                        )
                        self.assertEqual(p.returncode, 0, f"stdout={p.stdout!r} stderr={p.stderr!r}")
                        self.assertTrue(
                            marker.is_file(),
                            f"the sibling shell never ran (crashed before reaching it); "
                            f"stdout={p.stdout!r} stderr={p.stderr!r}",
                        )
                        result = marker.read_text(encoding="utf-8").strip()
                        self.assertEqual(
                            result, "CORRECT_ROOT",
                            f"validator landed in the WRONG directory (wildcard-char "
                            f"mis-resolution, e.g. pwsh's Set-Location $null -> $HOME): {result}",
                        )

    @unittest.skipIf(GIT is None, "needs git on PATH")
    def test_nonrepo_fallback_lands_on_the_correct_pack_root(self) -> None:
        """Claim 6 regression: the '..\\..' fallback depth (2 directory
        levels up from src.<provider>/scripts to the pack root) must resolve
        to the ACTUAL correct pack root, not merely 'somewhere that does not
        crash'. An off-by-one depth (e.g. a single '..', or '..\\..\\..')
        would silently point the validator at the wrong directory instead of
        failing loudly -- this test mirrors the REAL src.<provider>/scripts
        nesting exactly and asserts the resolved cwd is the correct root."""
        for interp in INTERPRETERS:
            for validator in VALIDATORS:
                with self.subTest(interp=Path(interp).stem, validator=str(validator.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        self._require_nonrepo_dir(root)

                        # Mirror the REAL monorepo/standalone-branch nesting
                        # exactly: <root>/src.gemini/scripts/validate-pack.ps1
                        # (or src.qwen), 2 directory levels deep.
                        intermediate = validator.parent.parent.name
                        scripts = root / intermediate / "scripts"
                        scripts.mkdir(parents=True)
                        copied = scripts / "validate-pack.ps1"
                        shutil.copy2(validator, copied)
                        _write_cwd_probe_script(scripts)
                        (root / "ORCHESTRARIUM_EXPECTED_ROOT.marker").write_text("x", encoding="utf-8")

                        marker = root / "shell.marker"
                        env = dict(os.environ)
                        env["ORCHESTRARIUM_SHELL_PROBE"] = str(marker)

                        p = _run_ps1(interp, copied, cwd=str(root), env=env)

                        self.assertEqual(p.returncode, 0, f"stdout={p.stdout!r} stderr={p.stderr!r}")
                        self.assertTrue(
                            marker.is_file(),
                            f"the sibling shell never ran; stdout={p.stdout!r} stderr={p.stderr!r}",
                        )
                        result = marker.read_text(encoding="utf-8").strip()
                        self.assertEqual(
                            result, "CORRECT_ROOT",
                            f"fallback depth resolved to the WRONG directory: {result}",
                        )

    @unittest.skipIf(GIT is None, "needs git on PATH")
    def test_primary_branch_resolves_bracket_named_repo_root(self) -> None:
        """F-B regression: `Set-Location $repoRoot` -- the PRIMARY,
        git-available branch, run on EVERY in-repo invocation -- was still
        positional even after the fallback (non-repo) branch a few lines
        below it was given -LiteralPath. Set-Location treats a positional
        argument as a WILDCARD pattern, so a real repo living under a
        bracket-named directory (e.g. 'repo[v2]') fails wildcard
        resolution. Reproduced directly this session: pwsh 7 throws "Cannot
        find path ... because it does not exist" (the validator never
        runs); Windows PowerShell 5.1 happens to still succeed -- the
        OPPOSITE engine split from the fallback branch's failure modes
        (PS 5.1 crash / pwsh silent-$HOME), so that branch's fix and test
        do not cover this one. This is the mutant the coordinator reported
        as surviving the full suite in either direction."""
        for interp in INTERPRETERS:
            for validator in VALIDATORS:
                with self.subTest(interp=Path(interp).stem, validator=str(validator.relative_to(REPO_ROOT))):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        bracket_repo = root / "repo[v2]"
                        scripts = bracket_repo / "src.gemini" / "scripts"
                        scripts.mkdir(parents=True)
                        copied = scripts / "validate-pack.ps1"
                        shutil.copy2(validator, copied)
                        _write_cwd_probe_script(scripts)
                        (bracket_repo / "ORCHESTRARIUM_EXPECTED_ROOT.marker").write_text("x", encoding="utf-8")

                        assert GIT is not None
                        subprocess.run([GIT, "init", "-q", str(bracket_repo)], check=True, capture_output=True)
                        subprocess.run([GIT, "-C", str(bracket_repo), "config", "user.email", "t@t"],
                                        check=True, capture_output=True)
                        subprocess.run([GIT, "-C", str(bracket_repo), "config", "user.name", "t"],
                                        check=True, capture_output=True)

                        marker = root / "shell.marker"
                        env = dict(os.environ)
                        env["ORCHESTRARIUM_SHELL_PROBE"] = str(marker)

                        p = _run_ps1(interp, copied, cwd=str(bracket_repo), env=env)
                        combined = p.stdout + p.stderr

                        self.assertNotIn(
                            "Cannot find path", combined,
                            f"Set-Location wildcard-resolution failure on a bracket-named "
                            f"repo root:\n{combined}",
                        )
                        self.assertEqual(p.returncode, 0, f"stdout={p.stdout!r} stderr={p.stderr!r}")
                        self.assertTrue(
                            marker.is_file(),
                            f"the sibling shell never ran; stdout={p.stdout!r} stderr={p.stderr!r}",
                        )
                        result = marker.read_text(encoding="utf-8").strip()
                        self.assertEqual(
                            result, "CORRECT_ROOT",
                            f"validator landed in the WRONG directory: {result}",
                        )


if __name__ == "__main__":
    unittest.main()
