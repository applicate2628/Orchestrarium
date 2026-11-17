"""Offline task-scoped Astra admission; no model calls."""
import json
import unittest
from scripts.model_routing.launch_policy import qualify_launch
from scripts import provider_prompt

class ScopedAstraTests(unittest.TestCase):
    def grant(self, task="critical-design"):
        return {"taskClass": task, "scope": "accepted architecture task",
                "approvalReference": "user-approved-task"}

    def qualify(self, grant, task="critical-design", effort="high", model="gpt-6.2-astra"):
        return qualify_launch("codex", model, effort, task_class=task,
                              astra_task_authorization=grant)

    def test_accepted_task_classes_and_retries(self):
        for task in ("critical-design", "critical-security", "review"):
            grant = self.grant(task)
            for effort in ("high", "xhigh"):
                for _ in range(2):
                    self.assertIsNone(self.qualify(grant, task, effort))
            self.assertEqual(grant, self.grant(task))

    def test_scope_must_be_complete_and_match_selected_class(self):
        for grant in (None, True, {}, [], self.grant("engineering"),
                      dict(self.grant(), scope=" "),
                      dict(self.grant(), approvalReference=""),
                      dict(self.grant(), approvalReference=True)):
            self.assertEqual(self.qualify(grant), "individual-launch-approval-required")
        self.assertIsNotNone(self.qualify(self.grant("engineering"), "engineering"))

    def test_scope_does_not_admit_max_or_legacy_astra(self):
        for effort in ("medium", "max"):
            self.assertIsNotNone(self.qualify(self.grant(), effort=effort))
        self.assertIsNotNone(self.qualify(self.grant(), model="gpt-6-astra"))
        self.assertIsNone(qualify_launch("codex", "gpt-6.2-astra", "max",
                                        user_approved_max=True))

    def test_actual_managed_guard_uses_scoped_grant(self):
        control = provider_prompt.Control()
        control.task_class = "review"
        control.astra_task_authorization = self.grant("review")
        selected = provider_prompt.PolicyBoundLaunch(
            control, "audit", (), "gpt-6.2-astra", "high",
            provider_prompt.ExternalRoleProvenance("architecture-reviewer", "external-reviewer"), None)
        provider_prompt._qualify_managed_model_launch("codex", selected)
        control.task_class = "engineering"
        with self.assertRaisesRegex(ValueError, "individual-launch-approval-required"):
            provider_prompt._qualify_managed_model_launch("codex", selected)

    def test_native_resolver_carries_scope_and_preserves_max_gate(self):
        import importlib.util
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location("astra_scope_resolver",
                                                     root / "scripts/resolve-agents-mode.py")
        resolver = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = resolver
        spec.loader.exec_module(resolver)
        description = resolver.describe_ordinary_native_role_options(
            "qa-engineer", "review",
            {"explicitModelControl": True, "explicitReasoningEffortControl": True},
            repo_root=root)
        self.assertEqual(description["status"], "available", description)
        grant = self.grant("review")
        args = dict(requested_model="gpt-6.2-astra", requested_effort="high",
                    caller_rationale="substantive audit", approved_execution_scope={"read": True},
                    astra_task_authorization=grant)
        decision = resolver.resolve_ordinary_native_dispatch(description, **args)
        self.assertEqual(decision["status"], "resolved", decision)
        self.assertEqual(decision["astraTaskAuthorization"], grant)
        args["requested_effort"] = "max"
        self.assertEqual(resolver.resolve_ordinary_native_dispatch(description, **args)["status"], "denied")

    def test_wrapper_parses_scope_not_provider_flag(self):
        grant = self.grant("review")
        control = provider_prompt.parse_control(
            ["--astra-task-authorization-json", json.dumps(grant),
             "--task-class", "review", "--role", "architecture-reviewer", "audit"],
            provider="codex")
        self.assertEqual(control.astra_task_authorization, grant)
        self.assertFalse(control.user_approved_launch)
        self.assertNotIn("--astra-task-authorization-json", control.provider_flags)
        with self.assertRaises(ValueError):
            provider_prompt.parse_control(
                ["--astra-task-authorization-json", "true", "audit"], provider="codex")

if __name__ == "__main__":
    unittest.main()
