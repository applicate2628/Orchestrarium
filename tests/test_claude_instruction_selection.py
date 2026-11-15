"""Pure selection tests; load only the leaf parser, never an installer."""
import importlib.util
from pathlib import Path
import unittest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts/installation/instruction_selection.py"
SPEC = importlib.util.spec_from_file_location("instruction_selection_under_test", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)
parse = MODULE.parse_claude_instruction_grants
ERROR = "E_CLAUDE_INSTRUCTION_SELECTION_INVALID"
DIGEST = "0123456789abcdef" * 4
SOURCES = frozenset({"agents/lead.md", "commands/nested/review.MD"})


class InstructionSelectionTests(unittest.TestCase):
    def invalid(self, values, sources=SOURCES):
        with self.assertRaisesRegex(ValueError, "^" + ERROR + "$"):
            parse(values, sources)

    def test_agent_and_recursive_command_preserve_input_order(self):
        values = ("commands/nested/review.MD=" + DIGEST, "agents/lead.md=" + "a" * 64)
        result = parse(values, SOURCES)
        self.assertEqual(list(result.items()), [
            ("commands/nested/review.MD", DIGEST), ("agents/lead.md", "a" * 64)])

    def test_empty_grants_do_not_infer_adoption_or_history_from_source(self):
        self.assertEqual(parse((), SOURCES), {})
        self.assertEqual(parse((), frozenset()), {})

    def test_source_catalog_does_not_select_unrequested_entries(self):
        self.assertEqual(parse(("agents/lead.md=" + DIGEST,), SOURCES),
                         {"agents/lead.md": DIGEST})

    def test_unknown_or_absent_source_is_rejected(self):
        self.invalid(("agents/missing.md=" + DIGEST,))
        self.invalid(("agents/lead.md=" + DIGEST,), frozenset())

    def test_exact_source_spelling_is_required(self):
        for name in ("agents/Lead.md", "commands/nested/review.md", "Agents/lead.md"):
            with self.subTest(name=name):
                self.invalid((name + "=" + DIGEST,))

    def test_duplicate_grants_are_rejected_even_with_same_digest(self):
        self.invalid(("agents/lead.md=" + DIGEST,) * 2)
        self.invalid(("agents/lead.md=" + DIGEST, "agents/lead.md=" + "f" * 64))

    def test_casefold_alias_grants_are_rejected(self):
        self.invalid(("agents/lead.md=" + DIGEST, "agents/LEAD.md=" + DIGEST))

    def test_ambiguous_source_catalog_is_rejected_without_grants(self):
        for sources in (
            frozenset({"agents/lead.md", "agents/LEAD.md"}),
            frozenset({"commands/Straße.md", "commands/STRASSE.md"}),
        ):
            with self.subTest(sources=sources):
                self.invalid((), sources)

    def test_unsafe_names_are_rejected_in_grants_and_source_catalog(self):
        names = (
            "", "/agents/lead.md", "//agents/lead.md", "C:/agents/lead.md",
            "agents\\lead.md", "agents/../lead.md", "agents/./lead.md",
            "commands//lead.md", "commands/x./lead.md", "commands/x /lead.md",
            "commands/ lead.md", "commands/a\t.md", "commands/a\n.md",
            "commands/a\x00.md", "commands/a\x7f.md", "commands/a\x85.md",
            "commands/a\u200b.md", "commands/a\ud800.md",
            "agents/nested/lead.md", "commands/lead.txt", "commands/.md",
            "commands/__pycache__/lead.md", "commands/__PYCACHE__/lead.md",
            "receipts/lead.md", "commands/receipts/lead.md",
            "commands/a:stream.md", "commands/a=other.md",
            "commands/a*.md", "commands/a?.md", "commands/a|b.md",
            "commands/a<.md", 'commands/a".md', "agents/lead.md/",
            ".claude/agents/lead.md",
        )
        for name in names:
            with self.subTest(name=name):
                self.invalid((name + "=" + DIGEST,), frozenset({name}))
                self.invalid((), frozenset({name}))

    def test_malformed_digest_and_separator_are_rejected(self):
        for digest in ("", "a" * 63, "a" * 65, "A" * 64, "g" * 64,
                       DIGEST + "\n", " " + DIGEST, DIGEST + "=", "sha256:" + DIGEST):
            with self.subTest(digest=digest):
                self.invalid(("agents/lead.md=" + digest,))
        self.invalid(("agents/lead.md",))

    def test_nonstring_entries_fail_with_consistent_error(self):
        for value in (None, True, 0, b"agents/lead.md", {}, []):
            with self.subTest(value=value):
                self.invalid((value,))
        for name in (None, True, 0, b"agents/lead.md"):
            with self.subTest(name=name):
                self.invalid((), frozenset({name}))

    def test_container_types_are_explicit_not_truthy_force(self):
        for values in (None, True, False, [], {}, "", "agents/lead.md=" + DIGEST):
            with self.subTest(values=values):
                self.invalid(values)
        for sources in (None, True, [], {}, set(), ("agents/lead.md",)):
            with self.subTest(sources=sources):
                self.invalid((), sources)

    def test_inputs_are_not_mutated_and_results_are_independent(self):
        values = ("agents/lead.md=" + DIGEST,)
        sources = SOURCES
        result = parse(values, sources)
        result.clear()
        self.assertEqual(parse(values, sources), {"agents/lead.md": DIGEST})
        self.assertEqual(values, ("agents/lead.md=" + DIGEST,))
        self.assertEqual(sources, SOURCES)


if __name__ == "__main__":
    unittest.main()
