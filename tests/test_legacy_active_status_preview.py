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

    def run_owner(self, root, *args):
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "update", "--root", str(root),
             "--slug", "selected", *args, "--transition-read-admission", "selected-native"],
            capture_output=True, text=True, encoding="utf-8",
        )

    def test_apply_retains_exact_preimage_and_preserves_existing_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item = root / "work-items" / "active" / "selected"
            item.mkdir(parents=True)
            old = b"Lifecycle: active\nTask: Existing work.\nOwner: \xff\n"
            (item / "status.md").write_bytes(old)
            (item / "evidence.txt").write_bytes(b"established custody")
            ledger = item / "agent-runs.jsonl"
            ledger.write_bytes(b"")
            neighbor = item.with_name("damaged-neighbor")
            neighbor.mkdir()
            neighbor_status = neighbor / "status.md"
            neighbor_status.write_bytes(b"Owner: \xff\n")
            draft = root / "new-status.md"
            draft.write_text(
                "---\ntemplate: staged\nstatus: active\n"
                "started: 2026-11-25T09:00:00Z\nupdated: 2026-11-25T09:00:00Z\n---\n"
                "Task: Existing work.\nCurrent step: Restore the current record.\n"
                "Last result: Legacy task retained.\nNext action: Verify the outcome.\n"
                "Scope boundary: One task only.\nOwner: Lead.\nIntegration owner: Lead.\n"
                "Evidence gate: evidence.txt; historical outcomes are not inferred.\n",
                encoding="utf-8",
            )
            digest = hashlib.sha256(old).hexdigest()
            bad = self.run_owner(root, "--status-file", str(draft), "--recover-from-sha256", "0" * 64)
            self.assertNotEqual(bad.returncode, 0)
            self.assertEqual((item / "status.md").read_bytes(), old)
            args = ("--status-file", str(draft), "--recover-from-sha256", digest)
            first = self.run_owner(root, *args)
            self.assertEqual(first.returncode, 0, first.stderr or first.stdout)
            self.assertEqual((item / "status.md").read_bytes(), draft.read_bytes())
            self.assertEqual((item / "evidence.txt").read_bytes(), b"established custody")
            self.assertEqual(ledger.read_bytes(), b"")
            self.assertEqual(neighbor_status.read_bytes(), b"Owner: \xff\n")
            self.assertIn("damaged-neighbor", (root / "work-items" / "README.md").read_text(encoding="utf-8"))
            originals = [path for path in item.iterdir() if path.is_file() and path.read_bytes() == old]
            self.assertEqual(len(originals), 1)
            files = {p.name: p.read_bytes() for p in item.iterdir() if p.is_file()}
            again = self.run_owner(root, *args)
            self.assertEqual(again.returncode, 0, again.stderr or again.stdout)
            self.assertEqual({p.name: p.read_bytes() for p in item.iterdir() if p.is_file()}, files)


    def test_missing_history_requires_explicit_current_admission(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            item = root / "work-items" / "active" / "selected"
            item.mkdir(parents=True)
            old = b"State: active\nTask: Existing work.\n"
            current = item / "status.md"
            current.write_bytes(old)
            draft = root / "new-status.md"
            draft.write_text(
                "---\ntemplate: staged\nstatus: active\n"
                "started: 2026-11-25T09:00:00Z\nupdated: 2026-11-25T09:00:00Z\n---\n"
                "Task: Existing work.\nCurrent step: Recover the record.\n"
                "Last result: Historical ledger unavailable.\nNext action: Verify the outcome.\n"
                "Scope boundary: One task only.\nOwner: Lead.\nIntegration owner: Lead.\n"
                "Evidence gate: Current facts only; no historical acceptance.\n", encoding="utf-8",
            )
            args = ("--status-file", str(draft), "--recover-from-sha256",
                    hashlib.sha256(old).hexdigest())
            ledger = item / "agent-runs.jsonl"
            refused = self.run_owner(root, *args)
            self.assertNotEqual(refused.returncode, 0)
            self.assertEqual(current.read_bytes(), old)
            self.assertFalse(ledger.exists())
            authorized = (*args, "--admit-current-tracking-at", "2026-11-25T09:30:00Z")
            interrupted = self.run_owner(root, *authorized, "--inject-readme-failure", "after-canonical")
            self.assertNotEqual(interrupted.returncode, 0)
            self.assertIn("WI-README-STALE", interrupted.stderr + interrupted.stdout)
            self.assertEqual(current.read_bytes(), draft.read_bytes())
            recovered = self.run_owner(root, *authorized)
            self.assertEqual(recovered.returncode, 0, recovered.stderr or recovered.stdout)
            self.assertTrue((root / "work-items" / "README.md").is_file())
            checker = SCRIPT.with_name("check-work-items-state.py")
            audit = subprocess.run(
                [sys.executable, "-B", str(checker), "--root", str(root), "--active-only",
                 "--transition-read-admission", "selected-native"],
                capture_output=True, text=True, encoding="utf-8",
            )
            self.assertEqual(audit.returncode, 0, audit.stdout + audit.stderr)
            rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertIn("2026-11-25T09:30:00Z", ledger.read_text(encoding="utf-8"))
            self.assertIn("legacy status recovery", str(rows[0]["scope"]))
            self.assertNotIn("PASS", ledger.read_text(encoding="utf-8"))
            before = ledger.read_bytes()
            self.assertEqual(self.run_owner(root, *authorized).returncode, 0)
            self.assertEqual(ledger.read_bytes(), before)
