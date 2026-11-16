"""Bounded current-selection removal; no provider or model is invoked."""
import contextlib
import hashlib
import importlib.util
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
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
from installation import ownership, uninstall

def digest(data):
    return hashlib.sha256(data).hexdigest()

class CodecTests(unittest.TestCase):
    def test_created_controls_and_payload_remain_separate(self):
        raw = ownership.serialize_fresh_install(
            {".claude/agents/a.md": "a"*64},
            {".claude/settings.json": "b"*64}, "claude", "global")
        record = ownership.decode_record(raw, "claude", "global")
        self.assertEqual(record["configs"][".claude/settings.json"],
                         {"kind":"created-file","sha256":"b"*64})
        self.assertNotIn("layout", record)
    def test_non_control_and_bad_digest_refuse(self):
        for controls in ({".claude/agents/a.md":"a"*64},
                         {".claude/settings.json":"bad"}):
            with self.assertRaises(ValueError):
                ownership.serialize_fresh_install({}, controls, "claude", "global")

@unittest.skipUnless(os.name == "nt", "Uses existing admitted native Windows transaction")
class PhysicalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.dont_write_bytecode = True
        spec = importlib.util.spec_from_file_location("presdk_uninstall_backend", ROOT/"scripts/production_installer.py")
        cls.backend = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.backend
        spec.loader.exec_module(cls.backend)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="orche-uninstall-")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.target = self.home/".claude"
        self.file = self.target/"agents/a.md"
        self.file.parent.mkdir(parents=True)
        self.file.write_bytes(b"owned")
        self.user = self.target/"agents/user.md"
        self.user.write_bytes(b"user")
        self.control = self.target/"settings.json"
        self.control.write_bytes(b'{"hooks":{}}')
        self.receipt = self.target/ownership.RECEIPT_NAME
        self.receipt.write_bytes(ownership.serialize_fresh_install(
            {".claude/agents/a.md":digest(b"owned")},
            {".claude/settings.json":digest(self.control.read_bytes())},
            "claude","global"))
        self.addCleanup(patch.stopall)
        patch.object(self.backend, "_target", return_value=("global",self.target,None)).start()
        patch.object(self.backend, "_resolve_global_home", return_value=self.home).start()
        patch.object(self.backend.subprocess, "Popen", side_effect=AssertionError("No subprocess allowed")).start()

    def call(self, apply=False, token=None):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = uninstall.run(self.backend, ROOT, "claude",
                SimpleNamespace(apply=apply,dry_run=False,uninstall_selection=token))
        rows=[json.loads(l) for l in out.getvalue().splitlines() if l.startswith("{")]
        return result, rows[0] if rows else {}



    def add_document(self, edited=False):
        from installation import configuration
        block = "\r\n".join((configuration.MARKERS["claude"][0], "owned",
                              configuration.MARKERS["claude"][1]))
        self.document = self.target / "CLAUDE.md"
        raw = ("user before\r\n" + block + "\r\nuser after\r\n").encode()
        self.document.write_bytes(raw.replace(b"owned", b"edited") if edited else raw)
        record = ownership.decode_record(self.receipt.read_bytes(), "claude", "global")
        record["configs"][".claude/CLAUDE.md"] = {
            "kind":"block", "blockKind":"claude",
            "sha256":configuration.text_receipt_digest(block)}
        self.receipt.write_bytes(ownership.serialize_record(record, "claude", "global"))
        return raw

    def test_owned_document_block_preserves_exact_user_bytes_and_repeat(self):
        self.add_document()
        _, report = self.call()
        self.assertEqual(report["removeBlocks"], [".claude/CLAUDE.md"])
        self.assertEqual(self.call(True, report["selection"])[0], 0)
        self.assertEqual(self.document.read_bytes(), b"user before\r\n\r\nuser after\r\n")
        _, report = self.call()
        self.assertEqual(self.call(True, report["selection"])[0], 0)

    def test_edited_document_block_preserves_whole_installation(self):
        self.add_document(edited=True)
        before = self.document.read_bytes()
        _, report = self.call()
        self.assertEqual(self.call(True, report["selection"])[0], 2)
        self.assertEqual(self.document.read_bytes(), before)
        self.assertTrue(self.file.exists())
        self.assertTrue(self.control.exists())

    def test_document_block_rollback_restores_exact_bytes(self):
        before = self.add_document()
        self.test_late_failure_rolls_back()
        self.assertEqual(self.document.read_bytes(), before)

    def test_missing_owned_block_preserves_document(self):
        self.add_document()
        self.document.write_bytes(b"user only\r\n")
        identity = self.document.stat().st_ino
        _, report = self.call()
        self.assertEqual(report["removeBlocks"], [])
        self.assertEqual(self.call(True, report["selection"])[0], 0)
        self.assertEqual(self.document.read_bytes(), b"user only\r\n")
        self.assertEqual(self.document.stat().st_ino, identity)


    def test_absent_document_block_changed_during_apply_preserves_new_content(self):
        self.add_document()
        self.document.write_bytes(b"user only")
        _, report = self.call()
        original = self.backend._CreateOnlyMutablePath.remove_exact_file
        def change(owner, relative, expected):
            result = original(owner, relative, expected)
            if relative.name == "settings.json":
                self.document.write_bytes(b"concurrent user edit")
            return result
        with patch.object(self.backend._CreateOnlyMutablePath, "remove_exact_file", change):
            with self.assertRaisesRegex(self.backend._InstallFailure, "E_ROLLBACK_SETTLEMENT_FAILED.*E_UNINSTALL_DOCUMENT_DRIFT"):
                self.call(True, report["selection"])
        self.assertEqual(self.document.read_bytes(), b"concurrent user edit")
        self.assertEqual(self.file.read_bytes(), b"owned")
        self.assertTrue(self.control.exists())

    def link_agents(self):
        import _winapi
        storage = self.home / "storage"
        self.file.parent.rename(storage)
        _winapi.CreateJunction(str(storage), str(self.target / "agents"))
        return storage

    def test_linked_apply_repeat_and_neighbor(self):
        storage = self.link_agents()
        _, report = self.call()
        self.assertEqual(self.call(True, report["selection"])[0], 0)
        self.assertFalse((storage / "a.md").exists())
        self.assertEqual((storage / "user.md").read_bytes(), b"user")
        self.assertTrue(os.path.isjunction(self.target / "agents"))
        _, report = self.call()
        self.assertEqual(self.call(True, report["selection"])[0], 0)

    def test_linked_same_bytes_retarget_refuses(self):
        import _winapi
        storage = self.link_agents()
        _, report = self.call()
        other = self.home / "other"
        other.mkdir()
        (other / "a.md").write_bytes(b"owned")
        os.rmdir(self.target / "agents")
        _winapi.CreateJunction(str(other), str(self.target / "agents"))
        with self.assertRaisesRegex(ValueError, "E_UNINSTALL_SELECTION_DRIFT"):
            self.call(True, report["selection"])
        self.assertEqual((storage / "a.md").read_bytes(), b"owned")
        self.assertEqual((other / "a.md").read_bytes(), b"owned")
        self.assertTrue(self.control.exists())


    def test_linked_retarget_during_apply_does_not_touch_new_target(self):
        import _winapi
        storage = self.link_agents()
        other = self.home / "other"
        other.mkdir()
        (other / "a.md").write_bytes(b"owned")
        _, report = self.call()
        original = self.backend._CreateOnlyMutablePath.remove_exact_file
        def retarget(owner, relative, expected):
            result = original(owner, relative, expected)
            if relative.name == "settings.json":
                os.rmdir(self.target / "agents")
                _winapi.CreateJunction(str(other), str(self.target / "agents"))
            return result
        with patch.object(self.backend._CreateOnlyMutablePath, "remove_exact_file", retarget):
            with self.assertRaises(ValueError):
                self.call(True, report["selection"])
        self.assertEqual((storage / "a.md").read_bytes(), b"owned")
        self.assertEqual((other / "a.md").read_bytes(), b"owned")
        self.assertEqual(self.control.read_bytes(), b'{"hooks":{}}')

    def test_linked_late_failure_rolls_back_physical_payload(self):
        storage = self.link_agents()
        self.test_late_failure_rolls_back()
        self.assertEqual((storage / "a.md").read_bytes(), b"owned")
        self.assertTrue(os.path.isjunction(self.target / "agents"))

    def test_preview_apply_repeat_preserves_neighbor(self):
        before=self.receipt.read_bytes()
        result, report=self.call()
        self.assertEqual(result,0)
        self.assertEqual(self.receipt.read_bytes(),before)
        result,_=self.call(True,report["selection"])
        self.assertEqual(result,0)
        self.assertFalse(self.file.exists())
        self.assertFalse(self.control.exists())
        self.assertEqual(self.user.read_bytes(),b"user")
        _, again=self.call()
        self.assertEqual(self.call(True,again["selection"])[0],0)

    def test_changed_control_preserves_runtime(self):
        self.control.write_bytes(b'{"hooks":{},"user":true}')
        _, report=self.call()
        self.assertEqual(self.call(True,report["selection"])[0],2)
        self.assertEqual(self.file.read_bytes(),b"owned")
        self.assertTrue(self.control.exists())

    def test_late_failure_rolls_back(self):
        before=self.receipt.read_bytes()
        _, report=self.call()
        original=self.backend._CreateOnlyMutablePath.replace_file_atomic
        def fail(owner, relative, *args, **kwargs):
            if relative.name == ownership.RECEIPT_NAME:
                raise RuntimeError("receipt failpoint")
            return original(owner,relative,*args,**kwargs)
        with patch.object(self.backend._CreateOnlyMutablePath,"replace_file_atomic",fail):
            with self.assertRaisesRegex(RuntimeError,"receipt failpoint"):
                self.call(True,report["selection"])
        self.assertEqual(self.file.read_bytes(),b"owned")
        self.assertEqual(self.control.read_bytes(),b'{"hooks":{}}')
        self.assertEqual(self.receipt.read_bytes(),before)

    def test_drifted_selection_does_not_mutate(self):
        _, report=self.call()
        self.file.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError,"E_UNINSTALL_SELECTION_DRIFT"):
            self.call(True,report["selection"])
        self.assertEqual(self.file.read_bytes(),b"changed")
        self.assertTrue(self.control.exists())

    def test_legacy_receipt_never_claims_existing_control(self):
        self.receipt.write_bytes(ownership.serialize_fresh_payloads(
            {".claude/agents/a.md":digest(b"owned")},"claude","global"))
        _, report=self.call()
        self.assertEqual(self.call(True,report["selection"])[0],2)
        self.assertTrue(self.file.exists())
        self.assertTrue(self.control.exists())

    def test_actual_creator_records_new_control_without_adopting_existing(self):
        home = self.home / "new-home"
        home.mkdir()
        target = home / ".claude"
        target.mkdir()
        settings = target / "settings.json"
        settings.write_bytes(b'{"user":true}')
        receipt = target / ownership.RECEIPT_NAME
        with self.backend._InstallTransaction([receipt, target / "agents", target / ".agents-mode.yaml"], enabled=True, track_fresh_files=True) as tx:
            owner = self.backend._CreateOnlyMutablePath(home, tx, dry_run=False)
            owner.create_file(Path(".claude/agents/created.md"), b"created")
            owner.create_file(Path(".claude/.agents-mode.yaml"), b"mode: new")
            self.backend._record_fresh_provider_receipt("claude", "global", receipt, owner)
            tx.commit()
        record = ownership.decode_record(receipt.read_bytes(), "claude", "global")
        self.assertEqual(record["configs"], {".claude/.agents-mode.yaml":
            {"kind":"created-file","sha256":digest(b"mode: new")}})
        self.assertEqual(settings.read_bytes(), b'{"user":true}')

    def test_public_entrypoint_preview_and_apply(self):
        out=io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(self.backend.install("claude", ["--global", "--uninstall"]),0)
        selection=json.loads(next(l for l in out.getvalue().splitlines() if l.startswith("{")))["selection"]
        with contextlib.redirect_stdout(io.StringIO()):
            result=self.backend.install("claude", ["--global", "--uninstall", "--apply",
                                                   "--uninstall-selection", selection])
        self.assertEqual(result,0)
        self.assertFalse(self.file.exists())
        self.assertEqual(self.user.read_bytes(),b"user")

    def test_modified_owned_payload_is_preserved(self):
        self.file.write_bytes(b"user edit")
        _,report=self.call()
        self.assertEqual(self.call(True,report["selection"])[0],2)
        self.assertEqual(self.file.read_bytes(),b"user edit")
        record=ownership.decode_record(self.receipt.read_bytes(),"claude","global")
        self.assertIn(".claude/agents/a.md",record["files"])

    def test_exact_raw_receipt_and_replaced_receipt_refuse(self):
        _,report=self.call()
        raw=self.receipt.read_bytes()
        self.receipt.write_bytes(raw.replace(b"\n", b"\r\n"))
        with self.assertRaisesRegex(ValueError,"E_UNINSTALL_SELECTION_DRIFT"):
            self.call(True,report["selection"])
        _,report=self.call()
        other=self.receipt.with_suffix(".new")
        other.write_bytes(self.receipt.read_bytes())
        os.replace(other,self.receipt)
        with self.assertRaisesRegex(ValueError,"E_UNINSTALL_SELECTION_DRIFT"):
            self.call(True,report["selection"])
        self.assertTrue(self.file.exists())

    def test_uninstall_cli_does_not_select_other_operations(self):
        before=self.receipt.read_bytes()
        for provider,args in (("codex",["--global","--uninstall"]),
            ("claude",["--global","--uninstall-selection","0"*64]),
            ("claude",["--global","--uninstall","--replace-modified-lead","x"])):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(self.backend.install(provider,args),1)
        self.assertEqual(self.receipt.read_bytes(),before)
        self.assertTrue(self.file.exists())

if __name__ == "__main__":
    unittest.main()
