"""docs/README.md is GENERATED (not frozen) for a standalone branch.

Gap 3 of work-items/bugs/2026-07-07-installer-gaps-...: the extractor carried the
branch's frozen docs/README.md, whose "Current docs in this branch:" list drifted
behind the monorepo (named 2 docs while the branch shipped 8, plus dead routing/
links). It is now regenerated from the monorepo copy: the list is rebuilt from the
docs actually shipped under out/docs/, AND every markdown link is delinked if its
target does not resolve in the standalone tree (a sibling provider's src.<p>/ or
references-<p>/, or an excluded subtree) — the cross-provider dead-link class the
acceptance commission (Sonnet) caught. Tests the pure function against a real
temp out-tree (no git needed)."""
import shutil
import unittest
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "extract_provider_branch", ROOT / "scripts" / "extract-provider-branch.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
regenerate = _mod._regenerate_docs_readme

MONOREPO_README = b"""# Docs

This directory is the branch-level docs surface for the Orchestrarium monorepo common layer.

Use it together with:

- [../README.md](../README.md) for the repository overview
- [../src.claude/README.md](../src.claude/README.md) for the Claude source subtree
- [../src.codex/README.md](../src.codex/README.md) for the Codex source subtree
- [../references-qwen/README.md](../references-qwen/README.md) for Qwen refs

Current docs in this branch:

- [agents-mode-reference.md](agents-mode-reference.md) for the schema
- [epics.md](epics.md) for grouping work-items
- [new-session-guide.md](new-session-guide.md) main-only, not shipped to branches
- [routing/12-lane-matrix.md](routing/12-lane-matrix.md) excluded subtree

## Terms and Abbreviations

- `agents-mode`: overlay. See [routing/x.md](routing/x.md) for lanes.
"""


class RegenerateDocsReadmeTest(unittest.TestCase):
    def setUp(self) -> None:
        # a standalone CLAUDE branch tree: ships README + docs/{shipped} +
        # src.claude/ + references-claude/, but NOT src.codex/ or references-qwen/
        self.out = ROOT / ".scratch" / "test-regenerate-readme-out"
        if self.out.exists():
            shutil.rmtree(self.out)
        (self.out / "docs").mkdir(parents=True)
        (self.out / "README.md").write_text("root\n")
        (self.out / "src.claude").mkdir()
        (self.out / "src.claude" / "README.md").write_text("claude\n")
        (self.out / "references-claude").mkdir()
        (self.out / "references-claude" / "README.md").write_text("refs\n")
        for name in ("agents-mode-reference.md", "epics.md"):
            (self.out / "docs" / name).write_text("doc\n")
        self.text = regenerate(MONOREPO_README, self.out, "claude").decode("utf-8")

    def tearDown(self) -> None:
        if self.out.exists():
            shutil.rmtree(self.out)

    def test_keeps_only_shipped_top_level_bullets(self) -> None:
        self.assertIn("- [agents-mode-reference.md](agents-mode-reference.md)", self.text)
        self.assertIn("- [epics.md](epics.md)", self.text)

    def test_drops_unshipped_and_excluded_subtree_bullets(self) -> None:
        self.assertNotIn("new-session-guide.md](new-session-guide.md)", self.text)
        self.assertNotIn("[routing/12-lane-matrix.md]", self.text)

    def test_live_cross_provider_link_is_kept(self) -> None:
        # src.claude/ ships on the claude branch -> link stays a real link
        self.assertIn("[../src.claude/README.md](../src.claude/README.md)", self.text)

    def test_dead_cross_provider_links_are_delinked(self) -> None:
        # src.codex/ + references-qwen/ do NOT ship on the claude branch -> the
        # link target is dropped (descriptive text kept), no dead link
        self.assertNotIn("](../src.codex/README.md)", self.text)
        self.assertNotIn("](../references-qwen/README.md)", self.text)
        self.assertIn("../src.codex/README.md for the Codex source subtree", self.text)

    def test_delinks_excluded_targets_in_prose(self) -> None:
        # a routing/ link in the Terms prose is delinked (text kept)
        self.assertNotIn("](routing/x.md)", self.text)
        self.assertIn("See routing/x.md for lanes.", self.text)

    def test_rewrites_intro_to_standalone_pack(self) -> None:
        self.assertIn("standalone Claude pack", self.text)
        self.assertNotIn("Orchestrarium monorepo common layer", self.text)

    def test_preserves_non_list_structure(self) -> None:
        self.assertIn("# Docs", self.text)
        self.assertIn("## Terms and Abbreviations", self.text)
        self.assertIn("Current docs in this branch:", self.text)


if __name__ == "__main__":
    unittest.main()
