"""Regression tests for the allowlist-aware publication leak-scanner.

Drives the REAL scanner (`check-publication-safety.sh`, both the Claude and
Codex byte-identical-logic copies) via its production `--cached` staged-scan
mode against a throwaway git repo, asserting EXIT CODES (the scanner contract:
exit 1 = BLOCK a leak marker was found; exit 0 = PASS clean). Exit-code
assertions are robust to multi-pattern double-fire (MF7).

Coverage:
  - must-BLOCK rows: concrete Windows/MSYS/macOS user homes (incl. lowercase
    drive, forward-slash, the MSYS-dead leading-slash forms), dev/work/projects
    roots, exact-vs-substring example tokens (`username2`, `meadow`), every
    non-path secret/transcript marker, and secret-combined-with-allowed-token
    lines (MF3).
  - must-PASS rows: every placeholder form, all 8 ALLOWED_USER_TOKENS,
    `%USERPROFILE%` / `%USERNAME%` / `$HOME` / `${...}`, `C:\\Windows\\...`,
    `C:\\Program Files\\...`, and generic prose.
  - fallback (no-Python / allowlist-owner-unreachable): refined-ERE branch still
    BLOCKs real paths + secrets and still PASSes true placeholders, emitting the
    degraded-mode notice.

MF6 (gate safety): this test file is itself scanned by the publication gate, so
it must contain NO machine-local-path literal that the scanner would flag. Every
flaggable path is therefore ASSEMBLED AT RUNTIME from fragments (drive letter,
separator, root word, and segment kept as separate string pieces joined by
`_join`), so no complete flaggable path token ever appears as a literal in the
tracked source. A self-test (`test_this_test_file_is_gate_safe`) imports the
reference `find_machine_paths` and asserts this file has zero flaggable lines.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CODEX_SCANNER = REPO_ROOT / "src.codex" / "skills" / "lead" / "scripts" / "check-publication-safety.sh"
CLAUDE_SCANNER = REPO_ROOT / "src.claude" / "agents" / "scripts" / "check-publication-safety.sh"
CODEX_REF = REPO_ROOT / "src.codex" / "skills" / "lead" / "hooks" / "check-machine-local-path.py"
SCANNERS = (CODEX_SCANNER, CLAUDE_SCANNER)

BACKSLASH = chr(92)  # keep the literal backslash out of source path literals


def _join(*parts: str) -> str:
    """Concatenate fragments with no separator. Used so a complete flaggable
    path is only ever built at runtime, never present as a source literal."""
    return "".join(parts)


def _bash() -> str | None:
    return shutil.which("bash")


def _git() -> str | None:
    return shutil.which("git")


def _load_find_machine_paths():
    spec = importlib.util.spec_from_file_location("_mlp_ref_test", str(CODEX_REF))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.find_machine_paths


# --- Row builders (assembled at runtime; no flaggable literal in source) ------
# Each entry is the file CONTENT to stage. Drive letters / separators / root
# words / segments are kept as fragments and joined so the tracked test source
# never contains a complete machine-local path token.

WIN = "C" + ":"            # "C:" assembled
WIN_D = "D" + ":"
WIN_LOWER = "c" + ":"
BS = BACKSLASH
FS = "/"
USERS = "Use" + "rs"       # "Users" split so the source has no `:\\Users` literal
users_lower = "use" + "rs"
REAL = "real" + "user"     # a concrete (non-allowed) username
DEV = "de" + "v"
WORK = "wo" + "rk"
PROJ = "proj" + "ects"
HOME = "ho" + "me"


def block_rows() -> dict[str, str]:
    return {
        "b01_win_home": _join(WIN, BS, USERS, BS, REAL),
        "b02_win_home_deep": _join(WIN, BS, USERS, BS, REAL, BS, ".claude", BS, "agents"),
        "b03_win_home_lower": _join(WIN_LOWER, BS, users_lower, BS, "dima"),
        "b04_win_home_fwd": _join(WIN, FS, USERS, FS, REAL),
        "b05_dev_root": _join(WIN_D, BS, DEV, BS, "Orchestrator", BS, "Orchestrarium"),
        "b06_work_root": _join(WIN_D, BS, WORK, BS, "proj"),
        "b07_projects_root": _join(WIN, BS, PROJ, BS, "dima"),  # realistic name (see adjacent finding re: \x)
        "b08_posix_home": _join(FS, HOME, FS, "dima", FS, WORK),
        "b09_macos_home": _join(FS, USERS, FS, "dima", FS, "proj"),
        "b10_msys_home": _join(FS, "c", FS, USERS, FS, "dima", FS, "x"),
        "b11_msys_dev": _join(FS, "d", FS, DEV, FS, "Orchestrator"),
        "b12_token_substring_username2": _join(WIN, BS, USERS, BS, "username2"),
        "b13_token_substring_meadow": _join(WIN, BS, USERS, BS, "meadow"),
        # non-path secrets / transcript markers (assembled so no real secret literal sits in source)
        "b14_aws": "AKIA" + ("A" * 16),
        "b15_ghp": "ghp_" + ("a" * 36),
        "b16_password": "pass" + "word" + ": hunter2",
        "b17_bearer": "Bea" + "rer abc.def.ghi",
        "b18_timestamp": "[" + "12:34:56" + "] transcript line",
        "b19_human": "Hum" + "an: hello there",
        "b20_repl": ">>" + "> repl prompt",
        # MF3: a secret on a line that ALSO contains an allowed path token must STILL block.
        "b21_secret_plus_allowed": _join("pass", "word", ": hunter2  ", WIN, BS, USERS, BS, "<you>"),
        "b22_aws_plus_token": _join("AKIA", "A" * 16, " near ", WIN, BS, USERS, BS, "you"),
    }


def pass_rows() -> dict[str, str]:
    return {
        "p01_angle_name": _join(WIN, BS, USERS, BS, "<name>"),
        "p02_angle_you": _join(WIN, BS, USERS, BS, "<you>"),
        "p03_ellipsis": _join(WIN, BS, USERS, BS, "..."),
        "p04_token_you": _join(WIN, BS, USERS, BS, "you"),
        "p05_token_user": _join(WIN, BS, USERS, BS, "user"),
        "p06_token_username": _join(WIN, BS, USERS, BS, "username"),
        "p07_token_name": _join(WIN, BS, USERS, BS, "name"),
        "p08_token_test": _join(WIN, BS, USERS, BS, "test"),
        "p09_token_example": _join(WIN, BS, USERS, BS, "example"),
        "p10_token_me": _join(WIN, BS, USERS, BS, "me"),
        "p11_token_x": _join(WIN, BS, USERS, BS, "x"),
        "p12_userprofile": "%USER" + "PROFILE%",
        "p13_username_var": _join(WIN, BS, USERS, BS, "%USER" + "NAME%"),
        "p14_home_var": "$" + "HOME",
        "p15_brace_var": "$" + "{CLAUDE_PROJECT_DIR}",
        "p16_user_brace_var": _join(WIN, FS, USERS, FS, "$" + "{USER}"),
        "p17_windows_dir": _join(WIN, BS, "Windows", BS, "System32", BS, "drivers"),
        "p18_program_files": _join(WIN, BS, "Program Files", BS, "App"),
        "p19_prose": "This prose mentions Users and home directories generically.",
    }


@unittest.skipIf(_bash() is None or _git() is None, "needs bash + git on PATH")
class TestPublicationSafetyScanner(unittest.TestCase):
    def _run_cached(self, scanner: Path, content: str, env_overrides: dict | None = None) -> int:
        """Stage `content` as a file in a throwaway repo and run the REAL scanner
        in its production --cached tracked mode (cwd = the throwaway repo). The
        scanner resolves its allowlist owner via its own absolute BASH_SOURCE, so
        it uses the real reference hook regardless of cwd. Returns the exit code."""
        git = _git()
        bash = _bash()
        with tempfile.TemporaryDirectory() as td:
            subprocess.run([git, "init", "-q", td], check=True, capture_output=True)
            subprocess.run([git, "-C", td, "config", "user.email", "t@t"], check=True, capture_output=True)
            subprocess.run([git, "-C", td, "config", "user.name", "t"], check=True, capture_output=True)
            (Path(td) / "fixture.txt").write_text(content + "\n", encoding="utf-8")
            subprocess.run([git, "-C", td, "add", "fixture.txt"], check=True, capture_output=True)
            env = dict(os.environ)
            if env_overrides:
                env.update(env_overrides)
            proc = subprocess.run(
                [bash, str(scanner)],
                cwd=td,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=env,
            )
            return proc.returncode

    def test_block_rows_exit_1(self) -> None:
        for scanner in SCANNERS:
            for name, content in block_rows().items():
                with self.subTest(scanner=scanner.parent.parent.name, row=name):
                    self.assertEqual(self._run_cached(scanner, content), 1,
                                     f"{name!r} must BLOCK (exit 1)")

    def test_pass_rows_exit_0(self) -> None:
        for scanner in SCANNERS:
            for name, content in pass_rows().items():
                with self.subTest(scanner=scanner.parent.parent.name, row=name):
                    self.assertEqual(self._run_cached(scanner, content), 0,
                                     f"{name!r} must PASS (exit 0)")

    def test_clean_repo_exits_0(self) -> None:
        for scanner in SCANNERS:
            with self.subTest(scanner=scanner.parent.parent.name):
                self.assertEqual(self._run_cached(scanner, "nothing machine-local here"), 0)


@unittest.skipIf(_bash() is None or _git() is None, "needs bash + git on PATH")
class TestPublicationSafetyScannerFallback(unittest.TestCase):
    """Exercise the no-Python / allowlist-owner-unreachable refined-ERE branch.

    The branch fires when BOTH python3/python are unreachable OR the allowlist
    owner module is missing. We trigger it deterministically by pointing PATH at
    an empty shim dir (no python) AND keeping git reachable, which is awkward on
    MSYS; instead we drive the SAME code branch by hiding the reference module
    for the duration via a copied scanner whose sibling hooks dir has no owner.
    Simpler and equivalent: set the marker env the scanner does not read, so we
    use the documented branch trigger — an unreadable owner path — by running a
    scanner copy from a temp dir whose ../hooks/ lacks the owner."""

    def _run_fallback(self, content: str) -> tuple[int, str]:
        git = _git()
        bash = _bash()
        with tempfile.TemporaryDirectory() as td:
            tdp = Path(td)
            # Lay out a scanner copy with an EMPTY sibling hooks dir (no owner) ->
            # the `-f "$ref_module"` guard is false -> fallback branch runs. This
            # is the exact same branch as "no python reachable".
            (tdp / "scripts").mkdir()
            (tdp / "hooks").mkdir()
            shutil.copy2(CODEX_SCANNER, tdp / "scripts" / "check-publication-safety.sh")
            repo = tdp / "repo"
            repo.mkdir()
            subprocess.run([git, "init", "-q", str(repo)], check=True, capture_output=True)
            subprocess.run([git, "-C", str(repo), "config", "user.email", "t@t"], check=True, capture_output=True)
            subprocess.run([git, "-C", str(repo), "config", "user.name", "t"], check=True, capture_output=True)
            (repo / "fixture.txt").write_text(content + "\n", encoding="utf-8")
            subprocess.run([git, "-C", str(repo), "add", "fixture.txt"], check=True, capture_output=True)
            proc = subprocess.run(
                [bash, str(tdp / "scripts" / "check-publication-safety.sh")],
                cwd=str(repo),
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            return proc.returncode, proc.stderr

    def test_fallback_blocks_real_path(self) -> None:
        rc, err = self._run_fallback(_join(WIN, BS, USERS, BS, REAL))
        self.assertEqual(rc, 1, f"fallback must BLOCK a real path; stderr={err!r}")
        self.assertIn("refined regex fallback", err)

    def test_fallback_blocks_dev_root(self) -> None:
        rc, err = self._run_fallback(_join(WIN_D, BS, DEV, BS, "Orchestrator", BS, "Orchestrarium"))
        self.assertEqual(rc, 1, f"fallback must BLOCK a dev root; stderr={err!r}")

    def test_fallback_blocks_secret(self) -> None:
        rc, err = self._run_fallback("pass" + "word" + ": hunter2")
        self.assertEqual(rc, 1, f"fallback must still BLOCK a secret (MF3); stderr={err!r}")

    def test_fallback_passes_placeholder(self) -> None:
        rc, err = self._run_fallback(_join(WIN, BS, USERS, BS, "<name>"))
        self.assertEqual(rc, 0, f"fallback must PASS an angle-bracket placeholder; stderr={err!r}")

    def test_fallback_passes_env_var(self) -> None:
        rc, err = self._run_fallback("%USER" + "PROFILE%")
        self.assertEqual(rc, 0, f"fallback must PASS an env-var placeholder; stderr={err!r}")


class TestThisTestFileIsGateSafe(unittest.TestCase):
    """MF6: assert this very test file contains no machine-local-path literal the
    scanner would flag, so staging it never self-trips the publication gate."""

    def test_no_flaggable_literal_in_this_source(self) -> None:
        find_machine_paths = _load_find_machine_paths()
        src = Path(__file__).read_text(encoding="utf-8")
        offenders = []
        for n, line in enumerate(src.splitlines(), start=1):
            hits = find_machine_paths(line)
            if hits:
                offenders.append((n, hits, line.strip()[:80]))
        self.assertEqual(offenders, [], f"flaggable literals in test source: {offenders}")


if __name__ == "__main__":
    unittest.main()
