"""Minimal synthetic producer receiving; no public install/full Source copies.

Executed repository closure: production_installer, hook registration/health,
provider_prompt and process_supervision support, this test and standard library.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location("producer_integration_under_test", ROOT / "scripts/production_installer.py")
PI = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PI
SPEC.loader.exec_module(PI)


def load_helper(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


H = load_helper("producer_hook_owner", "install-hypothesis-hook.py")
I = load_helper("producer_inventory_owner", "check-hook-health.py")


class ProducerIntegrationTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".scratch").mkdir(exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="producer-integration-test-", dir=ROOT / ".scratch")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.temp_patch = patch.object(PI.tempfile, "tempdir", str(self.root))
        self.temp_patch.start()
        self.addCleanup(self.temp_patch.stop)
        self.source = self.root / "source"
        self.source.mkdir()
        self.target = self.root / "target"
        self.target.mkdir()

    def transaction(self, paths, copies=(), link_objects=(), readonly=()):
        return PI._InstallTransaction(paths, enabled=True, copy_paths=tuple(copies),
                                      link_object_paths=tuple(link_objects), readonly_paths=tuple(readonly))

    def owner(self, transaction):
        return PI._CreateOnlyMutablePath(self.root, transaction, dry_run=False)

    def assert_clean(self):
        self.assertFalse(list(self.root.glob("orchestrarium-install-transaction-*")))
        self.assertFalse(list(self.root.rglob(".orchestrarium-retained-*")))
        self.assertFalse(list(self.root.rglob(".orchestrarium-migration-retention-*")))

    def test_copy_wrapper_uses_parent_snapshot_and_restores_metadata(self):
        source = self.source / "leaf"
        target = self.target / "leaf"
        source.write_bytes(b"new")
        target.write_bytes(b"old")
        os.utime(target, ns=(1_600_000_000_100_000_000, 1_600_000_000_200_000_000))
        before = target.stat()
        primary = RuntimeError("later producer failure")
        transaction = self.transaction([target], [target])
        with self.assertRaises(RuntimeError) as caught:
            with transaction:
                PI._copy_file(source, target, False, mutable_owner=self.owner(transaction))
                self.assertEqual(b"new", target.read_bytes())
                raise primary
        self.assertIs(primary, caught.exception)
        self.assertEqual(before.st_mtime_ns, target.stat().st_mtime_ns)
        self.assertEqual(b"old", target.read_bytes())
        self.assert_clean()

    def test_runtime_and_sync_wrappers_propagate_owner_and_skip_excluded(self):
        source = self.source / "runtime.py"
        source.write_bytes(b"runtime")
        installed = self.target / "runtime.py"
        sync_source = self.source / "sync"
        sync_source.mkdir()
        (sync_source / "keep.py").write_bytes(b"keep")
        (sync_source / "skip.py").write_bytes(b"skip")
        sync_target = self.target / "sync"
        sync_target.mkdir()
        keep = sync_target / "keep.py"
        transaction = self.transaction([installed, keep], [installed, keep])
        primary = RuntimeError("later")
        with self.assertRaises(RuntimeError) as caught:
            with transaction:
                owner = self.owner(transaction)
                PI._install_runtime_files(self.root, self.target, False,
                                          destinations=((source, installed),), mutable_owner=owner)
                PI._sync_tree(sync_source, sync_target, False,
                              excluded_files=frozenset({Path("skip.py")}), mutable_owner=owner)
                self.assertEqual([keep], PI._sync_file_destinations(
                    sync_source, sync_target, excluded_files=frozenset({Path("skip.py")})))
                self.assertFalse((sync_target / "skip.py").exists())
                raise primary
        self.assertIs(primary, caught.exception)
        self.assertFalse(installed.exists())
        self.assertFalse(keep.exists())
        self.assert_clean()

    def test_disabled_copy_and_dry_run_keep_direct_contract(self):
        source = self.source / "leaf"
        source.write_bytes(b"new")
        target = self.target / "leaf"
        transaction = PI._InstallTransaction([], enabled=False)
        owner = self.owner(transaction)
        PI._copy_file(source, target, True, mutable_owner=owner)
        self.assertFalse(target.exists())
        PI._copy_file(source, target, False, mutable_owner=owner)
        self.assertEqual(b"new", target.read_bytes())
        self.assertFalse(transaction._effects)

    def test_copy_into_new_parent_has_one_clean_inverse(self):
        source = self.source / "leaf"
        source.write_bytes(b"new")
        target = self.target / "new-parent" / "leaf"
        transaction = self.transaction([target], [target])
        primary = RuntimeError("later")
        with self.assertRaises(RuntimeError) as caught:
            with transaction:
                PI._copy_file(source, target, False, mutable_owner=self.owner(transaction))
                raise primary
        self.assertIs(primary, caught.exception)
        self.assertFalse(target.parent.exists())
        self.assert_clean()

    def test_ui_contract_copy_participates_before_later_failure(self):
        source = self.source / PI.UI_CONTINUITY_CONTRACT_SOURCE
        source.parent.mkdir(parents=True)
        source.write_bytes(b"neutral contract")
        target = self.target / PI.UI_CONTINUITY_CONTRACT_TARGET
        target.parent.mkdir()
        primary = RuntimeError("later")
        transaction = self.transaction([target], [target])
        with self.assertRaises(RuntimeError) as caught:
            with transaction:
                PI._install_ui_continuity_contract(self.source, self.target, False,
                                                    mutable_owner=self.owner(transaction))
                self.assertEqual(source.read_bytes(), target.read_bytes())
                raise primary
        self.assertIs(primary, caught.exception)
        self.assertFalse(target.exists())
        self.assert_clean()

    def test_typed_stale_file_tree_and_link_restore_original_objects(self):
        commands = self.target / "commands"
        skills = self.target / "skills"
        commands.mkdir()
        skills.mkdir()
        stale_file = commands / "agents-stale.md"
        stale_tree = skills / "agents-stale"
        stale_file.write_bytes(b"stale file")
        stale_tree.mkdir()
        (stale_tree / "leaf").write_bytes(b"stale tree")
        link = skills / "agents-link"
        link.symlink_to(stale_tree.name, target_is_directory=True)
        original = {p: PI._CreateOnlyMutablePath._identity(p) for p in (stale_file, stale_tree, link)}
        transaction = self.transaction([stale_file, skills])
        primary = RuntimeError("later")
        with self.assertRaises(RuntimeError) as caught:
            with transaction:
                owner = self.owner(transaction)
                PI._reclaim_claude_namespace(self.source, commands, skills, False,
                                             commands_owner=owner, skills_owner=owner)
                self.assertFalse(stale_file.exists())
                self.assertFalse(stale_tree.exists())
                self.assertFalse(link.is_symlink())
                raise primary
        self.assertIs(primary, caught.exception)
        self.assertEqual(original, {p: PI._CreateOnlyMutablePath._identity(p) for p in original})
        self.assertEqual(b"stale tree", (stale_tree / "leaf").read_bytes())
        self.assertEqual(stale_tree.name, os.readlink(link))
        self.assert_clean()

    def test_exact_typed_link_snapshot_admission_keeps_link_object(self):
        referent = self.target / "referent"
        referent.mkdir()
        link = self.target / "agents-stale"
        link.symlink_to(referent.name, target_is_directory=True)
        original = PI._CreateOnlyMutablePath._identity(link)
        primary = RuntimeError("later")
        transaction = self.transaction([link], link_objects=(link,))
        with self.assertRaises(RuntimeError) as caught:
            with transaction:
                owner = self.owner(transaction)
                owner.retain_path(link.relative_to(owner.anchor), PI._admitted_mutation_image(transaction, link))
                raise primary
        self.assertIs(primary, caught.exception)
        self.assertEqual(original, PI._CreateOnlyMutablePath._identity(link))
        self.assertTrue(referent.is_dir())
        self.assert_clean()

    def test_equal_byte_foreign_stale_leaf_is_refused_and_preserved(self):
        commands = self.target / "commands"
        commands.mkdir()
        stale = commands / "agents-stale.md"
        stale.write_bytes(b"stale")
        transaction = self.transaction([stale])
        with self.assertRaises(PI._InstallFailure) as caught:
            with transaction:
                foreign = self.target / "foreign"
                foreign.write_bytes(b"stale")
                os.replace(foreign, stale)
                PI._reclaim_claude_namespace(self.source, commands, self.target / "skills", False,
                                             commands_owner=self.owner(transaction))
        self.assertIn("retention original source", str(caught.exception.cause))
        self.assertEqual(b"stale", stale.read_bytes())
        self.assertTrue(caught.exception.recovery_path.is_dir())

    def test_native_no_plan_config_uses_its_existing_migration_inverse(self):
        config = self.target / "config.toml"
        config.write_bytes(b"# user bytes\n[features]\nmulti_agent_v2 = true\n")
        original = config.read_bytes()
        original_identity = PI._CreateOnlyMutablePath._identity(config)
        agents = self.target / "agents"
        agents.mkdir()
        role = PI._NativeRoleRegistration("synthetic", "Synthetic role", Path("synthetic.toml"))
        primary = RuntimeError("later")
        transaction = self.transaction([])  # Native config deliberately has no snapshot inverse.
        with patch.object(PI, "_native_role_registrations", return_value=(role,)):
            with self.assertRaises(RuntimeError) as caught:
                with transaction:
                    owner = self.owner(transaction)
                    PI._reconcile_codex_native_config(config, owner,
                        source_agents=self.source, target_agents=agents, manifest={})
                    self.assertIn(b"[agents.synthetic]", config.read_bytes())
                    raise primary
        self.assertIs(primary, caught.exception)
        self.assertEqual(original_identity, PI._CreateOnlyMutablePath._identity(config))
        self.assertEqual(original, config.read_bytes())
        self.assert_clean()

    def test_planned_native_legacy_removal_uses_exact_retention_inverse(self):
        config = self.target / "config.toml"
        config.write_bytes(b"[features]\nmulti_agent_v2 = true\n")
        legacy = self.target / "legacy.toml"
        legacy.write_bytes(b"synthetic frozen legacy")
        original_identity = PI._CreateOnlyMutablePath._identity(legacy)
        plan = SimpleNamespace(config_exists=True, config_prior_digest=PI._file_sha256(config),
                               config_payload=config.read_bytes(), legacy_exists=True, legacy_path=legacy)
        transaction = self.transaction([])
        primary = RuntimeError("later")
        with patch.object(PI, "CODEX_LEGACY_LUNA_SHA256", PI._file_sha256(legacy)):
            with self.assertRaises(RuntimeError) as caught:
                with transaction:
                    PI._reconcile_codex_native_config(config, self.owner(transaction), plan=plan)
                    self.assertFalse(legacy.exists())
                    raise primary
        self.assertIs(primary, caught.exception)
        self.assertEqual(original_identity, PI._CreateOnlyMutablePath._identity(legacy))
        self.assert_clean()

    def legacy_fixture(self, existing_backup):
        canonical_source = self.source / "skill"
        canonical_source.mkdir()
        (canonical_source / "leaf").write_bytes(b"canonical")
        canonical_target = self.target / "canonical"
        canonical_target.mkdir()
        (canonical_target / "leaf").write_bytes(b"canonical")
        projection = self.target / "skills"
        projection.mkdir()
        installed = projection / "skill"
        installed.mkdir()
        (installed / "leaf").write_bytes(b"historical")
        historical_digest = PI._tree_sha256(installed)
        backup = self.target / "backups" / "skill" / historical_digest
        if existing_backup:
            backup.mkdir(parents=True)
            (backup / "leaf").write_bytes(b"historical")
        canonical = SimpleNamespace(name="skill", source=canonical_source,
                                    source_digest=PI._tree_sha256(canonical_source), ignore_runtime_cache=False)
        canonical_plan = SimpleNamespace(skills=(canonical,))
        plan = (PI._SkillProjectionPlan("skill", canonical_target, canonical.source_digest,
                "migrate", historical_digest, backup, PI._CreateOnlyMutablePath._identity(installed),
                historical_digest if existing_backup else None),)
        return canonical_plan, plan, projection, installed, backup

    def test_legacy_absent_persistent_backup_restores_before_projection_failure(self):
        self.receive_legacy_failure(False)

    def test_legacy_exact_backup_remains_unchanged_on_projection_failure(self):
        self.receive_legacy_failure(True)

    def test_existing_backup_replaced_after_enter_refuses_before_foreign_digest_or_source_effect(self):
        canonical, plan, projection, installed, backup = self.legacy_fixture(True)
        source_identity = PI._CreateOnlyMutablePath._identity(installed)
        transaction = self.transaction([installed, backup], readonly=(backup,))
        digest = PI._tree_sha256
        native_digest = PI._WindowsBoundNode.digest
        foreign_reads = []
        foreign_native_reads = []
        original_file_proof = []
        failure = None
        displaced = backup.with_name("displaced-original")
        def observed_native(bound):
            if (original_file_proof and bound.path == backup / "leaf"
                    and bound.proof != original_file_proof[0]):
                foreign_native_reads.append(bound.path)
            return native_digest(bound)
        try:
            with patch.object(PI._WindowsBoundNode, "digest", observed_native), transaction:
                original = transaction._original[backup][backup]
                original_file_proof.append(transaction._original[backup][backup / "leaf"].native_proof)
                backup.rename(displaced)
                backup.mkdir()
                (backup / "leaf").write_bytes(b"historical")
                foreign = transaction._capture_node(backup)
                self.assertNotEqual(original.native_proof, foreign.native_proof)
                foreign_identity = PI._CreateOnlyMutablePath._identity(backup)
                def observed(path, **kwargs):
                    if Path(path) == backup:
                        foreign_reads.append(PI._CreateOnlyMutablePath._identity(backup))
                    return digest(path, **kwargs)
                with patch.object(PI, "_tree_sha256", observed):
                    owner = self.owner(transaction)
                    PI._apply_codex_legacy_skill_projection_plan(plan, canonical, projection,
                        PI._CreateOnlyMutablePath._identity(projection), owner, owner)
                    transaction.commit()
        except PI._InstallFailure as error:
            failure = error
        self.assertIsNotNone(failure, f"replacement committed; foreign digest reads={len(foreign_reads)}; "
            f"source_is_original={PI._CreateOnlyMutablePath._identity(installed)==source_identity}; "
            f"recovery={transaction._remaining_recovery()}")
        self.assertEqual(foreign_reads, [])
        self.assertEqual(foreign_native_reads, [])
        self.assertFalse(transaction._effects)
        self.assertEqual(PI._CreateOnlyMutablePath._identity(installed), source_identity)
        self.assertEqual(PI._CreateOnlyMutablePath._identity(backup), foreign_identity)
        self.assertTrue(displaced.is_dir())
        self.assertEqual((installed / "leaf").read_bytes(), b"historical")
        self.assertTrue(failure.recovery_path.exists())

    def test_existing_backup_member_replaced_after_enter_refuses_before_foreign_digest(self):
        canonical, plan, projection, installed, backup = self.legacy_fixture(True)
        source_identity = PI._CreateOnlyMutablePath._identity(installed)
        transaction = self.transaction([installed, backup], readonly=(backup,))
        digest = PI._tree_sha256
        reads = []
        with self.assertRaises(PI._InstallFailure):
            with transaction:
                member = backup / "leaf"
                before = transaction._original[backup][member]
                member.rename(self.root / "original-backup-member")
                member.write_bytes(b"historical")
                foreign = transaction._capture_node(member, kind="file", data=before.data)
                self.assertNotEqual(before.native_proof, foreign.native_proof)
                def observed(path, **kwargs):
                    if Path(path) == backup:
                        reads.append(path)
                    return digest(path, **kwargs)
                with patch.object(PI, "_tree_sha256", observed):
                    owner = self.owner(transaction)
                    PI._apply_codex_legacy_skill_projection_plan(plan, canonical, projection,
                        PI._CreateOnlyMutablePath._identity(projection), owner, owner)
        self.assertEqual(reads, [])
        self.assertEqual(PI._CreateOnlyMutablePath._identity(installed), source_identity)
        self.assertFalse(transaction._effects)
        self.assertEqual((backup / "leaf").read_bytes(), b"historical")

    def test_existing_backup_parent_retarget_with_same_backup_object_refuses(self):
        canonical, plan, projection, installed, backup = self.legacy_fixture(True)
        source_identity = PI._CreateOnlyMutablePath._identity(installed)
        backup_identity = PI._CreateOnlyMutablePath._identity(backup)
        digest = PI._tree_sha256
        reads = []
        with self.assertRaises(PI._InstallFailure) as caught:
            with self.transaction([installed, backup], readonly=(backup,)) as transaction:
                displaced = self.root / "original-backup-parent"
                backup.parent.rename(displaced)
                backup.parent.mkdir()
                (displaced / backup.name).rename(backup)
                self.assertEqual(PI._CreateOnlyMutablePath._identity(backup), backup_identity)
                def observed(path, **kwargs):
                    if Path(path) == backup:
                        reads.append(path)
                    return digest(path, **kwargs)
                with patch.object(PI, "_tree_sha256", observed):
                    owner = self.owner(transaction)
                    PI._apply_codex_legacy_skill_projection_plan(plan, canonical, projection,
                        PI._CreateOnlyMutablePath._identity(projection), owner, owner)
        self.assertEqual(reads, [])
        self.assertIsInstance(caught.exception.cause, ValueError)
        self.assertIn("original parent", str(caught.exception.cause))
        self.assertTrue(caught.exception.recovery_path.exists())
        self.assertEqual(PI._CreateOnlyMutablePath._identity(installed), source_identity)
        self.assertEqual(PI._CreateOnlyMutablePath._identity(backup), backup_identity)
        self.assertFalse(transaction._effects)

    def test_absent_backup_late_equal_tree_is_not_adopted(self):
        canonical, plan, projection, installed, backup = self.legacy_fixture(False)
        source_identity = PI._CreateOnlyMutablePath._identity(installed)
        with self.assertRaises(PI._InstallFailure):
            with self.transaction([installed, backup], readonly=(backup,)) as transaction:
                backup.mkdir(parents=True)
                (backup / "leaf").write_bytes(b"historical")
                foreign_identity = PI._CreateOnlyMutablePath._identity(backup)
                owner = self.owner(transaction)
                PI._apply_codex_legacy_skill_projection_plan(plan, canonical, projection,
                    PI._CreateOnlyMutablePath._identity(projection), owner, owner)
        self.assertEqual(PI._CreateOnlyMutablePath._identity(installed), source_identity)
        self.assertEqual(PI._CreateOnlyMutablePath._identity(backup), foreign_identity)
        self.assertFalse(transaction._effects)

    def test_existing_backup_replaced_after_retention_blocks_source_disposal_on_commit(self):
        canonical, plan, projection, installed, backup = self.legacy_fixture(True)
        external_projection = self.root / "readonly-external-projection"
        projection.rename(external_projection)
        projection, installed = external_projection, external_projection / installed.name
        source_identity = PI._CreateOnlyMutablePath._identity(installed)
        with self.assertRaises(PI._InstallFailure) as caught:
            with self.transaction([installed, backup], readonly=(backup,)) as transaction:
                home_owner = PI._CreateOnlyMutablePath(self.target, transaction, dry_run=False)
                projection_owner = PI._CreateOnlyMutablePath(projection, transaction, dry_run=False)
                PI._apply_codex_legacy_skill_projection_plan(plan, canonical, projection,
                    PI._CreateOnlyMutablePath._identity(projection), home_owner, projection_owner)
                source_effect = next(effect for effect in transaction._effects if effect.path == installed and effect.before)
                self.assertEqual(len(source_effect.readonly_dependencies), 1)
                backup.rename(self.root / "original-backup")
                backup.mkdir()
                (backup / "leaf").write_bytes(b"historical")
                foreign_identity = PI._CreateOnlyMutablePath._identity(backup)
                transaction.commit()
        self.assertIn("READ_ONLY_DEPENDENCY_CHANGED", str(caught.exception))
        self.assertFalse(source_effect.settled)
        self.assertIsNotNone(source_effect.retained_state)
        self.assertEqual(PI._CreateOnlyMutablePath._identity(source_effect.retained), source_identity)
        self.assertEqual((source_effect.retained / "leaf").read_bytes(), b"historical")
        self.assertEqual(PI._CreateOnlyMutablePath._identity(backup), foreign_identity)
        self.assertTrue(caught.exception.recovery_path.exists())

    def test_foreign_readonly_backup_does_not_block_safe_inverse_or_sibling(self):
        canonical, plan, projection, installed, backup = self.legacy_fixture(True)
        source_identity = PI._CreateOnlyMutablePath._identity(installed)
        sibling = self.target / "safe-sibling"
        sibling.write_bytes(b"original sibling")
        primary = RuntimeError("later pre-commit failure")
        with self.assertRaises(PI._InstallFailure) as caught:
            with self.transaction([installed, backup, sibling], readonly=(backup,)) as transaction:
                owner = self.owner(transaction)
                owner.write_file(sibling.relative_to(owner.anchor), b"new sibling")
                PI._apply_codex_legacy_skill_projection_plan(plan, canonical, projection,
                    PI._CreateOnlyMutablePath._identity(projection), owner, owner)
                backup.rename(self.root / "original-backup")
                backup.mkdir()
                (backup / "leaf").write_bytes(b"historical")
                raise primary
        self.assertIs(caught.exception.cause, primary)
        self.assertEqual(PI._CreateOnlyMutablePath._identity(installed), source_identity)
        self.assertEqual((installed / "leaf").read_bytes(), b"historical")
        self.assertEqual(sibling.read_bytes(), b"original sibling")
        self.assertEqual((backup / "leaf").read_bytes(), b"historical")
        self.assertTrue(caught.exception.recovery_path.exists())

    def test_unchanged_existing_backup_commit_keeps_exact_object_without_backup_effect(self):
        canonical, plan, projection, installed, backup = self.legacy_fixture(True)
        backup_identity = PI._CreateOnlyMutablePath._identity(backup)
        with self.transaction([installed, backup], readonly=(backup,)) as transaction:
            owner = self.owner(transaction)
            PI._apply_codex_legacy_skill_projection_plan(plan, canonical, projection,
                PI._CreateOnlyMutablePath._identity(projection), owner, owner)
            self.assertFalse(any(effect.path == backup for effect in transaction._effects))
            transaction.commit()
        self.assertEqual(PI._CreateOnlyMutablePath._identity(backup), backup_identity)
        self.assertTrue(PI._projection_resolves_to(installed, plan[0].canonical_target))
        self.assertEqual(transaction._remaining_recovery(), (None, [], []))
        self.assert_clean()

    def test_existing_backup_inplace_content_drift_blocks_commit_disposal(self):
        canonical, plan, projection, installed, backup = self.legacy_fixture(True)
        source_identity = PI._CreateOnlyMutablePath._identity(installed)
        with self.assertRaises(PI._InstallFailure) as caught:
            with self.transaction([installed, backup], readonly=(backup,)) as transaction:
                owner = self.owner(transaction)
                PI._apply_codex_legacy_skill_projection_plan(plan, canonical, projection,
                    PI._CreateOnlyMutablePath._identity(projection), owner, owner)
                source_effect = next(effect for effect in transaction._effects if effect.path == installed and effect.before)
                (backup / "leaf").write_bytes(b"changed in original member")
                transaction.commit()
        self.assertIn("original bytes", str(caught.exception))
        self.assertEqual(PI._CreateOnlyMutablePath._identity(source_effect.retained), source_identity)
        self.assertEqual((backup / "leaf").read_bytes(), b"changed in original member")
        self.assertTrue(caught.exception.recovery_path.exists())

    def test_readonly_contract_keeps_dry_run_without_dependency_or_effect(self):
        canonical, plan, projection, installed, backup = self.legacy_fixture(True)
        source_identity = PI._CreateOnlyMutablePath._identity(installed)
        backup_identity = PI._CreateOnlyMutablePath._identity(backup)
        transaction = PI._InstallTransaction([], enabled=False)
        owner = PI._CreateOnlyMutablePath(self.root, transaction, dry_run=True)
        with patch.object(transaction, "bind_readonly_path", wraps=transaction.bind_readonly_path) as bind:
            result = PI._apply_codex_legacy_skill_projection_plan(plan, canonical, projection,
                PI._CreateOnlyMutablePath._identity(projection), owner, owner)
        self.assertEqual(result, ())
        bind.assert_not_called()
        self.assertFalse(transaction._effects)
        self.assertEqual(PI._CreateOnlyMutablePath._identity(installed), source_identity)
        self.assertEqual(PI._CreateOnlyMutablePath._identity(backup), backup_identity)
        self.assert_clean()

    def test_readonly_contract_preserves_direct_existing_backup_boundary(self):
        canonical, plan, projection, installed, backup = self.legacy_fixture(True)
        backup_identity = PI._CreateOnlyMutablePath._identity(backup)
        transaction = PI._InstallTransaction([], enabled=False)
        owner = self.owner(transaction)
        result = PI._apply_codex_legacy_skill_projection_plan(plan, canonical, projection,
            PI._CreateOnlyMutablePath._identity(projection), owner, owner)
        self.assertEqual(result, ())
        self.assertEqual(PI._CreateOnlyMutablePath._identity(backup), backup_identity)
        self.assertTrue(PI._projection_resolves_to(installed, plan[0].canonical_target))
        self.assertEqual(transaction._remaining_recovery(), (None, [], []))
        self.assert_clean()

    def test_readonly_contract_preserves_collision_row_beside_admitted_migration(self):
        canonical, plan, projection, installed, backup = self.legacy_fixture(False)
        collision_source = self.source / "collision"
        collision_target = self.target / "canonical-collision"
        collision_installed = projection / "collision"
        collision_backup = self.target / "collision-backup"
        for path, content in ((collision_source, b"canonical"), (collision_target, b"canonical"),
                              (collision_installed, b"old"), (collision_backup, b"different")):
            path.mkdir()
            (path / "leaf").write_bytes(content)
        source_identity = PI._CreateOnlyMutablePath._identity(collision_installed)
        backup_identity = PI._CreateOnlyMutablePath._identity(collision_backup)
        new_skill = SimpleNamespace(name="collision", source=collision_source,
            source_digest=PI._tree_sha256(collision_source), ignore_runtime_cache=False)
        canonical = SimpleNamespace(skills=canonical.skills + (new_skill,))
        collision = PI._SkillProjectionPlan("collision", collision_target, new_skill.source_digest,
            "collision", PI._tree_sha256(collision_installed), collision_backup,
            source_identity, PI._tree_sha256(collision_backup))
        with self.transaction([installed, backup], readonly=(backup,)) as transaction:
            owner = self.owner(transaction)
            result = PI._apply_codex_legacy_skill_projection_plan(plan + (collision,), canonical, projection,
                PI._CreateOnlyMutablePath._identity(projection), owner, owner)
            self.assertEqual(result, ("collision",))
            transaction.commit()
        self.assertEqual(PI._CreateOnlyMutablePath._identity(collision_installed), source_identity)
        self.assertEqual(PI._CreateOnlyMutablePath._identity(collision_backup), backup_identity)
        self.assertTrue(PI._projection_resolves_to(installed, plan[0].canonical_target))
        self.assert_clean()

    def test_legacy_commit_keeps_exact_persistent_backup_and_projection(self):
        canonical, plan, projection, installed, backup = self.legacy_fixture(False)
        original = PI._CreateOnlyMutablePath._identity(installed)
        transaction = self.transaction([installed, backup], readonly=(backup,))
        with transaction:
            owner = self.owner(transaction)
            PI._apply_codex_legacy_skill_projection_plan(plan, canonical, projection,
                PI._CreateOnlyMutablePath._identity(projection), owner, owner)
            transaction.commit()
        self.assertEqual(original, PI._CreateOnlyMutablePath._identity(backup))
        self.assertEqual(b"historical", (backup / "leaf").read_bytes())
        self.assertTrue(PI._projection_resolves_to(installed, plan[0].canonical_target))
        self.assertEqual(transaction._remaining_recovery(), (None, [], []))
        self.assert_clean()

    def receive_legacy_failure(self, existing_backup):
        canonical, plan, projection, installed, backup = self.legacy_fixture(existing_backup)
        original = PI._CreateOnlyMutablePath._identity(installed)
        backup_original = PI._CreateOnlyMutablePath._identity(backup) if existing_backup else None
        transaction = self.transaction([installed, backup], readonly=(backup,))
        primary = RuntimeError("projection creation failed")
        with self.assertRaises(RuntimeError) as caught:
            with transaction:
                owner = self.owner(transaction)
                with patch.object(owner, "create_projection", side_effect=primary):
                    PI._apply_codex_legacy_skill_projection_plan(plan, canonical, projection,
                        PI._CreateOnlyMutablePath._identity(projection), owner, owner)
        self.assertIs(primary, caught.exception)
        self.assertEqual(original, PI._CreateOnlyMutablePath._identity(installed))
        self.assertEqual(b"historical", (installed / "leaf").read_bytes())
        if existing_backup:
            self.assertEqual(backup_original, PI._CreateOnlyMutablePath._identity(backup))
        else:
            self.assertFalse((self.target / "backups").exists())
        self.assert_clean()

    def test_retired_fallback_uses_admitted_owner_instead_of_untracked_unlink(self):
        retired = self.target / "retired.py"
        retired.write_bytes(b"stock")
        original = PI._CreateOnlyMutablePath._identity(retired)
        unrelated_anchor = self.root / "other"
        unrelated_anchor.mkdir()
        transaction = self.transaction([retired])
        primary = RuntimeError("later")
        with self.assertRaises(RuntimeError) as caught:
            with transaction:
                owner = self.owner(transaction)
                other = PI._CreateOnlyMutablePath(unrelated_anchor, transaction, dry_run=False)
                PI._reclaim_retired(self.target, {"retired.py": PI._file_sha256(retired)}, False,
                    transaction=transaction, mutable_owner=other, fallback_owners=(owner,))
                self.assertFalse(retired.exists())
                raise primary
        self.assertIs(primary, caught.exception)
        self.assertEqual(original, PI._CreateOnlyMutablePath._identity(retired))
        self.assert_clean()

    def documentation_fixture(self):
        shared = self.source / "shared" / "AGENTS.shared.md"
        shared.parent.mkdir()
        shared.write_text("# Shared Governance\nnew shared\n", encoding="utf-8")
        pack = self.source / "pack"
        pack.mkdir()
        (pack / "AGENTS.codex.md").write_text("new codex\n", encoding="utf-8")
        (pack / "CLAUDE.md").write_text("@AGENTS.md\n# Claude Code Pack\n", encoding="utf-8")
        return pack

    def test_codex_document_merge_is_inplace_lf_and_rolls_back_user_bytes(self):
        pack = self.documentation_fixture()
        target = self.target / "AGENTS.md"
        original = ("user prefix\r\n" + PI.CODEX_BEGIN + "\r\nold\r\n" + PI.CODEX_END + "\r\nuser tail\r\n").encode()
        target.write_bytes(original)
        identity = PI._CreateOnlyMutablePath._identity(target)
        primary = RuntimeError("later")
        transaction = self.transaction([target])
        with self.assertRaises(RuntimeError) as caught:
            with transaction:
                PI._merge_codex_agents(self.source, pack, target, False, mutable_owner=self.owner(transaction))
                self.assertEqual(identity, PI._CreateOnlyMutablePath._identity(target))
                current = target.read_bytes()
                self.assertIn(b"new codex", current)
                self.assertIn(b"user tail", current)
                self.assertNotIn(b"\r", current)
                raise primary
        self.assertIs(primary, caught.exception)
        self.assertEqual(original, target.read_bytes())
        self.assert_clean()

    def test_claude_two_documents_share_parent_inverse(self):
        pack = self.documentation_fixture()
        target = self.target / "CLAUDE.md"
        agents = self.target / "AGENTS.md"
        target.write_bytes(b"user prefix\r\n@AGENTS.md\r\nold pack\r\n")
        agents.write_bytes(b"local agent instructions\r\n")
        original = {p: p.read_bytes() for p in (target, agents)}
        primary = RuntimeError("later")
        transaction = self.transaction([target, agents])
        with self.assertRaises(RuntimeError) as caught:
            with transaction:
                PI._merge_claude_docs(self.source, pack, target, False, mutable_owner=self.owner(transaction))
                self.assertIn(b"user prefix", target.read_bytes())
                self.assertIn(b"local agent instructions", agents.read_bytes())
                self.assertIn(b"new shared", agents.read_bytes())
                raise primary
        self.assertIs(primary, caught.exception)
        self.assertEqual(original, {p: p.read_bytes() for p in original})
        self.assert_clean()

    def helper_loader(self, name, path):
        if path.name == "install-hypothesis-hook.py":
            return H
        if path.name == "check-hook-health.py":
            return I
        self.fail("unexpected helper execution surface: " + str(path))

    def test_settings_atomic_change_and_nochange_share_original_snapshot(self):
        target = self.target / "settings.json"
        target.write_bytes(b'{"custom":"keep"}')
        original = target.read_bytes()
        transaction = self.transaction([target])
        primary = RuntimeError("later")
        with patch.object(PI, "_load_module_from_path", side_effect=self.helper_loader):
            with self.assertRaises(RuntimeError) as caught:
                with transaction:
                    owner = self.owner(transaction)
                    self.assertEqual("lead-default-written", PI._merge_claude_main_agent_settings(
                        self.source, target, "force", False, mutable_owner=owner))
                    self.assertEqual({"custom": "keep", "agent": "lead"}, json.loads(target.read_bytes()))
                    after = target.read_bytes()
                    identity = PI._CreateOnlyMutablePath._identity(target)
                    self.assertEqual("lead-already-selected", PI._merge_claude_main_agent_settings(
                        self.source, target, "force", False, mutable_owner=owner))
                    self.assertEqual(identity, PI._CreateOnlyMutablePath._identity(target))
                    self.assertEqual(after, target.read_bytes())
                    raise primary
        self.assertIs(primary, caught.exception)
        self.assertEqual(original, target.read_bytes())
        self.assert_clean()

    def hook_fixture(self, provider="codex", linked=False, directory_link=False):
        marker = "check-bugfix-discipline"
        script = self.source / (marker + ".py")
        script.write_text("pass\n", encoding="utf-8")
        matcher = H.TOOL_MATCHER_REGEX
        specs = [(marker, script, "PreToolUse", matcher)]
        storage = self.target / "hooks.json"
        foreign = {"type": "command", "command": "echo custom"}
        _marker, directory, event, retired_matcher = next(
            item for item in PI._HOOK_METADATA if item[0] == "check-mcp-momentum")
        retired_target = H.resolve_hook_target(str(self.source / directory / "check-mcp-momentum.py"),
                                             "windows" if os.name == "nt" else "posix", "codex", require_script=False)
        retired = H.build_codex_entry(retired_target, "windows" if os.name == "nt" else "posix",
                                     event, retired_matcher)
        retired["hooks"].append(foreign)
        original = H.encode_hook_config({"custom": "保持", "hooks": {event: [retired]}})
        storage.write_bytes(original)
        selected = storage
        if linked:
            selected = self.root / "selected.json"
            selected.symlink_to(storage)
        if directory_link:
            alias = self.root / "selected-parent"
            alias.symlink_to(self.target, target_is_directory=True)
            selected = alias / storage.name
        return specs, selected, storage, storage.parent / I.INVENTORY_NAME, original, foreign

    @contextlib.contextmanager
    def hook_support(self, specs, primary=None):
        invocations = []
        def run(arguments, _root):
            invocations.append(arguments)
            self.assertTrue("--validate-only" in arguments or "--test-transaction-preflight" in arguments)
            return subprocess.CompletedProcess(arguments, 0)
        def checkpoint(_root, _installer, _registration, _provider, _mode, stage):
            if stage == "verify" and primary is not None:
                raise primary
        with contextlib.ExitStack() as resources:
            resources.enter_context(patch.object(PI, "_load_module_from_path", side_effect=self.helper_loader))
            resources.enter_context(patch.object(PI, "_hook_health_module", return_value=I))
            resources.enter_context(patch.object(PI, "_hook_specs", return_value=specs))
            resources.enter_context(patch.object(I, "_manifest_stems", return_value={spec[0] for spec in specs}))
            resources.enter_context(patch.object(I, "resolve_codex_command", return_value=["synthetic-codex"]))
            resources.enter_context(patch.object(PI, "_run", side_effect=run))
            resources.enter_context(patch.object(PI, "_checkpoint", side_effect=checkpoint))
            resources.enter_context(patch.object(PI, "_run_hook_health_bounded",
                return_value=subprocess.CompletedProcess([], 0)))
            yield invocations

    def receive_hooks(self, linked=False, directory_link=False):
        specs, selected, storage, inventory, original, foreign = self.hook_fixture(
            linked=linked, directory_link=directory_link)
        paths = [storage, inventory] + ([selected] if linked else [])
        transaction = self.transaction(paths, link_objects=(selected,) if linked else ())
        primary = RuntimeError("hook transaction checkpoint failed at verify")
        selected_identity = PI._CreateOnlyMutablePath._identity(selected) if linked else None
        with self.hook_support(specs, primary) as invocations:
            with self.assertRaises(RuntimeError) as caught:
                with transaction:
                    PI._install_hooks(self.source, "codex", selected, self.source, "target", inventory,
                                      transaction=transaction, mutable_owner=self.owner(transaction))
        self.assertIs(primary, caught.exception)
        self.assertEqual(original, storage.read_bytes())
        self.assertFalse(inventory.exists())
        self.assertFalse(any("--remove" in command for command in invocations))
        if linked:
            self.assertEqual(selected_identity, PI._CreateOnlyMutablePath._identity(selected))
            self.assertTrue(selected.is_symlink())
        if directory_link:
            self.assertTrue(selected.parent.is_symlink())
        self.assert_clean()

    def test_real_hook_transform_inventory_and_later_inverse(self):
        self.receive_hooks()

    def test_real_selected_file_link_hook_publication_preserves_link_and_inverse(self):
        self.receive_hooks(linked=True)

    def test_real_selected_directory_link_hook_publication_uses_ordinary_storage(self):
        self.receive_hooks(directory_link=True)

    def test_hook_commit_real_inventory_wire_and_parent_absence_binding(self):
        specs, selected, storage, inventory, _original, foreign = self.hook_fixture()
        transaction = self.transaction([storage, inventory])
        with self.hook_support(specs):
            with transaction:
                PI._install_hooks(self.source, "codex", selected, self.source, "target", inventory,
                                  transaction=transaction, mutable_owner=self.owner(transaction))
                data = json.loads(storage.read_bytes())
                handlers = [handler for entries in data["hooks"].values() for group in entries for handler in group["hooks"]]
                self.assertIn(foreign, handlers)
                self.assertFalse(any("check-mcp-momentum.py" in handler.get("command", "") for handler in handlers))
                payload = json.loads(inventory.read_bytes())
                self.assertEqual({"schemaVersion", "sourcePath", "hooks"}, set(payload))
                self.assertEqual({"stem", "identity"}, set(payload["hooks"][0]))
                self.assertNotIn(b"\r", inventory.read_bytes())
                self.assertEqual({specs[0][0]}, I._load_codex_inventory(
                    inventory, target=selected, host_os="windows" if os.name == "nt" else "posix")[0])
                transaction.commit()
        self.assert_clean()

    def test_malformed_hook_json_systemexit_becomes_visible_stage_cause(self):
        specs, _selected, storage, _inventory, _original, _foreign = self.hook_fixture()
        storage.write_bytes(b"{")
        transaction = self.transaction([storage])
        with self.hook_support(specs), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(RuntimeError) as caught:
                with transaction:
                    PI._install_hooks(self.source, "claude", storage, self.source, "target",
                                      transaction=transaction, mutable_owner=self.owner(transaction))
        self.assertIsInstance(caught.exception.__cause__, SystemExit)
        self.assertEqual(1, caught.exception.__cause__.code)
        self.assertEqual(b"{", storage.read_bytes())
        self.assert_clean()

    def test_inventory_foreign_creation_is_not_adopted_from_plan(self):
        specs, selected, storage, inventory, original, _foreign = self.hook_fixture()
        original_plan = I.plan_codex_inventory
        def prepare(**arguments):
            plan = original_plan(**arguments)
            inventory.write_bytes(plan.content)  # Outside writer after original absence admission.
            return plan
        transaction = self.transaction([storage, inventory])
        with self.hook_support(specs), patch.object(I, "plan_codex_inventory", side_effect=prepare):
            with self.assertRaises(PI._InstallFailure) as caught:
                with transaction:
                    PI._install_hooks(self.source, "codex", selected, self.source, "target", inventory,
                                      transaction=transaction, mutable_owner=self.owner(transaction))
        self.assertIn("byte destination absence", str(caught.exception.cause))
        self.assertEqual(original, storage.read_bytes())
        self.assertTrue(inventory.exists())
        self.assertTrue(caught.exception.recovery_path.exists())

    def test_hook_best_effort_and_inventory_required_fsync_remain_distinct(self):
        specs, selected, storage, inventory, original, _foreign = self.hook_fixture()
        transaction = self.transaction([storage, inventory])
        primary = OSError("synthetic fsync refusal")
        with self.hook_support(specs):
            with self.assertRaises(I._HookHealthFailure) as caught:
                with transaction:
                    with patch.object(PI.os, "fsync", side_effect=primary):
                        PI._install_hooks(self.source, "codex", selected, self.source, "target", inventory,
                                          transaction=transaction, mutable_owner=self.owner(transaction))
        self.assertIs(primary, caught.exception.__cause__)
        self.assertEqual(original, storage.read_bytes())
        self.assertFalse(inventory.exists())
        self.assert_clean()

    def receive_claude_empty_retirement(self, linked):
        specs, _selected, storage, _inventory, _original, _foreign = self.hook_fixture()
        retired_script = self.source / "check-work-items-archival-stop.py"
        entry = H.build_claude_entry(H.HookTarget(sys.executable, (str(retired_script),)), "Stop")
        original = H.encode_hook_config({"hooks": {"Stop": [entry]}})
        storage.write_bytes(original)
        selected = storage
        if linked:
            selected = self.root / "selected.json"
            selected.symlink_to(storage)
        transaction = self.transaction([storage] + ([selected] if linked else []),
                                       link_objects=(selected,) if linked else ())
        primary = RuntimeError("verify after empty retirement and new registration")
        with self.hook_support(specs, primary):
            with self.assertRaises(RuntimeError) as caught:
                with transaction:
                    PI._install_hooks(self.source, "claude", selected, self.source, "target",
                                      transaction=transaction, mutable_owner=self.owner(transaction))
        self.assertIs(primary, caught.exception)
        self.assertEqual(original, storage.read_bytes())
        if linked:
            self.assertTrue(selected.is_symlink())
        self.assert_clean()

    def test_claude_empty_regular_retirement_then_registration_has_one_inverse(self):
        self.receive_claude_empty_retirement(False)

    def test_claude_empty_link_retirement_preserves_link_then_registers(self):
        self.receive_claude_empty_retirement(True)

    def test_document_and_settings_dryrun_keep_no_effect_and_custom_policy(self):
        pack = self.documentation_fixture()
        document = self.target / "AGENTS.md"
        settings = self.target / "settings.json"
        document.write_bytes(b"user doc\r\n")
        settings.write_bytes(b'{"agent":"custom","other":0}')
        before = {p: p.read_bytes() for p in (document, settings)}
        transaction = self.transaction(list(before))
        with transaction:
            owner = self.owner(transaction)
            PI._merge_codex_agents(self.source, pack, document, True, mutable_owner=owner)
            self.assertEqual("preserved-nonlead-agent", PI._merge_claude_main_agent_settings(
                self.source, settings, "force", False, mutable_owner=owner))
            self.assertEqual("mode-unresolved", PI._merge_claude_main_agent_settings(
                self.source, settings, "unresolved", True, mutable_owner=owner))
            self.assertEqual(before, {p: p.read_bytes() for p in before})
            transaction.commit()
        self.assert_clean()

    def cross_owner_legacy_fixture(self):
        canonical, plan, projection, installed, backup = self.legacy_fixture(False)
        external = self.root / "external-projection"
        projection.rename(external)
        return canonical, plan, external, external / installed.name, backup

    def test_cross_owner_legacy_producer_later_failure_restores_original_and_backup_absence(self):
        canonical, plan, projection, installed, backup = self.cross_owner_legacy_fixture()
        original = PI._CreateOnlyMutablePath._identity(installed)
        primary = RuntimeError("after actual projection publication")
        with self.assertRaises(RuntimeError) as caught:
            with self.transaction([installed, backup], readonly=(backup,)) as transaction:
                home_owner = PI._CreateOnlyMutablePath(self.target, transaction, dry_run=False)
                projection_owner = PI._CreateOnlyMutablePath(projection, transaction, dry_run=False)
                PI._apply_codex_legacy_skill_projection_plan(plan, canonical, projection,
                    PI._CreateOnlyMutablePath._identity(projection), home_owner, projection_owner)
                self.assertTrue(PI._projection_resolves_to(installed, plan[0].canonical_target))
                self.assertEqual(original, PI._CreateOnlyMutablePath._identity(backup))
                raise primary
        self.assertIs(caught.exception, primary)
        self.assertEqual(original, PI._CreateOnlyMutablePath._identity(installed))
        self.assertEqual((installed / "leaf").read_bytes(), b"historical")
        self.assertFalse((self.target / "backups").exists())
        self.assert_clean()

    def test_cross_owner_legacy_producer_commit_retains_original_and_new_projection(self):
        canonical, plan, projection, installed, backup = self.cross_owner_legacy_fixture()
        original = PI._CreateOnlyMutablePath._identity(installed)
        with self.transaction([installed, backup], readonly=(backup,)) as transaction:
            home_owner = PI._CreateOnlyMutablePath(self.target, transaction, dry_run=False)
            projection_owner = PI._CreateOnlyMutablePath(projection, transaction, dry_run=False)
            PI._apply_codex_legacy_skill_projection_plan(plan, canonical, projection,
                PI._CreateOnlyMutablePath._identity(projection), home_owner, projection_owner)
            transaction.commit()
        self.assertEqual(original, PI._CreateOnlyMutablePath._identity(backup))
        self.assertEqual((backup / "leaf").read_bytes(), b"historical")
        self.assertTrue(PI._projection_resolves_to(installed, plan[0].canonical_target))
        self.assertEqual(transaction._remaining_recovery(), (None, [], []))
        self.assert_clean()


if __name__ == "__main__":
    unittest.main()
