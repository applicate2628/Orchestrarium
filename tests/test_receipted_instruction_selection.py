"""Pure receipt projection tests; no installer or physical owner is imported."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from installation.instruction_selection import (
    claude_instruction_grants_from_receipt as select,
    parse_claude_receipt_grant as parse,
)

ERROR = "E_CLAUDE_RECEIPT_SELECTION_INVALID"
OLD = "a" * 64
OTHER = "b" * 64
SOURCES = frozenset({"agents/lead.md", "commands/nested/review.MD"})


def payload(files=None, **changes):
    value = dict(schema="orche.provider-install.v1", provider="claude",
                 scope="project", files={".claude/agents/lead.md": OLD}
                 if files is None else files)
    value.update(changes)
    return json.dumps(value).encode("utf-8")


def pin(raw):
    return hashlib.sha256(raw).hexdigest()


class ReceiptedInstructionSelectionTests(unittest.TestCase):
    def invalid(self, raw, digest=None, scope="project", sources=SOURCES):
        with self.assertRaisesRegex(ValueError, "^" + ERROR + "$"):
            select(raw, pin(raw) if digest is None else digest, scope, sources)

    def test_pin_is_explicit_optional_and_strict(self):
        self.assertIsNone(parse(()))
        self.assertEqual(parse((OLD,)), OLD)
        class Text(str):
            pass
        class Values(tuple):
            pass
        for values in (None, True, False, [], {}, OLD, (OLD, OLD),
                       (None,), (True,), (b"a" * 64,), (Text(OLD),),
                       Values((OLD,))):
            with self.subTest(values=values):
                with self.assertRaisesRegex(ValueError, "^" + ERROR + "$"):
                    parse(values)

    def test_bad_digest_values(self):
        for digest in ("", "a" * 63, "a" * 65, "A" * 64, "g" * 64,
                       OLD + "\n", " " + OLD, "sha256:" + OLD):
            with self.subTest(digest=digest):
                with self.assertRaisesRegex(ValueError, "^" + ERROR + "$"):
                    parse((digest,))
                self.invalid(payload(), digest=digest)
        for digest in (True, None, 0, b"a" * 64, [], {}):
            with self.subTest(digest=digest):
                with self.assertRaisesRegex(ValueError, "^" + ERROR + "$"):
                    select(payload(), digest, "project", SOURCES)

    def test_raw_bytes_digest_includes_whitespace(self):
        raw = payload()
        spaced = b" \n" + raw + b"\n "
        self.assertEqual(select(spaced, pin(spaced), "project", SOURCES),
                         {"agents/lead.md": OLD})
        self.invalid(spaced, digest=pin(raw))
        self.invalid(raw, digest=OTHER)

    def test_scope_and_provider_must_match(self):
        self.invalid(payload(provider="codex"))
        self.invalid(payload(scope="global"))
        raw = payload(scope="global")
        self.assertEqual(select(raw, pin(raw), "global", SOURCES),
                         {"agents/lead.md": OLD})
        for scope in ("", "PROJECT", None, True, [], {}):
            with self.subTest(scope=scope):
                self.invalid(payload(), scope=scope)

    def test_malformed_and_duplicate_json_refuse(self):
        for raw in (b"", b"{}", b"null", b"[]", b"false", b"\xff",
                    payload()[:-1], payload()[:-1] + b',"scope":"project"}',
                    payload().replace(b'"files": {', b'"files": {".claude/agents/lead.md":"' + OLD.encode() + b'",')):
            with self.subTest(raw=raw):
                self.invalid(raw)

    def test_receipt_type_is_exact_bytes(self):
        class Bytes(bytes):
            pass
        for raw in (None, True, "", [], {}, bytearray(payload()), Bytes(payload())):
            with self.subTest(raw=raw):
                self.invalid(raw, digest=OLD)

    def test_catalog_is_validated_even_without_matches(self):
        for sources in (None, True, set(), [], {}, ("agents/lead.md",),
                        frozenset({None}), frozenset({"agents/lead.md", "agents/LEAD.md"}),
                        frozenset({"commands/Straße.md", "commands/STRASSE.md"}),
                        frozenset({"agents/../lead.md"}), frozenset({"skills/lead.md"}),
                        frozenset({"agents/nested/lead.md"})):
            with self.subTest(sources=sources):
                self.invalid(payload(), sources=sources)

    def test_receipt_case_aliases_are_not_silently_excluded(self):
        for name in (".claude/agents/LEAD.md", ".claude/Agents/lead.md",
                     ".Claude/agents/lead.md"):
            with self.subTest(name=name):
                self.invalid(payload({name: OLD}))
                self.invalid(payload({".claude/agents/lead.md": OLD, name: OLD}))
        self.invalid(payload({".claude/commands/STRASSE.md": OLD}),
                     sources=frozenset({"commands/Straße.md"}))

    def test_only_current_source_listed_file_entries_are_selected(self):
        raw = payload({
            ".claude/agents/lead.md": OLD,
            ".claude/agents/retired.md": OTHER,
            ".claude/skills/example/SKILL.md": OTHER,
            ".claude/contracts/example.md": OTHER,
            ".claude/CLAUDE.md": OTHER,
            ".claude/settings.json": OTHER,
            ".claude/commands/nested/unlisted.md": OTHER,
        }, configs={".claude/AGENTS.md": {
            "kind": "block", "blockKind": "shared", "sha256": OTHER}})
        self.assertEqual(select(raw, pin(raw), "project", SOURCES),
                         {"agents/lead.md": OLD})

    def test_empty_or_no_eligible_selection_refuses(self):
        for raw in (payload({}), payload({".claude/agents/retired.md": OLD}),
                    payload({}, configs={".claude/CLAUDE.md": {
                        "kind": "block", "blockKind": "claude", "sha256": OLD}}),
                    payload({}, directories=[".claude/agents/lead.md"])):
            with self.subTest(raw=raw):
                self.invalid(raw)
        self.invalid(payload(), sources=frozenset())

    def test_record_schema_and_digest_validation_is_not_bypassed(self):
        for raw in (payload(schema="other"), payload(files=[]),
                    payload({".claude/agents/lead.md": True}),
                    payload({".claude/agents/lead.md": "A" * 64}),
                    payload({".claude/agents/lead.md": OLD,
                             ".claude/agents/../escape.md": OTHER}),
                    payload(layout="other"), payload(extra=True)):
            with self.subTest(raw=raw):
                self.invalid(raw)

    def test_deterministic_order_and_no_mutation(self):
        entries = {".claude/commands/nested/review.MD": OTHER,
                   ".claude/agents/lead.md": OLD}
        raw = payload(entries)
        before = raw[:]
        expected = [("agents/lead.md", OLD), ("commands/nested/review.MD", OTHER)]
        result = select(raw, pin(raw), "project", SOURCES)
        self.assertEqual(list(result.items()), expected)
        reverse = payload(dict(reversed(list(entries.items()))))
        self.assertEqual(list(select(reverse, pin(reverse), "project", SOURCES).items()), expected)
        result.clear()
        self.assertEqual(list(select(raw, pin(raw), "project", SOURCES).items()), expected)
        self.assertEqual(raw, before)
        self.assertEqual(SOURCES, frozenset({"agents/lead.md", "commands/nested/review.MD"}))


if __name__ == "__main__":
    unittest.main()
