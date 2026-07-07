"""All 8 installers carry exactly the canonical local-only .gitignore tier set.

Gap 5 of work-items/bugs/2026-07-07-installer-gaps-...: the four local-only tiers
(`/.reports/ /.plans/ /work-items/ /.scratch/`) were hardcoded in EIGHT installer
files (sh+ps1 × claude/codex/gemini/qwen). A new tier had to be added to all eight
by hand — this session added `/.plans/` twice (claude/codex first, then gemini/qwen
after an audit caught the gap). The single owner is now `shared/local-only-tiers.txt`
(validator-only; the installers keep the list inline for readability). This test
asserts every installer's inline tier set equals the owner's set — a tier added to
one installer but not another, or missing from one, fails.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIERS_FILE = ROOT / "shared" / "local-only-tiers.txt"

INSTALLERS = (
    "scripts/install-claude.sh",
    "scripts/install-claude.ps1",
    "scripts/install-codex.sh",
    "scripts/install-codex.ps1",
    "scripts/install-gemini.sh",
    "scripts/install-gemini.ps1",
    "scripts/install-qwen.sh",
    "scripts/install-qwen.ps1",
)

# A local-only tier token as written into .gitignore: /.name/ or /name/.
_TIER = re.compile(r"/\.?[A-Za-z0-9_-]+/")


def _canonical_tiers() -> set:
    tiers = set()
    for line in TIERS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            tiers.add(line)
    return tiers


def _installer_tier_array(text: str) -> set:
    """Extract the tier tokens from the installer's local-only entries array.
    bash: `entries=("/.reports/" "/.plans/" "/work-items/" "/.scratch/")`
    ps1:  `$entries = @("/.reports/", "/.plans/", "/work-items/", "/.scratch/")`
    Anchored to the `entries` assignment so unrelated `/x/` paths don't leak in."""
    m = re.search(r"entries\s*=\s*[@(]?\(([^)]*)\)", text)
    assert m, "could not find the local-only `entries` array in installer"
    return set(_TIER.findall(m.group(1)))


class LocalOnlyTierParityTest(unittest.TestCase):
    def test_all_installers_match_the_canonical_tier_set(self) -> None:
        canonical = _canonical_tiers()
        self.assertTrue(canonical, "canonical tier list is empty")
        for rel in INSTALLERS:
            text = (ROOT / rel).read_text(encoding="utf-8")
            with self.subTest(installer=rel):
                found = _installer_tier_array(text)
                self.assertEqual(
                    canonical, found,
                    f"{rel} local-only tier set {sorted(found)} != canonical "
                    f"{sorted(canonical)} (owner: shared/local-only-tiers.txt)",
                )

    def test_install_md_prose_lists_the_full_tier_set(self) -> None:
        """INSTALL.md restates the tier list in human-facing prose (3 bullets).
        Those prose copies are the same list under the same owner — gate them too
        so they cannot understate actual install behavior (they said 3 tiers,
        omitting /.scratch/, until 2026-07-07). Each `ensure ... .gitignore` line
        must name every canonical tier."""
        canonical = _canonical_tiers()
        install_md = (ROOT / "INSTALL.md").read_text(encoding="utf-8")
        prose_lines = [
            ln for ln in install_md.splitlines()
            if "are present in the target repo `.gitignore`" in ln
        ]
        self.assertTrue(prose_lines, "no INSTALL.md tier-prose lines found")
        for ln in prose_lines:
            named = set(_TIER.findall(ln))
            with self.subTest(line=ln[:60]):
                self.assertTrue(
                    canonical <= named,
                    f"INSTALL.md tier prose {sorted(named)} is missing "
                    f"{sorted(canonical - named)} (owner: shared/local-only-tiers.txt)",
                )


if __name__ == "__main__":
    unittest.main()
