"""Record syntax and input identity are not issuer authentication."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

class EvidenceRecordTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="evidence-record-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        spec = importlib.util.spec_from_file_location("evidence_builder", Path(__file__).resolve().parents[1] / "scripts/distribution/build.py")
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)
        self.path = self.root / "record.json"
        self.data = {"schemaVersion": 1, "target": "windows-x64", "runtime": {"python.exe": ["file", "a" * 64, False]}, "notices": {"LICENSE": ["file", "b" * 64, False]}}

    def test_record_bytes_preserved(self):
        raw = json.dumps(self.data, indent=2).encode() + b"\n"
        self.path.write_bytes(raw)
        self.assertEqual(self.builder._read_runtime_evidence(self.path, "windows-x64"), (raw, self.data))

    def test_invalid_record_refused(self):
        for key, value in (("schemaVersion", True), ("target", "linux-x64"), ("runtime", {}), ("notices", []), ("extra", True)):
            with self.subTest(key=key):
                bad = dict(self.data)
                bad[key] = value
                self.path.write_text(json.dumps(bad))
                with self.assertRaises(ValueError):
                    self.builder._read_runtime_evidence(self.path, "windows-x64")

    def test_invalid_member_refused(self):
        for member in (None, ["directory", "extra"], ["link", 1], ["file", "A"*64, False], ["file", "a"*64, 1]):
            with self.subTest(member=member):
                self.data["runtime"]["python.exe"] = member
                self.path.write_text(json.dumps(self.data))
                with self.assertRaises(ValueError):
                    self.builder._read_runtime_evidence(self.path, "windows-x64")

    def test_duplicate_key_refused(self):
        self.path.write_text('{"schemaVersion":1,"schemaVersion":1}')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.builder._read_runtime_evidence(self.path, "windows-x64")
