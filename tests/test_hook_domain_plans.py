"""Bounded domain-seam checks; imports only hook helper/health and stdlib."""

from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]


def load_owner(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


H = load_owner("domain_plan_hooks", "install-hypothesis-hook.py")
I = load_owner("domain_plan_health", "check-hook-health.py")


class DomainPlanTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".scratch").mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(
            prefix="hook-domain-plan-", dir=ROOT / ".scratch"
        )
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.target = self.root / "hooks.json"
        self.inventory = self.root / I.INVENTORY_NAME
        self.marker = "check-bugfix-discipline"
        self.script = self.root / (self.marker + ".py")
        self.script.write_text("pass\n", encoding="utf-8")
        self.entry = H.build_codex_entry(
            H.HookTarget(sys.executable, (str(self.script),)), "posix"
        )
        self.specs = [(self.marker, self.script, "PreToolUse", self.entry["matcher"])]

    def seed(self):
        data = {"custom": "保持", "hooks": {"PreToolUse": [self.entry]}}
        H.write_atomic(self.target, data)
        return data

    def plan(self, specs=None, inventory=None):
        return I.plan_codex_inventory(
            target=self.target, specs=self.specs if specs is None else specs,
            inventory_path=self.inventory if inventory is None else inventory,
            host_os="posix",
        )

    def test_encoder_preserves_native_newlines_unicode_and_standalone_bytes(self):
        data = {"custom": "保持", "number": 0, "hooks": {}}
        before = copy.deepcopy(data)
        encoded = H.encode_hook_config(data)
        expected = (json.dumps(data, indent=2, ensure_ascii=False) + "\n").replace(
            "\n", os.linesep
        ).encode("utf-8")
        self.assertEqual(expected, encoded)
        self.assertEqual(before, data)
        H.write_atomic(self.target, data)
        self.assertEqual(encoded, self.target.read_bytes())

    def test_install_remove_reuse_preserves_custom_metadata_and_codex_slots(self):
        old = copy.deepcopy(self.entry)
        old["groupCustom"] = True
        old["hooks"][0]["timeout"] = 7
        self.entry["hooks"][0]["statusMessage"] = "Active check"
        foreign = {"type": "command", "command": "echo custom"}
        old["hooks"].append(foreign)
        data = {"hooks": {"PreToolUse": [old]}, "other": 0}
        self.assertTrue(H.install(data, self.entry, "PreToolUse", self.marker,
                                  platform="codex", host_os="posix"))
        self.assertEqual(foreign, data["hooks"]["PreToolUse"][0]["hooks"][1])
        self.assertEqual(7, data["hooks"]["PreToolUse"][0]["hooks"][0]["timeout"])
        self.assertFalse(H.install(data, self.entry, "PreToolUse", self.marker,
                                   platform="codex", host_os="posix"))
        self.assertTrue(H.remove(data, "PreToolUse", self.marker,
                                 platform="codex", host_os="posix",
                                 managed_targets={self.marker: {str(self.script)}}))
        self.assertEqual([foreign], data["hooks"]["PreToolUse"][0]["hooks"])
        exact = {"hooks": {"PreToolUse": [copy.deepcopy(self.entry)]}}
        self.assertTrue(H.remove(exact, "PreToolUse", self.marker,
                                 expected_entry=self.entry, platform="codex"))
        self.assertEqual([], exact["hooks"]["PreToolUse"][0]["hooks"])

    def test_unchanged_install_noop_and_missing_removal(self):
        data = self.seed()
        self.assertFalse(H.install(data, self.entry, "PreToolUse", self.marker,
                                   platform="codex"))
        self.assertFalse(H.remove({}, "PreToolUse", self.marker, platform="codex"))

    def test_registration_partial_shape_still_rejects(self):
        for data in ({"hooks": 0}, {"hooks": {"PreToolUse": 0}}):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as failure:
                H.install(data, self.entry, "PreToolUse", self.marker)
            self.assertEqual(1, failure.exception.code)

    def test_cli_bad_json_empty_remove_and_dry_run_keep_existing_exits(self):
        self.target.write_bytes(b"{")
        argv = ["helper", "--target", str(self.target), "--platform", "claude", "--remove", "--script-path", str(self.script)]
        with patch.object(sys, "argv", argv), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as failure:
                H.main()
        self.assertEqual(1, failure.exception.code)
        claude = H.build_claude_entry(H.HookTarget(sys.executable, (str(self.script),)))
        H.write_atomic(self.target, {"hooks": {"PreToolUse": [claude]}})
        original = self.target.read_bytes()
        with patch.object(sys, "argv", argv + ["--dry-run"]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, H.main())
        self.assertEqual(original, self.target.read_bytes())
        with patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, H.main())
        self.assertFalse(self.target.exists())

    def test_inventory_plan_is_readonly_and_standalone_wire_is_identical(self):
        self.seed()
        original = self.target.read_bytes()
        before_identity = I._path_identity(self.target)
        before = sorted(p.name for p in self.root.iterdir())
        plan = self.plan()
        self.assertEqual(before, sorted(p.name for p in self.root.iterdir()))
        self.assertEqual(original, self.target.read_bytes())
        self.assertEqual(before_identity, plan.authority.target_identity)
        self.assertEqual(self.inventory, plan.authority.inventory)
        self.assertIsNone(plan.authority.inventory_identity)
        payload = json.loads(plan.content)
        self.assertEqual({"schemaVersion", "sourcePath", "hooks"}, set(payload))
        self.assertEqual({"identity", "stem"}, set(payload["hooks"][0]))
        self.assertEqual(1, payload["schemaVersion"])
        self.assertNotIn(b"\r", plan.content)
        self.assertTrue(plan.content.endswith(b"\n"))
        I.write_codex_inventory(target=self.target, specs=iter(self.specs),
                                inventory_path=self.inventory, host_os="posix")
        self.assertEqual(plan.content, self.inventory.read_bytes())
        stems, identities = I._load_codex_inventory(
            self.inventory, target=self.target, host_os="posix"
        )
        self.assertEqual({self.marker}, stems)
        self.assertEqual({payload["hooks"][0]["identity"]}, identities)

    def test_plan_stems_are_sorted_with_actual_source_identity(self):
        data = self.seed()
        other = "check-git-push-gate"
        script = self.root / (other + ".py")
        entry = H.build_codex_entry(H.HookTarget(sys.executable, (str(script),)), "posix", "Stop")
        data["hooks"]["Stop"] = [entry]
        H.write_atomic(self.target, data)
        plan = self.plan(self.specs + [(other, script, "Stop", None)])
        payload = json.loads(plan.content)
        self.assertEqual(sorted([self.marker, other]), [row["stem"] for row in payload["hooks"]])
        self.assertEqual(I._source_identity(self.target, "posix"), payload["sourcePath"])

    def test_missing_target_and_alternate_inventory_refuse_without_effects(self):
        with self.assertRaises(I._HookHealthFailure) as failure:
            self.plan()
        self.assertEqual("E_HOOK_INVENTORY_TARGET_INVALID", failure.exception.stable_id)
        self.assertFalse(self.inventory.exists())
        self.seed()
        with self.assertRaises(I._HookHealthFailure):
            self.plan(inventory=self.root / "alternate.json")
        self.assertFalse((self.root / "alternate.json").exists())

    def test_duplicate_missing_and_shape_mismatch_specs_refuse_readonly(self):
        self.seed()
        absent = ("check-absent", self.root / "check-absent.py", "Stop", None)
        mismatch = (self.marker, self.script, "Stop", None)
        for specs in (self.specs * 2, [absent], [mismatch]):
            with self.subTest(specs=specs), self.assertRaises(I._HookHealthFailure):
                self.plan(specs)
            self.assertFalse(self.inventory.exists())

    def test_zero_specs_keeps_existing_empty_schema_behavior(self):
        self.seed()
        self.assertEqual([], json.loads(self.plan([]).content)["hooks"])

    def test_windows_command_shape_uses_existing_classifier_and_identity(self):
        entry = H.build_codex_entry(
            H.HookTarget(sys.executable, (str(self.script),)), "windows", "Stop"
        )
        H.write_atomic(self.target, {"hooks": {"Stop": [entry]}})
        plan = I.plan_codex_inventory(
            target=self.target, specs=[(self.marker, self.script, "Stop", None)],
            inventory_path=self.inventory, host_os="windows",
        )
        payload = json.loads(plan.content)
        identity = json.loads(payload["hooks"][0]["identity"])
        self.assertEqual("stop", identity["event"])
        self.assertIsNone(identity["matcher"])
        self.assertEqual(I._source_identity(self.target, "windows"), identity["sourcePath"])
        I.write_codex_inventory(
            target=self.target, specs=[(self.marker, self.script, "Stop", None)],
            inventory_path=self.inventory, host_os="windows",
        )
        self.assertEqual(plan.content, self.inventory.read_bytes())

    def test_malformed_hook_data_refuses_without_inventory(self):
        for raw in (b"{", b"[]", b'{"hooks": 0}'):
            self.target.write_bytes(raw)
            with self.subTest(raw=raw), self.assertRaises(I._HookHealthFailure):
                self.plan()
            self.assertFalse(self.inventory.exists())

    def test_existing_inventory_authority_rejects_equal_byte_foreign_replacement(self):
        self.seed()
        self.inventory.write_bytes(b"original")
        plan = self.plan()
        replacement = self.root / "foreign.json"
        replacement.write_bytes(b"original")
        os.replace(replacement, self.inventory)
        with self.assertRaises(I._HookHealthFailure):
            I._recheck_inventory_authority(plan.authority, for_write=True)
        self.assertEqual(b"original", self.inventory.read_bytes())

    def test_hooks_authority_rejects_equal_byte_foreign_replacement(self):
        self.seed()
        plan = self.plan()
        replacement = self.root / "foreign.json"
        replacement.write_bytes(self.target.read_bytes())
        os.replace(replacement, self.target)
        with self.assertRaises(I._HookHealthFailure):
            I._recheck_inventory_authority(plan.authority, for_write=True)
        self.assertFalse(self.inventory.exists())

    def test_standalone_error_cleans_stage_and_preserves_inventory(self):
        self.seed()
        self.inventory.write_bytes(b"before")
        primary = OSError("synthetic replace failure")
        with patch.object(I.os, "replace", side_effect=primary):
            with self.assertRaises(I._HookHealthFailure) as failure:
                I.write_codex_inventory(target=self.target, specs=self.specs,
                                        inventory_path=self.inventory, host_os="posix")
        self.assertIs(primary, failure.exception.__cause__)
        self.assertEqual(b"before", self.inventory.read_bytes())
        self.assertFalse(list(self.root.glob(".codex-hook-inventory.json.*.tmp")))

    def make_link(self, target, link, directory=False):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except OSError as error:
            self.skipTest("synthetic symlink creation unavailable: " + str(error))

    def test_linked_hooks_plan_hands_off_exact_referent_authority_and_preserves_link(self):
        self.seed()
        selected = self.root / "selected.json"
        self.make_link(self.target.name, selected)
        original_link = I._path_identity(selected)
        raw = os.readlink(selected)
        plan = I.plan_codex_inventory(target=selected, specs=self.specs,
                                     inventory_path=self.inventory, host_os="posix")
        self.assertEqual(self.target, plan.authority.resolved_target)
        self.assertTrue(plan.authority.link_chain)
        I.write_codex_inventory(target=selected, specs=self.specs,
                                inventory_path=self.inventory, host_os="posix")
        self.assertEqual(plan.content, self.inventory.read_bytes())
        self.assertEqual(original_link, I._path_identity(selected))
        self.assertEqual(raw, os.readlink(selected))
        H.write_atomic(selected, {"custom": 0})
        self.assertEqual(original_link, I._path_identity(selected))
        self.assertEqual(H.encode_hook_config({"custom": 0}), self.target.read_bytes())

    def test_link_retarget_and_inventory_link_refuse(self):
        self.seed()
        selected = self.root / "selected.json"
        self.make_link(self.target.name, selected)
        plan = I.plan_codex_inventory(target=selected, specs=self.specs,
                                     inventory_path=self.inventory, host_os="posix")
        other = self.root / "other.json"
        other.write_bytes(self.target.read_bytes())
        selected.unlink()
        selected.symlink_to(other.name)
        with self.assertRaises(I._HookHealthFailure):
            I._recheck_inventory_authority(plan.authority, for_write=True)
        self.make_link(other.name, self.inventory)
        with self.assertRaises(I._HookHealthFailure):
            self.plan()

    def test_directory_link_resolves_inventory_to_ordinary_storage_sibling(self):
        storage = self.root / "storage"
        storage.mkdir()
        selected_parent = self.root / "selected-parent"
        self.make_link(storage.name, selected_parent, directory=True)
        target = selected_parent / "hooks.json"
        H.write_atomic(target, {"hooks": {"PreToolUse": [self.entry]}})
        inventory = storage / I.INVENTORY_NAME
        plan = I.plan_codex_inventory(
            target=target, specs=self.specs, inventory_path=inventory, host_os="posix"
        )
        self.assertEqual(storage / "hooks.json", plan.authority.resolved_target)
        self.assertEqual(inventory, plan.authority.inventory)
        self.assertTrue(plan.authority.link_chain)
        with self.assertRaises(I._HookHealthFailure):
            I.plan_codex_inventory(
                target=target, specs=self.specs,
                inventory_path=selected_parent / I.INVENTORY_NAME, host_os="posix"
            )
        I.write_codex_inventory(
            target=target, specs=self.specs, inventory_path=inventory, host_os="posix"
        )
        self.assertEqual(plan.content, inventory.read_bytes())

    def test_dangling_target_link_refuses_without_publication(self):
        self.make_link("absent.json", self.target)
        with self.assertRaises(I._HookHealthFailure):
            self.plan()
        self.assertTrue(self.target.is_symlink())
        self.assertFalse(self.inventory.exists())


if __name__ == "__main__":
    unittest.main()
