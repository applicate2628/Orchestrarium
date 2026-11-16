"""Read-only Linux leaf-link selection; not public POSIX installer admission."""
import os
import unittest
import test_presdk_uninstall as fixtures

@unittest.skipUnless(os.name == "posix", "Requires POSIX symlink fixtures")
class LinkedDocumentPreviewTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.PhysicalTests.setUpClass.__func__)
    setUp = fixtures.PhysicalTests.setUp
    add_document = fixtures.PhysicalTests.add_document
    call = fixtures.PhysicalTests.call

    def test_relative_link_preview_and_same_bytes_retarget(self):
        raw = self.add_document()
        physical = self.home / "physical.md"
        self.document.rename(physical)
        self.document.symlink_to("../physical.md")
        identity = self.document.lstat().st_ino
        receipt = self.receipt.read_bytes()
        _, first = self.call()
        self.assertEqual(first["removeBlocks"], [".claude/CLAUDE.md"])
        self.assertEqual(physical.read_bytes(), raw)
        self.assertEqual(self.document.lstat().st_ino, identity)
        other = self.home / "other.md"
        other.write_bytes(raw)
        self.document.unlink()
        self.document.symlink_to(other)
        _, second = self.call()
        self.assertNotEqual(first["selection"], second["selection"])
        self.assertEqual(physical.read_bytes(), raw)
        self.assertEqual(other.read_bytes(), raw)
        self.assertEqual(self.receipt.read_bytes(), receipt)
        record = fixtures.ownership.decode_record(receipt, "claude", "global")
        record["files"], record["configs"] = {}, {}
        self.receipt.write_bytes(fixtures.ownership.serialize_record(record, "claude", "global"))
        _, completed = self.call()
        self.assertEqual(completed["removeBlocks"], [])
        self.assertEqual(other.read_bytes(), raw)

if __name__ == "__main__":
    unittest.main()
