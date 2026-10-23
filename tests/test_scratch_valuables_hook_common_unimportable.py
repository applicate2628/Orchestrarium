"""Regression test for the check-scratch-valuables import contract when the
shared `hook_common` helper is unimportable.

THE BUG THIS FILE GUARDS AGAINST (work-items/bugs/2026-07-26-scratch-
valuables-degrades-to-scanning-the-wrong-project-and-reports-it-as-correct.
md): a prior version of `check-scratch-valuables.py` (and its two byte-
identical mirrors) caught the `hook_common` import in a `try/except
Exception` and substituted a stub `parse_envelope` that always returned
`{}`. Discarding the envelope's declared `cwd` made `_resolve_root` fall
through to `Path.cwd()`, so a broken install scanned the PROCESS's working
directory instead of the project the envelope named, and reported those
findings as belonging to the caller's own project. Measured directly (see
the reproduction this test encodes): an envelope declaring `cwd=projB` with
the process running at `projA` produced `KEEPME_projB` in the advisory when
`hook_common` was importable, and `KEEPME_projA` -- the WRONG project --
when it was not. Exit 0 either way.

WHY THIS FILE IS SEPARATE FROM
`test_universal_audit_hooks_hook_common_unimportable.py`: that file covers
the six PreToolUse audits, whose defect class was MUTENESS -- a missing
`hook_common` made them silently do nothing, indistinguishable from a clean
run with no hit. This hook's defect was a WRONG ANSWER, not a missing one:
it kept producing a report, just about the wrong project. Asserting only the
exit code (as the six-audit file does) would not catch a regression here --
a "fixed" version that silently reports the wrong project's inventory could
still exit 1 for an unrelated reason and pass an exit-code-only check. This
file therefore asserts the ROOT: it seeds two DISTINCT projects with
distinguishably-named scratch content and checks which project's content (if
any) appears in the hook's own output, both when `hook_common` is present
(pinning the correct, envelope-driven resolution) and when it is not
(pinning that a broken install reports NEITHER project, rather than
substituting the wrong one).

THE CURRENT CONTRACT: the Python entrypoint acquires its required helper
inside the process error boundary. A missing helper exits 0 with empty stdout
and stderr before root resolution or scanning. No fallback parser or invented
inventory is allowed.

WHY THE FIXTURE COPIES THE HOOK INTO AN ISOLATED TEMP DIRECTORY rather than
hiding/renaming the real `hook_common.py` in place: this repository's
`Worktree safety` rule forbids mutating tracked files outside the task's own
edits. Copying the hook (and, for the healthy case, a copy of the real
`hook_common.py`) into a throwaway directory reproduces both "the shared
helper is unimportable" and "the shared helper works normally" with zero
risk to the real tree.
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

CLAUDE_HOOK = REPO_ROOT / "src.claude" / "agents" / "scripts" / "check-scratch-valuables.py"
UNIVERSAL_HOOK = REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "check-scratch-valuables.py"
CODEX_HOOK = REPO_ROOT / "src.codex" / "skills" / "lead" / "scripts" / "check-scratch-valuables.py"
UNIVERSAL_HOOK_COMMON = REPO_ROOT / "scripts" / "universal-hooks" / "scripts" / "hook_common.py"

# The canon plus its two byte-identical mirrors (see scripts/sync-universal-
# hooks.py for the canonical direction).
HOOKS = (
    ("universal (canon)", UNIVERSAL_HOOK),
    ("claude mirror", CLAUDE_HOOK),
    ("codex mirror", CODEX_HOOK),
)


def _make_project(tmp_root: Path, name: str) -> Path:
    """A minimal git repo with one distinguishably-named, git-content-unique
    file under `.scratch/` -- exactly the shape `_scan_valuables` is built to
    flag (see check-scratch-valuables.py's own module docstring)."""
    proj = tmp_root / name
    scratch = proj / ".scratch"
    scratch.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(proj)], check=True, capture_output=True)
    (scratch / f"KEEPME_{name}.md").write_text(f"unique valuable content for {name}", encoding="utf-8")
    return proj


def _run_hook_isolated(
    hook_path: Path, *, cwd: Path, envelope: dict, with_hook_common: bool
) -> subprocess.CompletedProcess:
    """Copy `hook_path` into a fresh `<tmp>/scripts/` dir. When
    `with_hook_common` is True, also copy the real `hook_common.py` in
    alongside it (reproducing a healthy install); when False, leave the
    directory with only the hook itself (reproducing a broken one). The
    hook's own `sys.path.insert(0, ..dirname(__file__))` line resolves to
    that directory either way."""
    workdir = Path(tempfile.mkdtemp())
    scripts_dir = workdir / "scripts"
    scripts_dir.mkdir()
    isolated_hook = scripts_dir / hook_path.name
    shutil.copy2(hook_path, isolated_hook)
    if with_hook_common:
        shutil.copy2(UNIVERSAL_HOOK_COMMON, scripts_dir / "hook_common.py")
    return subprocess.run(
        [sys.executable, str(isolated_hook)],
        input=json.dumps(envelope),
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=str(cwd),
    )


class ScratchValuablesHookCommonUnimportableTests(unittest.TestCase):
    def test_healthy_install_resolves_root_from_the_envelope_not_the_process_cwd(self) -> None:
        """Pins the CORRECT, pre-existing behavior this defect silently
        abandoned: with `hook_common` importable, the hook scans the
        envelope-declared `cwd` (projB) even when the process itself is
        running at a different directory (projA)."""
        for label, hook_path in HOOKS:
            with self.subTest(hook=label):
                tmp_root = Path(tempfile.mkdtemp())
                proj_a = _make_project(tmp_root, "projA")
                proj_b = _make_project(tmp_root, "projB")
                envelope = {"cwd": str(proj_b)}

                result = _run_hook_isolated(
                    hook_path, cwd=proj_a, envelope=envelope, with_hook_common=True
                )

                self.assertEqual(result.returncode, 0)
                self.assertIn("KEEPME_projB", result.stdout)
                self.assertNotIn("KEEPME_projA", result.stdout)

    def test_broken_install_reports_neither_projects_inventory(self) -> None:
        """Pins the chosen contract for the defect itself: with `hook_common`
        unimportable, the hook must not scan ANY root and print it as if it
        were the right one. The Python entry exits silently with zero before
        root resolution or either project's inventory can be reported."""
        for label, hook_path in HOOKS:
            with self.subTest(hook=label):
                tmp_root = Path(tempfile.mkdtemp())
                proj_a = _make_project(tmp_root, "projA")
                proj_b = _make_project(tmp_root, "projB")
                envelope = {"cwd": str(proj_b)}

                result = _run_hook_isolated(
                    hook_path, cwd=proj_a, envelope=envelope, with_hook_common=False
                )

                self.assertEqual(result.returncode, 0)
                self.assertEqual(
                    result.stdout, "",
                    "a broken install must report NEITHER project's inventory -- "
                    "printing the wrong one is the exact defect this test guards "
                    "against, and printing nothing is the chosen fail-closed contract",
                )
                self.assertNotIn("KEEPME_projA", result.stdout)
                self.assertNotIn("KEEPME_projB", result.stdout)
                self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
