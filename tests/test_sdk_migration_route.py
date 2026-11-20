"""Memory-only checks for the active SDK materialization route."""
from contextlib import redirect_stdout
import hashlib
import io
from pathlib import Path, PurePosixPath
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]

class MigrationRouteTests(unittest.TestCase):
    def setUp(self):
        self.scope = {}
        exec(compile((ROOT / "scripts/installation/migration.py").read_bytes(),
                     "memory-migration", "exec"), self.scope)
        self.anchor = PurePosixPath("home")
        self.source = self.anchor / ".agents/skills/worker"
        self.target = self.anchor / ".claude/skills/worker"
        self.receipt_source = self.anchor / ".agents/skills/receipt.json"
        self.receipt_target = self.anchor / ".claude/skills/receipt.json"
        self.before = b'{"raw": true}\r\n'
        self.payload = b'{"selected":true}\n'
        self.dependency = NS(image={self.receipt_source: NS(
            kind="file", data=hashlib.sha256(self.before).hexdigest())})
        self.tx = Mock()
        self.tx.assert_readonly_path = Mock()
        self.tx.bind_readonly_path.return_value = self.dependency
        self.tx.__enter__ = Mock(return_value=self.tx)
        self.tx.__exit__ = Mock(return_value=False)
        self.owner = Mock()
        self.backend = NS(_target=Mock(return_value=("global", self.anchor / ".claude", None)),
            get_client=Mock(return_value={"payload_roots": (".claude/skills",)}),
            _InstallTransaction=Mock(return_value=self.tx),
            _CreateOnlyMutablePath=Mock(return_value=self.owner))
        self.scope["plan"] = Mock(return_value=[(self.target, self.source, "digest")])
        self.scope["receipt_plan"] = Mock(return_value=[
            (self.receipt_source, self.receipt_target, self.before, self.payload)])
        self.args = NS(apply=True, dry_run=False)

    def run_migration(self):
        with redirect_stdout(io.StringIO()):
            return self.scope["run"](self.backend, ROOT, "claude", self.args)

    def test_selected_owner_source_pins_and_receipt_bytes(self):
        self.assertEqual(self.run_migration(), 0)
        self.scope["plan"].assert_called_once_with(self.backend, self.anchor, "claude")
        self.backend._CreateOnlyMutablePath.assert_called_once_with(self.anchor, self.tx, dry_run=False)
        self.owner.materialize_exact_projection.assert_called_once_with(
            PurePosixPath(".claude/skills/worker"), self.source, "digest")
        self.owner.create_file.assert_called_once_with(
            PurePosixPath(".claude/skills/receipt.json"), self.payload)
        self.tx.assert_readonly_path.assert_called_with(self.dependency, check_content=True)
        self.assertEqual(self.tx.assert_readonly_path.call_count, 2)
        self.tx.commit.assert_called_once()
        kwargs = self.backend._InstallTransaction.call_args.kwargs
        self.assertEqual(kwargs["link_object_paths"], (self.target,))
        self.assertEqual(kwargs["readonly_paths"], (self.source, self.receipt_source))

    def test_changed_raw_receipt_refuses_write_and_commit(self):
        self.dependency.image[self.receipt_source].data = hashlib.sha256(
            self.before.replace(b"\r\n", b"\n")).hexdigest()
        with self.assertRaisesRegex(ValueError, "receipt source"):
            self.run_migration()
        self.owner.create_file.assert_not_called()
        self.tx.commit.assert_not_called()

    def test_preview_disables_transaction_and_owner_and_never_commits(self):
        self.args.dry_run = True
        self.run_migration()
        self.assertFalse(self.backend._InstallTransaction.call_args.kwargs["enabled"])
        self.assertTrue(self.backend._CreateOnlyMutablePath.call_args.kwargs["dry_run"])
        self.tx.commit.assert_not_called()

    def test_empty_plan_has_no_transaction(self):
        self.scope["plan"].return_value = []
        self.assertEqual(self.run_migration(), 0)
        self.backend._InstallTransaction.assert_not_called()



if __name__ == "__main__":
    unittest.main()
