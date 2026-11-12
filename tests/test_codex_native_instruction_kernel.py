"""Source-contract regressions, not evidence of native loading or compliance."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = "src.codex/AGENTS.codex.md"
OWNER = "src.codex/skills/lead/operating-model.md"

def read(relative):
    return (ROOT / relative).read_text(encoding="utf-8")

def section(text, heading):
    start = text.index("## " + heading + "\n")
    end = text.find("\n## ", start + 3)
    return text[start:end if end >= 0 else None]

class CodexNativeInstructionKernelTests(unittest.TestCase):
    def require(self, text, *phrases):
        for phrase in phrases:
            self.assertIn(phrase, text)

    def test_action_triggers_cover_all_callers(self):
        self.require(section(read(KERNEL), "Native dispatch kernel"),
            "Before selecting or resolving an ordinary native or skill-only Codex role",
            "or a named mechanical route", "submitting its native attempt", "receiving or interpreting its outcome",
            "every already-authorized caller (Root/Lead, direct, nested, or non-Lead) MUST read",
            "Before changing or diagnosing native role installation, registration, policy/manifest migration or configured controls, read both procedures",
            "not an eager import, activation of Lead, or permission to delegate", "not Claude Agent dispatch or external adapters")

    def test_current_owner_and_compaction_fail_closed(self):
        self.require(section(read(KERNEL), "Native dispatch kernel"),
            "src.codex/skills/lead/operating-model.md",
            "<project>/.agents/skills/lead/operating-model.md", "$HOME/.agents/skills/lead/operating-model.md",
            "within the already selected Source/project/global layout", "Use global only when existing layout selection chooses global",
            "Do not search current/parent directories or substitute a global owner for a missing selected project owner",
            "missing, stale, conflicting or uncertain",
            "hold only the dependent operation",
            "After handoff, interruption, compaction or resume, restore missing applicable obligations",
            "before the next dependent decision or action",
            "do not reread unchanged content already actually present", "including receiving an outstanding result")

    def test_kernel_keeps_consent_and_nonauthority(self):
        self.require(section(read(KERNEL), "Native dispatch kernel"),
            "every Astra attempt at any effort and every model Max",
            "genuine individual user agreement",
            "task, role, scope, provider route, model, effort and one attempt",
            "Low is excluded on every model",
            "copied approval flag or prior attempt never creates consent",
            "Current user configuration and parent permissions remain binding",
            "Missing inputs, rejection or drift confer no retry, fallback, alternative-route or permission-reset authority",
            "A genuinely authorized later action still requires resolved owner inputs")

    def test_kernel_keeps_tool_isolation_and_route_boundaries(self):
        self.require(section(read(KERNEL), "Native dispatch kernel"),
            "describe_ordinary_native_role_options", "resolve_ordinary_native_dispatch",
            "RoleDispatchPolicyV1", "Selectors launch nothing",
            "do not authorize a launch or fallback",
            "no generic shell/code execution", "no external realization",
            "Before every native subagent spawn",
            "exact task-scoped MCP/tool identifiers, or `none`",
            "The subagent must not use an unlisted tool even when the host inherits it", "prompts and hooks are not a sandbox",
            "independent risk, review, human publication and leak gates")

    def test_procedure_has_one_owner_without_circular_routing(self):
        kernel, owner = read(KERNEL), read(OWNER)
        for heading in ("Native Astra task-dependent route", "Native Luna mechanical corridor"):
            self.assertNotIn("## " + heading + "\n", kernel)
            self.assertEqual(owner.count("## " + heading + "\n"), 1)
        self.assertNotIn("in the installed `AGENTS.md`; follow that section", owner)
        self.require(owner, "procedure below", "These Codex-specific procedures",
                     "every already-authorized caller, including direct and nested callers")

    def test_ordinary_procedure_preserves_configured_controls(self):
        self.require(section(read(OWNER), "Native Astra task-dependent route"),
            "ordinary native and skill-only roles",
            "describe_ordinary_native_role_options", "resolve_ordinary_native_dispatch",
            "fork_turns=\"none\"", "no `agent_type`",
            "partial controls remain unresolved", "preserves noncontrol bytes",
            "without reserializing TOML", "configuration conflict",
            "capability-unknown", "unspecified by runtime",
            "user_approved_launch=False", "one combined agreement",
            "rechecks the resolved tuple at host submission")

    def test_mechanical_procedure_preserves_exact_contracts(self):
        self.require(section(read(OWNER), "Native Luna mechanical corridor"),
            "no decision authority", "luna-high", "E_NATIVE_V2_DISABLED",
            "E_ROLE_POLICY_INVALID", "fallback:\"none\"",
            "E_LUNA_UNAVAILABLE", "LunaExecutionContractV1", "ScoutFactsV1",
            "facts-only", "one exact patch to one existing file",
            "pre- and post-operation hashes", "including any carrier",
            "Generic code or shell execution remains forbidden",
            "share installer rollback", "no in-repository host caller",
            "human publication review plus the existing leak gate")

    def test_bootstrap_guards_and_recovery_remain_in_kernel(self):
        text = read(KERNEL)
        self.require(text, "Universal premise rule first",
            "**(a0) Pre-action orientation trigger**", "**(a) Pre-fix trigger**",
            "**(b) Pre-commit trigger**", "steps 1-3 must complete before the first edit lands",
            "explicit user authority", "fresh dirty/index census",
            "preservation of every unrelated working-tree byte and staged change",
            "no other work depends on them",
            "Epics: when several work-items serve one initiative, group them as an epic",
            "duplicates fail closed")

    def test_routing_order_and_mandatory_risks_remain(self):
        text = section(read(KERNEL), "Template routing")
        ordered = ("1. User explicitly names a role", "2. Roadmap",
                   "3. Standalone bounded fact", "4. Non-trivial factual",
                   "5. Decision", "6. PR review", "7. Task satisfies",
                   "8. Auth", "9. Hard performance", "10. Spatial",
                   "11. Multiple risk", "12. Otherwise")
        positions = [text.index(value) for value in ordered]
        self.assertEqual(positions, sorted(positions))
        self.require(text, "`$security-engineer` and `$security-reviewer` mandatory",
            "`$performance-engineer` and `$performance-reviewer` mandatory",
            "`$computational-scientist` and `$architecture-reviewer` mandatory")

    def test_callers_point_to_existing_procedure(self):
        self.require(read("src.codex/skills/lead/SKILL.md"),
                     "in the sibling `operating-model.md` under the installed AGENTS native-dispatch kernel")
        self.require(read("references-codex/subagent-operating-model.md"),
                     "../src.codex/skills/lead/operating-model.md#native-astra-task-dependent-route")
        self.require(read("shared/references/subagent-operating-model.md"),
                     "shared universal engineering rules remain in the shared spine")
        self.assertNotIn("Native Astra task-dependent route` from the installed `AGENTS.md`",
                         read("src.codex/skills/lead/SKILL.md"))

class KernelDutyMutationTests(unittest.TestCase):
    def test_kernel_boundary_phrase_deletions_are_detectable(self):
        text = section(read(KERNEL), "Native dispatch kernel")
        duties = (
            "selecting or resolving", "submitting its native attempt",
            "receiving or interpreting its outcome", "changing or diagnosing",
            "every already-authorized caller (Root/Lead, direct, nested, or non-Lead)",
            "Use global only when existing layout selection chooses global",
            "not an eager import, activation of Lead, or permission to delegate",
            "not Claude Agent dispatch or external adapters",
            "must not use an unlisted tool even when the host inherits it",
            "Supply applicable execution restrictions in the trusted child handoff",
            "including receiving an outstanding result",
            "do not reread unchanged content already actually present",
        )
        for duty in duties:
            with self.subTest(duty=duty):
                self.assertEqual(text.count(duty), 1)
                changed = text.replace(duty, "UNSATISFIED DUTY", 1)
                self.assertFalse(all(value in changed for value in duties))

    def test_all_native_tool_rule_has_one_universal_owner(self):
        kernel, owner = read(KERNEL), read(OWNER)
        marker = "Before every native subagent spawn, the caller discovers"
        self.assertEqual(kernel.count(marker), 1)
        self.assertNotIn(marker, owner)
        self.assertIn("Apply the universal **Native dispatch kernel** rule", owner)
        self.assertIn("exact `Allowed tools`, inherited-tool restrictions", owner)

    def test_missing_actual_runtime_identity_stays_unverified(self):
        self.assertIn("Record requested/resolved controls separately from actual runtime metadata; missing actual metadata is `unspecified by runtime`", read(KERNEL))


class NativeProcedureMaterializationTests(unittest.TestCase):
    def test_existing_lead_stage_carries_current_procedure_and_source_manifest(self):
        """Real existing staging owner; not a public install or native execution."""
        import hashlib
        import importlib.util
        import shutil
        import sys
        import tempfile
        from unittest.mock import patch

        module_name = "native_kernel_materialization_installer"
        spec = importlib.util.spec_from_file_location(module_name, ROOT / "scripts/production_installer.py")
        module = importlib.util.module_from_spec(spec)
        prior_path = list(sys.path)
        sys.path.insert(0, str(ROOT / "scripts"))
        sys.modules[module_name] = module
        try:
            with patch("subprocess.Popen", side_effect=AssertionError("no external process in staging test")), patch("socket.socket", side_effect=AssertionError("no network in staging test")):
                spec.loader.exec_module(module)
                with tempfile.TemporaryDirectory(prefix="native-kernel-stage-fixture-") as fixture:
                    helper = Path(fixture) / ".agents/skills/lead/scripts"
                    with patch.object(module.tempfile, "tempdir", fixture):
                        stage = module._stage_canonical_lead_tree(ROOT, ROOT / "src.codex/skills/lead", helper)
                    try:
                        expected = (ROOT / OWNER).read_bytes()
                        actual = (stage.path / "operating-model.md").read_bytes()
                        self.assertEqual(actual, expected)
                        self.assertIn(("operating-model.md", hashlib.sha256(expected).hexdigest()), stage.manifest)
                        self.assertIn(b"## Native dispatch procedures", actual)
                        self.assertIn(b"## Native Astra task-dependent route", actual)
                        self.assertIn(b"## Native Luna mechanical corridor", actual)
                        self.assertFalse(helper.exists())
                    finally:
                        shutil.rmtree(stage.path)
        finally:
            sys.path[:] = prior_path
            sys.modules.pop(module_name, None)

if __name__ == "__main__":
    unittest.main()
