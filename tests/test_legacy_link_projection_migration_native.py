"""Explicit legacy-link compatibility; Windows owner qualification, no models."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("legacy_link_owner_test", ROOT / "scripts" / "production_installer.py")
INSTALLER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = INSTALLER
SPEC.loader.exec_module(INSTALLER)


class LegacyLinkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="legacy-link-owner-")
        self.root = Path(self.temp.name)
        self.i = INSTALLER

    def tearDown(self):
        self.temp.cleanup()

    def fixture(self, *, linked=False, relative=False, junction=False):
        home = self.root / "home"
        canonical = home / ".agents" / "skills"
        projection = home / ".codex" / "skills"
        projection.parent.mkdir(parents=True)
        if linked:
            storage = self.root / "legacy-store"
            storage.mkdir()
            self.i._create_directory_projection(storage, projection, prefer_junction=True)
        else:
            projection.mkdir()
        legacy = projection / "lead"
        if junction:
            self.i._create_directory_projection(projection.resolve(), legacy, prefer_junction=True)
            self.assertTrue(self.i._is_directory_junction(legacy))
        else:
            os.symlink("." if relative else str(projection.resolve()), legacy, target_is_directory=True)
            self.assertTrue(legacy.is_symlink())
        current = canonical / "lead"
        current.mkdir(parents=True)
        (current / "SKILL.md").write_text("canonical lead\n", encoding="utf-8")
        (projection / "user-object.txt").write_text("preserve user\n", encoding="utf-8")
        plan = SimpleNamespace(skills=(self.i._CanonicalSkillPlan(
            "lead", current, self.i._tree_sha256(current), None, None, False),))
        return home, canonical, projection, legacy, plan

    def invoke(self, data, *, approved=True, dry_run=False):
        home, canonical, projection, legacy, plan = data
        self.i._install_codex_legacy_skill_compatibility(
            ROOT, home, home / ".codex", plan, canonical,
            frozenset({"lead"}) if approved else frozenset(), dry_run=dry_run)

    def test_preflight_binds_link_not_referent(self):
        data = self.fixture()
        home, canonical, projection, legacy, plan = data
        plans, _ = self.i._preflight_codex_legacy_skill_projections(
            plan, canonical, projection, home / ".codex" / "orchestrarium-legacy-skills", frozenset({"lead"}))
        self.assertEqual(plans[0].action, "migrate-link")
        self.assertEqual(plans[0].historical_link, self.i._InstallTransaction._capture_node(legacy))
        self.assertEqual(plans[0].historical_link.kind, "link")
        self.assertTrue(plans[0].backup_target.name.startswith("link-v1-"))

    def test_capture_replacement_cannot_admit_relative_link(self):
        data = self.fixture()
        home, canonical, projection, legacy, plan = data
        original_capture = self.i._InstallTransaction._capture_node
        changed = False
        def capture(path, **kwargs):
            nonlocal changed
            if path == legacy and not changed:
                changed = True
                legacy.unlink()
                os.symlink(".", legacy, target_is_directory=True)
                # Observe the new object, modeling a namespace replacement at
                # the old split readlink/capture boundary.
                return original_capture(path)
            return original_capture(path, **kwargs)
        with patch.object(self.i._InstallTransaction, "_capture_node", capture):
            with self.assertRaisesRegex(ValueError, "E_LEGACY_CODEX_SKILL_COLLISION"):
                self.i._preflight_codex_legacy_skill_projections(
                    plan, canonical, projection, home / ".codex" / "orchestrarium-legacy-skills", frozenset({"lead"}))
        self.assertTrue(changed)
        self.assertEqual(os.readlink(legacy), ".")
        self.assertFalse((home / ".codex" / "orchestrarium-legacy-skills").exists())

    def test_plan_rejects_link_replacement(self):
        data = self.fixture()
        home, canonical, projection, legacy, plan = data
        plans, root = self.i._preflight_codex_legacy_skill_projections(
            plan, canonical, projection, home / ".codex" / "orchestrarium-legacy-skills", frozenset({"lead"}))
        legacy.unlink()
        os.symlink(str(canonical / "lead"), legacy, target_is_directory=True)
        replacement = self.i._InstallTransaction._capture_node(legacy)
        with self.assertRaisesRegex(ValueError, "E_LEGACY_CODEX_SKILL_COLLISION"):
            self.i._assert_codex_legacy_skill_projection_plan_current(plans, plan, projection, root, dry_run=False)
        self.assertEqual(self.i._InstallTransaction._capture_node(legacy), replacement)

    @unittest.skipUnless(os.name == "nt", "transaction disposal backend is Windows-only")
    def test_absolute_link_retained_repaired_and_replayed(self):
        for linked, junction in ((False, False), (True, False), (True, True)):
            with self.subTest(linked=linked, junction=junction):
                with tempfile.TemporaryDirectory(dir=self.root) as tmp:
                    old_root, self.root = self.root, Path(tmp)
                    try:
                        data = self.fixture(linked=linked, junction=junction)
                        home, canonical, projection, legacy, plan = data
                        original = self.i._InstallTransaction._capture_node(legacy)
                        original_root = self.i._CreateOnlyMutablePath._identity(projection)
                        self.invoke(data, dry_run=True)
                        self.assertEqual(self.i._InstallTransaction._capture_node(legacy), original)
                        self.assertFalse((home / ".codex" / "orchestrarium-legacy-skills").exists())
                        self.invoke(data)
                        self.assertTrue(os.path.samefile(legacy, canonical / "lead"))
                        backups = list((home / ".codex" / "orchestrarium-legacy-skills" / "lead").iterdir())
                        self.assertEqual(len(backups), 1)
                        self.assertEqual(self.i._InstallTransaction._capture_node(backups[0]), original)
                        self.assertTrue(os.path.samefile(backups[0], projection))
                        self.assertEqual(self.i._CreateOnlyMutablePath._identity(projection), original_root)
                        self.assertEqual((projection / "user-object.txt").read_text(), "preserve user\n")
                        after = self.i._InstallTransaction._capture_node(legacy)
                        self.invoke(data)
                        self.assertEqual(self.i._InstallTransaction._capture_node(legacy), after)
                        self.assertEqual(self.i._InstallTransaction._capture_node(backups[0]), original)
                    finally:
                        self.root = old_root

    @unittest.skipUnless(os.name == "nt", "transaction disposal backend is Windows-only")
    def test_unapproved_and_relative_links_stay_collisions(self):
        for relative, approved in ((False, False), (True, True)):
            with self.subTest(relative=relative, approved=approved):
                with tempfile.TemporaryDirectory(dir=self.root) as tmp:
                    old_root, self.root = self.root, Path(tmp)
                    try:
                        data = self.fixture(relative=relative)
                        home, canonical, projection, legacy, plan = data
                        before = self.i._InstallTransaction._capture_node(legacy)
                        with self.assertRaisesRegex(ValueError, "E_LEGACY_CODEX_SKILL_COLLISION"):
                            self.invoke(data, approved=approved)
                        self.assertEqual(self.i._InstallTransaction._capture_node(legacy), before)
                        self.assertFalse((home / ".codex" / "orchestrarium-legacy-skills").exists())
                    finally:
                        self.root = old_root

    @unittest.skipUnless(os.name == "nt", "transaction disposal backend is Windows-only")
    def test_failure_restores_exact_link_object(self):
        for boundary in ("before-retain", "after-retain", "after-link"):
            with self.subTest(boundary=boundary):
                with tempfile.TemporaryDirectory(dir=self.root) as tmp:
                    old_root, self.root = self.root, Path(tmp)
                    try:
                        data = self.fixture(linked=True)
                        home, canonical, projection, legacy, plan = data
                        before = self.i._InstallTransaction._capture_node(legacy)
                        original_retain = self.i._CreateOnlyMutablePath.retain_path
                        original_projection = self.i._CreateOnlyMutablePath.create_projection
                        def retain(owner, relative, expected, **kwargs):
                            if boundary == "before-retain":
                                raise OSError("injected before retain")
                            result = original_retain(owner, relative, expected, **kwargs)
                            if boundary == "after-retain":
                                raise OSError("injected after retain")
                            return result
                        def create(owner, relative, source):
                            result = original_projection(owner, relative, source)
                            if boundary == "after-link":
                                raise OSError("injected after link")
                            return result
                        with patch.object(self.i._CreateOnlyMutablePath, "retain_path", retain), patch.object(self.i._CreateOnlyMutablePath, "create_projection", create):
                            with self.assertRaisesRegex(OSError, "injected"):
                                self.invoke(data)
                        self.assertEqual(self.i._InstallTransaction._capture_node(legacy), before)
                        self.assertTrue(os.path.samefile(legacy, projection))
                        self.assertFalse((home / ".codex" / "orchestrarium-legacy-skills").exists())
                        self.assertEqual((projection / "user-object.txt").read_text(), "preserve user\n")
                    finally:
                        self.root = old_root

    @unittest.skipUnless(os.name == "nt", "transaction disposal backend is Windows-only")
    def test_existing_backup_is_never_reused_or_overwritten(self):
        for kind in ("file", "link"):
            with self.subTest(kind=kind):
                with tempfile.TemporaryDirectory(dir=self.root) as tmp:
                    old_root, self.root = self.root, Path(tmp)
                    try:
                        data = self.fixture()
                        home, canonical, projection, legacy, plan = data
                        plans, _ = self.i._preflight_codex_legacy_skill_projections(
                            plan, canonical, projection, home / ".codex" / "orchestrarium-legacy-skills", frozenset({"lead"}))
                        backup = plans[0].backup_target
                        backup.parent.mkdir(parents=True)
                        if kind == "file":
                            backup.write_text("unrelated backup occupant")
                        else:
                            os.symlink(str(projection), backup, target_is_directory=True)
                        original = self.i._InstallTransaction._capture_node(legacy)
                        backup_before = self.i._InstallTransaction._capture_node(backup)
                        with self.assertRaisesRegex(ValueError, "E_LEGACY_CODEX_SKILL_COLLISION"):
                            self.invoke(data)
                        self.assertEqual(self.i._InstallTransaction._capture_node(legacy), original)
                        self.assertEqual(self.i._InstallTransaction._capture_node(backup), backup_before)
                    finally:
                        self.root = old_root

    @unittest.skipUnless(os.name == "nt", "transaction disposal backend is Windows-only")
    def test_late_backup_occupant_and_original_link_are_preserved(self):
        data = self.fixture(linked=True)
        home, canonical, projection, legacy, plan = data
        before = self.i._InstallTransaction._capture_node(legacy)
        original = self.i._CreateOnlyMutablePath.retain_path
        foreign = None
        def retain(owner, relative, expected, **kwargs):
            nonlocal foreign
            foreign = kwargs["retained_destination"]
            foreign.write_bytes(b"concurrent unowned object")
            return original(owner, relative, expected, **kwargs)
        with patch.object(self.i._CreateOnlyMutablePath, "retain_path", retain):
            with self.assertRaises(Exception):
                self.invoke(data)
        self.assertIsNotNone(foreign)
        self.assertEqual(foreign.read_bytes(), b"concurrent unowned object")
        self.assertEqual(self.i._InstallTransaction._capture_node(legacy), before)
        self.assertTrue(os.path.samefile(legacy, projection))

    def test_missing_and_file_targets_remain_collisions(self):
        data = self.fixture()
        home, canonical, projection, legacy, plan = data
        for target in (self.root / "absent", canonical / "lead" / "SKILL.md"):
            with self.subTest(target=target.name):
                legacy.unlink()
                os.symlink(str(target), legacy, target_is_directory=not target.is_file())
                plans, _ = self.i._preflight_codex_legacy_skill_projections(
                    plan, canonical, projection, home / ".codex" / "orchestrarium-legacy-skills", frozenset({"lead"}))
                self.assertEqual(plans[0].action, "collision")
                self.assertIsNone(plans[0].historical_link)

    @unittest.skipUnless(os.name == "nt", "transaction disposal backend is Windows-only")
    def test_public_install_repairs_all_source_names(self):
        home = self.root / "home"
        (home / ".codex").mkdir(parents=True)
        store = self.root / "legacy-store"
        store.mkdir()
        projection = home / ".codex" / "skills"
        self.i._create_directory_projection(store, projection, prefer_junction=True)
        names = sorted(path.name for path in (ROOT / "src.codex" / "skills").iterdir() if path.is_dir())
        self.assertEqual(len(names), 54)
        originals = {}
        for name in names:
            leaf = projection / name
            os.symlink(str(store), leaf, target_is_directory=True)
            originals[name] = self.i._InstallTransaction._capture_node(leaf)
        (store / "custom.txt").write_text("untouched user data\n")
        args = ["--global", "--no-hypothesis-hook"]
        for name in names:
            args.extend(("--migrate-legacy-skill", name))
        with patch.dict(os.environ, {"HOME": str(home), "USERPROFILE": str(home)}):
            self.assertEqual(self.i.install("codex", args), 0)
            after = {name: self.i._InstallTransaction._capture_node(projection / name) for name in names}
            self.assertEqual(self.i.install("codex", args), 0)
        for name in names:
            self.assertTrue(os.path.samefile(projection / name, home / ".agents" / "skills" / name))
            self.assertEqual(self.i._InstallTransaction._capture_node(projection / name), after[name])
            backups = list((home / ".codex" / "orchestrarium-legacy-skills" / name).iterdir())
            self.assertEqual(len(backups), 1)
            self.assertEqual(self.i._InstallTransaction._capture_node(backups[0]), originals[name])
        self.assertEqual((store / "custom.txt").read_text(), "untouched user data\n")


if __name__ == "__main__":
    unittest.main()
