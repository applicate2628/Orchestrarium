"""Verify qualification coverage against the checked-out owners; no model calls."""
import hashlib
import json
from pathlib import Path
import runpy
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = "tests/fixtures/workflow-qualification-matrix-20261127.json"


def read(path):
    return json.loads((ROOT / path).read_text(encoding="utf-8-sig"))


def names(directory, pattern):
    files = (ROOT / directory).glob(pattern)
    return {p.parent.name if p.name == "SKILL.md" else p.stem: p for p in files}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class WorkflowQualificationMatrixTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix = read(FIXTURE)
        cls.rows = cls.matrix["matrix"]

    def entries(self, kind):
        selected = [row for row in self.rows if row["kind"] == kind]
        result = {row["id"]: row for row in selected}
        self.assertEqual(len(result), len(selected), kind)
        return result

    def test_source_owners_are_pinned(self):
        for rel, digest in self.matrix["source_sha256"].items():
            self.assertEqual(sha(ROOT / rel), digest, rel)

    def test_role_and_skill_coverage(self):
        policy = read("shared/role-routing-policy.v1.json")
        native = set(read("src.codex/agents/orchestrarium-role-manifest.json")["roles"])
        self.assertEqual(native, set(policy["roles"]))
        external = set(read("shared/external-role-taxonomy.v1.json")["roles"])
        claude = names("adapters/claude/agents", "*.md")
        codex_skills = names("src.codex/skills", "*/SKILL.md")
        claude_skills = names("adapters/claude/skills", "*/SKILL.md")
        expected_roles = native | set(policy["skillOnlyRoles"]) | external | set(claude)
        choices = self.entries("role-choice")
        handoffs = self.entries("role-handoff")
        self.assertEqual(set(choices), expected_roles)
        self.assertEqual(set(handoffs), expected_roles)
        for identity, file in claude.items():
            self.assertEqual(choices[identity]["claude_agent_source_sha256"], sha(file))
        procedures = self.entries("standalone-skill")
        linked = {id: row for id, row in choices.items() if row.get("combined_skill_delivery")}
        self.assertEqual(set(linked), (set(claude) - native - set(policy["skillOnlyRoles"]) - external)
                         & (set(codex_skills) | set(claude_skills)))
        self.assertEqual(set(procedures) | set(linked),
                         (set(codex_skills) | set(claude_skills)) - expected_roles | set(linked))
        for identity, row in (procedures | linked).items():
            expected = {pack: sha(files[identity]) for pack, files in
                        (("codex", codex_skills), ("claude", claude_skills)) if identity in files}
            self.assertEqual({r["pack"]: r["sha256"] for r in row["variants"]}, expected)

    def test_provider_binding_and_advice_coverage(self):
        manifest = runpy.run_path(str(ROOT / "scripts/universal_hooks_manifest.py"))
        bindings = manifest["REGISTERED_HOOK_STEMS_BY_PLATFORM"]
        metadata = {name: (event, matcher) for name, _, event, matcher in manifest["HOOK_METADATA"]}
        cases = self.entries("hook-binding")
        self.assertEqual(set(cases), {f"{provider}:{id}"
                                      for provider, ids in bindings.items() for id in ids})
        for id, case in cases.items():
            self.assertEqual(case["arms"], ["positive", "ordinary"])
            self.assertEqual((case["event"], case["matcher"]), metadata[id.split(":", 1)[1]])
        self.assertTrue(self.entries("hook-cue").keys() <= cases.keys())

    def test_production_installer_projects_exact_hook_binding(self):
        with patch.object(sys, "path", [str(ROOT), *sys.path]):
            installer = runpy.run_path(str(ROOT / "scripts/production_installer.py"))
        binding_rows = self.entries("hook-binding")
        project = ROOT / "unused-hook-matrix-test-project"
        for provider in ("codex", "claude"):
            actual = {
                f"{provider}:{marker}": (event, matcher)
                for marker, _, event, matcher in installer["_hook_specs"](provider, project)
            }
            expected = {
                id: (row["event"], row["matcher"])
                for id, row in binding_rows.items() if id.startswith(provider + ":")
            }
            self.assertEqual(actual, expected, provider)

    def test_bugfix_pair_distinguishes_start_events_from_receipts(self):
        cases = self.entries("workflow")
        pair = [cases[f"bugfix-{kind}"] for kind in ("one-start", "two-starts")]
        inputs = [case["input"] for case in pair]
        for key in ("task", "scope"):
            self.assertEqual(inputs[0][key], inputs[1][key])
        self.assertEqual(inputs[0]["independent_start_export"]["coverage"],
                         inputs[1]["independent_start_export"]["coverage"])
        for count, (case, stimulus) in enumerate(zip(pair, inputs), start=1):
            self.assertEqual(case["arms"], ["baseline", "workflow"])
            start_ids = stimulus["independent_start_export"]["start_ids"]
            receipts = stimulus["completion_receipts"]
            self.assertEqual(len(start_ids), count)
            self.assertEqual(len({r["receipt_id"] for r in receipts}), 2)
            self.assertEqual({r["worker_start_id"] for r in receipts}, set(start_ids))
            self.assertNotIn("criteria", stimulus)

    def test_each_logical_execution_has_an_exact_unique_id(self):
        actual = {lane: 0 for lane in self.matrix["logical_runs"]}
        ids = set()
        for row in self.rows:
            self.assertEqual(set(row["arms"]), set(row["run_ids"]))
            self.assertEqual(len(row["arms"]), len(row["run_ids"]))
            for arm in row["arms"]:
                run_id = row["run_ids"][arm]
                self.assertEqual(run_id, ":".join((row["lane"], row["kind"], row["id"], arm)))
                self.assertNotIn(run_id, ids)
                ids.add(run_id)
                actual[row["lane"]] += 1
        self.assertEqual(actual, self.matrix["logical_runs"])


if __name__ == "__main__":
    unittest.main()
