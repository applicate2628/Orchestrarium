#!/usr/bin/env python3
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "src.codex/skills/policy-overlay"


class PolicyOverlaySkillContractTests(unittest.TestCase):
    def test_common_skill_is_self_contained_and_provider_neutral(self) -> None:
        required = (
            "SKILL.md",
            "agents/openai.yaml",
            "policy-overlays.v1.json",
            "policies/lean-implementation.md",
            "policies/complexity-review.md",
            "scripts/policy-overlays.py",
            "scripts/policy_overlay_core.py",
            "references/ponytail-compatibility.md",
        )
        for relative in required:
            with self.subTest(relative=relative):
                self.assertTrue((SKILL / relative).is_file())
        self.assertFalse((ROOT / "src.claude/skills/policy-overlay").exists())

    def test_catalog_keeps_ponytail_external_and_builtins_non_authorizing(self) -> None:
        catalog = json.loads((SKILL / "policy-overlays.v1.json").read_text())
        ponytail = catalog["compatibilityPackages"]["ponytail"]
        self.assertEqual(ponytail["repository"], "DietrichGebert/ponytail")
        self.assertEqual(ponytail["ownership"], "external-host-managed")
        self.assertFalse(ponytail["required"])
        self.assertTrue(catalog["overlays"])
        self.assertTrue(
            all(not record["authorizing"] for record in catalog["overlays"].values())
        )

    def test_human_facing_docs_have_linked_toc_and_terms(self) -> None:
        for path in (
            SKILL / "SKILL.md",
            SKILL / "references/ponytail-compatibility.md",
            ROOT / "docs/policy-overlays.md",
        ):
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertIn("## Table of contents", text)
                self.assertRegex(text, r"\[[^\]]+\]\(#[^)]+\)")
                self.assertIn("## Terms and abbreviations", text)

    def test_docs_index_links_the_policy_overlay_guide(self) -> None:
        index = (ROOT / "docs/README.md").read_text(encoding="utf-8")
        self.assertIn("[policy-overlays.md](policy-overlays.md)", index)
        self.assertIn("policy overlay", index.casefold())

    def test_lean_and_complexity_policies_keep_safety_boundary(self) -> None:
        lean = (SKILL / "policies/lean-implementation.md").read_text()
        review = (SKILL / "policies/complexity-review.md").read_text()
        for token in ("security", "trust", "mandatory", "explicit"):
            self.assertIn(token, lean.casefold())
        for token in ("does not replace", "security", "correctness", "publication"):
            self.assertIn(token, review.casefold())


if __name__ == "__main__":
    unittest.main()
