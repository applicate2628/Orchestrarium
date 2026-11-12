"""Preparation integration with memory I/O and the actual pure adapter/parser.

Only selected function definitions are executed, never installer initialization
or physical ownership acquisition. Synthetic paths are deliberately not files.
"""
from __future__ import annotations

import ast
import contextlib
from dataclasses import FrozenInstanceError
import io
from pathlib import Path, PurePosixPath
import sys
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "production_installer.py"
sys.path.insert(0, str(ROOT / "scripts"))
from installation.document_outcomes import DocumentResult, render_documents
from installation.receipt_plan import plan_changes
from installer_markdown import document_context, document_h1_starts


class MemorySource(PurePosixPath):
    texts = {}
    events = []

    def read_text(self, *, encoding):
        assert encoding == "utf-8"
        self.events.append(("source", str(self)))
        return self.texts[str(self)]


class CodexDocumentPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(SOURCE.read_bytes())
        names = {"_prepare_codex_agents", "_merge_codex_agents", "_render_codex_document", "_codex_document_payload", "_warn_codex_project_budget"}
        nodes = [n for n in cls.tree.body if isinstance(n, ast.FunctionDef)
                 and n.name in names]
        if {n.name for n in nodes} != names:
            raise AssertionError("Missing Codex preparation integration function")
        constants = [n for n in cls.tree.body if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id in
                             {"CODEX_BEGIN", "CODEX_END"} for t in n.targets)]
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
        self.existing = None
        self.owner = object()
        self.root = MemorySource("/synthetic-source")
        self.source = self.root / "src.codex"
        self.target = PurePosixPath("/synthetic-target/instructions.md")
        MemorySource.events = self.events
        MemorySource.texts = {
            str(self.root / "shared" / "AGENTS.shared.md"):
                "# Shared Governance\nShared rule.\n",
            str(self.source / "AGENTS.codex.md"):
                "# Codex Platform Rules\nCodex rule.\n",
        }
        self.adapter = Mock(wraps=render_documents)
        self.scope = {
            "_markdown_document_h1_starts": document_h1_starts, "_markdown_document_context": document_context,
            "_read_owned_text": self.read_owned,
            "_write_owned_text": self.write_owned,
        }
        for alias in self.adapter_imports:
            if alias.name == "render_documents":
                self.scope[alias.asname or alias.name] = self.adapter
            elif alias.name == "DocumentResult":
                self.scope[alias.asname or alias.name] = DocumentResult
        exec(compile(self.module, "isolated-codex-preparation", "exec"), self.scope)
        self.prepare = self.scope["_prepare_codex_agents"]
        self.merge = self.scope["_merge_codex_agents"]
        self.begin = self.scope["CODEX_BEGIN"]
        self.end = self.scope["CODEX_END"]
        self.pack = (self.begin + "\n# Shared Governance\nShared rule.\n\n"
                     "# Codex Platform Rules\nCodex rule.\n" + self.end + "\n")

    def read_owned(self, target, owner, *, preserve_newlines):
        self.assertEqual(target, self.target)
        self.assertIs(owner, self.owner)
        self.assertIs(preserve_newlines, True)
        self.events.append(("target", str(target)))
        return self.existing

    def write_owned(self, target, content, owner):
        self.events.append(("write", str(target)))
        self.writes.append((target, content, owner))

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

    def test_installer_imports_common_adapter_without_importing_installer(self):
        self.assertIn("render_documents", [a.name for a in self.adapter_imports])

    def guarded_import_code(self):
        guards = [node for node in self.tree.body if isinstance(node, ast.Try)
                  and any(isinstance(child, ast.ImportFrom)
                          and child.module == "installation.document_outcomes"
                          for child in node.body)]
        self.assertEqual(len(guards), 1)
        module = ast.fix_missing_locations(ast.Module(body=guards, type_ignores=[]))
        return compile(module, "isolated-document-import", "exec")

    def test_guarded_import_success_and_intended_missing_module_fallback(self):
        from types import SimpleNamespace

        imported = SimpleNamespace(DocumentResult=object(), render_document=object(), render_documents=object())
        direct = "installation.document_outcomes"
        fallback = "scripts.installation.document_outcomes"
        for missing in (None, "installation", direct):
            with self.subTest(missing=missing):
                calls = []

                def controlled_import(name, globals=None, locals=None, fromlist=(), level=0):
                    calls.append((name, tuple(fromlist), level))
                    self.assertIn(name, (direct, fallback))
                    if name == direct and missing is not None:
                        raise ModuleNotFoundError("synthetic missing dependency", name=missing)
                    return imported

                scope = {"__builtins__": {"__import__": controlled_import,
                                         "ModuleNotFoundError": ModuleNotFoundError}}
                exec(self.guarded_import_code(), scope)
                expected = [direct] if missing is None else [direct, fallback]
                self.assertEqual(calls, [(name, ("DocumentResult", "render_document", "render_documents"), 0)
                                         for name in expected])
                self.assertIs(scope["_DocumentResult"], imported.DocumentResult)
                self.assertIs(scope["_render_document_outcome"], imported.render_document)
                self.assertIs(scope["_render_document_outcomes"], imported.render_documents)

    def test_guarded_import_reraises_transitive_missing_module_without_fallback(self):
        calls = []
        failure = ModuleNotFoundError("synthetic transitive dependency",
                                      name="installation.receipt_plan")

        def controlled_import(name, globals=None, locals=None, fromlist=(), level=0):
            calls.append((name, tuple(fromlist), level))
            raise failure

        scope = {"__builtins__": {"__import__": controlled_import,
                                 "ModuleNotFoundError": ModuleNotFoundError}}
        with self.assertRaises(ModuleNotFoundError) as caught:
            exec(self.guarded_import_code(), scope)
        self.assertIs(caught.exception, failure)
        self.assertEqual(calls, [("installation.document_outcomes",
                                 ("DocumentResult", "render_document", "render_documents"), 0)])
        self.assertNotIn("_DocumentResult", scope)
        self.assertNotIn("_render_document_outcomes", scope)
        self.assertNotIn("_render_document_outcome", scope)

    def test_exact_preimage_order_and_read_only_immutable_result(self):
        self.existing = "\ufeffUser 😀 保留\r\nKeep\rTail\n"
        result = self.prepare_result(project_scope=True)
        self.assertIsInstance(result, DocumentResult)
        self.assertEqual(result.before, self.existing.encode("utf-8"))
        self.assertEqual(result.renderer_input, self.existing)
        self.assertEqual(result.after, (self.pack + "\n" + self.existing).encode("utf-8"))
        self.assertEqual(result.read_mode, "exact-newlines")
        self.assertEqual(self.events, [
            ("source", str(self.root / "shared" / "AGENTS.shared.md")),
            ("source", str(self.source / "AGENTS.codex.md")),
            ("target", str(self.target)),
        ])
        self.assertEqual(self.writes, [])
        self.adapter.assert_called_once()
        self.assertEqual(self.adapter.call_args.args[:3],
                         ("codex", "project", {"AGENTS.md": result.before}))
        with self.assertRaises(FrozenInstanceError):
            result.after = b"changed"

    def test_logical_scopes_do_not_depend_on_physical_target(self):
        for project, scope, path in ((True, "project", "AGENTS.md"),
                                     (False, "global", ".codex/AGENTS.md")):
            with self.subTest(scope=scope):
                self.adapter.reset_mock()
                result = self.prepare_result(project_scope=project)
                self.assertEqual(result.path, path)
                self.assertEqual(result.kind, "codex")
                self.assertEqual(self.adapter.call_args.args[:3],
                                 ("codex", scope, {path: None}))
                self.assertEqual(self.writes, [])

    def test_absent_and_empty_keep_distinct_non_adopting_update_outcomes(self):
        for original, change in ((None, "missing-preimage"), ("", "existing-update")):
            with self.subTest(original=original):
                self.existing = original
                result = self.prepare_result(project_scope=True)
                self.assertEqual(result.before, None if original is None else b"")
                self.assertEqual(result.renderer_input, original)
                self.assertEqual(result.change, change)
                outcome = result.as_outcome()
                self.assertEqual(outcome.intent, "update")
                self.assertIsNone(outcome.adoption_sha256)
                self.assertIsNone(outcome.adoption_span)
                plan = plan_changes(None, "codex", "project", (outcome,), document_context)
                self.assertEqual(plan.artifacts[0].route, "legacy")
                self.assertEqual(plan.changes, ())
                self.assertEqual(self.writes, [])

    def test_prepare_to_plan_existing_document_stays_legacy_before_any_write(self):
        self.existing = "User header\r\n" + self.begin + "\nOld\n" + self.end + "\rTail\n"
        result = self.prepare_result()
        self.assertEqual(result.after,
                         ("User header\r\n" + self.pack.rstrip("\n") + "\rTail\n").encode())
        plan = plan_changes(None, "codex", "global",
                            (result.as_outcome(),), document_context)
        self.assertEqual(plan.artifacts[0].route, "legacy")
        self.assertEqual(plan.changes, ())
        self.assertEqual(self.writes, [])

    def test_wrapper_prepares_once_preserves_noop_without_write(self):
        self.existing = "\ufeffPrefix 😀\r\n" + self.pack.rstrip("\n") + "\rTail\n"
        spy = Mock(wraps=self.prepare)
        self.scope["_prepare_codex_agents"] = spy
        output = self.merge_result(project_scope=True)
        spy.assert_called_once_with(self.root, self.source, self.target,
                                    mutable_owner=self.owner, project_scope=True)
        self.adapter.assert_called_once()
        self.assertEqual(self.writes, [])
        self.assertNotIn(("write", str(self.target)), self.events)
        self.assertIn(str(len(self.existing.encode("utf-8"))) + " UTF-8 bytes", output)
        self.assertIn("WARNING: standalone project instruction budget", output)

    def test_dry_run_still_prepares_once_but_never_writes(self):
        self.existing = "User\r\n"
        spy = Mock(wraps=self.prepare)
        self.scope["_prepare_codex_agents"] = spy
        output = self.merge_result(dry_run=True)
        spy.assert_called_once()
        self.adapter.assert_called_once()
        self.assertEqual(self.writes, [])
        self.assertIn("[dry-run] would merge", output)
        self.assertNotIn("WARNING", output)

    def test_missing_end_refusal_is_exact_and_precedes_any_write(self):
        self.existing = self.begin + "\n# Shared Governance\nUSER TAIL KEEP\n"
        for action in (self.prepare_result, self.merge_result,
                       lambda: self.merge_result(dry_run=True)):
            with self.subTest(action=action):
                with self.assertRaises(ValueError) as caught:
                    action()
                self.assertEqual(str(caught.exception),
                                 "E_CODEX_DOCUMENT_AMBIGUOUS: missing managed end marker")
                self.assertEqual(self.writes, [])


if __name__ == "__main__":
    unittest.main()
