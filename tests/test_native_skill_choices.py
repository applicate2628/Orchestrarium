import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = [sys.executable, "-B", str(ROOT / "scripts/resolve-agents-mode.py"), "--provider", "codex", "--json"]
ENTRIES = [
    {"id": "pack:review", "name": "review", "description": "General review of diffs", "source": "pack", "group": "architecture", "available": True},
    {"id": "plugin:review", "name": "review", "description": "Architecture review of API boundaries", "source": "plugin", "group": "architecture", "available": True},
    {"id": "off:review", "name": "API architecture review", "description": "API architecture review", "source": "plugin", "group": "architecture", "available": False},
]
RESOLVE = ["--ordinary-native-action", "resolve", "--task-class", "exploration", "--role", "analyst",
           "--host-controls", "explicit", "--caller-rationale", "Inspect only.", "--approved-scope-json", '{"read":true}']


def run(*args, catalog=ENTRIES):
    return json.loads(subprocess.check_output([*CLI, *args], input=json.dumps(catalog).encode(), cwd=ROOT))


class SkillChoicesTests(unittest.TestCase):
    def test_external_can_rank_first_and_duplicates_are_distinct(self):
        result = run("--skill-query", "architecture API review", "--skill-group", "architecture")
        self.assertEqual(result["status"], "available")
        self.assertEqual([row["id"] for row in result["skills"]], ["plugin:review", "pack:review"])
        self.assertEqual({row["source"] for row in result["skills"]}, {"pack", "plugin"})
        self.assertNotIn("invocation", result)

    def test_unknown_and_unavailable_catalog_are_distinct(self):
        self.assertEqual(run("--skill-query", "nonexistent")["skills"], [])
        self.assertEqual(run("--skill-query", "review", catalog=None)["status"], "unavailable")

    def test_selection_changes_only_that_invocation(self):
        base = run(*RESOLVE)
        self.assertNotIn("taskSkill", base["invocation"])
        ranked = run("--skill-query", "architecture API review")["skills"]
        self.assertEqual(ranked[0]["id"], "plugin:review")
        selected = run(*RESOLVE, "--worker-skill-id", "pack:review")
        self.assertEqual(selected["invocation"].pop("taskSkill"),
                         {"id": "pack:review", "source": "pack", "name": "review"})
        self.assertEqual(selected, base)
        self.assertEqual(run(*RESOLVE), base)

    def test_missing_receiver_skill_does_not_fall_back_by_name(self):
        base = run(*RESOLVE)
        result = run(*RESOLVE, "--worker-skill-id", "plugin:review", catalog=ENTRIES[:1])
        self.assertEqual(result.pop("taskSkillStatus"), "unavailable")
        self.assertEqual(result, base)

    def test_conflicting_identity_is_not_suggested_or_attached(self):
        entries = [*ENTRIES, {**ENTRIES[1], "source": "other"}]
        result = run("--skill-query", "review", catalog=entries)
        self.assertEqual([row["id"] for row in result["skills"]], ["pack:review"])
        decision = run(*RESOLVE, "--worker-skill-id", "plugin:review", catalog=entries)
        self.assertEqual(decision["taskSkillStatus"], "unavailable")
        self.assertNotIn("taskSkill", decision["invocation"])

    def test_group_only_search_does_not_expand_worker_prompt(self):
        rows = run("--skill-group", "ARCHITECTURE")["skills"]
        self.assertEqual(len(rows), 2)
        self.assertEqual(run("--skill-group", "unrelated")["skills"], [])
        self.assertEqual(run(*RESOLVE)["invocation"]["promptPreamble"],
                         run(*RESOLVE, "--worker-skill-id", "plugin:review")["invocation"]["promptPreamble"])

    def test_disabled_exact_receiver_entry_never_selects_same_name(self):
        lead = run("--skill-query", "architecture API review")["skills"]
        selected = lead[0]
        self.assertEqual(selected["id"], "plugin:review")
        receiving = [{**row, "available": False} if row["id"] == selected["id"] else row
                     for row in ENTRIES]
        decision = run(*RESOLVE, "--worker-skill-id", selected["id"], catalog=receiving)
        self.assertEqual(decision.pop("taskSkillStatus"), "unavailable")
        self.assertEqual(decision, run(*RESOLVE))

    def test_denied_invocation_is_unchanged(self):
        opts = (*RESOLVE, "--host-controls", "unavailable")
        self.assertEqual(run(*opts, "--worker-skill-id", "plugin:review"), run(*opts))


    def test_live_pack_descriptions_surface_the_owner_for_natural_tasks(self):
        catalog = []
        for path in sorted((ROOT / "src.codex" / "skills").glob("*/SKILL.md")):
            for line in path.read_text(encoding="utf-8-sig").splitlines()[:8]:
                if line.startswith("description: "):
                    catalog.append({
                        "id": f"pack:{path.parent.name}", "name": path.parent.name,
                        "description": line.removeprefix("description: ").strip('"'),
                        "source": "pack", "available": True,
                    })
                    break
        self.assertGreater(len(catalog), 30)
        for skill, query in [
            ("review-changes", "Review this change: the serializer now writes null for "
             "missing measurements, and its tests pass. An unchanged report view "
             "still coerces its measurement input to a number. What should you "
             "check before accepting the change?"),
            ("review-changes", "Audit a commit range and trace unchanged downstream "
             "callers whose parser still assumes the old output contract."),
            ("repo-cleanup", "Clean redundant worktree artifacts and list which "
             "files can be removed."),
            ("repo-cleanup", "Prepare this repository for transfer; classify stale "
             "local worktrees and their artifacts without deleting files."),
        ]:
            with self.subTest(skill=skill, query=query):
                hits = run("--skill-query", query, catalog=catalog)["skills"]
                self.assertEqual(hits[0]["id"], f"pack:{skill}")


if __name__ == "__main__":
    unittest.main()
