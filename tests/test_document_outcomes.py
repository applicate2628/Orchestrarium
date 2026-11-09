"""Pure adapter plus AST-isolated existing producers; no installer import."""
from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from installation.document_outcomes import render_document, render_documents
from installation.receipt_plan import plan_changes
from installer_markdown import document_context, document_h1_starts


class DocumentOutcomesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tree = ast.parse((ROOT / "scripts/production_installer.py").read_bytes())
        names = {"_render_codex_document", "_render_claude_document", "_claude_document_context"}
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        constants = [n for n in tree.body if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id in
                             {"CODEX_BEGIN", "CODEX_END", "_CLAUDE_DOC_MARKER_PREFIXES"}
                             for t in n.targets)]
        cls.module = ast.fix_missing_locations(ast.Module(
            body=[ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)]
            + constants + nodes, type_ignores=[]))

    def setUp(self):
        self.scope = {"re": re, "_markdown_document_h1_starts": document_h1_starts, "_markdown_document_context": document_context}
        exec(compile(self.module, "isolated-existing-producers", "exec"), self.scope)
        self.calls = []

    def codex(self, kind, text):
        self.assertEqual(kind, "codex")
        self.calls.append((kind, text))
        pack = (self.scope["CODEX_BEGIN"] + "\n# Shared Governance\nShared rule.\n\n"
                "# Codex Platform Rules\nCodex rule.\n" + self.scope["CODEX_END"] + "\n")
        return self.scope["_render_codex_document"](text, pack)

    def claude(self, kind, text):
        self.calls.append((kind, text))
        payload = "# Claude Code Pack\nClaude rule.\n" if kind == "claude" else "# Shared Governance\nShared rule.\n"
        return self.scope["_render_claude_document"](text, payload, claude=kind == "claude")

    def test_codex_exact_bytes_and_legacy_route(self):
        raw = "User 😀\r\nKeep\rTail\n".encode()
        result, = render_documents("codex", "project", {"AGENTS.md": raw}, self.codex)
        self.assertEqual(result.before, raw)
        self.assertEqual(result.renderer_input, raw.decode())
        self.assertTrue(result.after.endswith(raw))
        self.assertEqual(result.read_mode, "exact-newlines")
        self.assertEqual(result.change, "existing-update")
        plan = plan_changes(None, "codex", "project", (result.as_outcome(),), document_context)
        self.assertEqual(plan.artifacts[0].route, "legacy")
        self.assertEqual(plan.changes, ())

    def test_codex_missing_not_creation_authority(self):
        result, = render_documents("codex", "project", {"AGENTS.md": None}, self.codex)
        self.assertEqual(result.change, "missing-preimage")
        self.assertIsNone(result.before)
        self.assertEqual(result.as_outcome().intent, "update")
        plan = plan_changes(None, "codex", "project", (result.as_outcome(),), document_context)
        self.assertEqual(plan.artifacts[0].route, "legacy")
        self.assertEqual(plan.changes, ())

    def test_empty_is_not_absent(self):
        result, = render_documents("codex", "project", {"AGENTS.md": b""}, self.codex)
        self.assertEqual(result.before, b"")
        self.assertEqual(result.renderer_input, "")
        self.assertEqual(result.change, "existing-update")

    def test_marked_and_examples_use_existing_codex_producer(self):
        begin, end = self.scope["CODEX_BEGIN"], self.scope["CODEX_END"]
        prefix = "Example\r\n```\r\n" + begin + "\r\nExample\r\n" + end + "\r\n```\r\n"
        suffix = "\rUSER TAIL\r\n"
        raw = (prefix + begin + "\r\nOld\r\n" + end + suffix).encode()
        result, = render_documents("codex", "project", {"AGENTS.md": raw}, self.codex)
        self.assertTrue(result.after.startswith(prefix.encode()))
        self.assertTrue(result.after.endswith(suffix.encode()))
        self.assertEqual(result.as_outcome().before, raw)

    def test_claude_retains_raw_before_and_after(self):
        raw = "User 😀\r\nKeep\rTail\n".encode()
        inputs = {".claude/CLAUDE.md": raw, ".claude/AGENTS.md": b"Other\r"}
        results = render_documents("claude", "global", inputs, self.claude)
        self.assertEqual(tuple(r.path for r in results), tuple(inputs))
        for result in results:
            self.assertEqual(result.before, inputs[result.path])
            self.assertEqual(result.renderer_input, inputs[result.path].decode())
            self.assertEqual(result.read_mode, "exact-newlines")
            self.assertEqual(result.as_outcome().intent, "update")
        self.assertTrue(results[0].after.endswith(raw))
        self.assertEqual([x.route for x in plan_changes(None, "claude", "global",
                         tuple(r.as_outcome() for r in results), document_context).artifacts],
                         ["legacy", "legacy"])

    def test_claude_marked_updates_preserve_exact_outside_newlines(self):
        for kind, path in (("claude", ".claude/CLAUDE.md"), ("shared", ".claude/AGENTS.md")):
            for newline in ("\n", "\r\n", "\r"):
                with self.subTest(kind=kind, newline=repr(newline)):
                    prefix = "\ufeffUser 😀\r\nMixed\r" + ("@AGENTS.md" + newline if kind == "claude" else "")
                    begin = f"<!-- BEGIN ORCHESTRARIUM {kind.upper()} MANAGED -->" + newline
                    end = f"<!-- END ORCHESTRARIUM {kind.upper()} MANAGED -->" + newline
                    suffix = "Tail\r\nKeep\rLast without newline"
                    raw = (prefix + begin + "Old body" + newline + end + suffix).encode()
                    result = render_document("claude", "project", path, raw, self.claude)
                    payload = "# Claude Code Pack\nClaude rule.\n" if kind == "claude" else "# Shared Governance\nShared rule.\n"
                    self.assertEqual(result.after, (prefix + begin + payload + end + suffix).encode())
                    self.assertEqual(result.before, raw)

    def test_claude_lone_cr_boundary_does_not_absorb_new_blank_line(self):
        prefix = "User\r<!-- BEGIN ORCHESTRARIUM SHARED MANAGED -->\r"
        suffix = "<!-- END ORCHESTRARIUM SHARED MANAGED -->\rTail"
        raw = prefix + "Old\r" + suffix
        payload = "\nNew rule.\n"
        after = self.scope["_render_claude_document"](raw, payload, claude=False)
        self.assertEqual(after, prefix + "\r\nNew rule.\n" + suffix)
        normalize = lambda value: value.replace("\r\n", "\n").replace("\r", "\n")
        self.assertEqual(normalize(after), normalize(prefix) + payload + normalize(suffix))

    def test_claude_noop_keeps_every_existing_newline(self):
        for kind, path in (("claude", ".claude/CLAUDE.md"), ("shared", ".claude/AGENTS.md")):
            for newline in ("\r\n", "\r"):
                with self.subTest(kind=kind, newline=repr(newline)):
                    raw = ("User\r\n" + self.claude(kind, None).replace("\n", newline) + "Tail\r").encode()
                    result = render_document("claude", "global", path, raw, self.claude)
                    self.assertEqual(result.after, raw)
                    self.assertEqual(result.change, "unchanged")

    def test_claude_legacy_and_import_insertion_preserve_outside_bytes(self):
        prefix, suffix = "User 😀\r\n", "Tail\rNo newline"
        for kind, path in (("claude", ".claude/CLAUDE.md"), ("shared", ".claude/AGENTS.md")):
            payload = "# Claude Code Pack\nClaude rule.\n" if kind == "claude" else "# Shared Governance\nShared rule.\n"
            anchor = "@AGENTS.md\r\n" if kind == "claude" else ""
            raw = (prefix + anchor + payload.replace("\n", "\r\n") + suffix).encode()
            result = render_document("claude", "global", path, raw, self.claude)
            self.assertTrue(result.after.startswith((prefix + anchor).encode()))
            self.assertTrue(result.after.endswith(suffix.encode()))
        raw = (prefix + "@AGENTS.md\r" + suffix).encode()
        result = render_document("claude", "global", ".claude/CLAUDE.md", raw, self.claude)
        self.assertTrue(result.after.startswith(prefix.encode()))
        self.assertTrue(result.after.endswith(("@AGENTS.md\r" + suffix).encode()))

    def test_claude_second_refusal_returns_no_partial_batch(self):
        inputs = {".claude/CLAUDE.md": None,
                  ".claude/AGENTS.md": b"# Shared Governance\nChanged unknown old body\n"}
        with self.assertRaisesRegex(ValueError, "LEGACY_AMBIGUOUS"):
            render_documents("claude", "project", inputs, self.claude)
        self.assertEqual([k for k, _ in self.calls], ["claude", "shared"])
        self.assertEqual(inputs[".claude/AGENTS.md"], b"# Shared Governance\nChanged unknown old body\n")

    def test_decode_all_preimages_before_render(self):
        for raw in (b"\xff", bytearray(b"not immutable"), "text"):
            with self.subTest(raw=raw):
                with self.assertRaises((ValueError, UnicodeError)):
                    render_documents("claude", "project",
                                     {".claude/CLAUDE.md": None, ".claude/AGENTS.md": raw},
                                     self.claude)
                self.assertEqual(self.calls, [])

    def test_exact_document_set_required_before_callbacks(self):
        for inputs in ({}, {"AGENTS.md": None, "extra": None}, {"agents.md": None}):
            with self.assertRaises(ValueError):
                render_documents("codex", "project", inputs, self.codex)
        self.assertEqual(self.calls, [])

    def test_global_codex_path(self):
        result, = render_documents("codex", "global", {".codex/AGENTS.md": b"User"}, self.codex)
        self.assertEqual(result.path, ".codex/AGENTS.md")

    def test_provider_scope_rejected(self):
        for provider, scope in (("unknown", "project"), ("codex", "other")):
            with self.assertRaises(ValueError):
                render_documents(provider, scope, {}, self.codex)
        self.assertEqual(self.calls, [])

    def test_callback_result_and_errors_not_suppressed(self):
        for result in (None, b"bytes", 1):
            with self.assertRaises(ValueError):
                render_documents("codex", "project", {"AGENTS.md": b"User"},
                                 lambda *_: result)
        def refuse(*_):
            raise RuntimeError("producer refused")
        with self.assertRaisesRegex(RuntimeError, "producer refused"):
            render_documents("codex", "project", {"AGENTS.md": b"User"}, refuse)

    def test_unencodable_render_refuses(self):
        with self.assertRaises(UnicodeError):
            render_documents("codex", "project", {"AGENTS.md": b"User"},
                             lambda *_: "\ud800")

    def test_snapshot_before_callbacks(self):
        inputs = {".claude/CLAUDE.md": b"First", ".claude/AGENTS.md": b"Original"}
        def render(kind, text):
            inputs[".claude/AGENTS.md"] = b"Changed"
            return text
        results = render_documents("claude", "project", inputs, render)
        self.assertEqual(results[1].before, b"Original")
        self.assertEqual(results[1].after, b"Original")

    def test_unchanged_and_frozen(self):
        result, = render_documents("codex", "project", {"AGENTS.md": b"User"},
                                  lambda _kind, text: text)
        self.assertEqual(result.change, "unchanged")
        with self.assertRaises(FrozenInstanceError):
            result.after = b"Changed"

    def test_recorded_claude_noop_preserves_raw_preimage(self):
        import json
        from installation import configuration, ownership
        text = self.claude("claude", None)
        raw = ("USER PREFIX\r\n" + text + "USER TAIL\r").encode()
        shared = self.claude("shared", None).encode()
        record = {"schema": ownership.SCHEMA, "provider": "claude", "scope": "project",
                  "files": {}, "configs": {".claude/CLAUDE.md": {
                      "kind": "block", "blockKind": "claude",
                      "sha256": configuration.block_digest(raw.decode(), "claude", document_context)}}}
        results = render_documents("claude", "project",
                                   {".claude/CLAUDE.md": raw, ".claude/AGENTS.md": shared}, self.claude)
        plan = plan_changes(json.dumps(record).encode(), "claude", "project",
                            tuple(r.as_outcome() for r in results), document_context)
        self.assertEqual([a.route for a in plan.artifacts], ["recorded-proposal", "legacy"])
        self.assertEqual(results[0].after, raw)
        self.assertEqual(results[0].before, raw)

    def test_adapter_keeps_raw_inline_end_boundary(self):
        begin, end = self.scope["CODEX_BEGIN"], self.scope["CODEX_END"]
        tail = "`\nOld\n" + end + "\nUSER TAIL KEEP\n"
        raw = (begin + "\nExample `" + end + tail).encode()
        pack = self.codex("codex", None)
        result, = render_documents("codex", "project", {"AGENTS.md": raw}, self.codex)
        self.assertEqual(result.after, (pack.rstrip("\n") + tail).encode())
        self.assertEqual(result.before, raw)

    def test_adapter_masked_end_keeps_second_block(self):
        begin, end = self.scope["CODEX_BEGIN"], self.scope["CODEX_END"]
        tail = ("\n```\nUSER BETWEEN KEEP\n" + begin
                + "\nSecond body\n" + end + "\nUSER LAST KEEP\n")
        raw = (begin + "\n# Shared Governance\n```markdown\nExample\n" + end + tail).encode()
        pack = self.codex("codex", None)
        result, = render_documents("codex", "project", {"AGENTS.md": raw}, self.codex)
        self.assertEqual(result.after, (pack.rstrip("\n") + tail).encode())
        self.assertEqual(result.as_outcome().before, raw)

    def test_adapter_legacy_unclosed_fence_keeps_raw_policy(self):
        tail = "## Project policies\nUSER TAIL KEEP\n"
        raw = ("# Shared Governance\nOld\n```markdown\nExample\n" + tail).encode()
        pack = self.codex("codex", None)
        result, = render_documents("codex", "project", {"AGENTS.md": raw}, self.codex)
        self.assertEqual(result.after, (pack + tail).encode())
        self.assertEqual(result.as_outcome().intent, "update")

    def test_adapter_missing_end_propagates_exact_error_without_writer(self):
        raw = (self.scope["CODEX_BEGIN"] + "\n# Shared Governance\nUSER TAIL KEEP\n").encode()
        with self.assertRaises(ValueError) as caught:
            render_documents("codex", "project", {"AGENTS.md": raw}, self.codex)
        self.assertEqual(str(caught.exception),
                         "E_CODEX_DOCUMENT_AMBIGUOUS: missing managed end marker")

    def test_adapter_absent_codex_does_not_invoke_parser(self):
        def unexpected(_text):
            self.fail("Absent document must not invoke parser")
        self.scope["_markdown_document_context"] = unexpected
        result, = render_documents("codex", "project", {"AGENTS.md": None}, self.codex)
        self.assertTrue(result.after.startswith(self.scope["CODEX_BEGIN"].encode()))
        self.assertEqual(result.as_outcome().intent, "update")
        self.assertIsNone(result.before)

    def test_no_receipt_or_adoption_selection_in_adapter(self):
        result, = render_documents("codex", "project", {"AGENTS.md": b"User"}, self.codex)
        outcome = result.as_outcome()
        self.assertIsNone(outcome.adoption_sha256)
        self.assertIsNone(outcome.adoption_span)
        self.assertEqual(outcome.intent, "update")

    def test_single_matches_batch_for_each_provider_scope_and_kind(self):
        cases = (("codex", "global", {".codex/AGENTS.md": b"User"}),
                 ("codex", "project", {"AGENTS.md": b"User"}),
                 ("claude", "global", {".claude/CLAUDE.md": b"User",
                                       ".claude/AGENTS.md": b"Other"}),
                 ("claude", "project", {".claude/CLAUDE.md": b"User",
                                        ".claude/AGENTS.md": b"Other"}))
        for provider, scope, inputs in cases:
            with self.subTest(provider=provider, scope=scope):
                renderer = self.codex if provider == "codex" else self.claude
                batch = render_documents(provider, scope, inputs, renderer)
                single = tuple(render_document(provider, scope, path, raw, renderer)
                               for path, raw in inputs.items())
                self.assertEqual(single, batch)

    def test_single_rejects_unknown_or_non_string_paths_before_callback(self):
        class StringPath(str):
            pass
        for path in ("", "CLAUDE.md", "agents.md", "../AGENTS.md",
                     ".codex/AGENTS.md", None, [], Path("AGENTS.md"),
                     StringPath("AGENTS.md")):
            with self.subTest(path=path):
                with self.assertRaisesRegex(ValueError, "E_DOCUMENT_OUTCOMES_PATH"):
                    render_document("codex", "project", path, b"User", self.codex)
        self.assertEqual(self.calls, [])

    def test_single_rejects_provider_scope_and_preimages_without_callback(self):
        for provider, scope in (("unknown", "project"), ("codex", "other"),
                                (None, "project")):
            with self.subTest(provider=provider, scope=scope):
                with self.assertRaises(ValueError):
                    render_document(provider, scope, "AGENTS.md", b"User", self.codex)
        for raw in (b"\xff", bytearray(b"User"), memoryview(b"User"), "User", 0):
            with self.subTest(raw=raw):
                with self.assertRaises((ValueError, UnicodeError)):
                    render_document("codex", "project", "AGENTS.md", raw, self.codex)
        self.assertEqual(self.calls, [])

    def test_single_callback_contract_and_errors(self):
        for renderer in (None, "renderer", 1):
            with self.assertRaisesRegex(ValueError, "E_DOCUMENT_OUTCOMES_RENDERER"):
                render_document("codex", "project", "AGENTS.md", b"\xff", renderer)
        for rendered in (None, b"bytes", 1):
            with self.assertRaisesRegex(ValueError, "E_DOCUMENT_OUTCOMES_RENDERED_TEXT"):
                render_document("codex", "project", "AGENTS.md", b"User",
                                lambda *_: rendered)
        def refuse(*_):
            raise RuntimeError("producer refused")
        with self.assertRaisesRegex(RuntimeError, "producer refused"):
            render_document("codex", "project", "AGENTS.md", None, refuse)
        with self.assertRaises(UnicodeError):
            render_document("codex", "project", "AGENTS.md", None, lambda *_: "\ud800")

    def test_single_missing_empty_unchanged_and_update_only(self):
        for raw, expected in ((None, "missing-preimage"), (b"", "unchanged"),
                              (b"User", "unchanged")):
            with self.subTest(raw=raw):
                result = render_document("codex", "project", "AGENTS.md", raw,
                                         lambda _kind, text: "" if text is None else text)
                self.assertEqual(result.change, expected)
                self.assertEqual(result.before, raw)
                self.assertEqual(result.renderer_input, None if raw is None else raw.decode())
                outcome = result.as_outcome()
                self.assertEqual(outcome.intent, "update")
                self.assertEqual(outcome.before, raw)
                self.assertIsNone(outcome.adoption_sha256)
                self.assertIsNone(outcome.adoption_span)
                with self.assertRaises(FrozenInstanceError):
                    result.before = b"Changed"

    def test_single_exact_raw_and_provider_newline_views(self):
        raw = "User \u2603\r\nKeep\rTail\n".encode()
        for provider, path, expected, mode in (
            ("codex", "AGENTS.md", raw.decode(), "exact-newlines"),
            ("claude", ".claude/AGENTS.md", raw.decode(),
             "exact-newlines"),
        ):
            with self.subTest(provider=provider):
                calls = []
                def render(kind, text):
                    calls.append((kind, text))
                    return text
                result = render_document(provider, "project", path, raw, render)
                self.assertEqual(calls, [("codex" if provider == "codex" else "shared", expected)])
                self.assertIs(result.before, raw)
                self.assertEqual(result.renderer_input, expected)
                self.assertEqual(result.after, expected.encode())
                self.assertEqual(result.read_mode, mode)
                self.assertEqual(result.change, "unchanged")
                self.assertEqual(result.as_outcome().intent, "update")

    def test_batch_validation_order_remains_complete_map_then_callback_then_decode(self):
        with self.assertRaisesRegex(ValueError, "E_DOCUMENT_OUTCOMES_INPUT_SET"):
            render_documents("codex", "project", {}, None)
        with self.assertRaisesRegex(ValueError, "E_DOCUMENT_OUTCOMES_RENDERER"):
            render_documents("codex", "project", {"AGENTS.md": b"\xff"}, None)
        inputs = {".claude/CLAUDE.md": b"\xff", ".claude/AGENTS.md": "bad"}
        with self.assertRaises(UnicodeDecodeError):
            render_documents("claude", "project", inputs, self.claude)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
