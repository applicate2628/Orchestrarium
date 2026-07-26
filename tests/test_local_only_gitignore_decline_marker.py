"""Regression coverage for
work-items/bugs/2026-07-25-tier-writer-silently-reverts-considered-decline.md.

Before this fix, `ensure_local_only_gitignore_entries` (bash) /
`Ensure-LocalOnlyGitignoreEntries` (PowerShell) -- duplicated identically
across all 8 installers (install-{claude,codex,gemini,qwen}.{sh,ps1}) --
matched tier presence by exact whole-line `.gitignore` content only. An
operator who deliberately removed a tier's line (e.g. to track work-items/ in
git on purpose) had no way to record that decision: the writer could not
distinguish "never configured" from "considered and declined", so the next
project-mode install silently re-appended the removed tier.

The fix adds a per-tier sentinel comment
(`# orchestrarium:local-only-tier-declined:<entry>`) that the writer checks
with the SAME grep -Fxq / -contains whole-line matcher used for tier
presence, so writer and any future detection code cannot disagree about the
same file (the registry entry's explicit "same matcher semantics" requirement).

This module drives the ACTUAL function bodies extracted verbatim from each of
the 8 real installer files (never a .py reimplementation of the matcher
logic), executed under bash / PowerShell respectively, so a change to one
installer that is not mirrored to its 7 siblings is caught here exactly like
the pre-existing tier-parity test (test_local_only_gitignore_tiers.py) catches
a missing tier -- this test catches a missing DECLINE behavior instead.

Falsification note: `test_all_eight_installers_are_covered` asserts the
extraction succeeds for exactly 8 files (4 sh + 4 ps1) so a 9th installer, or
one of the 8 losing the marker during a future edit, cannot silently drop out
of coverage.

REVISE round 2 (adversarial gate, real Windows PowerShell 5.1 + real Linux GNU
grep): the sentinel matcher was CASE-SENSITIVE on bash (`grep -Fxq`, no `-i`)
but CASE-INSENSITIVE on PowerShell (`-contains`), so a differently-cased
sentinel was honored forever on Windows and silently re-ignored on Linux --
"same matcher semantics" held within each engine but not ACROSS them. A second
axis: a CRLF- or UTF-8-BOM-carrying .gitignore (e.g. produced by a teammate's
PowerShell install) defeated `grep -Fxq` outright on Linux for BOTH the entry
check and the sentinel check. A third, separate defect: appending at end of
file overrides an earlier git-native `!entry` negation (git's own "last
matching pattern wins" rule), silently re-ignoring a path an operator already
un-ignored using git's own syntax -- the exact defect class the sentinel
exists to prevent, one layer down.

`FixtureTableEquivalenceTest` below is the fixture table this cost: each row
is one before-content shape (plain sentinel, case-mismatched sentinel, BOM,
CRLF, trailing whitespace, `!` negation in both spelling forms, a
substring/typo'd sentinel naming the WRONG entry) with one expected outcome,
run identically against every bash installer AND every (PowerShell host,
PowerShell installer) pair -- so bash and PowerShell are asserted to agree on
every row, not just internally consistent with themselves.

REVISE round 3 (same adversarial gate): round 2's fix was incomplete in two
ways, both judged against rather than accepted.

1. The NEGATION detector added for finding 7 in the SAME round shipped with
   the SAME case-sensitivity asymmetry the sentinel fix had just closed:
   `install-claude.ps1`'s negation check stayed on `-contains` (case-
   insensitive) while bash's stayed on `grep -Fxq` (case-sensitive) --
   confirmed empirically with `!/WORK-ITEMS/` on three engines: Git Bash did
   NOT detect it (appended `/work-items/`, silently re-ignoring the tree the
   operator had explicitly un-ignored), pwsh 7 and Windows PowerShell 5.1 DID
   (safe). New code, same bug class, right beside the fix for it.
2. The presence-check asymmetry, left in place and disclosed in round 2 as a
   scope call, was judged NOT defensible: for a tier system whose entire
   purpose is keeping local-only content out of publication,
   "believed-configured-on-Windows, actually-not-ignoring-on-Linux" is a
   correctness bug, not a cosmetic inconsistency one entry array shares with
   a decline sentinel.

The canonical answer -- CASE-SENSITIVE on both engines (`-ccontains` on
PowerShell, unchanged `grep -Fxq` on bash) -- now applies uniformly to all
THREE checks (presence, negation, sentinel), with the same BOM/CRLF/
trailing-whitespace normalization already built. `negation_case_mismatch_is_
not_honored` is the new fixture row this round adds, run on both engines
exactly like the sentinel's case-mismatch row -- its absence from round 2's
table (which had a case row for the sentinel but none for negation) is
exactly why the negation regression shipped undetected.

REVISE round 5 (adversarial gate, retracting a prior PASS): round 4's own
"canonical answer" -- git's own core.ignorecase authority for negation, but
via a FIXED four-form spelling enumeration -- was itself found insufficient a
THIRD time: real git honors glob forms (`!**/work-items/`), character
classes (`!/work-item[s]`), and single-char wildcards (`!/work-item?`) that
no fixed list of literal spellings can fully enumerate, confirmed via an
end-to-end destroy proof (`/wo*/` plus `!**/work-items/`, core.ignorecase=
true: tracked before the writer ran, silently re-ignored after). The
enumeration is retired entirely in favor of delegating to `git check-ignore`
itself for negation detection: an isolated throwaway repo (never the
operator's real .gitignore) is seeded with the target file's own content and
probed twice -- once as-is, once with `!`-lines stripped -- so "declined via
negation" is now an ASKED question, not a guessed spelling. This same round
also closed two PowerShell-specific defects in the retired `core.ignorecase`
read this replaces: it crashed the whole installer under Windows PowerShell
5.1 on a corrupt `.git/config` value (`$ErrorActionPreference = "Stop"`
promoting a native command's stderr to a terminating exception), and it read
`core.ignorecase` WITHOUT `--local`, so a non-repo project_root's decision
could leak the operator's unrelated GLOBAL git config. Both defects are moot
under the new mechanism (the vulnerable read no longer exists in the negation
path), but the fixed-spelling fixture rows below are reworked accordingly:
each negation row now carries a base ignore pattern the writer's OWN literal
presence check does NOT recognize (`/work-items`, no trailing slash -- same
convention `GitGroundTruthTest` already used), so the row exercises
negation delegation rather than short-circuiting at presence; a fixed
case-mismatch row is retired in favor of the existing (now doubled)
`GitGroundTruthTest`/`PowerShellGitGroundTruthTest` classes, which control
`core.ignorecase` explicitly rather than depending on the test machine's own
filesystem case-sensitivity -- the ONE assumption a fixed-table row cannot
make once the decision is delegated to real git.

REVISE round 6 (adversarial gate, retracting round 5's PASS): the round-5
redesign reintroduced the exact defect this whole bug family was opened for,
and shipped green because the fixture rows were CHANGED to accommodate the
new code instead of the code being fixed to satisfy the rows. Four findings,
in the order addressed:

1. A BARE, unpaired negation (e.g. "!/work-items/" alone, no companion
   positive pattern anywhere in the file) is un-ignored both WITH and
   WITHOUT negations present, so round 5's whole-file before/after
   differential probe could not tell "declined via negation" apart from
   "genuinely missing" -- it called a bare negation genuinely missing and
   appended, which added the very positive pattern the operator had just
   negated, flipping git's real verdict from NOT-ignored to IGNORED:
   the opposite of what was written, on bash, pwsh 7, and Windows
   PowerShell 5.1 (reproduced directly this session). Fixed by testing
   EACH "!"-prefixed line's own stripped pattern in ISOLATION -- "would
   THIS pattern alone cover the tier" -- rather than a whole-file
   differential; this catches a bare negation regardless of whether a
   companion positive pattern exists, still via git's own matcher (not a
   spelling list), and was the root reason round 5's four ORIGINAL bare
   fixture rows had been rewritten with an added base pattern rather than
   kept as-is -- restored here to their pre-round-5-rework bytes as the
   regression lock, with the base-pattern-paired variants kept ALONGSIDE
   rather than in place of them.
2. The throwaway repo used for negation delegation inherited the
   OPERATOR's ambient git environment (global `core.excludesFile`,
   `init.templateDir`-seeded `info/exclude`) with no neutralization --
   confirmed this session that an operator's own global
   `core.excludesFile` covering a tier made the writer silently decide
   "already ignored" for a PROJECT whose own .gitignore said nothing
   about it, so a teammate cloning without that global config would track
   the tier: local-only content entering version control, the exact
   publication-safety failure this tier system exists to prevent. Fixed
   with `GIT_CONFIG_NOSYSTEM` + a nonexistent `GIT_CONFIG_GLOBAL` +
   `git init --template=<nonexistent>` around every native call targeting
   the throwaway repo.
3. The throwaway repo had no cleanup guarantee beyond the success path --
   an interrupt, abort, or hung git left `orchestrarium-giprobe-*`
   directories in temp. Fixed with a bash EXIT-trap that CHAINS onto
   whatever trap the calling installer script already has registered
   (confirmed necessary: `install-codex.sh` sets its own EXIT trap before
   this function runs, and a naive `trap ... EXIT` here would silently
   replace it, dropping that sibling cleanup) rather than a bare
   `trap ... EXIT`; verified against a REAL SIGTERM sent mid-probe. The
   PowerShell side uses `try/finally`, verified to still run on both an
   injected mid-loop exception and a genuine
   `PipelineStoppedException` (Ctrl-C's exception type) passing through an
   untyped `catch { }` untouched rather than being swallowed by it.
4. The fixture-table classes gained a real dependency on `git` being on
   PATH (delegation) where the retired string-matching mechanism did not,
   and the table's own `git`-presence skip gate means a git-less machine
   now silently skips that coverage instead of exercising it -- unchanged
   this round (latent, not exercised on this machine; disclosed rather
   than engineered around further).

REVISE round 7 (adversarial gate, retracting round 6's PASS on one item):
round 6 closed the three NAMED environment-leakage vectors (global
`core.excludesFile`, `init.templateDir`, both via GIT_CONFIG_GLOBAL/
GIT_CONFIG_NOSYSTEM) but only those instances, not the class. Round 7 named
`GIT_DIR`, `GIT_WORK_TREE`, and `GIT_CONFIG_COUNT` by name -- each still
redirected the probe onto a completely different repository or injected
arbitrary config straight from the environment, entirely bypassing the
round-6 fix: confirmed this session that `-C <dir>` does NOT override an
ambient `GIT_WORK_TREE` (alone, or paired with `GIT_DIR`), and that
`GIT_CONFIG_COUNT` + `GIT_CONFIG_KEY_n`/`GIT_CONFIG_VALUE_n` inject config
directly from the environment independent of `GIT_CONFIG_NOSYSTEM`/
`GIT_CONFIG_GLOBAL` (a THIRD vector, not even named by the reviewer, found
by reading git's own documented environment-variable list rather than
extending piecemeal from the two already-named ones -- the reviewer's exact
point that naming instances one at a time guarantees the next unnamed one).
A realistic trigger: the installer running from inside a git hook,
mid-rebase, or from a CI/IDE wrapper that exports these. Fixed by clearing
the WHOLE git-documented repository-location and configuration-location
environment-variable class in one place (`GIT_DIR`, `GIT_WORK_TREE`,
`GIT_COMMON_DIR`, `GIT_NAMESPACE`, `GIT_CEILING_DIRECTORIES`,
`GIT_DISCOVERY_ACROSS_FILESYSTEM`, `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY`,
`GIT_ALTERNATE_OBJECT_DIRECTORIES`, `GIT_CONFIG_SYSTEM`, `GIT_CONFIG_COUNT`)
for the entire unresolved-tier block on both engines -- verified
independently on PowerShell rather than assumed from the bash-side finding,
per the reviewer's explicit warning that this family has been bitten by
exactly that asymmetry twice already. Also closed: the round-2 bare-form
coverage gap was two-thirds unrepaired (globstar had a bare row; character
class and single-char wildcard did not) -- the two missing rows are added.

REVISE round 8 (adversarial gate, retracting round 7's PASS): round 7 fixed
the class of ENVIRONMENT VARIABLES, but the remaining vector was not an
environment variable at all. `core.excludesFile` has no default VALUE, but
git falls back to a default PATH ($XDG_CONFIG_HOME/git/ignore, else
$HOME/.config/git/ignore) whenever core.excludesFile is UNSET -- exactly the
state `GIT_CONFIG_GLOBAL=<nonexistent>` (round 6's fix) leaves it in, so
round 6 never closed this. Confirmed this session on bash, pwsh 7, and
Windows PowerShell 5.1: an ambient HOME or XDG_CONFIG_HOME pointing at a
real `~/.config/git/ignore` covering the tier still leaked in SILENTLY.
`~/.config/git/ignore` is the standard personal global-gitignore location,
making this plausibly the most likely trigger of any vector in this family.
Fixed by setting core.excludesFile EXPLICITLY on the throwaway repo (a
nonexistent path is enough) rather than relying on it staying unset -- an
explicit value ends the fallback permanently, so no future default-path
fallback can reopen it under a different name. Second, smaller: the four
documented pathspec-magic variables (`GIT_ICASE_PATHSPECS`,
`GIT_LITERAL_PATHSPECS`, `GIT_NOGLOB_PATHSPECS`, `GIT_GLOB_PATHSPECS`) make
`check-ignore` itself fail (exit 128) since it takes pathspecs -- not a
silent leak, but the tier was left unwritten with only a disclosure
message; added to the cleared set. Third: a factual correction to the round-
7 product-code comment (and to the reviewer's own round-7 relay, which
repeated the same inversion) -- measured with `git rev-parse --show-toplevel
--git-dir` as well as `check-ignore`: GIT_WORK_TREE ALONE redirects BOTH the
working tree and git-dir discovery (leaking a WORKING-TREE-relative ignore
source, e.g. a plain `.gitignore`); GIT_DIR ALONE redirects ONLY git-dir
discovery, leaving the working tree in place (leaking a GIT-DIR-relative
source, e.g. `$GIT_DIR/info/exclude`, while a `.gitignore` does not leak) --
both are real, independent leaks through different ignore-source channels;
clearing both (as the round-7 fix already does) closes both regardless of
which channel a given operator's ambient state uses. The actual FIX was
unaffected by the inversion (it already clears both variables); only the
maintainer-facing explanation of the mechanism was wrong. The invariant this
whole family of fixes serves, now stated explicitly in the product code:
the probe consults nothing outside the throwaway repository and the file
under test. The reviewer's own environment-variable enumeration is
empirical, not a claim of completeness (the documented list was read via
enumeration, not a rendered man page, on the reviewing machine) -- treat
that as an open edge the invariant is meant to cover, not a gap to chase
with a longer list.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SH_INSTALLERS = (
    REPO_ROOT / "scripts" / "install-claude.sh",
    REPO_ROOT / "scripts" / "install-codex.sh",
    REPO_ROOT / "scripts" / "install-gemini.sh",
    REPO_ROOT / "scripts" / "install-qwen.sh",
)
PS1_INSTALLERS = (
    REPO_ROOT / "scripts" / "install-claude.ps1",
    REPO_ROOT / "scripts" / "install-codex.ps1",
    REPO_ROOT / "scripts" / "install-gemini.ps1",
    REPO_ROOT / "scripts" / "install-qwen.ps1",
)

BASH = shutil.which("bash")


def _powershell_interpreters() -> list[str]:
    found: list[str] = []
    for name in ("pwsh", "powershell"):
        exe = shutil.which(name)
        if exe:
            found.append(exe)
    return found


PS_INTERPRETERS = _powershell_interpreters()

_BASH_FUNC_RE = re.compile(
    r"^ensure_local_only_gitignore_entries\(\) \{\n(?:.*\n)*?^\}\n", re.M
)
_PS1_FUNC_RE = re.compile(
    r"^function Ensure-LocalOnlyGitignoreEntries \{\n(?:.*\n)*?^\}\n", re.M
)


def _extract_bash_function(installer: Path) -> str:
    text = installer.read_text(encoding="utf-8", newline="")
    m = _BASH_FUNC_RE.search(text)
    assert m, f"could not find ensure_local_only_gitignore_entries in {installer}"
    return m.group(0)


def _extract_ps1_function(installer: Path) -> str:
    text = installer.read_text(encoding="utf-8", newline="")
    m = _PS1_FUNC_RE.search(text)
    assert m, f"could not find Ensure-LocalOnlyGitignoreEntries in {installer}"
    return m.group(0)


def _run_bash_writer(
    installer: Path, project_root: Path, *, dry_run: bool = False, env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    func = _extract_bash_function(installer)
    script = "\n".join((
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f"DRY_RUN={1 if dry_run else 0}",
        func,
        'ensure_local_only_gitignore_entries "$1"',
    ))
    with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False, encoding="utf-8", newline="\n") as f:
        f.write(script)
        wrapper = Path(f.name)
    try:
        return subprocess.run(
            [BASH, str(wrapper), str(project_root)],
            capture_output=True, text=True, env=env,
        )
    finally:
        wrapper.unlink(missing_ok=True)


def _run_ps1_writer(
    interp: str, installer: Path, project_root: Path, *, dry_run: bool = False, env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    func = _extract_ps1_function(installer)
    script = "\n".join((
        "param([string]$ProjectRoot)",
        f"$DryRun = ${'true' if dry_run else 'false'}",
        func,
        "Ensure-LocalOnlyGitignoreEntries -ProjectRoot $ProjectRoot",
    ))
    with tempfile.NamedTemporaryFile("w", suffix=".ps1", delete=False, encoding="utf-8", newline="\r\n") as f:
        f.write(script)
        wrapper = Path(f.name)
    try:
        return subprocess.run(
            [interp, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(wrapper), str(project_root)],
            capture_output=True, text=True, env=env,
        )
    finally:
        wrapper.unlink(missing_ok=True)


class ExtractionCoversAllEightInstallersTest(unittest.TestCase):
    def test_all_eight_installers_are_covered(self) -> None:
        for installer in SH_INSTALLERS:
            with self.subTest(installer=installer.name):
                self.assertTrue(installer.is_file())
                _extract_bash_function(installer)  # raises if not found
        for installer in PS1_INSTALLERS:
            with self.subTest(installer=installer.name):
                self.assertTrue(installer.is_file())
                _extract_ps1_function(installer)  # raises if not found
        self.assertEqual(len(SH_INSTALLERS), 4)
        self.assertEqual(len(PS1_INSTALLERS), 4)


@unittest.skipIf(BASH is None, "no bash on PATH")
class BashTierWriterDeclineMarkerTest(unittest.TestCase):
    def test_declined_tier_is_not_reappended(self) -> None:
        """Core regression: three tiers present, the fourth (/work-items/)
        deliberately declined via the sentinel -- the writer must leave the
        .gitignore untouched for that tier and report the decline, never
        silently re-append it."""
        for installer in SH_INSTALLERS:
            with self.subTest(installer=installer.name):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    gitignore = root / ".gitignore"
                    gitignore.write_text(
                        "/.reports/\n/.plans/\n/.scratch/\n"
                        "# orchestrarium:local-only-tier-declined:/work-items/\n",
                        encoding="utf-8", newline="",
                    )
                    p = _run_bash_writer(installer, root)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    after = gitignore.read_text(encoding="utf-8", newline="")
                    self.assertNotIn(
                        "/work-items/\n", after.replace(
                            "# orchestrarium:local-only-tier-declined:/work-items/\n", ""
                        ),
                        f"declined tier was re-appended by {installer.name}:\n{after}",
                    )
                    self.assertIn("declined by operator", p.stdout)

    def test_missing_tier_without_decline_marker_is_still_appended(self) -> None:
        """Baseline behavior preserved: a genuinely missing tier (no sentinel)
        still gets appended -- the decline marker must not become a blanket
        opt-out."""
        for installer in SH_INSTALLERS:
            with self.subTest(installer=installer.name):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    gitignore = root / ".gitignore"
                    gitignore.write_text("/.reports/\n/.plans/\n/.scratch/\n", encoding="utf-8", newline="")
                    p = _run_bash_writer(installer, root)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    after = gitignore.read_text(encoding="utf-8", newline="")
                    self.assertIn("/work-items/", after)
                    self.assertIn("added '/work-items/'", p.stdout)

    def test_fresh_gitignore_gets_all_four_tiers(self) -> None:
        for installer in SH_INSTALLERS:
            with self.subTest(installer=installer.name):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    p = _run_bash_writer(installer, root)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    after = (root / ".gitignore").read_text(encoding="utf-8", newline="")
                    for entry in ("/.reports/", "/.plans/", "/work-items/", "/.scratch/"):
                        self.assertIn(entry, after)

    def test_second_run_is_idempotent_and_silent_about_declined_tier(self) -> None:
        for installer in SH_INSTALLERS:
            with self.subTest(installer=installer.name):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    gitignore = root / ".gitignore"
                    gitignore.write_text(
                        "/.reports/\n/.plans/\n/.scratch/\n"
                        "# orchestrarium:local-only-tier-declined:/work-items/\n",
                        encoding="utf-8", newline="",
                    )
                    _run_bash_writer(installer, root)
                    before = gitignore.read_text(encoding="utf-8", newline="")
                    p2 = _run_bash_writer(installer, root)
                    after = gitignore.read_text(encoding="utf-8", newline="")
                    self.assertEqual(before, after, "a second run must not mutate the file further")
                    self.assertEqual(p2.returncode, 0, p2.stderr)


@unittest.skipIf(not PS_INTERPRETERS, "no PowerShell host (pwsh/powershell) on PATH")
class PowerShellTierWriterDeclineMarkerTest(unittest.TestCase):
    def test_declined_tier_is_not_reappended(self) -> None:
        for interp in PS_INTERPRETERS:
            for installer in PS1_INSTALLERS:
                with self.subTest(interp=Path(interp).stem, installer=installer.name):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        gitignore = root / ".gitignore"
                        gitignore.write_text(
                            "/.reports/\r\n/.plans/\r\n/.scratch/\r\n"
                            "# orchestrarium:local-only-tier-declined:/work-items/\r\n",
                            encoding="utf-8", newline="",
                        )
                        p = _run_ps1_writer(interp, installer, root)
                        self.assertEqual(p.returncode, 0, p.stderr)
                        after = gitignore.read_text(encoding="utf-8", newline="")
                        self.assertNotIn(
                            "/work-items/\r\n", after.replace(
                                "# orchestrarium:local-only-tier-declined:/work-items/\r\n", ""
                            ),
                            f"declined tier was re-appended by {installer.name} under {interp}:\n{after}",
                        )
                        self.assertIn("declined by operator", p.stdout)

    def test_missing_tier_without_decline_marker_is_still_appended(self) -> None:
        for interp in PS_INTERPRETERS:
            for installer in PS1_INSTALLERS:
                with self.subTest(interp=Path(interp).stem, installer=installer.name):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        gitignore = root / ".gitignore"
                        gitignore.write_text("/.reports/\r\n/.plans/\r\n/.scratch/\r\n", encoding="utf-8", newline="")
                        p = _run_ps1_writer(interp, installer, root)
                        self.assertEqual(p.returncode, 0, p.stderr)
                        after = gitignore.read_text(encoding="utf-8", newline="")
                        self.assertIn("/work-items/", after)
                        self.assertIn("added '/work-items/'", p.stdout)

    def test_fresh_gitignore_gets_all_four_tiers(self) -> None:
        for interp in PS_INTERPRETERS:
            for installer in PS1_INSTALLERS:
                with self.subTest(interp=Path(interp).stem, installer=installer.name):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        p = _run_ps1_writer(interp, installer, root)
                        self.assertEqual(p.returncode, 0, p.stderr)
                        after = (root / ".gitignore").read_text(encoding="utf-8", newline="")
                        for entry in ("/.reports/", "/.plans/", "/work-items/", "/.scratch/"):
                            self.assertIn(entry, after)


# ---------------------------------------------------------------------------
# Fixture-table cross-engine equivalence (REVISE round 2, Findings 6/7/10).
#
# Each row is a raw BYTE sequence for .gitignore's starting content (never a
# Python string, so BOM / CRLF are exact, not a text-mode reinterpretation),
# the expected outcome for the /work-items/ tier specifically, and the stdout
# substring that outcome must produce. `ADDED` = "added '/work-items/'" (the
# literal message the writer prints on a real append) doubles as both the
# appended-marker AND, where it is itself the expected message, the row's
# `message` value -- so asserting `message in stdout` and asserting the
# append boolean are never two independently-typo-able strings.
# ---------------------------------------------------------------------------

_ADDED_MARKER = "added '/work-items/'"
_SENTINEL_MESSAGE = "declined by operator"
# REVISE round 4 (F-D): the writer no longer asserts "already un-ignored" as
# settled fact -- it only checks for A negation line's presence, not full
# gitignore precedence, so a later broader ignore pattern could still
# re-ignore the tree. The message was softened to disclose that uncertainty.
_NEGATION_MESSAGE = "has a '!' negation on file"
# Bystander tiers most fixture rows' "before" content provides as already
# correctly present via a plain literal line -- see F-C below and
# `_expected_bystanders_added`: a normalization break (e.g. a BOM-strip
# regression) can corrupt one of THESE lines while the row's directly-
# asserted /work-items/ outcome stays correct, which is exactly the blind
# spot an earlier round of this table shipped with.
_BYSTANDER_ENTRIES = ("/.reports/", "/.plans/", "/.scratch/")


def _expected_bystanders_added(content: bytes) -> set[str]:
    """REVISE round 5 (Finding 4): the bystander guard used to assert
    UNIVERSALLY that no bystander is ever added, in every row -- correct for
    every row that ALREADY carries all three bystanders as literal lines
    (which was every row at the time), but false-failing the moment a
    legitimate row (e.g. a first-time install with an empty .gitignore)
    genuinely needs to add one, with a failure message that named the wrong
    cause. Deriving the expectation from the row's OWN content -- the same
    exact-whole-line literal presence test the writer itself applies for a
    tier's un-prefixed alternate spelling, no BOM/CRLF/trailing-whitespace
    normalization needed since every row's bystander lines (when present) are
    written in the writer's own plain canonical form -- makes the guard
    correct for BOTH a row that pre-supplies all bystanders and one that
    genuinely needs them created."""
    stripped = content[3:] if content[:3] == b"\xef\xbb\xbf" else content
    normalized_lines = [
        line.rstrip() for line in stripped.decode("utf-8").replace("\r\n", "\n").split("\n")
    ]
    return {
        bystander
        for bystander in _BYSTANDER_ENTRIES
        if bystander not in normalized_lines and bystander.lstrip("/") not in normalized_lines
    }


def _build_large_gitignore_with_sentinel() -> bytes:
    """~200 KB of filler between the bystander tiers and the sentinel -- well
    past the ~64 KiB pipe buffer where F-A's SIGPIPE/pipefail inversion bug
    bit (a match that WAS found got reported as not found once the file grew
    large enough): confirmed empirically this session clean under ~64 KB,
    failing at ~100 KB+ against the pre-fix `printf | grep -q` pipeline."""
    filler_line = b"x" * 78 + b"\n"
    filler = filler_line * 2600  # ~203 KB, well past the ~64 KiB threshold
    return (
        b"/.reports/\n/.plans/\n/.scratch/\n"
        + filler
        + b"# orchestrarium:local-only-tier-declined:/work-items/\n"
    )


_LARGE_GITIGNORE_WITH_SENTINEL = _build_large_gitignore_with_sentinel()

FIXTURE_TABLE = (
    # name, before-content bytes, expect /work-items/ appended, expected stdout substring
    (
        "plain_missing_is_appended",
        b"/.reports/\n/.plans/\n/.scratch/\n",
        True,
        _ADDED_MARKER,
    ),
    (
        "sentinel_honored_plain",
        b"/.reports/\n/.plans/\n/.scratch/\n"
        b"# orchestrarium:local-only-tier-declined:/work-items/\n",
        False,
        _SENTINEL_MESSAGE,
    ),
    (
        # Finding 6, case mutant: a differently-cased sentinel must NOT be
        # honored -- the canonical answer is case-SENSITIVE on both engines.
        "sentinel_case_mismatch_is_not_honored",
        b"/.reports/\n/.plans/\n/.scratch/\n"
        b"# Orchestrarium:Local-Only-Tier-Declined:/work-items/\n",
        True,
        _ADDED_MARKER,
    ),
    (
        # Finding 6, second axis: a UTF-8 BOM on the first line plus CRLF
        # line endings throughout (as a real PowerShell-produced .gitignore
        # carries) must not defeat the sentinel match.
        "sentinel_honored_with_bom_and_crlf",
        b"\xef\xbb\xbf/.reports/\r\n/.plans/\r\n/.scratch/\r\n"
        b"# orchestrarium:local-only-tier-declined:/work-items/\r\n",
        False,
        _SENTINEL_MESSAGE,
    ),
    (
        # Finding 6: trailing whitespace an operator may have typed by hand
        # must not defeat the sentinel match.
        "sentinel_honored_with_trailing_whitespace",
        b"/.reports/\n/.plans/\n/.scratch/\n"
        b"# orchestrarium:local-only-tier-declined:/work-items/   \n",
        False,
        _SENTINEL_MESSAGE,
    ),
    (
        # Finding 10, substring mutant: a sentinel naming a DIFFERENT (here:
        # singular, typo'd) entry must not decline /work-items/ -- proves
        # exact whole-line matching, not a substring/prefix match.
        "sentinel_for_wrong_entry_is_not_honored",
        b"/.reports/\n/.plans/\n/.scratch/\n"
        b"# orchestrarium:local-only-tier-declined:/work-item/\n",
        True,
        _ADDED_MARKER,
    ),
    (
        # Finding 7 (original, restored to its PRE-ROUND-5-REWORK bytes):
        # git's own negation syntax, leading-slash form, BARE -- no
        # companion positive pattern anywhere in the file. REVISE round 6:
        # an earlier round REPLACED this row's bytes with a base-pattern-
        # paired variant instead of keeping it, on the belief that a bare
        # row would short-circuit at presence -- that belief was never
        # verified and was wrong (a bare negation reaches the probe just
        # fine); replaying these EXACT original bytes against that round's
        # code showed all four such rows failing (Finding 1: a bare
        # negation was un-ignored both with and without itself present, so
        # the differential probe called it "genuinely missing" and
        # appended, flipping git's real verdict to IGNORED -- the opposite
        # of what the operator wrote). Fixed by testing each negation
        # line's OWN stripped pattern in ISOLATION (see the module
        # docstring) rather than a whole-file before/after differential;
        # this exact row is now the regression lock for that fix.
        "negation_leading_slash_form_is_honored",
        b"/.reports/\n/.plans/\n/.scratch/\n!/work-items/\n",
        False,
        _NEGATION_MESSAGE,
    ),
    (
        "negation_no_leading_slash_form_is_honored",
        b"/.reports/\n/.plans/\n/.scratch/\n!work-items/\n",
        False,
        _NEGATION_MESSAGE,
    ),
    (
        # REVISE round 4, F-D ground truth (confirmed against real git this
        # session via `git check-ignore -v`): a negation WITHOUT the trailing
        # slash, leading slash present, is a real spelling git recognizes.
        "negation_no_trailing_slash_leading_slash_is_honored",
        b"/.reports/\n/.plans/\n/.scratch/\n!/work-items\n",
        False,
        _NEGATION_MESSAGE,
    ),
    (
        # REVISE round 4, F-D ground truth: neither leading nor trailing
        # slash -- also a real spelling git recognizes.
        "negation_no_slashes_at_all_is_honored",
        b"/.reports/\n/.plans/\n/.scratch/\n!work-items\n",
        False,
        _NEGATION_MESSAGE,
    ),
    (
        # REVISE round 6: the base-pattern-PAIRED variants of the four rows
        # above, added ALONGSIDE the restored bare originals rather than in
        # place of them -- this is the REALISTIC "operator edited a
        # .gitignore this writer previously wrote" shape (a companion
        # positive pattern already present) and exercises the SAME
        # isolated-pattern probe from the other direction (a negation whose
        # target IS otherwise positively covered elsewhere in the file).
        "negation_leading_slash_form_paired_with_base_pattern_is_honored",
        b"/.reports/\n/.plans/\n/.scratch/\n/work-items\n!/work-items/\n",
        False,
        _NEGATION_MESSAGE,
    ),
    (
        # REVISE round 5 (Finding 2), new spellings the four-form enumeration
        # missed a THIRD time -- confirmed against real git this session via
        # `git check-ignore -v`, and this exact form is the end-to-end
        # destroy proof: `/wo*/` plus `!**/work-items/`, core.ignorecase=true,
        # tracked '/work-items/' before the writer ran and was silently
        # re-ignored after, under the retired enumeration.
        "negation_globstar_form_is_honored",
        b"/.reports/\n/.plans/\n/.scratch/\n/wo*/\n!**/work-items/\n",
        False,
        _NEGATION_MESSAGE,
    ),
    (
        # REVISE round 6: the SAME globstar spelling, but BARE -- no
        # companion positive pattern -- locking in that Finding 1's fix
        # generalizes to arbitrary glob spellings, not just the four
        # original literal forms.
        "negation_globstar_form_bare_is_honored",
        b"/.reports/\n/.plans/\n/.scratch/\n!**/work-items/\n",
        False,
        _NEGATION_MESSAGE,
    ),
    (
        # REVISE round 5 (Finding 2): character-class spelling.
        "negation_character_class_form_is_honored",
        b"/.reports/\n/.plans/\n/.scratch/\n/work-items\n!/work-item[s]\n",
        False,
        _NEGATION_MESSAGE,
    ),
    (
        # REVISE round 7: the character-class spelling, but BARE -- no
        # companion positive pattern. Round 5 added bare-form coverage for
        # the four basic spellings and globstar but left character class and
        # single-char wildcard with only base-pattern rows -- the bare form
        # is the operator-realistic one AND the one that regressed in round
        # 5 (Finding 1), so leaving these two uncovered repeats that
        # methodology gap in miniature.
        "negation_character_class_form_bare_is_honored",
        b"/.reports/\n/.plans/\n/.scratch/\n!/work-item[s]\n",
        False,
        _NEGATION_MESSAGE,
    ),
    (
        # REVISE round 5 (Finding 2): single-char wildcard spelling.
        "negation_single_char_wildcard_form_is_honored",
        b"/.reports/\n/.plans/\n/.scratch/\n/work-items\n!/work-item?\n",
        False,
        _NEGATION_MESSAGE,
    ),
    (
        # REVISE round 7: the single-char wildcard spelling, but BARE -- see
        # the character-class row above for why this coverage matters.
        "negation_single_char_wildcard_form_bare_is_honored",
        b"/.reports/\n/.plans/\n/.scratch/\n!/work-item?\n",
        False,
        _NEGATION_MESSAGE,
    ),
    (
        # REVISE round 5: an UNRELATED negation elsewhere in the file must
        # NOT be mistaken for a decline of /work-items/ -- proves the
        # per-negation-line isolated probe attributes "not ignored" to a
        # SPECIFIC negation line's actual (isolated) effect, not to "some
        # `!` line exists somewhere in this file" (a cruder heuristic that
        # would false-positive here and silently fail to protect a
        # genuinely missing tier).
        "unrelated_negation_elsewhere_is_not_mistaken_for_a_decline",
        b"/.reports/\n/.plans/\n/.scratch/\n!/some-other-thing/\n",
        True,
        _ADDED_MARKER,
    ),
    (
        # REVISE round 5 (Finding 4): the exact row the adversarial gate used
        # to demonstrate the F-C bystander guard's false-failure mode -- a
        # legitimate first-time install with a completely empty .gitignore
        # must add ALL FOUR entries, bystanders included, and the guard must
        # not mistake that for a bystander "unexpectedly re-added".
        "first_time_install_empty_gitignore",
        b"",
        True,
        _ADDED_MARKER,
    ),
    (
        # Finding 10, substring mutant (the specific gap a mutation-testing
        # pass found in an earlier draft of this table): the marker text
        # appearing as a SUBSTRING inside a longer, prose-like line -- not an
        # exact whole-line sentinel -- must NOT be honored. A `grep -Fxq`
        # regressed to `grep -Fq` (dropping the whole-line anchor `-x`) makes
        # this line match and silently swallow the tier; the earlier
        # "sentinel_for_wrong_entry_is_not_honored" row above does NOT catch
        # that regression (a SHORTER wrong-entry line can never substring-
        # contain the LONGER correct marker text), which is exactly why this
        # row exists as a separate case.
        "marker_text_as_substring_in_prose_is_not_honored",
        b"/.reports/\n/.plans/\n/.scratch/\n"
        b"# orchestrarium:local-only-tier-declined:/work-items/ is just an example, not a real decline\n",
        True,
        _ADDED_MARKER,
    ),
    (
        # F-A regression guard: a ~200 KB file with the sentinel AFTER the
        # ~64 KiB pipe-buffer threshold must still be honored. This is the
        # exact size class where `printf '%s\n' "$normalized" | grep -Fxq`
        # (a match found, then SIGPIPE on the unread remainder, then
        # pipefail promoting that SIGPIPE over grep's own success) silently
        # inverted a real match into "not found" -- clean under this
        # threshold is not evidence of correctness at this one.
        "large_file_sentinel_still_honored",
        _LARGE_GITIGNORE_WITH_SENTINEL,
        False,
        _SENTINEL_MESSAGE,
    ),
)


@unittest.skipIf(BASH is None, "no bash on PATH")
@unittest.skipIf(shutil.which("git") is None, "negation delegation needs git on PATH")
class BashFixtureTableEquivalenceTest(unittest.TestCase):
    def test_fixture_table_on_bash(self) -> None:
        for name, content, expect_appended, expect_message in FIXTURE_TABLE:
            expected_bystanders_added = _expected_bystanders_added(content)
            for installer in SH_INSTALLERS:
                with self.subTest(fixture=name, installer=installer.name):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        gitignore = root / ".gitignore"
                        gitignore.write_bytes(content)
                        p = _run_bash_writer(installer, root)
                        self.assertEqual(p.returncode, 0, p.stderr)
                        actually_appended = _ADDED_MARKER in p.stdout
                        self.assertEqual(
                            actually_appended, expect_appended,
                            f"{name} on {installer.name}: appended={actually_appended} "
                            f"expected={expect_appended}; stdout={p.stdout!r}",
                        )
                        self.assertIn(
                            expect_message, p.stdout,
                            f"{name} on {installer.name}: stdout={p.stdout!r}",
                        )
                        # REVISE round 5 (Finding 4): a mutant-sensitive
                        # element (BOM, CRLF, etc.) placed on a BYSTANDER
                        # line -- one this row does not directly assert on --
                        # can corrupt that bystander while the row's own
                        # /work-items/ assertion stays green. The expectation
                        # is now DERIVED from this row's own content (was a
                        # bystander already present as a plain literal line,
                        # or does this row genuinely need it created, e.g. a
                        # first-time empty-.gitignore install) instead of a
                        # blanket "never added" that false-failed on exactly
                        # that legitimate case.
                        for bystander in _BYSTANDER_ENTRIES:
                            actually_added_bystander = f"added '{bystander}'" in p.stdout
                            self.assertEqual(
                                actually_added_bystander, bystander in expected_bystanders_added,
                                f"{name} on {installer.name}: bystander tier {bystander} "
                                f"added={actually_added_bystander} "
                                f"expected={bystander in expected_bystanders_added}; "
                                f"stdout={p.stdout!r}",
                            )


@unittest.skipIf(not PS_INTERPRETERS, "no PowerShell host (pwsh/powershell) on PATH")
@unittest.skipIf(shutil.which("git") is None, "negation delegation needs git on PATH")
class PowerShellFixtureTableEquivalenceTest(unittest.TestCase):
    def test_fixture_table_on_powershell(self) -> None:
        for name, content, expect_appended, expect_message in FIXTURE_TABLE:
            expected_bystanders_added = _expected_bystanders_added(content)
            for interp in PS_INTERPRETERS:
                for installer in PS1_INSTALLERS:
                    with self.subTest(fixture=name, interp=Path(interp).stem, installer=installer.name):
                        with tempfile.TemporaryDirectory() as td:
                            root = Path(td)
                            gitignore = root / ".gitignore"
                            gitignore.write_bytes(content)
                            p = _run_ps1_writer(interp, installer, root)
                            self.assertEqual(p.returncode, 0, p.stderr)
                            actually_appended = _ADDED_MARKER in p.stdout
                            self.assertEqual(
                                actually_appended, expect_appended,
                                f"{name} on {installer.name} ({interp}): appended={actually_appended} "
                                f"expected={expect_appended}; stdout={p.stdout!r}",
                            )
                            self.assertIn(
                                expect_message, p.stdout,
                                f"{name} on {installer.name} ({interp}): stdout={p.stdout!r}",
                            )
                            # REVISE round 5 (Finding 4): see the bash
                            # counterpart above -- expectation derived from
                            # this row's own content, not a blanket "never
                            # added".
                            for bystander in _BYSTANDER_ENTRIES:
                                actually_added_bystander = f"added '{bystander}'" in p.stdout
                                self.assertEqual(
                                    actually_added_bystander, bystander in expected_bystanders_added,
                                    f"{name} on {installer.name} ({interp}): bystander tier "
                                    f"{bystander} added={actually_added_bystander} "
                                    f"expected={bystander in expected_bystanders_added}; "
                                    f"stdout={p.stdout!r}",
                                )


GIT = shutil.which("git")


def _path_without_git() -> str | None:
    """A PATH value with EVERY directory that resolves a `git`/`git.exe`
    removed (bash, grep, sed, mktemp etc. all stay resolvable) -- used to
    exercise the writer's safe fallback when negation delegation cannot run
    at all. Removing only `shutil.which("git")`'s own directory is not
    enough: this machine's real PATH carries several independent git
    providers (a Git-for-Windows install, GitHub Desktop's bundled copy, a
    `cmd` shim, distinct mount views of the same mingw64 tree) -- confirmed
    this session that stripping just the first hit still leaves git
    resolvable via a later PATH entry -- so every candidate directory is
    checked, not just the one `which` happens to report first."""
    if GIT is None:
        return None
    remaining = []
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        entry_path = Path(entry)
        if any((entry_path / name).is_file() for name in ("git", "git.exe", "git.EXE")):
            continue
        remaining.append(entry)
    return os.pathsep.join(remaining)


@unittest.skipIf(BASH is None or GIT is None, "needs bash and git on PATH (to build a git-less PATH from)")
class BashNegationGitUnavailableFallbackTest(unittest.TestCase):
    """REVISE round 5: when `git` itself is not on PATH, the throwaway-repo
    negation delegation this round adds cannot run at all. The writer must
    degrade SAFELY -- leave every unresolved tier alone with a distinct
    disclosure message -- rather than either crash or guess via a spelling
    list (the very mechanism this round retires). Appending blindly here
    would risk silently overriding a real, undetectable negation; this test
    locks in the conservative choice."""

    def test_unresolved_tiers_are_left_alone_without_git(self) -> None:
        path_without_git = _path_without_git()
        env = dict(os.environ)
        env["PATH"] = path_without_git
        # Precondition check, not an assumption: some MSYS2/Git-for-Windows
        # bash builds re-derive their OWN base PATH (`/usr/bin`, `/mingw64/
        # bin`, `/cmd`) at startup independent of an inherited PATH override
        # -- confirmed this session (stripping every PATH entry that
        # resolves `git`/`git.exe` still left `command -v git` succeeding
        # inside the subprocess). Where that holds, "hide git from a bash
        # child process via env PATH alone" is not achievable here, so the
        # test honestly skips rather than asserting a precondition it cannot
        # verify actually held.
        probe = subprocess.run(
            [BASH, "-c", "command -v git >/dev/null 2>&1"], env=env, capture_output=True, text=True,
        )
        if probe.returncode == 0:
            self.skipTest(
                "this bash cannot be made to see git unavailable via env PATH alone "
                "(some MSYS2/Git-for-Windows builds re-derive their own base PATH) -- "
                "git-unavailable fallback verified manually this session instead"
            )
        for installer in SH_INSTALLERS:
            with self.subTest(installer=installer.name):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    (root / ".gitignore").write_text(
                        "/wo*/\n!**/work-items/\n", encoding="utf-8", newline="",
                    )
                    p = _run_bash_writer(installer, root, env=env)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertNotIn(
                        "added '/work-items/'", p.stdout,
                        f"{installer.name}: writer appended /work-items/ with git unavailable -- "
                        f"cannot have verified an undetected negation; stdout={p.stdout!r}",
                    )
                    self.assertIn(
                        "could not be checked against git", p.stdout,
                        f"{installer.name}: missing the git-unavailable disclosure message; "
                        f"stdout={p.stdout!r}",
                    )
                    after = (root / ".gitignore").read_text(encoding="utf-8", newline="")
                    # An exact-whole-line check, not a substring one: the
                    # base fixture's OWN negation line ("!**/work-items/")
                    # legitimately CONTAINS "/work-items/" as a substring, so
                    # a naive `assertNotIn` would false-fail on the fixture's
                    # own unrelated content, not on an actual (re-)append.
                    self.assertNotIn("/work-items/", after.splitlines())


@unittest.skipIf(not PS_INTERPRETERS or GIT is None, "needs a PowerShell host and git on PATH (to build a git-less PATH from)")
class PowerShellNegationGitUnavailableFallbackTest(unittest.TestCase):
    """PowerShell counterpart to BashNegationGitUnavailableFallbackTest above.
    Windows-native processes do not carry the MSYS2 own-base-PATH
    re-derivation the bash test above has to defend against, so this is
    expected to be reliable rather than skip-prone -- verified manually this
    session on both pwsh 7 and Windows PowerShell 5.1 before being locked in
    here as a permanent regression."""

    def test_unresolved_tiers_are_left_alone_without_git(self) -> None:
        path_without_git = _path_without_git()
        env = dict(os.environ)
        env["PATH"] = path_without_git
        for interp in PS_INTERPRETERS:
            for installer in PS1_INSTALLERS:
                with self.subTest(interp=Path(interp).stem, installer=installer.name):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        (root / ".gitignore").write_text(
                            "/wo*/\r\n!**/work-items/\r\n", encoding="utf-8", newline="",
                        )
                        p = _run_ps1_writer(interp, installer, root, env=env)
                        self.assertEqual(p.returncode, 0, p.stderr)
                        self.assertNotIn(
                            "added '/work-items/'", p.stdout,
                            f"{installer.name} ({interp}): writer appended /work-items/ with git "
                            f"unavailable -- cannot have verified an undetected negation; "
                            f"stdout={p.stdout!r}",
                        )
                        self.assertIn(
                            "could not be checked against git", p.stdout,
                            f"{installer.name} ({interp}): missing the git-unavailable disclosure "
                            f"message; stdout={p.stdout!r}",
                        )
                        after = (root / ".gitignore").read_text(encoding="utf-8", newline="")
                        self.assertNotIn("/work-items/", after.splitlines())


def _build_fake_global_gitconfig(tmp_path: Path) -> str:
    """REVISE round 6 (Finding 3): a fake GLOBAL git config -- pointed at via
    the GIT_CONFIG_GLOBAL env var, which git itself recognizes as an override
    for the global config file location -- that carries BOTH leak vectors
    found this session: a `core.excludesFile` covering the tier, and an
    `init.templateDir` whose `info/exclude` also covers it. Using
    GIT_CONFIG_GLOBAL to simulate "the operator's real ~/.gitconfig has this"
    means the test never touches the actual developer machine's real global
    git config."""
    excludes_file = tmp_path / "fake-global-excludes"
    excludes_file.write_text("/work-items/\n", encoding="utf-8", newline="\n")
    template_dir = tmp_path / "fake-template-dir"
    (template_dir / "info").mkdir(parents=True)
    (template_dir / "info" / "exclude").write_text("/work-items/\n", encoding="utf-8", newline="\n")
    fake_global = tmp_path / "fake-global-gitconfig"
    fake_global.write_text(
        f"[core]\n\texcludesFile = {excludes_file.as_posix()}\n"
        f"[init]\n\ttemplateDir = {template_dir.as_posix()}\n",
        encoding="utf-8", newline="\n",
    )
    return str(fake_global)


@unittest.skipIf(BASH is None or GIT is None, "needs bash and git on PATH")
class BashGitEnvironmentNeutralizationTest(unittest.TestCase):
    """REVISE round 6 (Finding 3): the throwaway repo used for negation
    delegation must not inherit the OPERATOR's ambient git environment.
    Without neutralization, an operator's own global `core.excludesFile` or
    `init.templateDir` covering a tier makes the writer silently decide
    "already ignored" for a PROJECT whose own .gitignore says nothing about
    it -- so a teammate cloning without that global config would track the
    tier: local-only content entering version control, the exact
    publication-safety failure this tier system exists to prevent."""

    def test_operator_global_excludes_and_template_do_not_leak_into_the_decision(self) -> None:
        for installer in SH_INSTALLERS:
            with self.subTest(installer=installer.name):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    fake_global = _build_fake_global_gitconfig(root)
                    env = dict(os.environ)
                    env["GIT_CONFIG_GLOBAL"] = fake_global
                    # No .gitignore at all: a genuinely first-time install.
                    p = _run_bash_writer(installer, root, env=env)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertIn(
                        "added '/work-items/'", p.stdout,
                        f"{installer.name}: writer silently skipped /work-items/ because the "
                        f"operator's GLOBAL git config (not this project's own .gitignore) covers "
                        f"it -- this is the Finding 3 environment-leakage defect; "
                        f"stdout={p.stdout!r}",
                    )
                    after = (root / ".gitignore").read_text(encoding="utf-8", newline="")
                    self.assertIn("/work-items/", after.splitlines())

    def test_ambient_repository_location_vars_do_not_redirect_the_probe(self) -> None:
        """REVISE round 7 (the class, not the instances): round 6 named and
        closed GIT_CONFIG_GLOBAL/core.excludesFile and init.templateDir.
        Round 7 named GIT_DIR, GIT_WORK_TREE, and GIT_CONFIG_COUNT BY NAME --
        each still redirected the probe onto a DIFFERENT repository or
        injected arbitrary config from the environment, entirely bypassing
        the round-6 neutralization (confirmed this session: `-C <dir>` does
        NOT override an ambient GIT_WORK_TREE, and GIT_CONFIG_COUNT/
        GIT_CONFIG_KEY_n/GIT_CONFIG_VALUE_n inject config directly from the
        environment, independent of GIT_CONFIG_NOSYSTEM/GIT_CONFIG_GLOBAL).
        Fixed by clearing the WHOLE git-documented repository-location and
        configuration-location environment-variable class in one place, not
        by chasing named instances one at a time -- this test locks in three
        representative members of that class (an unrelated repo via
        GIT_WORK_TREE alone, the same paired with GIT_DIR, and a
        GIT_CONFIG_COUNT-injected core.excludesFile), not an exhaustive
        enumeration of the class itself."""
        with tempfile.TemporaryDirectory() as other_td:
            other_repo = Path(other_td) / "other-repo"
            other_repo.mkdir()
            subprocess.run([GIT, "init", "-q", str(other_repo)], check=True, capture_output=True)
            (other_repo / ".gitignore").write_text("/work-items/\n", encoding="utf-8", newline="\n")

            injected_excludes = Path(other_td) / "injected-excludes"
            injected_excludes.write_text("/work-items/\n", encoding="utf-8", newline="\n")

            scenarios = (
                ("GIT_WORK_TREE_alone", {"GIT_WORK_TREE": str(other_repo)}),
                ("GIT_DIR_and_WORK_TREE", {"GIT_DIR": str(other_repo / ".git"), "GIT_WORK_TREE": str(other_repo)}),
                (
                    "GIT_CONFIG_COUNT_injection",
                    {
                        "GIT_CONFIG_COUNT": "1",
                        "GIT_CONFIG_KEY_0": "core.excludesFile",
                        "GIT_CONFIG_VALUE_0": str(injected_excludes),
                    },
                ),
            )
            for scenario_name, extra_env in scenarios:
                for installer in SH_INSTALLERS:
                    with self.subTest(scenario=scenario_name, installer=installer.name):
                        with tempfile.TemporaryDirectory() as td:
                            root = Path(td)
                            env = dict(os.environ)
                            env.update(extra_env)
                            p = _run_bash_writer(installer, root, env=env)
                            self.assertEqual(p.returncode, 0, p.stderr)
                            self.assertIn(
                                "added '/work-items/'", p.stdout,
                                f"{scenario_name} on {installer.name}: writer silently skipped "
                                f"/work-items/ because an ambient repository-location/config "
                                f"env var redirected the probe onto a DIFFERENT repository; "
                                f"stdout={p.stdout!r}",
                            )
                            after = (root / ".gitignore").read_text(encoding="utf-8", newline="")
                            self.assertIn("/work-items/", after.splitlines())

    def test_default_excludes_path_fallback_and_pathspec_magic_do_not_leak(self) -> None:
        """REVISE round 8: `core.excludesFile` has no default VALUE, but git
        falls back to a default PATH ($XDG_CONFIG_HOME/git/ignore, else
        $HOME/.config/git/ignore) whenever core.excludesFile itself is
        UNSET -- which is exactly the state `GIT_CONFIG_GLOBAL=<nonexistent>`
        (round 6's fix) leaves it in, so round 6's fix did NOT close this:
        confirmed this session that an ambient HOME or XDG_CONFIG_HOME
        pointing at a real `~/.config/git/ignore` covering the tier leaked
        in SILENTLY even with GIT_CONFIG_NOSYSTEM/GIT_CONFIG_GLOBAL already
        neutralized. This is plausibly the MOST LIKELY trigger of any vector
        found in this family: `~/.config/git/ignore` is the standard
        personal global-gitignore location. Fixed by setting
        core.excludesFile EXPLICITLY on the throwaway repo (a nonexistent
        path is enough) rather than relying on it staying unset. Also locks
        in the four pathspec-magic variables (GIT_ICASE_PATHSPECS,
        GIT_LITERAL_PATHSPECS, GIT_NOGLOB_PATHSPECS, GIT_GLOB_PATHSPECS),
        which make `check-ignore` fail outright (exit 128) -- not a silent
        leak, but the tier was still left unwritten with only a
        "could not be checked" disclosure until these were added to the
        cleared set."""
        with tempfile.TemporaryDirectory() as fake_home_td:
            fake_home = Path(fake_home_td)
            (fake_home / ".config" / "git").mkdir(parents=True)
            (fake_home / ".config" / "git" / "ignore").write_text(
                "/work-items/\n", encoding="utf-8", newline="\n",
            )

            scenarios = (
                ("HOME_default_excludes_path", {"HOME": str(fake_home)}),
                ("XDG_CONFIG_HOME_default_excludes_path", {"XDG_CONFIG_HOME": str(fake_home / ".config")}),
                ("pathspec_GIT_ICASE_PATHSPECS", {"GIT_ICASE_PATHSPECS": "1"}),
                ("pathspec_GIT_LITERAL_PATHSPECS", {"GIT_LITERAL_PATHSPECS": "1"}),
                ("pathspec_GIT_NOGLOB_PATHSPECS", {"GIT_NOGLOB_PATHSPECS": "1"}),
                ("pathspec_GIT_GLOB_PATHSPECS", {"GIT_GLOB_PATHSPECS": "1"}),
            )
            for scenario_name, extra_env in scenarios:
                for installer in SH_INSTALLERS:
                    with self.subTest(scenario=scenario_name, installer=installer.name):
                        with tempfile.TemporaryDirectory() as td:
                            root = Path(td)
                            env = dict(os.environ)
                            env.update(extra_env)
                            p = _run_bash_writer(installer, root, env=env)
                            self.assertEqual(p.returncode, 0, p.stderr)
                            self.assertIn(
                                "added '/work-items/'", p.stdout,
                                f"{scenario_name} on {installer.name}: writer did not append "
                                f"/work-items/ -- either the default-excludes-path fallback "
                                f"leaked in silently, or a pathspec-magic variable was not "
                                f"cleared; stdout={p.stdout!r}",
                            )
                            after = (root / ".gitignore").read_text(encoding="utf-8", newline="")
                            self.assertIn("/work-items/", after.splitlines())


@unittest.skipIf(not PS_INTERPRETERS or GIT is None, "needs a PowerShell host and git on PATH")
class PowerShellGitEnvironmentNeutralizationTest(unittest.TestCase):
    """PowerShell counterpart to BashGitEnvironmentNeutralizationTest above."""

    def test_operator_global_excludes_and_template_do_not_leak_into_the_decision(self) -> None:
        for interp in PS_INTERPRETERS:
            for installer in PS1_INSTALLERS:
                with self.subTest(interp=Path(interp).stem, installer=installer.name):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        fake_global = _build_fake_global_gitconfig(root)
                        env = dict(os.environ)
                        env["GIT_CONFIG_GLOBAL"] = fake_global
                        p = _run_ps1_writer(interp, installer, root, env=env)
                        self.assertEqual(p.returncode, 0, p.stderr)
                        self.assertIn(
                            "added '/work-items/'", p.stdout,
                            f"{installer.name} ({interp}): writer silently skipped /work-items/ "
                            f"because the operator's GLOBAL git config leaked in; "
                            f"stdout={p.stdout!r}",
                        )
                        after = (root / ".gitignore").read_text(encoding="utf-8", newline="")
                        self.assertIn("/work-items/", after.splitlines())

    def test_ambient_repository_location_vars_do_not_redirect_the_probe(self) -> None:
        """PowerShell counterpart to the bash version above -- the reviewer
        explicitly flagged that PowerShell parity must be MEASURED, not
        assumed, since this family has already been bitten twice by that
        exact asymmetry."""
        with tempfile.TemporaryDirectory() as other_td:
            other_repo = Path(other_td) / "other-repo"
            other_repo.mkdir()
            subprocess.run([GIT, "init", "-q", str(other_repo)], check=True, capture_output=True)
            (other_repo / ".gitignore").write_text("/work-items/\n", encoding="utf-8", newline="\n")

            injected_excludes = Path(other_td) / "injected-excludes"
            injected_excludes.write_text("/work-items/\n", encoding="utf-8", newline="\n")

            scenarios = (
                ("GIT_WORK_TREE_alone", {"GIT_WORK_TREE": str(other_repo)}),
                ("GIT_DIR_and_WORK_TREE", {"GIT_DIR": str(other_repo / ".git"), "GIT_WORK_TREE": str(other_repo)}),
                (
                    "GIT_CONFIG_COUNT_injection",
                    {
                        "GIT_CONFIG_COUNT": "1",
                        "GIT_CONFIG_KEY_0": "core.excludesFile",
                        "GIT_CONFIG_VALUE_0": str(injected_excludes),
                    },
                ),
            )
            for scenario_name, extra_env in scenarios:
                for interp in PS_INTERPRETERS:
                    for installer in PS1_INSTALLERS:
                        with self.subTest(scenario=scenario_name, interp=Path(interp).stem, installer=installer.name):
                            with tempfile.TemporaryDirectory() as td:
                                root = Path(td)
                                env = dict(os.environ)
                                env.update(extra_env)
                                p = _run_ps1_writer(interp, installer, root, env=env)
                                self.assertEqual(p.returncode, 0, p.stderr)
                                self.assertIn(
                                    "added '/work-items/'", p.stdout,
                                    f"{scenario_name} on {installer.name} ({interp}): writer silently "
                                    f"skipped /work-items/ because an ambient repository-location/"
                                    f"config env var redirected the probe; stdout={p.stdout!r}",
                                )
                                after = (root / ".gitignore").read_text(encoding="utf-8", newline="")
                                self.assertIn("/work-items/", after.splitlines())

    def test_default_excludes_path_fallback_and_pathspec_magic_do_not_leak(self) -> None:
        """PowerShell counterpart to the bash version above -- verified
        directly, not assumed from the bash-side finding, on both pwsh 7
        and Windows PowerShell 5.1 (the latter surfacing the pathspec-magic
        failure as a NativeCommandError before the writer's own
        relax-and-restore wrap around the native call absorbs it)."""
        with tempfile.TemporaryDirectory() as fake_home_td:
            fake_home = Path(fake_home_td)
            (fake_home / ".config" / "git").mkdir(parents=True)
            (fake_home / ".config" / "git" / "ignore").write_text(
                "/work-items/\n", encoding="utf-8", newline="\n",
            )

            scenarios = (
                ("HOME_default_excludes_path", {"HOME": str(fake_home)}),
                ("XDG_CONFIG_HOME_default_excludes_path", {"XDG_CONFIG_HOME": str(fake_home / ".config")}),
                ("pathspec_GIT_ICASE_PATHSPECS", {"GIT_ICASE_PATHSPECS": "1"}),
                ("pathspec_GIT_LITERAL_PATHSPECS", {"GIT_LITERAL_PATHSPECS": "1"}),
                ("pathspec_GIT_NOGLOB_PATHSPECS", {"GIT_NOGLOB_PATHSPECS": "1"}),
                ("pathspec_GIT_GLOB_PATHSPECS", {"GIT_GLOB_PATHSPECS": "1"}),
            )
            for scenario_name, extra_env in scenarios:
                for interp in PS_INTERPRETERS:
                    for installer in PS1_INSTALLERS:
                        with self.subTest(scenario=scenario_name, interp=Path(interp).stem, installer=installer.name):
                            with tempfile.TemporaryDirectory() as td:
                                root = Path(td)
                                env = dict(os.environ)
                                env.update(extra_env)
                                p = _run_ps1_writer(interp, installer, root, env=env)
                                self.assertEqual(p.returncode, 0, p.stderr)
                                self.assertIn(
                                    "added '/work-items/'", p.stdout,
                                    f"{scenario_name} on {installer.name} ({interp}): writer did not "
                                    f"append /work-items/; stdout={p.stdout!r}",
                                )
                                after = (root / ".gitignore").read_text(encoding="utf-8", newline="")
                                self.assertIn("/work-items/", after.splitlines())


def _write_bash_excludes_failure_shim(shim_dir: Path, real_git: str) -> Path:
    """A `git` placed first on PATH that passes every invocation through to
    the REAL git UNMODIFIED except the one exact call the round-8 hardening
    fix targets -- `git -C <dir> config core.excludesFile <path>` -- which it
    fails with exit 1, emitting a recognizable stdout marker so a preflight
    probe can confirm THIS shim (not a real git failure for some unrelated
    reason) actually fired. `git init`, `check-ignore`, and the
    `core.ignorecase` mirror calls all reach the real git untouched, so the
    throwaway repo this fix guards is genuinely alive for the run -- only its
    own hardening write is made to fail, mirroring the exact fault an
    external review forced (injecting the failure into ONLY this command
    left the installer returning 0 and the tier silently left unappended,
    with the ambient-leak fixture from
    test_default_excludes_path_fallback_and_pathspec_magic_do_not_leak
    proving the leak survives without this fix)."""
    shim_dir.mkdir(parents=True, exist_ok=True)
    git_shim = shim_dir / "git"
    git_shim.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "-C" ] && [ "$3" = "config" ] && [ "$4" = "core.excludesFile" ]; then\n'
        '  echo "FAKE_GIT_EXCLUDES_FAILURE_MARKER"\n'
        "  exit 1\n"
        "fi\n"
        'exec "$REAL_GIT" "$@"\n',
        encoding="utf-8", newline="\n",
    )
    git_shim.chmod(0o755)
    return git_shim


def _write_ps1_excludes_failure_shim(shim_dir: Path) -> Path:
    """Windows/PowerShell counterpart to _write_bash_excludes_failure_shim
    above: a `git.cmd` placed first on PATH so native command resolution
    finds it before the real git.exe. Delegates every invocation to the real
    git (path supplied via the REAL_GIT env var, quoted for a path that may
    contain spaces) except the one exact `-C <dir> config
    core.excludesFile <path>` call, which it fails with exit code 1 after
    the same stdout marker."""
    shim_dir.mkdir(parents=True, exist_ok=True)
    git_cmd = shim_dir / "git.cmd"
    git_cmd.write_text(
        "@echo off\r\n"
        'if "%~1"=="-C" if "%~3"=="config" if "%~4"=="core.excludesFile" (\r\n'
        "  echo FAKE_GIT_EXCLUDES_FAILURE_MARKER\r\n"
        "  exit /b 1\r\n"
        ")\r\n"
        '"%REAL_GIT%" %*\r\n',
        encoding="utf-8", newline="",
    )
    return git_cmd


@unittest.skipIf(BASH is None or GIT is None, "needs bash and git on PATH")
class BashConfigWriteFailureFailsClosedTest(unittest.TestCase):
    """Regression for
    work-items/bugs/2026-07-26-the-excludesfile-hardening-step-does-not-verify-its-own-precondition.md
    (external-review-forced): the `git config core.excludesFile ...`
    hardening write added for round 8 (see
    BashGitEnvironmentNeutralizationTest.test_default_excludes_path_fallback_
    and_pathspec_magic_do_not_leak above) had its OWN failure discarded via
    `|| true`, while its neighbour two lines above (`git init`) already fails
    the probe closed on failure -- one precondition failed closed, the other
    failed open, in the SAME function. An external review injected a failure
    into ONLY the excludesFile write and confirmed the installer still
    returned 0 with the tier silently left unappended -- looking safe by the
    OTHER assertion direction (nothing wrongly ignored) -- but a probe whose
    own hardening step could not be confirmed is UNVERIFIABLE, not merely
    unhardened, and the round-8 fixture above proves the concrete
    consequence: the ambient-leak scenario this hardening step exists to
    close survives it silently when the write itself fails partway. Fixed by
    checking the write's own exit status and discarding the throwaway repo
    (mirroring the `git init` check already immediately above it) rather
    than assuming success.

    This test locks in the fail-closed direction directly, independent of
    any particular ambient leak: an injected excludesFile-write failure, on
    its own, must decline every unresolved tier rather than silently trust
    an unverifiable probe."""

    def test_excludes_write_failure_declines_rather_than_silently_proceeds(self) -> None:
        for installer in SH_INSTALLERS:
            with self.subTest(installer=installer.name):
                with tempfile.TemporaryDirectory() as shim_td, tempfile.TemporaryDirectory() as td:
                    shim_dir = Path(shim_td)
                    _write_bash_excludes_failure_shim(shim_dir, GIT)
                    env = dict(os.environ)
                    env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
                    env["REAL_GIT"] = GIT

                    # Precondition check, not an assumption (same defensive
                    # style as BashNegationGitUnavailableFallbackTest above):
                    # some MSYS2/Git-for-Windows bash builds re-derive their
                    # OWN base PATH at startup, which could resolve "git" to
                    # something other than this shim despite the PATH
                    # override. Confirm the SHIM specifically fired (via its
                    # marker), not merely that some command failed, before
                    # trusting the end-to-end run below.
                    probe = subprocess.run(
                        [BASH, "-c",
                         "git -C orchestrarium-nonexistent-probe-dir config "
                         "core.excludesFile orchestrarium-nonexistent-probe-dir.noexcludes"],
                        env=env, capture_output=True, text=True,
                    )
                    if "FAKE_GIT_EXCLUDES_FAILURE_MARKER" not in probe.stdout:
                        self.skipTest(
                            "this bash does not resolve 'git' to the injected shim "
                            "(some MSYS2/Git-for-Windows builds re-derive their own base "
                            "PATH) -- cannot inject the excludesFile-write failure via env "
                            "PATH alone here"
                        )

                    root = Path(td)
                    # No .gitignore at all: every one of the four tiers is
                    # unresolved, so the injected failure's effect on ALL of
                    # them (giprobe_root is computed once, before the
                    # per-entry loop) is visible in one run.
                    p = _run_bash_writer(installer, root, env=env)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertNotIn(
                        "added '/work-items/'", p.stdout,
                        f"{installer.name}: writer appended /work-items/ despite the "
                        f"core.excludesFile hardening write failing -- the unverifiable "
                        f"probe result was silently trusted instead of declined; "
                        f"stdout={p.stdout!r}",
                    )
                    self.assertIn(
                        "could not be checked against git", p.stdout,
                        f"{installer.name}: missing the unverifiable-probe disclosure "
                        f"message after the injected excludesFile-write failure; "
                        f"stdout={p.stdout!r}",
                    )
                    gitignore_path = root / ".gitignore"
                    after = gitignore_path.read_text(encoding="utf-8", newline="") if gitignore_path.is_file() else ""
                    for entry in ("/.reports/", "/.plans/", "/work-items/", "/.scratch/"):
                        self.assertNotIn(
                            entry, after.splitlines(),
                            f"{installer.name}: '{entry}' present in .gitignore after an "
                            f"unverifiable probe result -- should have been declined, not "
                            f"written",
                        )


@unittest.skipIf(not PS_INTERPRETERS or GIT is None, "needs a PowerShell host and git on PATH")
class PowerShellConfigWriteFailureFailsClosedTest(unittest.TestCase):
    """PowerShell counterpart to BashConfigWriteFailureFailsClosedTest above.
    Windows-native process resolution is expected to be reliable (no MSYS2
    own-base-PATH re-derivation to defend against), but the shim's marker is
    still verified directly via a preflight probe rather than assumed, for
    the same reason the fixture tables in this module measure PowerShell
    parity instead of inferring it from the bash-side result."""

    def test_excludes_write_failure_declines_rather_than_silently_proceeds(self) -> None:
        for interp in PS_INTERPRETERS:
            for installer in PS1_INSTALLERS:
                with self.subTest(interp=Path(interp).stem, installer=installer.name):
                    with tempfile.TemporaryDirectory() as shim_td, tempfile.TemporaryDirectory() as td:
                        shim_dir = Path(shim_td)
                        _write_ps1_excludes_failure_shim(shim_dir)
                        env = dict(os.environ)
                        env["PATH"] = str(shim_dir) + os.pathsep + env.get("PATH", "")
                        env["REAL_GIT"] = GIT

                        probe = subprocess.run(
                            [interp, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                             "git -C orchestrarium-nonexistent-probe-dir config "
                             "core.excludesFile orchestrarium-nonexistent-probe-dir.noexcludes"],
                            env=env, capture_output=True, text=True,
                        )
                        if "FAKE_GIT_EXCLUDES_FAILURE_MARKER" not in probe.stdout:
                            self.skipTest(
                                f"{interp}: 'git' does not resolve to the injected shim here -- "
                                f"cannot inject the excludesFile-write failure via env PATH alone"
                            )

                        root = Path(td)
                        p = _run_ps1_writer(interp, installer, root, env=env)
                        self.assertEqual(p.returncode, 0, p.stderr)
                        self.assertNotIn(
                            "added '/work-items/'", p.stdout,
                            f"{installer.name} ({interp}): writer appended /work-items/ despite "
                            f"the core.excludesFile hardening write failing -- the unverifiable "
                            f"probe result was silently trusted instead of declined; "
                            f"stdout={p.stdout!r}",
                        )
                        self.assertIn(
                            "could not be checked against git", p.stdout,
                            f"{installer.name} ({interp}): missing the unverifiable-probe "
                            f"disclosure message after the injected excludesFile-write failure; "
                            f"stdout={p.stdout!r}",
                        )
                        gitignore_path = root / ".gitignore"
                        after = (
                            gitignore_path.read_text(encoding="utf-8", newline="")
                            if gitignore_path.is_file() else ""
                        )
                        for entry in ("/.reports/", "/.plans/", "/work-items/", "/.scratch/"):
                            self.assertNotIn(
                                entry, after.splitlines(),
                                f"{installer.name} ({interp}): '{entry}' present in .gitignore "
                                f"after an unverifiable probe result -- should have been "
                                f"declined, not written",
                            )


@unittest.skipIf(BASH is None or GIT is None, "needs bash and git on PATH")
class GitGroundTruthTest(unittest.TestCase):
    """REVISE round 4: "consider whether the table needs ... a git-ground-
    truth row more than it needs another matcher tweak." Every other test in
    this module verifies the writer against ITSELF (does its own decision
    match its own stated rule) -- this class instead verifies the writer's
    negation decision against REAL git behavior via `git check-ignore -v`,
    the same methodology the adversarial gate used to find the
    core.ignorecase split in the first place.

    REVISE round 5: the writer no longer reads project_root's own
    core.ignorecase directly (that read is what crashed Windows PowerShell
    5.1 on a corrupt value, and what leaked global config outside a repo --
    see the module docstring); negation is delegated to `git check-ignore`
    via an isolated throwaway repo instead. That throwaway repo mirrors
    project_root's own EXPLICIT LOCAL `core.ignorecase` when project_root is
    already a repo with one set (exactly what these tests configure via
    `git config core.ignorecase <value>` below), falling back to its own
    filesystem auto-detection only when project_root has no such override --
    so setting `core.ignorecase` explicitly on `root` below still
    deterministically controls the writer's decision, unchanged from round 4.

    The base ignore pattern deliberately uses `/work-items` (leading slash,
    NO trailing slash) rather than either of the writer's own two exact
    recognized presence forms (`/work-items/`, `work-items/`, both WITH a
    trailing slash) -- git still treats it as ignoring the directory (a
    pattern without a trailing slash matches both files and dirs of that
    name), but the writer's presence check does not recognize it as
    "already present", so these tests cleanly exercise the NEGATION path
    rather than being confounded by an early presence-check short-circuit
    (confirmed necessary this session: using the writer's own recognized
    `work-items/` form as the base pattern short-circuits at presence and
    never reaches the negation logic at all, testing the wrong code path)."""

    def _init_repo(self, root: Path) -> None:
        subprocess.run([GIT, "init", "-q", str(root)], check=True, capture_output=True)
        subprocess.run([GIT, "-C", str(root), "config", "user.email", "t@t"], check=True, capture_output=True)
        subprocess.run([GIT, "-C", str(root), "config", "user.name", "t"], check=True, capture_output=True)

    def _git_says_ignored(self, root: Path, probe: str = "work-items/probe.txt") -> bool:
        """Ground truth: True if git itself currently ignores the probe path,
        independent of anything our writer thinks."""
        target = root / probe
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
        p = subprocess.run(
            [GIT, "-C", str(root), "check-ignore", "-v", probe],
            capture_output=True, text=True,
        )
        return p.returncode == 0

    def test_writer_does_not_append_when_git_itself_is_not_ignoring(self) -> None:
        """core.ignorecase=true: a mixed-case negation ("!/Work-Items/") is
        real to git (measured this session), so git itself is NOT ignoring
        work-items/. The writer must not append -- doing so would fight a
        real, currently-effective decline, the exact originating defect
        class this whole bug is about."""
        for installer in SH_INSTALLERS:
            with self.subTest(installer=installer.name):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    self._init_repo(root)
                    subprocess.run([GIT, "-C", str(root), "config", "core.ignorecase", "true"],
                                    check=True, capture_output=True)
                    (root / ".gitignore").write_text(
                        "/.reports/\n/.plans/\n/.scratch/\n/work-items\n!/Work-Items/\n",
                        encoding="utf-8", newline="",
                    )
                    self.assertFalse(
                        self._git_says_ignored(root),
                        "test setup invalid: git should NOT be ignoring work-items/ here",
                    )

                    p = _run_bash_writer(installer, root)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertNotIn(
                        "added '/work-items/'", p.stdout,
                        f"{installer.name}: writer appended /work-items/ despite git itself "
                        f"NOT ignoring it (case-insensitive negation actually honored by git) "
                        f"-- this IS the silent-revert-of-a-real-decline defect; "
                        f"stdout={p.stdout!r}",
                    )

    def test_writer_does_not_redundantly_append_when_git_itself_is_still_ignoring(self) -> None:
        """The mirror case: core.ignorecase=false means git does NOT honor
        the mixed-case negation, so git itself is STILL ignoring
        work-items/ via the pre-existing `/work-items` pattern alone.

        REVISE round 5: under the retired string-enumeration negation
        detector, the writer was blind to any already-effective pattern
        other than its own two exact literal spellings, so it would
        redundantly append '/work-items/' here even though the directory was
        ALREADY being ignored. Delegating to `git check-ignore` makes the
        writer recognize "already achieves the goal" the same way it already
        recognized its own literal spelling, so it now correctly does
        nothing here -- a strictly more correct behavior (no redundant
        duplicate line), verified against the same ground truth as the
        sibling test above rather than assuming an append is always safe
        whenever git is not fighting a decline."""
        for installer in SH_INSTALLERS:
            with self.subTest(installer=installer.name):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    self._init_repo(root)
                    subprocess.run([GIT, "-C", str(root), "config", "core.ignorecase", "false"],
                                    check=True, capture_output=True)
                    (root / ".gitignore").write_text(
                        "/.reports/\n/.plans/\n/.scratch/\n/work-items\n!/Work-Items/\n",
                        encoding="utf-8", newline="",
                    )
                    self.assertTrue(
                        self._git_says_ignored(root),
                        "test setup invalid: git should still be ignoring work-items/ here",
                    )

                    p = _run_bash_writer(installer, root)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertNotIn(
                        "added '/work-items/'", p.stdout,
                        f"{installer.name}: writer redundantly appended /work-items/ even "
                        f"though git itself already ignores it via the pre-existing pattern; "
                        f"stdout={p.stdout!r}",
                    )

    def test_writer_decision_matches_git_for_a_case_mismatched_positive_pattern(self) -> None:
        """REVISE round 5: replaces the retired
        `presence_case_mismatch_does_not_count_as_present` fixture-table row,
        which assumed a FIXED case-sensitive answer independent of git's own
        core.ignorecase -- no longer true once a differently-cased line not
        recognized by the writer's own literal presence check is instead
        resolved via git delegation. Parametrized exactly like the negation
        pair above: a differently-cased POSITIVE pattern (no negation at all)
        must make the writer track git's real verdict in BOTH directions,
        never a fixed assumption."""
        for installer in SH_INSTALLERS:
            for ignorecase, expect_git_ignored, expect_appended in (
                ("true", True, False),
                ("false", False, True),
            ):
                with self.subTest(installer=installer.name, ignorecase=ignorecase):
                    with tempfile.TemporaryDirectory() as td:
                        root = Path(td)
                        self._init_repo(root)
                        subprocess.run([GIT, "-C", str(root), "config", "core.ignorecase", ignorecase],
                                        check=True, capture_output=True)
                        (root / ".gitignore").write_text(
                            "/.reports/\n/.plans/\n/.scratch/\n/WORK-ITEMS/\n",
                            encoding="utf-8", newline="",
                        )
                        self.assertEqual(
                            self._git_says_ignored(root), expect_git_ignored,
                            f"test setup invalid for ignorecase={ignorecase}",
                        )

                        p = _run_bash_writer(installer, root)
                        self.assertEqual(p.returncode, 0, p.stderr)
                        appended = "added '/work-items/'" in p.stdout
                        self.assertEqual(
                            appended, expect_appended,
                            f"{installer.name}, ignorecase={ignorecase}: appended={appended} "
                            f"expected={expect_appended} -- writer decision disagrees with "
                            f"real git; stdout={p.stdout!r}",
                        )


@unittest.skipIf(not PS_INTERPRETERS or GIT is None, "needs a PowerShell host and git on PATH")
class PowerShellGitGroundTruthTest(unittest.TestCase):
    """PowerShell counterpart to GitGroundTruthTest above -- same ground
    truth (`git check-ignore -v`), same fixture, driven through the real
    Ensure-LocalOnlyGitignoreEntries function instead of the bash one."""

    def _init_repo(self, root: Path) -> None:
        subprocess.run([GIT, "init", "-q", str(root)], check=True, capture_output=True)
        subprocess.run([GIT, "-C", str(root), "config", "user.email", "t@t"], check=True, capture_output=True)
        subprocess.run([GIT, "-C", str(root), "config", "user.name", "t"], check=True, capture_output=True)

    def _git_says_ignored(self, root: Path, probe: str = "work-items/probe.txt") -> bool:
        target = root / probe
        target.parent.mkdir(parents=True, exist_ok=True)
        target.touch()
        p = subprocess.run(
            [GIT, "-C", str(root), "check-ignore", "-v", probe],
            capture_output=True, text=True,
        )
        return p.returncode == 0

    def test_writer_decision_matches_git_ground_truth_both_directions(self) -> None:
        for interp in PS_INTERPRETERS:
            for installer in PS1_INSTALLERS:
                # REVISE round 5: the ignorecase=false branch's expectation
                # flips from True to False -- git already ignores work-items/
                # via the pre-existing `/work-items` pattern alone (the
                # mixed-case negation does not apply case-sensitively), so
                # the writer recognizing "already achieves the goal" via
                # delegation is strictly more correct than the retired
                # string-enumeration detector's blind redundant append.
                for ignorecase, expect_git_ignored, expect_appended in (
                    ("true", False, False),
                    ("false", True, False),
                ):
                    with self.subTest(interp=Path(interp).stem, installer=installer.name, ignorecase=ignorecase):
                        with tempfile.TemporaryDirectory() as td:
                            root = Path(td)
                            self._init_repo(root)
                            subprocess.run([GIT, "-C", str(root), "config", "core.ignorecase", ignorecase],
                                            check=True, capture_output=True)
                            (root / ".gitignore").write_text(
                                "/.reports/\r\n/.plans/\r\n/.scratch/\r\n/work-items\r\n!/Work-Items/\r\n",
                                encoding="utf-8", newline="",
                            )
                            self.assertEqual(
                                self._git_says_ignored(root), expect_git_ignored,
                                f"test setup invalid for ignorecase={ignorecase}",
                            )

                            p = _run_ps1_writer(interp, installer, root)
                            self.assertEqual(p.returncode, 0, p.stderr)
                            appended = "added '/work-items/'" in p.stdout
                            self.assertEqual(
                                appended, expect_appended,
                                f"{installer.name} ({interp}), ignorecase={ignorecase}: "
                                f"appended={appended} expected={expect_appended} -- writer "
                                f"decision disagrees with real git; stdout={p.stdout!r}",
                            )

    def test_writer_decision_matches_git_for_a_case_mismatched_positive_pattern(self) -> None:
        """PowerShell counterpart to the bash version above -- replaces the
        retired `presence_case_mismatch_does_not_count_as_present` fixture
        row for the same reason."""
        for interp in PS_INTERPRETERS:
            for installer in PS1_INSTALLERS:
                for ignorecase, expect_git_ignored, expect_appended in (
                    ("true", True, False),
                    ("false", False, True),
                ):
                    with self.subTest(interp=Path(interp).stem, installer=installer.name, ignorecase=ignorecase):
                        with tempfile.TemporaryDirectory() as td:
                            root = Path(td)
                            self._init_repo(root)
                            subprocess.run([GIT, "-C", str(root), "config", "core.ignorecase", ignorecase],
                                            check=True, capture_output=True)
                            (root / ".gitignore").write_text(
                                "/.reports/\r\n/.plans/\r\n/.scratch/\r\n/WORK-ITEMS/\r\n",
                                encoding="utf-8", newline="",
                            )
                            self.assertEqual(
                                self._git_says_ignored(root), expect_git_ignored,
                                f"test setup invalid for ignorecase={ignorecase}",
                            )

                            p = _run_ps1_writer(interp, installer, root)
                            self.assertEqual(p.returncode, 0, p.stderr)
                            appended = "added '/work-items/'" in p.stdout
                            self.assertEqual(
                                appended, expect_appended,
                                f"{installer.name} ({interp}), ignorecase={ignorecase}: "
                                f"appended={appended} expected={expect_appended} -- writer "
                                f"decision disagrees with real git; stdout={p.stdout!r}",
                            )


if __name__ == "__main__":
    unittest.main()
