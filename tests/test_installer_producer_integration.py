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
import runpy
import shlex
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

    def test_runtime_reminder_cache_preserves_seals_and_rollback_custody(self):
        """RC1-RC3: actual reminder imports, settled warm replacement and readback."""
        inputs = ("hooks/check-parallel-mcp-momentum.py", "scripts/agents_mode_runtime.py", "scripts/hook_common.py")
        cases = (("disabled", True, False, False, False),
                 ("replacement", True, True, False, False),
                 ("created-warm", False, True, True, False),
                 ("commit-warm", True, True, True, True))
        for name, existing, bytecode, warm, commit in cases:
            with self.subTest(case=name):
                capsule = self.root / name
                capsule.mkdir()
                source = capsule / "source"
                anchor = capsule / "anchor"
                anchor.mkdir()
                parent = anchor / "canonical" / "skills"
                target = parent / "lead"
                for relative in inputs:
                    member = source / relative
                    member.parent.mkdir(parents=True, exist_ok=True)
                    member.write_bytes((ROOT / "src.codex/skills/lead" / relative).read_bytes())
                if existing:
                    target.mkdir(parents=True)
                    (target / "old").write_bytes(b"exact original")
                original = PI._InstallTransaction._observe(target)
                selected = [parent]
                if name == "replacement":
                    logical = capsule / "provider-skills"
                    logical.symlink_to(parent, target_is_directory=True)
                    alias = PI._InstallTransaction._capture_node(logical)
                    selected.append(logical / "lead" / "old")
                tx = self.transaction(selected)
                primary = RuntimeError("PRIVATE_unrelated_primary")
                observed = None
                caught = None
                try:
                    with tx:
                        owner = PI._CreateOnlyMutablePath(anchor, tx, dry_run=False)
                        if existing:
                            owner.replace_exact_tree(Path("canonical/skills/lead"),
                                PI._tree_sha256(target, ignore_runtime_cache=True), source, ignore_runtime_cache=True)
                        else:
                            owner.create_tree(Path("canonical/skills/lead"), source, ignore_runtime_cache=True)
                        effect = tx._effects[-1]
                        sealed = dict(effect.actual)
                        modules = {key: sys.modules.pop(key, None) for key in ("hook_common", "agents_mode_runtime")}
                        old_path = list(sys.path)
                        old_bytecode = sys.dont_write_bytecode
                        try:
                            sys.dont_write_bytecode = not bytecode
                            with patch.object(sys, "stdin", io.StringIO('{"agent_id":"private-test-child"}')):
                                with self.assertRaises(SystemExit) as done:
                                    runpy.run_path(str(target / inputs[0]), run_name="__main__")
                            self.assertEqual(done.exception.code, 0)
                        finally:
                            sys.dont_write_bytecode = old_bytecode
                            sys.path[:] = old_path
                            for key, previous in modules.items():
                                sys.modules.pop(key, None)
                                if previous is not None:
                                    sys.modules[key] = previous
                        caches = sorted(target.rglob("*.pyc"))
                        self.assertEqual(bool(caches), bytecode)
                        tx.assert_effect_current(effect)
                        self.assertTrue(all(effect.actual[path] == node for path, node in sealed.items()))
                        if warm:
                            cache = caches[0]
                            old_node = tx._capture_node(cache)
                            temporary = cache.with_suffix(".pyc.temporary")
                            temporary.write_bytes(b"untrusted settled warm bytes")
                            os.replace(temporary, cache)
                            self.assertFalse(tx._point_matches(cache, old_node, check_file_content=True))
                            tx.assert_effect_current(effect)
                        observed = tx._observe(target)
                        if commit:
                            tx.commit()
                        else:
                            raise primary
                except BaseException as error:
                    caught = error
                self.assertIs(caught, None if commit else primary)
                if commit:
                    self.assertTrue(tx._image_matches(target, observed))
                    self.assertIsNone(effect.quarantine_state)
                else:
                    self.assertTrue(tx._image_matches(target, original))
                    if name == "replacement":
                        self.assertTrue(tx._point_matches(logical, alias))
                        self.assertEqual((logical / "lead" / "old").read_bytes(), b"exact original")
                    if bytecode:
                        self.assertTrue(effect.settled)
                        self.assertTrue(tx._image_matches(effect.quarantine,
                            tx._relocate(observed, target, effect.quarantine)))
                        self.assertIsNone(tx._remaining_recovery()[0])
                        self.assertIn("retained-current=", PI._installer_failure_text(primary))
                        if not existing:
                            self.assertFalse(target.exists())
                            self.assertTrue(parent.is_dir())
                            self.assertTrue(any(record.disposition == "custody-support" for record in tx._slice_a_created))
                    else:
                        self.assertFalse(list(parent.glob("*.after")))

    def test_runtime_cache_does_not_authorize_generic_disposal_or_unknown_members(self):
        (self.source / "body.py").write_bytes(b"authored")
        tx = self.transaction([])
        primary = RuntimeError("private failure")
        with self.assertRaises(PI._InstallFailure):
            with tx:
                target = self.owner(tx).create_tree(Path("target/lead"), self.source, ignore_runtime_cache=True)
                effect = tx._effects[-1]
                cache = target / "__pycache__"
                cache.mkdir()
                (cache / "body.pyc").write_bytes(b"unproved cache bytes")
                tx.assert_effect_current(effect)
                with self.assertRaisesRegex(ValueError, "observed runtime disposal"):
                    tx._dispose_image(target, effect.actual)
                (cache / "operator-note.txt").write_bytes(b"preserve unknown")
                raise primary
        self.assertEqual((cache / "operator-note.txt").read_bytes(), b"preserve unknown")
        self.assertEqual((target / "body.py").read_bytes(), b"authored")

    def test_runtime_selection_preserves_sealed_and_unknown_member_refusals(self):
        for name in ("disabled", "changed", "missing", "foreign-native", "sealed-cache", "temporary", "reparse"):
            with self.subTest(case=name):
                capsule = self.root / name
                capsule.mkdir()
                source = capsule / "source"
                source.mkdir()
                (source / "body.py").write_bytes(b"sealed bytes")
                tx = self.transaction([])
                sentinel = capsule / "outside"
                sentinel.write_bytes(b"outside untouched")
                with self.assertRaises(PI._InstallFailure):
                    with tx:
                        owner = PI._CreateOnlyMutablePath(capsule, tx, dry_run=False)
                        target = owner.create_tree(Path("lead"), source, ignore_runtime_cache=name != "disabled")
                        effect = tx._effects[-1]
                        if name == "changed":
                            (target / "body.py").write_bytes(b"changed bytes")
                        elif name == "missing":
                            (target / "body.py").unlink()
                        elif name == "foreign-native":
                            (target / "body.py").rename(capsule / "preserved-original")
                            (target / "body.py").write_bytes(b"sealed bytes")
                        elif name == "sealed-cache":
                            cache = owner.create_file(Path("lead/__pycache__/sealed.pyc"), b"sealed cache")
                            cache.write_bytes(b"changed cache")
                        else:
                            cache = target / "__pycache__"
                            if name == "reparse":
                                cache.symlink_to(source, target_is_directory=True)
                            else:
                                cache.mkdir()
                                (cache / ("body.pyc.temporary" if name == "temporary" else "body.pyc")).write_bytes(b"unknown")
                        with self.assertRaises(ValueError):
                            tx.assert_effect_current(effect)
                        raise RuntimeError("independent private primary")
                self.assertEqual(sentinel.read_bytes(), b"outside untouched")

    def test_custody_support_refuses_foreign_sibling_and_settles_disjoint_effect(self):
        (self.source / "body.py").write_bytes(b"authored")
        safe = self.target / "safe"
        safe.write_bytes(b"safe original")
        old_safe = PI._InstallTransaction._capture_node(safe)
        tx = self.transaction([self.target / "created", safe])
        with self.assertRaises(PI._InstallFailure) as caught:
            with tx:
                owner = self.owner(tx)
                owner.replace_exact_file(Path("target/safe"), PI._file_sha256(safe), b"safe new")
                target = owner.create_tree(Path("target/created/skills/lead"), self.source, ignore_runtime_cache=True)
                cache = target / "__pycache__"
                cache.mkdir()
                (cache / "body.pyc").write_bytes(b"observed")
                (target.parent / "foreign-note").write_bytes(b"preserve sibling")
                raise RuntimeError("private primary")
        self.assertTrue(tx._point_matches(safe, old_safe, check_file_content=True))
        self.assertFalse(target.exists())
        self.assertEqual((target.parent / "foreign-note").read_bytes(), b"preserve sibling")
        self.assertTrue(any(member.phase == "created" for member in caught.exception.members))
        self.assertTrue(tx._effects[-1].quarantine_state)

    def test_settled_custody_reentry_rechecks_exact_retained_image(self):
        (self.source / "body.py").write_bytes(b"authored")
        tx = self.transaction([])
        primary = RuntimeError("private unrelated primary")
        with self.assertRaises(RuntimeError) as caught:
            with tx:
                target = self.owner(tx).create_tree(Path("target/created/lead"), self.source, ignore_runtime_cache=True)
                cache = target / "__pycache__"
                cache.mkdir()
                (cache / "body.pyc").write_bytes(b"observed bytes")
                raise primary
        self.assertIs(caught.exception, primary)
        self.assertEqual(tx._settle_effects(), ([], [], ()))
        effect = tx._effects[-1]
        (effect.quarantine / "body.py").write_bytes(b"changed custody")
        unresolved, failures, _errors = tx._settle_effects()
        self.assertTrue(unresolved)
        self.assertTrue(failures)
        self.assertEqual((effect.quarantine / "body.py").read_bytes(), b"changed custody")

    def test_runtime_custody_move_refuses_occupied_destination_and_post_acquisition_change(self):
        for case in ("occupied", "changed-before-move"):
            with self.subTest(case=case):
                capsule = self.root / case
                capsule.mkdir()
                source = capsule / "source"
                source.mkdir()
                (source / "body.py").write_bytes(b"new authored")
                target = capsule / "lead"
                target.mkdir()
                (target / "body.py").write_bytes(b"old original")
                old = PI._InstallTransaction._observe(target)
                tx = self.transaction([target])
                primary = RuntimeError("private primary")
                native_move = tx._native_publish_no_replace
                injected = []
                def move(source_path, destination, **kwargs):
                    if source_path == target and destination.name.endswith(".after"):
                        (source_path / "__pycache__/raced.pyc").write_bytes(b"unobserved race bytes")
                        injected.append(True)
                    return native_move(source_path, destination, **kwargs)
                with self.assertRaises(PI._InstallFailure) as caught:
                    with patch.object(tx, "_native_publish_no_replace",
                                      side_effect=move if case == "changed-before-move" else native_move), tx:
                        owner = PI._CreateOnlyMutablePath(capsule, tx, dry_run=False)
                        owner.replace_exact_tree(Path("lead"), PI._tree_sha256(target), source, ignore_runtime_cache=True)
                        effect = tx._effects[-1]
                        cache = target / "__pycache__"
                        cache.mkdir()
                        (cache / "body.pyc").write_bytes(b"observed")
                        tx.assert_effect_current(effect)
                        if case == "occupied":
                            destination = effect.retained.with_name(effect.retained.name + ".after")
                            destination.write_bytes(b"foreign occupied destination")
                        raise primary
                self.assertIs(caught.exception.cause, primary)
                self.assertTrue(tx._image_matches(effect.retained, tx._relocate(old, target, effect.retained)))
                if case == "occupied":
                    self.assertEqual(destination.read_bytes(), b"foreign occupied destination")
                    self.assertEqual((target / "body.py").read_bytes(), b"new authored")
                else:
                    self.assertEqual(injected, [True])
                    self.assertEqual((effect.quarantine / "__pycache__/raced.pyc").read_bytes(), b"unobserved race bytes")

    def test_typed_recovery_rewrap_preserves_custody_and_exact_primary_fields(self):
        for committed in (False, True):
            with self.subTest(committed=committed):
                capsule = self.root / ("committed-rewrap" if committed else "rollback-rewrap")
                capsule.mkdir()
                source = capsule / "source"
                source.mkdir()
                (source / "body.py").write_bytes(b"authored")
                tx = self.transaction([])
                cause = ValueError("PRIVATE_rewrap_cause")
                member = PI._RollbackFailureMember("backup", 7, "PRIVATE_member_path",
                    "E_ROLLBACK_BACKUP_CLEANUP_FAILED", "PRIVATE_member_cause", participant="backup")
                primary = PI._InstallFailure("E_HOOK_HEALTH_FAILED", "health", cause,
                    members=(member,), recovery_path=capsule / "PRIVATE_obsolete_recovery")
                original = str(primary)
                with self.assertRaises(PI._InstallFailure) as caught:
                    with tx:
                        owner = PI._CreateOnlyMutablePath(capsule, tx, dry_run=False)
                        target = owner.create_tree(Path("lead"), source, ignore_runtime_cache=True)
                        (target / "__pycache__").mkdir()
                        (target / "__pycache__/body.pyc").write_bytes(b"observed")
                        if committed:
                            self.assertEqual(tx._settle_effects(), ([], [], ()))
                            tx.commit()
                        raise primary
                final = caught.exception
                self.assertIsNot(final, primary)
                self.assertIs(final.__cause__, primary)
                self.assertIs(final.cause, cause)
                self.assertIs(final.members, primary.members)
                self.assertIs(final.members[0], member)
                self.assertIsNone(final.recovery_path)
                self.assertEqual(str(primary), original)
                self.assertFalse(target.exists())
                effect = tx._effects[-1]
                self.assertTrue(tx._image_matches(effect.quarantine, effect.quarantine_state))
                public = PI._installer_failure_text(final)
                self.assertEqual(public.count("retained-current="), 1)
                self.assertNotIn("PRIVATE", public)

    def test_public_custody_currentness_keeps_prior_settlement_distinct_from_later_refusal(self):
        (self.source / "body.py").write_bytes(b"authored")
        for case in ("unchanged", "changed-custody", "changed-target"):
            with self.subTest(case=case):
                capsule = self.root / case
                capsule.mkdir()
                parent = capsule / "created/skills"
                tx = self.transaction([parent])
                primary = RuntimeError("PRIVATE_reentry_primary")
                escaped = None
                try:
                    with tx:
                        owner = PI._CreateOnlyMutablePath(capsule, tx, dry_run=False)
                        target = owner.create_tree(Path("created/skills/lead"), self.source, ignore_runtime_cache=True)
                        (target / "__pycache__").mkdir()
                        (target / "__pycache__/body.pyc").write_bytes(b"observed")
                        self.assertEqual(tx._settle_effects(), ([], [], ()))
                        effect = tx._effects[-1]
                        self.assertTrue(effect.settled)
                        self.assertTrue(tx._image_matches(effect.quarantine, effect.quarantine_state))
                        if case == "changed-custody":
                            (effect.quarantine / "body.py").write_bytes(b"later changed custody")
                        elif case == "changed-target":
                            target.mkdir()
                            (target / "foreign").write_bytes(b"later foreign target")
                        raise primary
                except BaseException as error:
                    escaped = error
                self.assertTrue(effect.settled)  # The actual earlier event remains recorded.
                self.assertIs(escaped if case == "unchanged" else escaped.cause, primary)
                stderr = io.StringIO()
                with patch.object(PI, "_target", side_effect=escaped), contextlib.redirect_stderr(stderr):
                    code = PI.install("claude", ["--target", str(capsule)])
                public = stderr.getvalue()
                self.assertEqual(code, 1)
                self.assertIn("prior-settlement:complete", public)
                if case == "unchanged":
                    self.assertIn("current-verification:verified", public)
                    self.assertIn("disposition:preserved;target-restoration:complete", public)
                else:
                    self.assertIn("current-verification:refused", public)
                    self.assertNotIn("disposition:preserved", public)
                    self.assertNotIn("target-restoration:complete", public)
                    self.assertTrue(all(member.participant in {"created", "snapshot", "effect", "backup"}
                                        for member in escaped.members))
                self.assertNotIn("PRIVATE", public)
                self.assertNotIn(str(capsule), public)

    def test_actual_direct_effect_failures_have_effect_and_created_domains(self):
        (self.source / "body.py").write_bytes(b"authored")
        tx = PI._InstallTransaction([], enabled=False)
        primary = RuntimeError("PRIVATE_direct_primary")
        with self.assertRaises(PI._InstallFailure) as caught:
            with tx.direct_operation():
                target = self.owner(tx).create_tree(Path("target/lead"), self.source, ignore_runtime_cache=True)
                (target / "body.py").write_bytes(b"foreign drift")
                raise primary
        self.assertIs(caught.exception.cause, primary)
        effects = [member for member in caught.exception.members if member.phase == "snapshot"]
        self.assertTrue(effects)
        self.assertTrue(all(member.participant == "effect" for member in effects))
        self.assertTrue(all(member.participant == "created" for member in caught.exception.members if member.phase == "created"))
        public = PI._installer_failure_text(caught.exception)
        self.assertIn("participant:effect", public)
        self.assertNotIn("PRIVATE", public)

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

    def test_sdk_runtime_delivery_is_complete_and_rollback_preserves_unmanaged_files(self):
        """Use the real delivery inventory and copy owner, without invoking providers."""
        expected = {f"sdk_execution/{path.name}" for path in
                    (ROOT / "scripts/sdk_execution").glob("*.py")}
        expected.add("process_supervision/sdk_worker.py")
        self.assertTrue(expected)
        for host, relative in (("codex", "skills/lead/scripts"),
                               ("claude", "agents/scripts")):
            with self.subTest(host=host):
                target = self.target / host / relative
                destinations = PI._runtime_file_destinations(
                    ROOT, target, include_codex_helpers=host == "codex")
                selected = tuple((source, dest) for source, dest in destinations
                                 if source.is_relative_to(ROOT / "scripts")
                                 if source.relative_to(ROOT / "scripts").as_posix() in expected)
                self.assertEqual(expected, {dest.relative_to(target).as_posix()
                                            for _, dest in selected})
                sentinel = target / "sdk_execution/operator-local.txt"
                sentinel.parent.mkdir(parents=True)
                sentinel.write_bytes(b"preserve operator file")
                existing = target / "sdk_execution/contracts.py"
                existing.write_bytes(b"prior installed contracts")
                os.utime(existing, ns=(1_600_000_000_100_000_000, 1_600_000_000_200_000_000))
                prior_mtime = existing.stat().st_mtime_ns
                transaction = self.transaction([dest for _, dest in selected],
                                               [dest for _, dest in selected])
                with self.assertRaisesRegex(RuntimeError, "later producer failure"):
                    with transaction:
                        PI._install_runtime_files(ROOT, target, False,
                            destinations=selected, mutable_owner=self.owner(transaction))
                        for source, dest in selected:
                            self.assertEqual(source.read_bytes(), dest.read_bytes())
                        self.assertEqual(b"preserve operator file", sentinel.read_bytes())
                        raise RuntimeError("later producer failure")
                self.assertTrue(all(not dest.exists() for _, dest in selected if dest != existing))
                self.assertEqual(b"prior installed contracts", existing.read_bytes())
                self.assertEqual(prior_mtime, existing.stat().st_mtime_ns)
                self.assertEqual(b"preserve operator file", sentinel.read_bytes())
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

    def test_claude_instructions_preserve_custom_on_success_rerun_and_rollback(self):
        for scope in ("agents", "commands"):
            with self.subTest(scope=scope):
                source = self.source / scope
                target = self.target / scope
                source.mkdir()
                target.mkdir()
                for name in ("custom.md", "equal.md", "new.md"):
                    (source / name).write_bytes(b"---\nname: stock\n---\nstock body\n")
                custom = target / "custom.md"
                original = b"---\nname: user\nextra: retained\n---\nuser body\n"
                custom.write_bytes(original)
                equal = target / "equal.md"
                equal.write_bytes((source / "equal.md").read_bytes())
                new = target / "new.md"
                paths = [custom, equal, new]
                for _ in range(2):
                    with self.transaction(paths, paths) as transaction:
                        PI._sync_tree(source, target, False, mutable_owner=self.owner(transaction),
                                      instruction_scope=scope)
                        transaction.commit()
                    self.assertEqual(original, custom.read_bytes())
                    self.assertEqual((source / "equal.md").read_bytes(), equal.read_bytes())
                    self.assertEqual((source / "new.md").read_bytes(), new.read_bytes())
                new.unlink()
                with self.assertRaisesRegex(RuntimeError, "forced failure"):
                    with self.transaction(paths, paths) as transaction:
                        PI._sync_tree(source, target, False, mutable_owner=self.owner(transaction),
                                      instruction_scope=scope)
                        raise RuntimeError("forced failure")
                self.assertFalse(new.exists())
                self.assertEqual(original, custom.read_bytes())
        self.assert_clean()

    def test_unowned_stale_file_tree_and_link_are_preserved(self):
        commands = self.target / "commands"
        skills = self.target / "skills"
        commands.mkdir()
        skills.mkdir()
        stale_file = commands / "agents-stale.md"
        stale_tree = skills / "agents-stale"
        stale_file.write_bytes(b"user stale file")
        stale_tree.mkdir()
        (stale_tree / "leaf").write_bytes(b"user stale tree")
        link = skills / "agents-link"
        link.symlink_to(stale_tree.name, target_is_directory=True)
        original = {p: PI._CreateOnlyMutablePath._identity(p) for p in (stale_file, stale_tree, link)}
        with self.transaction([]) as transaction:
            owner = self.owner(transaction)
            PI._reclaim_claude_namespace(self.source, commands, skills, False,
                                         commands_owner=owner, skills_owner=owner)
            transaction.commit()
        self.assertEqual(original, {p: PI._CreateOnlyMutablePath._identity(p) for p in original})
        self.assertEqual(b"user stale file", stale_file.read_bytes())
        self.assertEqual(b"user stale tree", (stale_tree / "leaf").read_bytes())
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

    def test_instruction_copy_race_is_refused_and_preserved(self):
        source = self.source / "commands"
        target = self.target / "commands"
        source.mkdir()
        target.mkdir()
        (source / "new.md").write_bytes(b"stock")
        destination = target / "new.md"
        transaction = self.transaction([destination], [destination])
        with self.assertRaises(PI._InstallFailure):
            with transaction:
                destination.write_bytes(b"concurrent user")
                PI._sync_tree(source, target, False, mutable_owner=self.owner(transaction),
                              instruction_scope="commands")
        self.assertEqual(b"concurrent user", destination.read_bytes())

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
        selection, config_payload = PI._read_native_config_selection(
            config, PI._InstallTransaction([], enabled=False))
        plan = SimpleNamespace(config_exists=True, config_prior_digest=PI._file_sha256(config),
                               config_selection=selection, config_payload=config_payload,
                               legacy_exists=True, legacy_path=legacy)
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
        canonical = PI._CanonicalSkillPlan(
            name="skill", source=canonical_source,
            source_digest=PI._tree_sha256(canonical_source),
            installed_digest=PI._tree_sha256(canonical_target),
            accepted_prior=None, ignore_runtime_cache=False)
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
                if original.native_proof is not None:
                    self.assertNotEqual(original.native_proof, foreign.native_proof)
                else:
                    self.assertNotEqual(original.python_identity[:2], foreign.python_identity[:2])
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
        self.assertIsInstance(failure.cause, ValueError)
        self.assertTrue(str(failure.cause).startswith("E_READ_ONLY_DEPENDENCY_CHANGED:"))
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
        with self.assertRaises(PI._InstallFailure) as caught:
            with transaction:
                member = backup / "leaf"
                before = transaction._original[backup][member]
                member.rename(self.root / "original-backup-member")
                member.write_bytes(b"historical")
                foreign = transaction._capture_node(member, kind="file", data=before.data)
                if before.native_proof is not None:
                    self.assertNotEqual(before.native_proof, foreign.native_proof)
                else:
                    self.assertNotEqual(before.python_identity[:2], foreign.python_identity[:2])
                def observed(path, **kwargs):
                    if Path(path) == backup:
                        reads.append(path)
                    return digest(path, **kwargs)
                with patch.object(PI, "_tree_sha256", observed):
                    owner = self.owner(transaction)
                    PI._apply_codex_legacy_skill_projection_plan(plan, canonical, projection,
                        PI._CreateOnlyMutablePath._identity(projection), owner, owner)
        self.assertIsInstance(caught.exception.cause, ValueError)
        self.assertTrue(str(caught.exception.cause).startswith("E_READ_ONLY_DEPENDENCY_CHANGED:"))
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
        self.assertEqual(transaction._remaining_recovery(), (None, [], [], ()))
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
        self.assertEqual(transaction._remaining_recovery(), (None, [], [], ()))
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
        new_skill = PI._CanonicalSkillPlan(
            name="collision", source=collision_source,
            source_digest=PI._tree_sha256(collision_source), installed_digest=None,
            accepted_prior=None, ignore_runtime_cache=False)
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
        self.assertEqual(transaction._remaining_recovery(), (None, [], [], ()))
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

    def test_claude_missing_documents_create_bounded_source(self):
        pack = self.documentation_fixture()
        target, agents = self.target / "CLAUDE.md", self.target / "AGENTS.md"
        with self.transaction([target, agents]) as transaction:
            PI._merge_claude_docs(self.source, pack, target, True, mutable_owner=self.owner(transaction))
            self.assertFalse(target.exists())
            self.assertFalse(agents.exists())
            PI._merge_claude_docs(self.source, pack, target, False, mutable_owner=self.owner(transaction))
            transaction.commit()
        self.assertEqual("@AGENTS.md\n<!-- BEGIN ORCHESTRARIUM CLAUDE MANAGED -->\n# Claude Code Pack\n<!-- END ORCHESTRARIUM CLAUDE MANAGED -->\n", target.read_text())
        self.assertEqual("<!-- BEGIN ORCHESTRARIUM SHARED MANAGED -->\n# Shared Governance\nnew shared\n<!-- END ORCHESTRARIUM SHARED MANAGED -->\n", agents.read_text())
        self.assert_clean()

    def test_claude_documents_preserve_foreign_text_across_commits(self):
        pack = self.documentation_fixture()
        target, agents = self.target / "CLAUDE.md", self.target / "AGENTS.md"
        originals = {target: "@foreign.md\nlocal Claude rules\n", agents: "local shared rules\n"}
        for path, text in originals.items():
            path.write_text(text, encoding="utf-8")
        for cycle in range(2):
            with self.transaction([target, agents]) as transaction:
                PI._merge_claude_docs(self.source, pack, target, False, mutable_owner=self.owner(transaction))
                transaction.commit()
            for path, text in originals.items():
                self.assertTrue(path.read_text().endswith("\n" + text), (cycle, path))
        for path in originals:
            self.assertEqual(1, path.read_text().count("<!-- BEGIN ORCHESTRARIUM"))
        self.assert_clean()

    def test_claude_current_stock_imports_and_policies_survive_migration(self):
        target, agents = self.target / "CLAUDE.md", self.target / "AGENTS.md"
        source = (ROOT / 'adapters/claude/CLAUDE.md').read_text()
        anchor, body = source.split("\n", 1)
        shared = (ROOT / "shared/AGENTS.shared.md").read_text()
        prefix = "@before.md\n" + anchor + "\nKeep my rule between imports and the pack.\n@my-notes.md\n@AGENTS.md\n@second-notes.md  \n\n"
        suffix = "\n## Project policies\nKeep my rule.\n@after.md\n"
        target.write_text(prefix + body + suffix)
        agents.write_text("local prefix\n" + shared + "local suffix\n")
        expected = prefix + "<!-- BEGIN ORCHESTRARIUM CLAUDE MANAGED -->\n" + body + "<!-- END ORCHESTRARIUM CLAUDE MANAGED -->\n" + suffix
        for _ in range(2):
            with self.transaction([target, agents]) as transaction:
                PI._merge_claude_docs(ROOT, ROOT / 'adapters/claude', target, False, mutable_owner=self.owner(transaction))
                transaction.commit()
            self.assertEqual(expected, target.read_text())
            self.assertEqual("local prefix\n<!-- BEGIN ORCHESTRARIUM SHARED MANAGED -->\n" + shared + "<!-- END ORCHESTRARIUM SHARED MANAGED -->\nlocal suffix\n", agents.read_text())
        self.assert_clean()

    def test_claude_user_imports_and_prose_survive_first_and_later_installs(self):
        pack = self.documentation_fixture()
        target, agents = self.target / "CLAUDE.md", self.target / "AGENTS.md"
        originals = ("@AGENTS.md\nKeep my project rule.\n",
                     "User prefix\n@AGENTS.md\nold pack\n@other.md\nTail.\n",
                     "@AGENTS.md\n@AGENTS.md\nKeep both user imports.\n",
                     "User prefix\n@AGENTS.md")
        for original in originals:
            with self.subTest(original=original):
                target.write_bytes(original.replace("\n", "\r\n").encode())
                agents.write_bytes(b"User shared prefix\r\n")
                for cycle in range(2):
                    with self.transaction([target, agents]) as transaction:
                        PI._merge_claude_docs(self.source, pack, target, False, mutable_owner=self.owner(transaction))
                        transaction.commit()
                    text = target.read_text()
                    begin = "<!-- BEGIN ORCHESTRARIUM CLAUDE MANAGED -->\n"
                    end = "<!-- END ORCHESTRARIUM CLAUDE MANAGED -->\n"
                    before, body = text.split(begin)
                    _body, after = body.split(end)
                    self.assertEqual(original, before + after)
                    self.assertEqual(original.count("@AGENTS.md"), text.count("@AGENTS.md"))
                    self.assertNotIn(b"\r", target.read_bytes())
                changed = text + ("" if text.endswith("\n") else "\n") + "@AGENTS.md\nLater user import.\n"
                target.write_text(changed)
                with self.transaction([target, agents]) as transaction:
                    PI._merge_claude_docs(self.source, pack, target, False, mutable_owner=self.owner(transaction))
                    transaction.commit()
                self.assertEqual(changed, target.read_text())
        self.assert_clean()

    def test_claude_managed_region_preserves_arbitrary_outside_text(self):
        pack = self.documentation_fixture()
        target, agents = self.target / "CLAUDE.md", self.target / "AGENTS.md"
        begin = "<!-- BEGIN ORCHESTRARIUM CLAUDE MANAGED -->\n"
        end = "<!-- END ORCHESTRARIUM CLAUDE MANAGED -->\n"
        prefix = "User prefix\n@AGENTS.md\nLocal rule between anchor and region.\n@notes.md\n"
        suffix = "@AGENTS.md\nUser tail\n@more.md\n"
        target.write_text(prefix + begin + "old body\n" + end + suffix)
        agents.write_text("User shared prefix\n")
        for _ in range(2):
            with self.transaction([target, agents]) as transaction:
                PI._merge_claude_docs(self.source, pack, target, False, mutable_owner=self.owner(transaction))
                transaction.commit()
            self.assertEqual(prefix + begin + "# Claude Code Pack\n" + end + suffix, target.read_text())
        (pack / "CLAUDE.md").write_text("@AGENTS.md\nchanged body\n")
        with self.transaction([target, agents]) as transaction:
            PI._merge_claude_docs(self.source, pack, target, False, mutable_owner=self.owner(transaction))
            transaction.commit()
        self.assertEqual(prefix + begin + "changed body\n" + end + suffix, target.read_text())
        self.assert_clean()

    def test_claude_code_examples_do_not_supply_the_required_active_import(self):
        pack = self.documentation_fixture()
        target, agents = self.target / "CLAUDE.md", self.target / "AGENTS.md"
        examples = ("```text\n@AGENTS.md\n```\nUser rule.\n",
                    "`example\n2. literal continuation\n@AGENTS.md\n`\n",
                    "~~~text\n@AGENTS.md\n~~~\nUser rule.\n",
                    "`example\n@AGENTS.md\n`\nUser rule.\n",
                    "- `example\n@AGENTS.md\n`\n",
                    "> `example\n@AGENTS.md\n`\n",
                    "- `example\n  @AGENTS.md\n  `\n",
                    "> `example\n> @AGENTS.md\n> `\n",
                    "1. `example\n@AGENTS.md\n`\n",
                    "> > `example\n> > @AGENTS.md\n> > `\n")
        for original in examples:
            with self.subTest(example=original):
                (pack / "CLAUDE.md").write_text("@AGENTS.md\n# Claude Code Pack\n")
                target.write_text(original)
                agents.write_text("User shared rule.\n")
                for cycle in range(3):
                    if cycle == 2:
                        (pack / "CLAUDE.md").write_text("@AGENTS.md\nUpdated pack body.\n")
                    with self.transaction([target, agents]) as transaction:
                        PI._merge_claude_docs(self.source, pack, target, False, mutable_owner=self.owner(transaction))
                        transaction.commit()
                    text = target.read_text()
                    self.assertTrue(text.startswith("@AGENTS.md\n<!-- BEGIN ORCHESTRARIUM CLAUDE MANAGED -->\n"))
                    self.assertTrue(text.endswith("\n" + original))
                    self.assertEqual(2, text.count("@AGENTS.md"))
                    self.assertIn("Updated pack body.\n" if cycle == 2 else "# Claude Code Pack\n", text)
        self.assert_clean()

    def test_claude_context_resolves_blocks_before_inline_code(self):
        inactive = ("````md\n```\n@AGENTS.md\n```\n````\n",
                    "~~~md\n@AGENTS.md\n~~~~\n",
                    "`same paragraph\n@AGENTS.md\n`\n",
                    "``one ` within a span\n@AGENTS.md\n``\n",
                    "```md\n@AGENTS.md\n",
                    "    @AGENTS.md\n",
                    "- `example\n@AGENTS.md\n`\n",
                    "> `example\n@AGENTS.md\n`\n",
                    "- `example\n  @AGENTS.md\n  `\n",
                    "> `example\n> @AGENTS.md\n> `\n")
        active = ("Unmatched ` first.\n\n@AGENTS.md\nLast `.\n",
                  "Unmatched ` first.\n# Heading with `.\n@AGENTS.md\n",
                  "Unmatched ` first.\n~~~text\nexample `\n~~~\n@AGENTS.md\n",
                  "Escaped \\` first.\n@AGENTS.md\nLast `.\n",
                  "- Unmatched ` first.\n\n@AGENTS.md\nLast `.\n",
                  "> Unmatched ` first.\n\n@AGENTS.md\nLast `.\n",
                  "> Unmatched ` first.\n>\n@AGENTS.md\nLast `.\n",
                  "Unmatched ` first.\n- A new paragraph with `.\n@AGENTS.md\n",
                  "Unmatched ` first.\n> A new paragraph with `.\n@AGENTS.md\n",
                  "- Unmatched ` first.\n- Another item with `.\n@AGENTS.md\n",
                  "> Unmatched ` first.\n> # Heading with `.\n@AGENTS.md\n")
        for expected, examples in ((False, inactive), (True, active)):
            for original in examples:
                with self.subTest(text=original, active=expected):
                    visible, _ = PI._claude_document_context(original)
                    self.assertEqual(len(original), len(visible))
                    self.assertEqual([i for i, c in enumerate(original) if c == "\n"],
                                     [i for i, c in enumerate(visible) if c == "\n"])
                    self.assertEqual(expected, "@AGENTS.md" in visible)
        quoted = "`<!-- BEGIN ORCHESTRARIUM SHARED MANAGED -->`\n"
        self.assertNotIn("<!--", PI._claude_document_context(quoted)[0])

    def test_claude_quoted_fence_keeps_plain_import_and_both_owned_bodies_active(self):
        pack = self.documentation_fixture()
        target, agents = self.target / "CLAUDE.md", self.target / "AGENTS.md"
        prefix = "> ```text\n@AGENTS.md\n> ```\n"
        originals = {}
        for path, kind in ((target, "CLAUDE"), (agents, "SHARED")):
            old_body = ("# Claude Code Pack" if kind == "CLAUDE" else "# Shared Governance") + "\nold active rule\n"
            text = prefix + f"<!-- BEGIN ORCHESTRARIUM {kind} MANAGED -->\n" + old_body + f"<!-- END ORCHESTRARIUM {kind} MANAGED -->\n"
            originals[path] = (text, old_body)
            path.write_bytes(text.replace("\n", "\r\n").encode())
        for body in ("new body\n", "new body\n", "updated body\n"):
            (pack / "CLAUDE.md").write_text("@AGENTS.md\n" + body)
            (self.source / "shared/AGENTS.shared.md").write_text(body)
            with self.transaction([target, agents]) as transaction:
                PI._merge_claude_docs(self.source, pack, target, False, mutable_owner=self.owner(transaction))
                transaction.commit()
            for path, (original, old_body) in originals.items():
                self.assertEqual(original.replace(old_body, body), path.read_text())
        self.assert_clean()

    def test_claude_parser_lifts_original_spans_and_avoids_default_nesting_cutoff(self):
        cases = (
            ("![`x`](one) ![`x`](two)\n", [(2, 5), (14, 17)]),
            ("[x](`x`) ![`x`](dest)\n", [(11, 14)]),
            ("- x\n\n\t`α\n\ty`\n", [(6, 12)]),
            ("𝄞\t![`x`](one) ![`x`](two)\n", [(4, 7), (16, 19)]),
            ("é\t`α\r\ny`\r\n".replace("\r\n", "\n"), [(2, 7)]),
            ("![![`x`](inner)](outer)\n", [(4, 7)]),
            ("![`x`](bad space)\n", [(2, 5)]),
            ("<a title=\"`x`\"> `y`</a>\n", [(16, 19)]),
            ("unmatched `\n", []),
        )
        for source, expected in cases:
            with self.subTest(source=source):
                visible, spans = PI._claude_document_context(source)
                self.assertEqual(expected, spans)
                self.assertEqual(len(source), len(visible))
                self.assertEqual([i for i, char in enumerate(source) if char == "\n"],
                                 [i for i, char in enumerate(visible) if char == "\n"])
                for index, char in enumerate(source):
                    if not any(begin <= index < end for begin, end in spans):
                        self.assertEqual(char, visible[index])
        prefix = "> " * 24
        source = prefix + "`@AGENTS.md`\n\n@AGENTS.md\n"
        visible, spans = PI._claude_document_context(source)
        self.assertEqual([(len(prefix), len(prefix) + len("`@AGENTS.md`"))], spans)
        self.assertTrue(visible.endswith("\n\n@AGENTS.md\n"))
        source = prefix + "```text\n" + prefix + "@AGENTS.md\n" + prefix + "```\n"
        self.assertEqual([(0, len(source))], PI._claude_document_context(source)[1])

    def test_claude_stock_link_destination_dialect_keeps_dependency_and_zero_write_contract(self):
        pack = self.documentation_fixture()
        target, agents = self.target / "CLAUDE.md", self.target / "AGENTS.md"
        begin = "<!-- BEGIN ORCHESTRARIUM CLAUDE MANAGED -->\n"
        end = "<!-- END ORCHESTRARIUM CLAUDE MANAGED -->\n"
        for depth, active_control, valid in ((32, False, True), (33, False, False), (33, True, True)):
            with self.subTest(depth=depth, active_control=active_control):
                prefix = "[x](" + "(" * depth + "`" + ")" * depth + ")\n@AGENTS.md\n`\n\n"
                if active_control:
                    prefix += "@AGENTS.md\n\n"
                original = prefix + begin + "OLD PACK\n" + end
                target.write_bytes(original.replace("\n", "\r\n").encode())
                agents.write_bytes(b"User shared rules\r\n")
                if not valid:
                    self.assertEqual([(37, 85)], PI._claude_document_context(original)[1])
                    raw = {path: path.read_bytes() for path in (target, agents)}
                    with self.transaction([target, agents]) as transaction:
                        with patch.object(PI, "_write_owned_text", wraps=PI._write_owned_text) as write:
                            with self.assertRaisesRegex(ValueError, "E_CLAUDE_DOC_MARKERS_INVALID: CLAUDE.md"):
                                PI._merge_claude_docs(self.source, pack, target, False, mutable_owner=self.owner(transaction))
                            write.assert_not_called()
                        self.assertEqual(raw, {path: path.read_bytes() for path in raw})
                        transaction.commit()
                else:
                    for body in ("new body\n", "new body\n", "updated body\n"):
                        (pack / "CLAUDE.md").write_text("@AGENTS.md\n" + body)
                        with self.transaction([target, agents]) as transaction:
                            PI._merge_claude_docs(self.source, pack, target, False, mutable_owner=self.owner(transaction))
                            transaction.commit()
                        self.assertEqual(prefix + begin + body + end, target.read_text())
        self.assert_clean()

    def test_claude_parser_acquisition_failure_before_second_render_writes_neither_document(self):
        pack = self.documentation_fixture()
        target, agents = self.target / "CLAUDE.md", self.target / "AGENTS.md"
        target.write_bytes(b"@AGENTS.md\r\nUser rule\r\n")
        agents.write_bytes(b"Shared user rule\r\n")
        raw = {path: path.read_bytes() for path in (target, agents)}
        primary = RecursionError("synthetic parser resource failure")
        first_context = PI._claude_document_context(target.read_text())
        with self.transaction([target, agents]) as transaction:
            with patch.object(PI, "_markdown_document_context", side_effect=[first_context, primary]):
                with patch.object(PI, "_write_owned_text", wraps=PI._write_owned_text) as write:
                    with self.assertRaises(RecursionError) as caught:
                        PI._merge_claude_docs(self.source, pack, target, False, mutable_owner=self.owner(transaction))
                    self.assertIs(primary, caught.exception)
                    write.assert_not_called()
            self.assertEqual(raw, {path: path.read_bytes() for path in raw})
            transaction.commit()
        self.assert_clean()

    def test_claude_multiline_reference_keeps_stock_heading_and_user_example(self):
        pack = self.documentation_fixture()
        target, agents = self.target / "CLAUDE.md", self.target / "AGENTS.md"
        originals = {}
        for path, kind in ((target, "CLAUDE"), (agents, "SHARED")):
            example = f'[a]: /url "title\n# `<!-- BEGIN ORCHESTRARIUM {kind} MANAGED -->`\nend"\n'
            original = ("@AGENTS.md\n" if path == target else "") + example
            originals[path] = original
            path.write_text(original)
        for cycle in range(3):
            if cycle == 2:
                (pack / "CLAUDE.md").write_text("@AGENTS.md\nUpdated body.\n")
                (self.source / "shared/AGENTS.shared.md").write_text("Updated shared body.\n")
            with self.transaction([target, agents]) as transaction:
                PI._merge_claude_docs(self.source, pack, target, False, mutable_owner=self.owner(transaction))
                transaction.commit()
            for path, original in originals.items():
                kind = "CLAUDE" if path == target else "SHARED"
                begin = f"<!-- BEGIN ORCHESTRARIUM {kind} MANAGED -->\n"
                end = f"<!-- END ORCHESTRARIUM {kind} MANAGED -->\n"
                prefix, _, rest = path.read_text().partition(begin)
                _, found, suffix = rest.partition(end)
                self.assertTrue(found)
                self.assertEqual(original if path == target else "\n" + original, prefix + suffix)
        self.assert_clean()

    def test_claude_private_supply_missing_package_never_executes_ambient_code(self):
        import shutil
        for missing in ("mdurl", "markdown_it"):
            with self.subTest(missing=missing):
                fixture = self.root / ("supply-" + missing)
                private = fixture / "private"
                ambient = fixture / "ambient" / missing
                marker = fixture / "ambient-executed"
                shutil.copytree(ROOT / "scripts/installer_markdown", private / "installer_markdown")
                absent = private / "installer_markdown/vendor" / missing
                self.assertTrue(absent.resolve().is_relative_to(self.root.resolve()))
                self.assertFalse(any(path.is_symlink() for path in absent.rglob("*")))
                shutil.rmtree(absent)
                ambient.mkdir(parents=True)
                (ambient / "__init__.py").write_text(
                    "from pathlib import Path\nPath(" + repr(str(marker)) + ").write_text('executed')\n"
                    + "__version__ = " + repr("0.1.2" if missing == "mdurl" else "4.0.0") + "\n")
                probe = (
                    "import sys,json\nfrom pathlib import Path\n"
                    "sys.path[:0]=sys.argv[1:3]\n"
                    "try:\n import installer_markdown\n"
                    "except BaseException as error:\n print(json.dumps({'accepted':False,'errorType':type(error).__name__,'marker':Path(sys.argv[3]).exists()}))\n"
                    "else:\n print(json.dumps({'accepted':True,'marker':Path(sys.argv[3]).exists()}))\n")
                result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", probe,
                    str(private), str(ambient.parent), str(marker)], capture_output=True, text=True, timeout=30)
                self.assertEqual(0, result.returncode, result.stderr)
                observed = json.loads(result.stdout)
                self.assertFalse(observed["accepted"])
                self.assertFalse(observed["marker"], observed)
                self.assertFalse(marker.exists())

    def test_claude_managed_update_changes_only_bodies(self):
        pack = self.documentation_fixture()
        target, agents = self.target / "CLAUDE.md", self.target / "AGENTS.md"
        for path in (target, agents):
            path.write_text("foreign tail\n")
        with self.transaction([target, agents]) as transaction:
            PI._merge_claude_docs(self.source, pack, target, False, mutable_owner=self.owner(transaction))
            transaction.commit()
        before = {p: p.read_text() for p in (target, agents)}
        (pack / "CLAUDE.md").write_text("@AGENTS.md\nupdated Claude body\n")
        (self.source / "shared/AGENTS.shared.md").write_text("updated shared body\n")
        with self.transaction([target, agents]) as transaction:
            PI._merge_claude_docs(self.source, pack, target, False, mutable_owner=self.owner(transaction))
            transaction.commit()
        self.assertEqual(before[target].replace("# Claude Code Pack\n", "updated Claude body\n"), target.read_text())
        self.assertEqual(before[agents].replace("# Shared Governance\nnew shared\n", "updated shared body\n"), agents.read_text())
        self.assert_clean()

    def test_claude_quoted_markers_preserve_both_examples(self):
        pack = self.documentation_fixture()
        (pack / "CLAUDE.md").write_text("@AGENTS.md\n# Claude Code Pack\nCurrent source rules.\n")
        originals = {
            self.target / "CLAUDE.md": "@AGENTS.md\nMy example follows.\n```md\n<!-- BEGIN ORCHESTRARIUM CLAUDE MANAGED -->\nRetain user example alpha.\n<!-- END ORCHESTRARIUM CLAUDE MANAGED -->\n```\nUser tail.\n",
            self.target / "AGENTS.md": "My shared example follows.\n```md\n<!-- BEGIN ORCHESTRARIUM SHARED MANAGED -->\nRetain user example beta.\n<!-- END ORCHESTRARIUM SHARED MANAGED -->\n```\nUser shared tail.\n",
        }
        for path, text in originals.items():
            path.write_text(text)
        for cycle in range(3):
            if cycle == 2:
                (pack / "CLAUDE.md").write_text("@AGENTS.md\n# Claude Code Pack\nUpdated source rules.\n")
                (self.source / "shared/AGENTS.shared.md").write_text("# Shared Governance\nUpdated shared rules.\n")
            with self.transaction(list(originals)) as transaction:
                PI._merge_claude_docs(self.source, pack, self.target / "CLAUDE.md", False,
                    mutable_owner=self.owner(transaction))
                transaction.commit()
            for path, original in originals.items():
                kind = "CLAUDE" if path.name == "CLAUDE.md" else "SHARED"
                begin = f"<!-- BEGIN ORCHESTRARIUM {kind} MANAGED -->\n"
                end = f"<!-- END ORCHESTRARIUM {kind} MANAGED -->\n"
                text = path.read_text()
                before, _, after = text.partition(begin)
                _, found_end, after = after.partition(end)
                self.assertTrue(found_end)
                self.assertEqual(original if kind == "CLAUDE" else "\n" + original, before + after)
                self.assertEqual(2, text.count(begin))
        self.assert_clean()

    def test_claude_separate_paragraph_ticks_keep_both_owned_regions_active(self):
        pack = self.documentation_fixture()
        target, agents = self.target / "CLAUDE.md", self.target / "AGENTS.md"
        prefix = "Unmatched ` in paragraph one.\n\n"
        suffix = "\nA separate paragraph with another `.\n"
        for path, kind, heading, anchor in ((target, "CLAUDE", "# Claude Code Pack", "@AGENTS.md\n"),
                                            (agents, "SHARED", "# Shared Governance", "")):
            path.write_text(prefix + anchor + f"<!-- BEGIN ORCHESTRARIUM {kind} MANAGED -->\n"
                + heading + "\nold active rule\n" + f"<!-- END ORCHESTRARIUM {kind} MANAGED -->\n" + suffix)
        for rule in ("new active rule", "new active rule", "updated active rule"):
            (pack / "CLAUDE.md").write_text("@AGENTS.md\n# Claude Code Pack\n" + rule + "\n")
            (self.source / "shared/AGENTS.shared.md").write_text("# Shared Governance\n" + rule + "\n")
            with self.transaction([target, agents]) as transaction:
                PI._merge_claude_docs(self.source, pack, target, False, mutable_owner=self.owner(transaction))
                transaction.commit()
            for path, kind, heading, anchor in ((target, "CLAUDE", "# Claude Code Pack", "@AGENTS.md\n"),
                                                (agents, "SHARED", "# Shared Governance", "")):
                expected = prefix + anchor + f"<!-- BEGIN ORCHESTRARIUM {kind} MANAGED -->\n" + heading + "\n" + rule + "\n" + f"<!-- END ORCHESTRARIUM {kind} MANAGED -->\n" + suffix
                self.assertEqual(expected, path.read_text())
        self.assert_clean()

    def test_claude_legacy_body_requires_its_own_active_signature(self):
        pack = self.documentation_fixture()
        target, agents = self.target / "CLAUDE.md", self.target / "AGENTS.md"
        bodies = {target: "# Claude Code Pack\nCurrent source rules.\n```text\nInternal source example.\n```\nInline `source code`.\n",
                  agents: "# Shared Governance\nnew shared\n```text\nInternal shared example.\n```\n"}
        (pack / "CLAUDE.md").write_text("@AGENTS.md\n" + bodies[target])
        (self.source / "shared/AGENTS.shared.md").write_text(bodies[agents])
        for path, body in bodies.items():
            anchor = "@AGENTS.md\n" if path == target else ""
            path.write_text(anchor + "User prefix.\n" + body + "\n~~~md\n" + body + "~~~\nUser tail.\n")
        originals = {path: path.read_text() for path in bodies}
        for _ in range(2):
            with self.transaction([target, agents]) as transaction:
                PI._merge_claude_docs(self.source, pack, target, False, mutable_owner=self.owner(transaction))
                transaction.commit()
            for path, body in bodies.items():
                kind = "CLAUDE" if path == target else "SHARED"
                expected = originals[path].replace(body, f"<!-- BEGIN ORCHESTRARIUM {kind} MANAGED -->\n" + body + f"<!-- END ORCHESTRARIUM {kind} MANAGED -->\n", 1)
                self.assertEqual(expected, path.read_text())
        self.assert_clean()

    def test_claude_refuses_uncertain_documents_before_either_write(self):
        pack = self.documentation_fixture()
        (pack / "CLAUDE.md").write_text("@AGENTS.md\n# Claude Code Pack\nCurrent source rules.\n")
        target, agents = self.target / "CLAUDE.md", self.target / "AGENTS.md"
        begin = "<!-- BEGIN ORCHESTRARIUM CLAUDE MANAGED -->\n"
        end = "<!-- END ORCHESTRARIUM CLAUDE MANAGED -->\n"
        marked = "@AGENTS.md\n" + begin + "old body\n" + end
        cases = [
            (target, "@AGENTS.md\n# Claude Code Pack\nUnknown active old Claude rules.\n\n```md\n# Claude Code Pack\nCurrent source rules.\n```\nUser tail.\n", "LEGACY_AMBIGUOUS"),
            (agents, "# Shared Governance\nUnknown active old shared rules.\n\n```md\n# Shared Governance\nnew shared\n```\nUser shared tail.\n", "LEGACY_AMBIGUOUS"),
            (target, "@AGENTS.md\n# Claudestrator\nUnknown active old rules.\n\n# Claude Code Pack\nCurrent source rules.\n", "LEGACY_AMBIGUOUS"),
            (target, "@AGENTS.md\n# Claude Code Pack\nCurrent source rules.\n# Claude Code Pack\nCurrent source rules.\n", "LEGACY_AMBIGUOUS"),
            (agents, "# Shared Governance\nedited shared\n", "LEGACY_AMBIGUOUS"),
            (target, "@AGENTS.md\n# Claudestrator\nunknown older body\n", "LEGACY_AMBIGUOUS"),
            (target, "@AGENTS.md\n# Claude Code Pack\n# Claude Code Pack\n", "LEGACY_AMBIGUOUS"),
            (target, marked + begin + end, "MARKERS_INVALID"),
            (target, marked.replace(begin, begin.rstrip() + " extra\n"), "MARKERS_INVALID"),
            (target, marked.rstrip("\n"), "MARKERS_INVALID"),
            (target, marked.replace(begin, "inline " + begin), "MARKERS_INVALID"),
            (target, "@AGENTS.md\n" + end + begin, "MARKERS_INVALID"),
            (agents, begin + end, "MARKERS_INVALID"),
            (target, marked.replace("@AGENTS.md\n", ""), "MARKERS_INVALID"),
            (target, "```text\n@AGENTS.md\n```\n" + begin + "old body\n" + end, "MARKERS_INVALID"),
        ]
        for bad_path, text, code in cases:
            for dry_run in (False, True):
                with self.subTest(file=bad_path.name, text=text, dry_run=dry_run):
                    target.write_bytes(b"foreign Claude\r\n")
                    agents.write_bytes(b"foreign shared\r\n")
                    bad_path.write_bytes(text.replace("\n", "\r\n").encode())
                    original = {p: p.read_bytes() for p in (target, agents)}
                    with self.transaction([target, agents]) as transaction:
                        with patch.object(PI, "_write_owned_text", wraps=PI._write_owned_text) as write:
                            with self.assertRaisesRegex(ValueError, "E_CLAUDE_DOC_" + code + ": " + bad_path.name):
                                PI._merge_claude_docs(self.source, pack, target, dry_run, mutable_owner=self.owner(transaction))
                            write.assert_not_called()
                        self.assertEqual(original, {p: p.read_bytes() for p in original})
                        transaction.commit()
        (pack / "CLAUDE.md").write_text("@AGENTS.md\n# Claude Code Pack\ncurrent owned body\n")
        target.write_bytes(b"@AGENTS.md\r\n# Claude Code Pack\r\nedited owned body\r\n")
        agents.write_bytes(b"Unchanged user shared rules\r\n")
        original = {path: path.read_bytes() for path in (target, agents)}
        with self.transaction([target, agents]) as transaction:
            with patch.object(PI, "_write_owned_text", wraps=PI._write_owned_text) as write:
                with self.assertRaisesRegex(ValueError, "E_CLAUDE_DOC_LEGACY_AMBIGUOUS: CLAUDE.md"):
                    PI._merge_claude_docs(self.source, pack, target, False, mutable_owner=self.owner(transaction))
                write.assert_not_called()
            self.assertEqual(original, {path: path.read_bytes() for path in original})
            transaction.commit()
        self.assert_clean()

    def test_claude_dryrun_and_source_shape_are_write_free(self):
        pack = self.documentation_fixture()
        target, agents = self.target / "CLAUDE.md", self.target / "AGENTS.md"
        target.write_bytes(b"foreign Claude\r\n")
        agents.write_bytes(b"foreign shared\r\n")
        original = {p: p.read_bytes() for p in (target, agents)}
        with self.transaction([target, agents]) as transaction:
            with patch.object(PI, "_write_owned_text", wraps=PI._write_owned_text) as write:
                PI._merge_claude_docs(self.source, pack, target, True, mutable_owner=self.owner(transaction))
                (pack / "CLAUDE.md").write_text("changed source anchor\n")
                with self.assertRaisesRegex(ValueError, "E_CLAUDE_DOC_SOURCE_SHAPE"):
                    PI._merge_claude_docs(self.source, pack, target, True, mutable_owner=self.owner(transaction))
                (pack / "CLAUDE.md").write_text("@AGENTS.md\nvalid body\n")
                (self.source / "shared/AGENTS.shared.md").write_text("<!-- BEGIN ORCHESTRARIUM SHARED MANAGED -->\n")
                with self.assertRaisesRegex(ValueError, "E_CLAUDE_DOC_SOURCE_SHAPE: AGENTS.md"):
                    PI._merge_claude_docs(self.source, pack, target, False, mutable_owner=self.owner(transaction))
                write.assert_not_called()
            transaction.commit()
        self.assertEqual(original, {p: p.read_bytes() for p in original})
        self.assert_clean()

    def test_claude_two_documents_share_parent_inverse(self):
        pack = self.documentation_fixture()
        target, agents = self.target / "CLAUDE.md", self.target / "AGENTS.md"
        target.write_bytes(b"user prefix\r\n@AGENTS.md\r\n# Claude Code Pack\r\nuser tail\r\n")
        agents.write_bytes(b"local agent instructions\r\n")
        original = {p: p.read_bytes() for p in (target, agents)}
        primary = RuntimeError("later")
        for fail_after_first in (True, False):
            identities = {p: PI._CreateOnlyMutablePath._identity(p) for p in original}
            written = []
            real_write = PI._write_owned_text

            def write(path, content, owner):
                real_write(path, content, owner)
                written.append(path)
                self.assertEqual(identities[path], PI._CreateOnlyMutablePath._identity(path))
                self.assertNotIn(b"\r", path.read_bytes())
                if fail_after_first:
                    raise primary

            with self.assertRaises(RuntimeError) as caught:
                with self.transaction([target, agents]) as transaction:
                    with patch.object(PI, "_write_owned_text", side_effect=write):
                        PI._merge_claude_docs(self.source, pack, target, False, mutable_owner=self.owner(transaction))
                    self.assertIn(b"user prefix", target.read_bytes())
                    self.assertIn(b"local agent instructions", agents.read_bytes())
                    self.assertIn(b"new shared", agents.read_bytes())
                    raise primary
            self.assertEqual([target] if fail_after_first else [target, agents], written)
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

    def test_repeated_hook_install_reconciles_stale_inventory_and_rolls_back(self):
        specs, selected, storage, inventory, _original, _foreign = self.hook_fixture(linked=True)
        host = "windows" if os.name == "nt" else "posix"
        link = os.readlink(selected)
        checks = []

        def health(*_args):
            arguments = _args[0]
            selected_stems = {arguments[index + 1] for index, value in enumerate(arguments) if value == "--selected-hook"}
            self.assertEqual(selected_stems, {marker for marker, _script, _event, _matcher in specs})
            data = json.loads(storage.read_bytes())
            targets = {marker: {str(script)} for marker, script, _event, _matcher in specs}
            rows = list(I._iter_owned_hooks(data, set(targets), "codex", host, targets))
            records = [{"eventName": event, "matcher": matcher, "handlerType": "command",
                        "command": subprocess.list2cmdline(argv) if host == "windows" else shlex.join(argv),
                        "sourcePath": str(storage), "enabled": True, "trustStatus": "trusted",
                        "currentHash": "sha256:synthetic"}
                       for event, _stem, argv, matcher in rows]
            manifest = SimpleNamespace(registered_hook_specs=lambda _platform, _root: specs)
            with patch.object(I, "_codex_hooks_list", return_value=records), patch.object(I, "_hook_manifest", return_value=manifest):
                I.verify_config(target=selected, platform="codex", host_os=host, repo_root=self.source,
                                verify_fires=False, inventory_path=inventory, codex_trust_mode="require",
                                installed_root=self.source,
                                selected_stems=selected_stems,
                                codex_command=["synthetic-codex"], codex_home=self.root, query_cwd=self.root)
            checks.append(True)
            return subprocess.CompletedProcess([], 0)

        def install(primary=None):
            transaction = self.transaction([storage, inventory, selected], link_objects=(selected,))
            with self.hook_support(specs, primary), patch.object(PI, "_run_hook_health_bounded", side_effect=health):
                with transaction:
                    PI._install_hooks(self.source, "codex", selected, self.source, "target", inventory,
                                      transaction=transaction, mutable_owner=self.owner(transaction))
                    transaction.commit()

        install()
        hooks_before = storage.read_bytes()
        payload = json.loads(inventory.read_bytes())
        payload["sourcePath"] = str(self.root / "unwitnessed-old-alias.json")
        stale = json.dumps(payload).encode("utf-8")
        inventory.write_bytes(stale)
        install()
        self.assertEqual(hooks_before, storage.read_bytes())
        self.assertNotEqual(stale, inventory.read_bytes())
        self.assertEqual(link, os.readlink(selected))
        inventory.write_bytes(stale)
        with self.assertRaisesRegex(RuntimeError, "synthetic later failure"):
            install(RuntimeError("synthetic later failure"))
        self.assertEqual(stale, inventory.read_bytes())
        self.assertEqual(hooks_before, storage.read_bytes())
        self.assertEqual(link, os.readlink(selected))
        self.assertGreaterEqual(len(checks), 3)
        self.assert_clean()

    def test_changed_verified_legacy_is_rejected_before_registration_merge(self):
        specs, selected, storage, inventory, _original, _foreign = self.hook_fixture()
        marker = specs[0][0]
        legacy = self.source / "scripts" / (marker + ".sh")
        legacy.parent.mkdir()
        legacy.write_bytes(b"synthetic-pinned-legacy\n")
        digest = hashlib.sha256(legacy.read_bytes()).hexdigest()
        config = {"hooks": {"PreToolUse": [{"matcher": specs[0][3], "hooks": [
            {"type": "command", "command": subprocess.list2cmdline(["bash", str(legacy)])}
        ]}]}}
        storage.write_text(json.dumps(config), encoding="utf-8")
        before = storage.read_bytes()
        original = PI._verified_legacy_hook_targets
        calls = []

        def change_after_admission(*args, **kwargs):
            result = original(*args, **kwargs)
            calls.append(True)
            if len(calls) == 1:
                self.assertIn(str(legacy), result[marker])
                self.assertIn(str(legacy), kwargs["witnesses"])
                self.assertTrue(kwargs["witnesses"][str(legacy)])
                legacy.write_bytes(b"changed-before-merge\n")
            return result

        transaction = self.transaction([storage, inventory])
        with self.hook_support(specs), patch.dict(PI._CODEX_RETIRED_SH, {"scripts/" + legacy.name: digest}), \
             patch.object(PI, "_verified_legacy_hook_targets", side_effect=change_after_admission):
            with self.assertRaisesRegex(ValueError, "verified legacy hook artifact changed"):
                with transaction:
                    PI._install_hooks(self.source, "codex", selected, self.source, "target", inventory,
                                      transaction=transaction, mutable_owner=self.owner(transaction))
        self.assertGreaterEqual(len(calls), 2)
        self.assertEqual(before, storage.read_bytes())
        self.assertFalse(inventory.exists())
        self.assertEqual(b"changed-before-merge\n", legacy.read_bytes())
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
        self.assertEqual(transaction._remaining_recovery(), (None, [], [], ()))
        self.assert_clean()


if __name__ == "__main__":
    unittest.main()
