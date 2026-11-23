"""Receipt and uninstall boundaries preserve exact user text and file hashes."""
import contextlib
import hashlib
import io
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
INSTALL = load_module(ROOT / "scripts/production_installer.py", "uninstall_exact_text_backend")
CODEC = load_module(ROOT / "scripts/installation/ownership.py", "uninstall_exact_text_codec")
CONFIG = load_module(ROOT / "scripts/installation/configuration.py", "uninstall_exact_text_configuration")
UNINSTALL = load_module(ROOT / "scripts/installation/uninstall.py", "uninstall_exact_text_owner")


@unittest.skipUnless(os.name in {"nt", "posix"}, "Requires an admitted native transaction")
class ProviderUninstallExactTextTests(unittest.TestCase):
    def setUp(self):
        # The invoking test owner settles this isolated fixture using trash-first disposition.
        self.base = Path(tempfile.mkdtemp(prefix="provider-exact-text-"))
        self.target = self.base / ".claude"
        self.target.mkdir()
        staging = self.base / "staging"
        staging.mkdir()
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        stack.enter_context(patch.object(INSTALL, "_target", return_value=("project", self.target, self.base)))
        stack.enter_context(patch.object(INSTALL.tempfile, "tempdir", str(staging)))

    def remove(self, configs):
        receipt = self.target / CODEC.RECEIPT_NAME
        receipt.write_bytes(CODEC.encode_record({}, "claude", "project", configs=configs))
        with contextlib.redirect_stdout(io.StringIO()):
            return UNINSTALL.run(INSTALL, ROOT, "claude", SimpleNamespace(
                apply=True, dry_run=False, uninstall_selection=None))

    def test_managed_block_removal_preserves_foreign_crlf_bytes(self):
        begin, end = CONFIG.MARKERS["claude"]
        block = (begin + "\r\nmanaged instructions\r\n" + end).encode()
        prefix, suffix = b"User prefix\r\n", b"\r\nUser suffix\r\n"
        document = self.target / "CLAUDE.md"
        document.write_bytes(prefix + block + suffix)
        self.assertEqual(self.remove({".claude/CLAUDE.md": {
            "kind": "block", "blockKind": "claude",
            "sha256": CONFIG.text_receipt_digest(block.decode()),
        }}), 0)
        self.assertEqual(document.read_bytes(), prefix + suffix)

    def test_exact_owned_crlf_control_is_removed(self):
        mode = self.target / ".agents-mode.yaml"
        payload = b"# Preserved original newlines\r\nmcpMode: force\r\n"
        mode.write_bytes(payload)
        self.assertEqual(self.remove({".claude/.agents-mode.yaml": {
            "kind": "file", "sha256": hashlib.sha256(payload).hexdigest(),
        }}), 0)
        self.assertFalse(mode.exists())

    def test_created_preference_receipt_hashes_exact_postimage(self):
        mode = self.target / ".agents-mode.yaml"
        payload = b"# Migrated original newlines\r\nmcpMode: force\r\n"
        mode.write_bytes(payload)
        registration = self.target / "settings.json"
        owner = INSTALL._CreateOnlyMutablePath(
            self.base, INSTALL._InstallTransaction([], enabled=False), dry_run=False)
        result = INSTALL._capture_provider_configs(
            ROOT, "claude", "global", self.target, self.base, owner,
            {mode: None, registration: None}, {}, self.target / "CLAUDE.md", mode,
            registration, self.target / "agents", False)
        self.assertEqual(result[".claude/.agents-mode.yaml"], {
            "kind": "file", "sha256": hashlib.sha256(payload).hexdigest(),
        })
        self.assertEqual(mode.read_bytes(), payload)


if __name__ == "__main__":
    unittest.main()
