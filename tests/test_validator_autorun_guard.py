r"""Regression coverage for the Windows PowerShell 5.1 AutoRun-hazard fix in
the pack validators.

Bug: work-items/bugs/2026-07-26-validate-skill-pack-ps1-carries-the-same-masked-autorun-hazard.md

Mechanism (empirically reproduced below, WITHOUT touching the real Windows
registry): under Windows PowerShell 5.1, invoking ANY `.cmd`/`.bat` native
command that writes to its own stderr -- even when that stderr is redirected
with `2>$null` -- has that stray stderr text promoted into a TERMINATING
exception whenever `$ErrorActionPreference = 'Stop'` is in effect. A real
`cmd.exe` `AutoRun` registry hook (e.g. one conda installs) is one way a git
invocation acquires incidental stderr noise; a fake `git.cmd` that writes to
stderr on its own reproduces the identical PowerShell-engine-level promotion,
which is the actual mechanism at fault -- confirmed interactively against both
pwsh 7 (unaffected) and Windows PowerShell 5.1 (affected) before this test was
written. The validators' try/catch already prevented a hard crash, but it
swallowed the promoted exception and silently fell back to the WRONG root
(`$PSScriptRoot\..\..\..`), reporting success while validating the wrong tree.

Two test classes:
  * TestAutoRunHazardFixEndToEnd -- runs the REAL validator .ps1 (all four
    copies: claude, codex, gemini, qwen) against a fixture where the fallback
    root and the correct (git-derived) root are deliberately DIFFERENT
    directories, with a fake git.cmd that emits incidental stderr noise. Also
    runs the pre-fix committed blob (via `git show <PRE_FIX_COMMIT_SHA>:<path>`,
    a FIXED historical commit -- never `HEAD`, which is a moving ref that
    becomes the FIXED blob the instant this bug's own fix is committed)
    through the SAME fixture as a before/after control: the pre-fix code must
    reproduce the wrong-root fallback; the current code must not.
  * TestAutoRunIdiomSweep -- a static sweep for the same vulnerable idiom
    class (native call + `2>$null` + file-scoped EAP='Stop' + no local
    relaxation) across all `.ps1` files in the four provider trees, with a
    falsifying control on BOTH sides: a real in-repo file that LOOKS similar
    but must be rejected (await-codex-dispatch.ps1, EAP='SilentlyContinue'),
    and a synthetic planted vulnerable file that must be DETECTED (proving
    the sweep can find something, not just vacuously return empty).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# The before/after controls below need a FIXED historical blob that is
# PROVABLY vulnerable -- never `HEAD`. `HEAD` is a moving reference: while the
# AutoRun fix sat uncommitted, `HEAD` WAS the pre-fix (vulnerable) blob and a
# `HEAD`-pinned control passed; the moment the fix was committed, `HEAD`
# became the FIXED blob and the same control started asserting "the fixed
# code is still vulnerable" -- failing permanently, in CI, on every branch.
# Pinned to the last commit before the AutoRun fix landed (verified via this
# module's own `find_vulnerable_native_calls` detector: this commit's blob
# hits, the current blob does not). If history is later rewritten (e.g. this
# batch is split by family before publication) and this sha becomes
# unreachable, the two consumers below MUST degrade to `skipTest`, never to a
# failure -- a rewrite must not trade one time-bomb for another.
PRE_FIX_COMMIT_SHA = "39000253343ff0db23633497689468834e1c7ca0"

# (validator .ps1, sibling shell-script name, relative fallback depth) for all
# four provider trees. The fallback depth differs per tree (claude/codex are
# nested one level deeper than gemini/qwen) but is irrelevant to this test: we
# only care whether the validator lands on the git-derived root or ANY
# fallback, since the fixture makes them different directories either way.
VALIDATORS = (
    ("claude", ROOT / "src.claude" / "agents" / "scripts" / "validate-skill-pack.ps1", "validate-skill-pack.sh"),
    ("codex", ROOT / "src.codex" / "skills" / "lead" / "scripts" / "validate-skill-pack.ps1", "validate-skill-pack.sh"),
    ("gemini", ROOT / "src.gemini" / "scripts" / "validate-pack.ps1", "validate-pack.sh"),
    ("qwen", ROOT / "src.qwen" / "scripts" / "validate-pack.ps1", "validate-pack.sh"),
)


def _powershell_hosts() -> list[str]:
    return [p for p in (shutil.which("pwsh"), shutil.which("powershell")) if p]


def _write_fake_cmd(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("@echo off\r\n" + body, encoding="utf-8", newline="")


def _build_fixture(root: Path, validator_source: Path, sibling_name: str) -> tuple[Path, Path, Path]:
    """Returns (copied_validator_path, real_repo_root, marker_path).

    Layout:
      root/real-repo/                    -- the CORRECT root (fake git echoes this)
      root/pack/scripts/<validator>.ps1  -- copy under test
      root/pack/scripts/<sibling>        -- stub sibling (existence-only; the
                                             fake shell below ignores its content)
      root/fake-git/mingw64/bin/git.cmd  -- writes incidental stderr noise,
                                             echoes real-repo root, exit 0
      root/path-shells/{bash,sh}.cmd     -- fake shells: record %CD% to marker
    """
    real_repo = root / "real-repo"
    real_repo.mkdir(parents=True)

    scripts_dir = root / "pack" / "scripts"
    scripts_dir.mkdir(parents=True)
    copied_validator = scripts_dir / validator_source.name
    shutil.copy2(validator_source, copied_validator)
    (scripts_dir / sibling_name).write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8", newline="\n")

    git_dir = root / "fake-git" / "mingw64" / "bin"
    _write_fake_cmd(
        git_dir / "git.cmd",
        f"echo incidental-noise-from-something-else 1>&2\r\necho {real_repo}\r\nexit /b 0\r\n",
    )

    marker = root / "cwd.marker"
    path_shells = root / "path-shells"
    for name in ("bash.cmd", "sh.cmd"):
        _write_fake_cmd(path_shells / name, f'echo %CD%>>"{marker}"\r\nexit /b 0\r\n')

    return copied_validator, real_repo, marker


def _run_validator(interp: str, validator: Path, env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [interp, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(validator)],
        env=env, capture_output=True, text=True, timeout=30,
    )


@unittest.skipIf(not _powershell_hosts(), "no PowerShell host (pwsh/powershell) on PATH")
class TestAutoRunHazardFixEndToEnd(unittest.TestCase):

    def test_fixed_validator_resolves_the_correct_git_derived_root_under_incidental_stderr(self) -> None:
        for label, validator_source, sibling_name in VALIDATORS:
            for interp in _powershell_hosts():
                with self.subTest(validator=label, interp=Path(interp).stem):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        copied, real_repo, marker = _build_fixture(root, validator_source, sibling_name)
                        env = dict(os.environ)
                        env["PATH"] = os.pathsep.join((
                            str(root / "fake-git" / "mingw64" / "bin"),
                            str(root / "path-shells"),
                        ))
                        p = _run_validator(interp, copied, env)
                        self.assertEqual(p.returncode, 0, f"stdout={p.stdout!r} stderr={p.stderr!r}")
                        self.assertTrue(marker.exists(), "fake shell was never invoked")
                        recorded_cwd = marker.read_text(encoding="utf-8").strip()
                        self.assertEqual(
                            Path(recorded_cwd).resolve(), real_repo.resolve(),
                            f"validator must Set-Location to the git-derived root "
                            f"({real_repo}) despite incidental stderr noise from the "
                            f"fake git.cmd; instead it ran from {recorded_cwd!r} "
                            f"(the fallback-root symptom this bug describes)",
                        )

    def test_precommit_validator_reproduces_the_wrong_root_fallback_under_ps51(self) -> None:
        """Before/after control: the PRE-FIX committed blob -- pinned to a
        FIXED historical commit (`PRE_FIX_COMMIT_SHA`), via `git show`, never
        `HEAD` (a moving ref that becomes the FIXED blob the instant this
        bug's own fix is committed, silently inverting this control from
        "proves the defect" to "asserts the defect still exists") -- run
        through the IDENTICAL fixture, must exhibit the bug -- landing on the
        fallback root, not the git-derived one -- proving this fixture
        actually discriminates the defect rather than always passing.

        Scoped to claude+codex only: gemini/qwen's HEAD blob predates an
        UNRELATED concurrent hardening (WSL-launcher rejection + a PATH
        fallback search when no bash/sh sits directly under the derived git
        root) that claude/codex's HEAD copy already had. Without that later
        hardening, gemini/qwen's historical shell-resolution logic only
        checks the derived-root candidates directly and throws
        "Unable to locate bundled bash.exe" before ever reaching the
        git-rev-parse/AutoRun code path this test targets -- confirmed via
        `git show HEAD:src.gemini/scripts/validate-pack.ps1`, which has no
        PATH-fallback branch at all. Comparing against that HEAD would
        conflate two unrelated defects, so the fair before/after contrast is
        only available for claude/codex here; the CURRENT-content end-to-end
        test above already covers all four providers."""
        powershell = shutil.which("powershell")
        if not powershell:
            self.skipTest("Windows PowerShell 5.1 not on PATH")
        for label, validator_source, sibling_name in VALIDATORS:
            if label in ("gemini", "qwen"):
                continue
            rel = validator_source.relative_to(ROOT).as_posix()
            pre_fix = subprocess.run(
                ["git", "show", f"{PRE_FIX_COMMIT_SHA}:{rel}"], cwd=str(ROOT), capture_output=True, text=True,
            )
            if pre_fix.returncode != 0:
                self.skipTest(
                    f"pre-fix blob unavailable for {rel} at pinned commit "
                    f"{PRE_FIX_COMMIT_SHA} -- history was rewritten and the "
                    "commit is no longer reachable (or this is a shallow "
                    "clone); this before/after control needs a FIXED "
                    "historical blob, not a moving ref, so an unreachable "
                    "pin must degrade to skip, never to failure"
                )
            with self.subTest(validator=label):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    copied, real_repo, marker = _build_fixture(root, validator_source, sibling_name)
                    # Overwrite the just-copied (FIXED) validator with the
                    # PRE-FIX committed content for this one probe.
                    copied.write_text(pre_fix.stdout, encoding="utf-8")
                    env = dict(os.environ)
                    env["PATH"] = os.pathsep.join((
                        str(root / "fake-git" / "mingw64" / "bin"),
                        str(root / "path-shells"),
                    ))
                    p = _run_validator(powershell, copied, env)
                    self.assertEqual(p.returncode, 0, f"stdout={p.stdout!r} stderr={p.stderr!r}")
                    self.assertTrue(marker.exists(), "fake shell was never invoked")
                    recorded_cwd = Path(marker.read_text(encoding="utf-8").strip()).resolve()
                    self.assertNotEqual(
                        recorded_cwd, real_repo.resolve(),
                        "the PRE-FIX validator was expected to MISS the "
                        "git-derived root (that is the bug); if it now "
                        "matches, this fixture no longer reproduces the "
                        "pre-fix defect and the before/after contrast is void",
                    )


# ---------------------------------------------------------------------------
# Static sweep for the same idiom class across the four provider trees.
# ---------------------------------------------------------------------------

_EAP_STOP = re.compile(r"\$ErrorActionPreference\s*=\s*['\"]Stop['\"]")
_EAP_RELAX = re.compile(r"\$ErrorActionPreference\s*=\s*['\"](Continue|SilentlyContinue|Ignore)['\"]")


def find_vulnerable_native_calls(text: str, *, window: int = 15) -> list[int]:
    """Returns 1-indexed line numbers of native `... 2>$null` calls that sit
    under a file-scoped `$ErrorActionPreference = 'Stop'` with no local
    relax/restore guard within `window` lines before the call. A crude but
    adequate static heuristic -- validated below against known safe and
    known-vulnerable fixtures before being trusted for the real sweep."""
    lines = text.splitlines()
    if not _EAP_STOP.search(text):
        return []  # file never sets Stop -- not in this hazard's risk class
    hits = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue  # a comment line (e.g. the fix's own explanatory prose
            # quoting `2>$null` in backticks), not executable code
        if "2>$null" not in line:
            continue
        if "$ErrorActionPreference" in line:
            continue  # an inline assignment/comment mentioning the pattern, not a call
        window_start = max(0, idx - window)
        preceding = "\n".join(lines[window_start:idx])
        if _EAP_RELAX.search(preceding):
            continue  # guarded locally
        hits.append(idx + 1)
    return hits


class TestVulnerableIdiomDetectorSelfCheck(unittest.TestCase):
    """The sweep detector must be proven precise BEFORE trusting its output on
    the real tree: it must flag a synthetic vulnerable fixture (positive
    control) and reject two real in-repo shapes that look similar but are not
    vulnerable (negative controls) -- an empty sweep result is only evidence
    once these hold."""

    def test_detects_a_synthetic_planted_vulnerable_file(self) -> None:
        synthetic = (
            "$ErrorActionPreference = 'Stop'\n"
            "$out = & $git rev-parse --show-toplevel 2>$null\n"
        )
        hits = find_vulnerable_native_calls(synthetic)
        self.assertEqual(hits, [2], "detector failed to flag a genuinely vulnerable synthetic fixture")

    def test_rejects_await_codex_dispatch_ps1_wrong_eap_value(self) -> None:
        """Real falsifying control: await-codex-dispatch.ps1 uses the same
        `git ... 2>$null` idiom but under EAP='SilentlyContinue', not 'Stop' --
        it is structurally immune, and the sweep must say so, not flag it."""
        path = ROOT / "src.claude" / "agents" / "scripts" / "await-codex-dispatch.ps1"
        text = path.read_text(encoding="utf-8")
        self.assertIn("2>$null", text, "fixture assumption: this file must still carry the idiom")
        hits = find_vulnerable_native_calls(text)
        self.assertEqual(hits, [], f"await-codex-dispatch.ps1 must be rejected (EAP != Stop); got hits at {hits}")

    def test_rejects_the_fixed_check_publication_safety_reference(self) -> None:
        """Second falsifying control: the reference fix itself (guarded
        locally) must be rejected as NOT vulnerable."""
        path = ROOT / "src.claude" / "agents" / "scripts" / "check-publication-safety.ps1"
        text = path.read_text(encoding="utf-8")
        hits = find_vulnerable_native_calls(text)
        self.assertEqual(hits, [], f"the guarded reference implementation must not be flagged; got hits at {hits}")

    def test_detects_the_precommit_validator_as_vulnerable(self) -> None:
        """Third control, tying the detector to the real defect: the PRE-FIX
        validate-skill-pack.ps1 blob, pinned to a FIXED historical commit
        (`PRE_FIX_COMMIT_SHA`) -- never `HEAD`, which is a moving ref that
        becomes the FIXED blob the instant this bug's own fix is committed,
        silently flipping this control from "detects the historical defect"
        to "asserts the defect still exists" -- must be flagged."""
        pre_fix = subprocess.run(
            ["git", "show", f"{PRE_FIX_COMMIT_SHA}:src.claude/agents/scripts/validate-skill-pack.ps1"],
            cwd=str(ROOT), capture_output=True, text=True,
        )
        if pre_fix.returncode != 0:
            self.skipTest(
                f"pre-fix blob unavailable at pinned commit {PRE_FIX_COMMIT_SHA} "
                "-- history was rewritten and the commit is no longer "
                "reachable (or this is a shallow clone); this control needs "
                "a FIXED historical blob, not a moving ref, so an "
                "unreachable pin must degrade to skip, never to failure"
            )
        hits = find_vulnerable_native_calls(pre_fix.stdout)
        self.assertTrue(hits, "detector must flag the pre-fix committed validator as vulnerable")


class TestAutoRunIdiomSweepAcrossProviderTrees(unittest.TestCase):
    """The actual class-wide sweep this bug's own text demands ("treat it as
    a class, not two instances... a sweep needs a falsifying control"). Runs
    ONLY once TestVulnerableIdiomDetectorSelfCheck has proven the detector
    precise (pytest has no ordering guarantee across classes, so this class
    re-derives the same controls inline rather than depending on run order)."""

    def test_no_vulnerable_native_call_remains_in_any_ps1_under_the_four_provider_trees(self) -> None:
        provider_trees = (ROOT / "src.claude", ROOT / "src.codex", ROOT / "src.gemini", ROOT / "src.qwen")
        all_hits: dict[str, list[int]] = {}
        for tree in provider_trees:
            if not tree.is_dir():
                continue
            for ps1 in tree.rglob("*.ps1"):
                text = ps1.read_text(encoding="utf-8")
                hits = find_vulnerable_native_calls(text)
                if hits:
                    all_hits[str(ps1.relative_to(ROOT))] = hits
        self.assertEqual(
            all_hits, {},
            f"vulnerable AutoRun-class native call(s) remain unfixed: {all_hits}",
        )
