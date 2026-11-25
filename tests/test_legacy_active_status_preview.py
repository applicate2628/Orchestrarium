import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "mutate-work-item.py"


class LegacyActiveStatusPreviewTest(unittest.TestCase):
    def preview(self, source):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            active = root / "work-items" / "active" / "selected"
            active.mkdir(parents=True)
            status = active / "status.md"
            status.write_bytes(source)
            attachment = active / "evidence.txt"
            attachment.write_bytes(b"retained")
            result = subprocess.run(
                [sys.executable, "-B", str(SCRIPT), "update", "--root", str(root),
                 "--slug", "selected", "--preview-legacy",
                 "--transition-read-admission", "selected-native"],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertEqual(status.read_bytes(), source)
            self.assertEqual(attachment.read_bytes(), b"retained")
            self.assertFalse((root / "work-items" / "README.md").exists())
            preview = json.loads(result.stdout)
            self.assertEqual(preview["sourceSha256"], hashlib.sha256(source).hexdigest())
            return preview

    def test_recovers_unique_fields_from_bom_and_old_alias(self):
        preview = self.preview(
            b"\xef\xbb\xbf# Status\r\n\r\nLifecycle: ACTIVE\r\n"
            b"Task: Repair the record.\r\nNext action: Check the release.\r\n"
        )
        self.assertEqual(preview["fields"]["status"], "active")
        self.assertEqual(preview["fields"]["task"], "Repair the record.")
        self.assertEqual(preview["fields"]["next action"], "Check the release.")
        self.assertEqual(preview["unresolved"]["owner"], "missing")

    def test_returns_partial_facts_without_accepting_conflict_or_unclosed_code(self):
        preview = self.preview(
            b"State: active\nLifecycle: blocked\nTask: Known task.\n"
            b"```text\nOwner: Not a real owner.\n"
        )
        self.assertNotIn("status", preview["fields"])
        self.assertEqual(preview["unresolved"]["status"], "conflict")
        self.assertEqual(preview["fields"]["task"], "Known task.")
        self.assertNotIn("owner", preview["fields"])
        self.assertIn("unterminated-markdown-fence", preview["warnings"])

    def test_damaged_bytes_do_not_create_a_replacement_fact_or_hide_other_facts(self):
        preview = self.preview(
            b"State: active\nTask: Check the old record.\nOwner: bad \xff text\n"
            b"Next action: Confirm custody.\n"
        )
        self.assertEqual(preview["fields"]["next action"], "Confirm custody.")
        self.assertNotIn("owner", preview["fields"])
        self.assertEqual(preview["unresolved"]["owner"], "damaged")
