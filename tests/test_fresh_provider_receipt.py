"""Pure fresh-payload serialization; no installer or filesystem operations."""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from installation import ownership
from installation.clients import get_client

DIGEST = "a" * 64


class FreshProviderReceiptTests(unittest.TestCase):
    def test_empty_returns_none_for_both_providers_and_scopes(self):
        for provider in ("codex", "claude"):
            for scope in ("global", "project"):
                with self.subTest(provider=provider, scope=scope):
                    self.assertIsNone(ownership.serialize_fresh_payloads({}, provider, scope))

    def test_all_payload_roots_have_exact_minimal_record(self):
        for provider in ("codex", "claude"):
            for scope in ("global", "project"):
                files = {root + "/fake.txt": DIGEST
                         for root in get_client(provider)["payload_roots"]}
                with self.subTest(provider=provider, scope=scope):
                    raw = ownership.serialize_fresh_payloads(files, provider, scope)
                    expected = dict(schema=ownership.SCHEMA, provider=provider,
                                    scope=scope, files=files)
                    self.assertEqual(ownership.decode_record(raw, provider, scope), expected)
                    self.assertEqual(raw, ownership.serialize_record(expected, provider, scope))
                    self.assertTrue(raw.endswith(b"\n"))

    def test_root_boundaries_are_not_payload_children(self):
        for provider in ("codex", "claude"):
            files = {}
            for root in get_client(provider)["payload_roots"]:
                files[root] = DIGEST
                files[root + "-other/fake.txt"] = DIGEST
            self.assertIsNone(ownership.serialize_fresh_payloads(files, provider, "project"))

    def test_documents_configs_caches_and_receipts_are_excluded(self):
        for provider in ("codex", "claude"):
            client = get_client(provider)
            for scope in ("global", "project"):
                files = {path: DIGEST for path in client["documents"][scope]}
                files[client["mode_file"][scope]] = DIGEST
                files[client["registration"]] = DIGEST
                if client["native_config"]:
                    files[client["native_config"]] = DIGEST
                for root in client["payload_roots"]:
                    files[root + "/__pycache__/fake.pyc"] = DIGEST
                    files[root + "/nested/__pycache__/fake.pyc"] = DIGEST
                    files[root + "/" + ownership.RECEIPT_NAME] = DIGEST
                    files[root + "/nested/" + ownership.RECEIPT_NAME] = DIGEST
                self.assertIsNone(ownership.serialize_fresh_payloads(files, provider, scope))

    def test_only_confirmed_payload_input_is_retained_without_mutation(self):
        files = {".claude/agents/fake.md": DIGEST, ".claude/settings.json": DIGEST,
                 ".claude/skills/cache-like/__pycache__-notes.txt": DIGEST}
        original = files.copy()
        raw = ownership.serialize_fresh_payloads(files, "claude", "global")
        self.assertEqual(json.loads(raw)["files"], {
            ".claude/agents/fake.md": DIGEST,
            ".claude/skills/cache-like/__pycache__-notes.txt": DIGEST})
        self.assertEqual(files, original)
        self.assertEqual(set(json.loads(raw)), {"schema", "provider", "scope", "files"})

    def test_case_aliases_are_rejected_without_mutation(self):
        files = {".agents/skills/Fake.txt": DIGEST, ".agents/skills/fake.txt": DIGEST}
        original = files.copy()
        with self.assertRaises(ValueError):
            ownership.serialize_fresh_payloads(files, "codex", "project")
        self.assertEqual(files, original)

    def test_included_malformed_paths_are_rejected(self):
        for suffix in ("../fake", "./fake", "/fake", "fake/", "fake.", "fake ",
                       "fake:stream", "fake\\child", "fake\x00"):
            with self.subTest(suffix=suffix), self.assertRaises(ValueError):
                ownership.serialize_fresh_payloads(
                    {".agents/skills/" + suffix: DIGEST}, "codex", "global")

    def test_included_malformed_digests_are_rejected(self):
        for digest in ("", "a" * 63, "a" * 65, "A" * 64, "z" * 64, None, 42, {}):
            with self.subTest(digest=digest), self.assertRaises(ValueError):
                ownership.serialize_fresh_payloads(
                    {".claude/skills/fake.txt": digest}, "claude", "project")

    def test_invalid_identity_or_input_schema_is_rejected_even_if_empty(self):
        for provider, scope in (("unknown", "project"), ("codex", "other")):
            with self.subTest(provider=provider, scope=scope), self.assertRaises(ValueError):
                ownership.serialize_fresh_payloads({}, provider, scope)
        for files in (None, [], {"schema": ownership.SCHEMA, "files": {}}, {7: DIGEST}):
            with self.subTest(files=files), self.assertRaises(ValueError):
                ownership.serialize_fresh_payloads(files, "codex", "project")


if __name__ == "__main__":
    unittest.main()
