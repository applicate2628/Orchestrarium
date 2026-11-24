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
                self.call(apply=True, selection=preview["selection"])
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
        self.assertEqual(self.call(apply=True, selection=preview["selection"])[0], 0)
        self.assertFalse(self.payload.exists())
        self.assertFalse(self.control.exists())
        residual = ownership.decode_record(self.receipt.read_bytes(), "claude", "global")
        self.assertEqual(residual["files"], {})
        self.assertEqual(residual["configs"], {})


if __name__ == "__main__":
    unittest.main()
