"""Native Windows leaf-link receiving; run only in disposable caller storage."""
import os
import unittest
import test_presdk_uninstall as fixtures

@unittest.skipUnless(os.name == "nt", "Native Windows file-link acceptance")
class WindowsDocumentLinkTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.PhysicalTests.setUpClass.__func__)
    setUp = fixtures.PhysicalTests.setUp
    add_document = fixtures.PhysicalTests.add_document
    call = fixtures.PhysicalTests.call
    test_late_failure_rolls_back = None

    def link_document(self, absolute=False):
        raw = self.add_document()
        target = self.home / "physical.md"
        self.document.rename(target)
        self.document.symlink_to(target if absolute else "../physical.md")
        return target, raw, self.document.lstat().st_ino

    def test_relative_link_apply_repeat_preserves_link_and_user_text(self):
        target, raw, inode = self.link_document()
        _, report = self.call()
        self.assertEqual(self.call(True, report["selection"])[0], 0)
        self.assertEqual(target.read_bytes(), b"user before\r\n\r\nuser after\r\n")
        self.assertEqual(self.document.lstat().st_ino, inode)
        self.assertTrue(self.document.is_symlink())
        _, report = self.call()
        self.assertEqual(self.call(True, report["selection"])[0], 0)
        self.assertEqual(self.document.lstat().st_ino, inode)

    def test_absolute_link_rollback_restores_target_and_link(self):
        target, raw, inode = self.link_document(absolute=True)
        fixtures.PhysicalTests.test_late_failure_rolls_back(self)
        self.assertEqual(target.read_bytes(), raw)
        self.assertEqual(self.document.lstat().st_ino, inode)

    def test_same_bytes_retarget_refuses_without_mutation(self):
        target, raw, inode = self.link_document()
        _, report = self.call()
        other = self.home / "other.md"
        other.write_bytes(raw)
        self.document.unlink()
        self.document.symlink_to(other)
        with self.assertRaisesRegex(ValueError, "E_UNINSTALL_SELECTION_DRIFT"):
            self.call(True, report["selection"])
        self.assertEqual(target.read_bytes(), raw)
        self.assertEqual(other.read_bytes(), raw)
        self.assertTrue(self.file.exists())

if __name__ == "__main__":
    unittest.main()
