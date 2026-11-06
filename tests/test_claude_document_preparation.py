"""Claude preparation tests: AST-isolated functions, actual pure parser/adapter.

Synthetic paths never reach filesystem helpers. Installer initialization, main,
ownership acquisition and physical writer implementations are never executed.
"""
from __future__ import annotations

import ast
import contextlib
from dataclasses import FrozenInstanceError
import io
from pathlib import Path, PurePosixPath
import re
import sys
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "production_installer.py"
sys.path.insert(0, str(ROOT / "scripts"))
from installation.document_outcomes import DocumentResult, render_document
from installation.receipt_plan import plan_changes
from installer_markdown import document_context


class MemorySource(PurePosixPath):
    texts = {}
    events = []

    def read_text(self, *, encoding):
        assert encoding == "utf-8"
        self.events.append(("source", str(self)))
        value = self.texts[str(self)]
        if isinstance(value, Exception):
            raise value
        return value


class ClaudeDocumentPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(SOURCE.read_bytes())
        names = {"_prepare_claude_docs", "_merge_claude_docs",
                 "_render_claude_document", "_claude_document_context"}
        nodes = [n for n in cls.tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in names]
        if {n.name for n in nodes} != names:
            raise AssertionError("Missing Claude preparation integration function")
        constants = [n for n in cls.tree.body if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name)
                             and t.id == "_CLAUDE_DOC_MARKER_PREFIXES"
                             for t in n.targets)]
        cls.adapter_imports = [
            alias for node in ast.walk(cls.tree) if isinstance(node, ast.ImportFrom)
            and node.module == "installation.document_outcomes"
            for alias in node.names]
        cls.module = ast.fix_missing_locations(ast.Module(
            body=[ast.ImportFrom(module="__future__",
                                 names=[ast.alias(name="annotations")], level=0)]
            + constants + nodes, type_ignores=[]))

    def setUp(self):
        self.events = []
        self.writes = []
        self.owner = object()
        self.root = MemorySource("/synthetic-source")
        self.source = self.root / "src.claude"
        self.target = PurePosixPath("/synthetic-target/instructions.md")
        self.shared_target = self.target.parent / "AGENTS.md"
        self.claude_source = self.source / "CLAUDE.md"
        self.shared_source = self.root / "shared" / "AGENTS.shared.md"
        self.payloads = {"claude": "# Claude Code Pack\nClaude rule.\n",
                         "shared": "# Shared Governance\nShared rule.\n"}
        MemorySource.events = self.events
        MemorySource.texts = {
            str(self.claude_source): "@AGENTS.md\n" + self.payloads["claude"],
            str(self.shared_source): self.payloads["shared"],
        }
        self.existing = {self.target: None, self.shared_target: None}
        self.adapter = Mock(wraps=render_document)
        self.scope = {"re": re, "_markdown_document_context": document_context,
                      "_read_owned_text": self.read_owned,
                      "_write_owned_text": self.write_owned}
        for alias in self.adapter_imports:
            if alias.name == "render_document":
                self.scope[alias.asname or alias.name] = self.adapter
            elif alias.name == "DocumentResult":
                self.scope[alias.asname or alias.name] = DocumentResult
        exec(compile(self.module, "isolated-claude-preparation", "exec"), self.scope)
        self.prepare = self.scope["_prepare_claude_docs"]
        self.merge = self.scope["_merge_claude_docs"]
        self.actual_renderer = self.scope["_render_claude_document"]
        self.renderer = Mock(side_effect=self.render)
        self.scope["_render_claude_document"] = self.renderer

    def read_owned(self, target, owner, *, preserve_newlines):
        self.assertIn(target, (self.target, self.shared_target))
        self.assertIs(owner, self.owner)
        self.assertIs(preserve_newlines, True)
        self.events.append(("target", str(target)))
        value = self.existing[target]
        if isinstance(value, Exception):
            raise value
        return value

    def write_owned(self, target, content, owner):
        self.events.append(("write", str(target)))
        self.writes.append((target, content, owner))

    def render(self, existing, payload, *, claude):
        self.events.append(("render", "claude" if claude else "shared"))
        return self.actual_renderer(existing, payload, claude=claude)

    def prepare_result(self, *, project_scope=False):
        return self.prepare(self.root, self.source, self.target,
                            mutable_owner=self.owner, project_scope=project_scope)

    def merge_result(self, *, dry_run=False, project_scope=False):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = self.merge(self.root, self.source, self.target, dry_run,
                                mutable_owner=self.owner, project_scope=project_scope)
        self.assertIsNone(result)
        return output.getvalue()

    def expected_events(self):
        return [("source", str(self.claude_source)),
                ("source", str(self.shared_source)),
                ("target", str(self.target)), ("render", "claude"),
                ("target", str(self.shared_target)), ("render", "shared")]

    def test_imports_single_document_adapter(self):
        self.assertIn("render_document", [a.name for a in self.adapter_imports])

    def test_exact_preimages_and_normalized_rendering_preserve_bom_unicode(self):
        for target in self.existing:
            self.existing[target] = "\ufeffUser 😀 保留\r\nKeep\rTail\n"
        results = self.prepare_result()
        self.assertIsInstance(results, tuple)
        self.assertEqual(len(results), 2)
        self.assertEqual(self.events, self.expected_events())
        for result, target, kind in zip(results, self.existing, ("claude", "shared")):
            with self.subTest(kind=kind):
                raw = self.existing[target]
                normalized = raw.replace("\r\n", "\n").replace("\r", "\n")
                expected = self.actual_renderer(
                    normalized, self.payloads[kind], claude=kind == "claude")
                self.assertIsInstance(result, DocumentResult)
                self.assertEqual(result.before, raw.encode("utf-8"))
                self.assertEqual(result.renderer_input, normalized)
                self.assertEqual(result.after, expected.encode("utf-8"))
                self.assertEqual(result.read_mode, "universal-newlines")
                self.assertEqual(result.kind, kind)
                with self.assertRaises(FrozenInstanceError):
                    result.after = b"changed"
        self.assertEqual(self.writes, [])

    def test_scopes_and_logical_paths_are_independent_of_physical_path(self):
        for project, scope in ((False, "global"), (True, "project")):
            with self.subTest(scope=scope):
                self.adapter.reset_mock()
                results = self.prepare_result(project_scope=project)
                self.assertEqual(self.adapter.call_count, 2)
                for call, result, path in zip(
                        self.adapter.call_args_list, results,
                        (".claude/CLAUDE.md", ".claude/AGENTS.md")):
                    self.assertEqual(call.args[:4], ("claude", scope, path, None))
                    self.assertEqual(result.path, path)
                self.assertEqual(self.writes, [])

    def test_missing_and_empty_are_distinct_update_only_proposals_before_planning(self):
        for original, change in ((None, "missing-preimage"), ("", "existing-update")):
            with self.subTest(original=original):
                self.existing = dict.fromkeys(self.existing, original)
                results = self.prepare_result(project_scope=True)
                outcomes = tuple(result.as_outcome() for result in results)
                for result, outcome in zip(results, outcomes):
                    self.assertEqual(result.before, None if original is None else b"")
                    self.assertEqual(result.renderer_input, original)
                    self.assertEqual(result.change, change)
                    self.assertEqual(outcome.intent, "update")
                    self.assertIsNone(outcome.adoption_sha256)
                    self.assertIsNone(outcome.adoption_span)
                plan = plan_changes(None, "claude", "project", outcomes, document_context)
                self.assertEqual([a.route for a in plan.artifacts], ["legacy", "legacy"])
                self.assertEqual(plan.changes, ())
                self.assertEqual(self.writes, [])

    def test_existing_managed_bodies_prepare_before_plan_without_writes(self):
        for target, kind in zip(self.existing, ("claude", "shared")):
            self.existing[target] = self.actual_renderer(
                "User 😀\n", self.payloads[kind], claude=kind == "claude").replace("\n", "\r\n")
        results = self.prepare_result()
        plan = plan_changes(None, "claude", "global",
                            tuple(r.as_outcome() for r in results), document_context)
        self.assertEqual([a.route for a in plan.artifacts], ["legacy", "legacy"])
        self.assertEqual(plan.changes, ())
        self.assertEqual(self.writes, [])

    def test_each_failure_stops_later_reads_and_never_writes(self):
        for stage, event_count in (("source", 1), ("anchor", 1), ("shared-source", 2),
                                   ("first-read", 3), ("first-render", 4),
                                   ("second-read", 5), ("second-render", 6)):
            for dry_run in (False, True):
                with self.subTest(stage=stage, dry_run=dry_run):
                    self.setUp()
                    failure = ValueError("synthetic refusal")
                    if stage == "source":
                        MemorySource.texts[str(self.claude_source)] = failure
                    elif stage == "anchor":
                        MemorySource.texts[str(self.claude_source)] = "No anchor\n"
                    elif stage == "shared-source":
                        MemorySource.texts[str(self.shared_source)] = failure
                    elif stage.endswith("-read"):
                        target = self.target if stage == "first-read" else self.shared_target
                        self.existing[target] = failure
                    else:
                        def refusing_render(existing, payload, *, claude):
                            self.events.append(("render", "claude" if claude else "shared"))
                            if claude == (stage == "first-render"):
                                raise failure
                            return self.actual_renderer(existing, payload, claude=claude)
                        self.renderer.side_effect = refusing_render
                    with self.assertRaises(ValueError) as caught:
                        self.merge_result(dry_run=dry_run)
                    if stage == "anchor":
                        self.assertEqual(str(caught.exception),
                                         "E_CLAUDE_DOC_SOURCE_SHAPE: CLAUDE.md")
                    else:
                        self.assertIs(caught.exception, failure)
                    self.assertEqual(self.events, self.expected_events()[:event_count])
                    self.assertEqual(self.writes, [])

    def test_wrapper_prepares_once_then_writes_claude_and_shared_and_returns_none(self):
        self.existing[self.target] = "\ufeffUser 😀\r\n"
        self.existing[self.shared_target] = "Shared user\r"
        spy = Mock(wraps=self.prepare)
        self.scope["_prepare_claude_docs"] = spy
        self.assertEqual(self.merge_result(project_scope=True), "")
        spy.assert_called_once_with(self.root, self.source, self.target,
                                    mutable_owner=self.owner, project_scope=True)
        self.assertEqual(self.adapter.call_count, 2)
        self.assertEqual(self.events, self.expected_events() +
                         [("write", str(self.target)), ("write", str(self.shared_target))])
        for (target, content, owner), kind in zip(self.writes, ("claude", "shared")):
            normalized = self.existing[target].replace("\r\n", "\n").replace("\r", "\n")
            self.assertEqual(content, self.actual_renderer(
                normalized, self.payloads[kind], claude=kind == "claude"))
            self.assertIs(owner, self.owner)

    def test_dry_run_prepares_once_and_keeps_legacy_message_without_writes(self):
        spy = Mock(wraps=self.prepare)
        self.scope["_prepare_claude_docs"] = spy
        output = self.merge_result(dry_run=True)
        spy.assert_called_once()
        self.assertEqual(self.adapter.call_count, 2)
        self.assertEqual(self.events, self.expected_events())
        self.assertEqual(output, f"    [dry-run] would merge {self.target} and {self.shared_target}\n")
        self.assertEqual(self.writes, [])

    def test_both_outputs_are_decoded_before_first_write(self):
        from types import SimpleNamespace
        proposals = (SimpleNamespace(after=b"valid"),
                     SimpleNamespace(after=b"\xff"))
        self.scope["_prepare_claude_docs"] = Mock(return_value=proposals)
        with self.assertRaises(UnicodeDecodeError):
            self.merge_result()
        self.assertEqual(self.writes, [])

    def test_real_renderer_refusals_prevent_partial_publication(self):
        for target in self.existing:
            with self.subTest(target=target):
                self.existing = dict.fromkeys(self.existing, None)
                self.existing[target] = "<!-- BEGIN ORCHESTRARIUM CLAUDE MANAGED -->\n"
                with self.assertRaisesRegex(ValueError, "E_CLAUDE_DOC_MARKERS_INVALID"):
                    self.merge_result()
                self.assertEqual(self.writes, [])

    def test_main_explicitly_wires_scope_without_executing_main(self):
        main = next(node for node in self.tree.body
                    if isinstance(node, ast.FunctionDef) and node.name == "install")
        calls = [node for node in ast.walk(main) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name) and node.func.id == "_merge_claude_docs"]
        self.assertTrue(calls)
        expected = ast.dump(ast.parse("mode != 'global'", mode="eval").body)
        for call in calls:
            scope = next((kw.value for kw in call.keywords if kw.arg == "project_scope"), None)
            self.assertIsNotNone(scope)
            self.assertEqual(ast.dump(scope), expected)

    def test_native_wrapper_forwards_scope_keywords_without_importing_native_tests(self):
        tree = ast.parse((ROOT / "tests" / "test_native_role_slice_a.py").read_bytes())
        wrappers = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)
                    and node.name == "claude_docs"]
        self.assertEqual(len(wrappers), 1)
        wrapper = wrappers[0]
        self.assertIsNotNone(wrapper.args.kwarg)
        calls = [node for node in ast.walk(wrapper) if isinstance(node, ast.Call)
                 and isinstance(node.func, ast.Name)
                 and node.func.id == "original_claude_docs"]
        self.assertEqual(len(calls), 1)
        self.assertTrue(any(kw.arg is None and isinstance(kw.value, ast.Name)
                            and kw.value.id == wrapper.args.kwarg.arg
                            for kw in calls[0].keywords))


if __name__ == "__main__":
    unittest.main()
