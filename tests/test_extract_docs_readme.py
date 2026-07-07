"""docs/README.md is GENERATED (not frozen) for a standalone branch.

Gap 3 of work-items/bugs/2026-07-07-installer-gaps-...: the extractor carried the
branch's frozen docs/README.md, whose "Current docs in this branch:" list drifted
behind the monorepo (named 2 docs while the branch shipped 8, plus dead routing/
links). It is now regenerated from the monorepo copy with the list rebuilt from the
docs actually shipped under out/docs/. This unit-tests the pure regeneration
function directly (no git needed)."""
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "extract_provider_branch", ROOT / "scripts" / "extract-provider-branch.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
regenerate = _mod._regenerate_docs_readme

MONOREPO_README = b"""# Docs

Use it together with:

- [../README.md](../README.md) for the repository overview

Current docs in this branch:

- [agents-mode-reference.md](agents-mode-reference.md) for the schema
- [epics.md](epics.md) for grouping work-items
- [new-session-guide.md](new-session-guide.md) main-only, not shipped to branches
- [routing/12-lane-matrix.md](routing/12-lane-matrix.md) excluded subtree
- [routing/evidence.md](routing/evidence.md) - excluded subtree evidence

## Terms and Abbreviations

- `agents-mode`: overlay. See [routing/x.md](routing/x.md) for lanes.
"""


class RegenerateDocsReadmeTest(unittest.TestCase):
    def setUp(self) -> None:
        # branch ships only agents-mode-reference + epics (not new-session-guide,
        # not the routing/ subtree)
        self.out = regenerate(MONOREPO_README, {"agents-mode-reference.md", "epics.md"}).decode("utf-8")

    def test_keeps_only_shipped_top_level_bullets(self) -> None:
        self.assertIn("- [agents-mode-reference.md](agents-mode-reference.md)", self.out)
        self.assertIn("- [epics.md](epics.md)", self.out)

    def test_drops_unshipped_and_excluded_subtree_bullets(self) -> None:
        # new-session-guide is main-only (not in shipped set) -> bullet dropped
        self.assertNotIn("new-session-guide.md](new-session-guide.md)", self.out)
        # routing/ bullets (excluded subtree) -> dropped entirely
        self.assertNotIn("routing/12-lane-matrix.md](routing/", self.out)
        self.assertNotIn("[routing/evidence.md]", self.out)

    def test_delinks_excluded_targets_outside_the_list(self) -> None:
        # a routing/ link in the Terms prose is delinked (text kept, target dropped)
        self.assertNotIn("](routing/x.md)", self.out)
        self.assertIn("See routing/x.md for lanes.", self.out)

    def test_preserves_non_list_structure(self) -> None:
        self.assertIn("# Docs", self.out)
        self.assertIn("## Terms and Abbreviations", self.out)
        self.assertIn("Current docs in this branch:", self.out)


if __name__ == "__main__":
    unittest.main()
