"""Real transaction probes for control changes during selected-current removal."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import production_installer as backend
from installation import ownership, uninstall


@unittest.skipUnless(os.name in {"nt", "posix"}, "Requires an admitted native transaction")
class UninstallControlCurrentnessTests(unittest.TestCase):
    receipt_drift = "E_UNINSTALL_RECEIPT_DRIFT"

    def prepare(self, *, owned_control=False):
        # The invoking test owner settles this isolated fixture using trash-first disposition.
        self.fixture = Path(tempfile.mkdtemp(prefix="uninstall-currentness-"))
        self.home = self.fixture / "home"
        self.target = self.home / ".claude"
        self.payload = self.target / "agents/a.md"
        self.payload.parent.mkdir(parents=True)
        self.payload.write_bytes(b"owned payload")
        self.control = self.target / "settings.json"
        controls = {}
        if owned_control:
            self.control.write_bytes(b'{"hooks":{}}')
            controls[".claude/settings.json"] = hashlib.sha256(self.control.read_bytes()).hexdigest()
        self.receipt = self.target / ownership.RECEIPT_NAME
        self.receipt.write_bytes(ownership.serialize_fresh_install(
            {".claude/agents/a.md": hashlib.sha256(self.payload.read_bytes()).hexdigest()},
            controls, "claude", "global"))
        self.before = {path: path.read_bytes() for path in (self.payload, self.receipt)}
        self.payload_identity = self.payload.stat().st_ino
        staging = self.fixture / "staging"
        staging.mkdir()
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(backend, "_target", return_value=("global", self.target, None)))
        stack.enter_context(patch.object(backend, "_resolve_global_home", return_value=self.home))
        stack.enter_context(patch.object(backend.tempfile, "tempdir", str(staging)))

    def call(self, *, apply=False, selection=None):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = uninstall.run(backend, ROOT, "claude", SimpleNamespace(
                apply=apply, dry_run=False, uninstall_selection=selection))
        report = next(json.loads(line) for line in output.getvalue().splitlines()
                      if line.startswith("{"))
        return result, report

    def assert_late_control_is_preserved(self, name, diagnostic):
        _, preview = self.call()
        foreign = self.target / name
        foreign_bytes = b"foreign control referencing agents/a.md"
        original = backend._CreateOnlyMutablePath.replace_file_atomic
        injections = []

        def replace(owner, relative, *args, **kwargs):
            result = original(owner, relative, *args, **kwargs)
            if relative.name == ownership.RECEIPT_NAME:
                self.assertFalse(self.payload.exists())
                self.assertNotEqual(self.receipt.read_bytes(), self.before[self.receipt])
                foreign.write_bytes(foreign_bytes)
                injections.append(True)
            return result

        with patch.object(backend._CreateOnlyMutablePath, "replace_file_atomic", replace):
            with self.assertRaisesRegex((ValueError, backend._InstallFailure), diagnostic):
                self.call(apply=True, selection=preview.get("selection"))
        self.assertEqual(injections, [True])
        self.assertEqual(foreign.read_bytes(), foreign_bytes)
        self.assertEqual({path: path.read_bytes() for path in self.before}, self.before)
        self.assertEqual(self.payload.stat().st_ino, self.payload_identity)

    def test_absent_hook_configuration_created_during_apply_restores_owned_state(self):
        self.prepare()
        self.assert_late_control_is_preserved("settings.json", "E_UNINSTALL_CONTROL_DRIFT")

    def test_absent_document_created_during_apply_restores_owned_state(self):
        self.prepare()
        self.assert_late_control_is_preserved("CLAUDE.md", "E_UNINSTALL_DOCUMENT_DRIFT")

    def test_removed_control_recreated_during_apply_restores_owned_payload_and_receipt(self):
        self.prepare(owned_control=True)
        self.assert_late_control_is_preserved("settings.json", "E_UNINSTALL_CONTROL_DRIFT")

    def test_unchanged_owned_control_and_payload_are_removed(self):
        self.prepare(owned_control=True)
        _, preview = self.call()
        self.assertEqual(self.call(apply=True, selection=preview.get("selection"))[0], 0)
        self.assertFalse(self.payload.exists())
        self.assertFalse(self.control.exists())
        residual = ownership.decode_record(self.receipt.read_bytes(), "claude", "global")
        self.assertEqual(residual["files"], {})
        self.assertEqual(residual["configs"], {})

    def test_receipt_absent_at_transaction_entry_refuses_without_effects(self):
        self.prepare(owned_control=True)
        retained = self.fixture / "externally-moved-receipt.json"
        original_enter = backend._InstallTransaction.__enter__

        def enter(transaction):
            if transaction.enabled:
                self.receipt.rename(retained)
            return original_enter(transaction)

        with patch.object(backend._InstallTransaction, "__enter__", enter):
            with self.assertRaisesRegex(ValueError, self.receipt_drift):
                self.call(apply=True)
        self.assertFalse(self.receipt.exists())
        self.assertEqual(retained.read_bytes(), self.before[self.receipt])
        self.assertEqual(self.payload.read_bytes(), self.before[self.payload])
        self.assertEqual(self.payload.stat().st_ino, self.payload_identity)
        self.assertEqual(self.control.read_bytes(), b'{"hooks":{}}')


class OwnedCopiesControlCurrentnessTests(UninstallControlCurrentnessTests):
    """The copy-layout route must retain its own recorded-control preimages."""
    receipt_drift = "Ownership record changed during uninstall"

    def prepare(self, *, owned_control=False):
        super().prepare(owned_control=owned_control)
        record = ownership.decode_record(self.receipt.read_bytes(), "claude", "global")
        record["layout"] = ownership.LAYOUT
        configs = record.setdefault("configs", {})
        for name in ("settings.json", "CLAUDE.md"):
            configs.setdefault(".claude/" + name, {
                "kind": "created-file",
                "sha256": hashlib.sha256(b"previously installed control").hexdigest(),
            })
        self.receipt.write_bytes(ownership.serialize_record(record, "claude", "global"))
        self.before[self.receipt] = self.receipt.read_bytes()

    def assert_late_control_is_preserved(self, name, diagnostic):
        super().assert_late_control_is_preserved(name, "E_UNINSTALL_CONTROL_DRIFT")


if __name__ == "__main__":
    unittest.main()
