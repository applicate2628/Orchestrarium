"""Qualify warning output without importing or running installer effects."""
from __future__ import annotations

import ast
import contextlib
import inspect
import io
from pathlib import Path, PurePosixPath
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "production_installer.py"


class MemoryPath(PurePosixPath):
    texts = {}

    def read_text(self, *, encoding):
        assert encoding == "utf-8"
        return self.texts[str(self)]


class CodexProjectBudgetWarningTests(unittest.TestCase):
    def setUp(self):
        self.tree = ast.parse(SOURCE.read_bytes())
        function = next(n for n in self.tree.body
                        if isinstance(n, ast.FunctionDef) and n.name == "_merge_codex_agents")
        future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
        isolated = ast.fix_missing_locations(ast.Module(body=[future, function], type_ignores=[]))
        constants = {}
        for node in self.tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in {"CODEX_BEGIN", "CODEX_END"}:
                        constants[target.id] = ast.literal_eval(node.value)
        self.existing = "# Project\nKeep my rule.\n"
        self.writes = []
        self.scope = dict(constants,
                          _markdown_document_context=lambda text: (text, []),
                          _read_owned_text=lambda *_args: self.existing,
                          _write_owned_text=lambda *args: self.writes.append(args))
        exec(compile(isolated, str(SOURCE), "exec"), self.scope)
        self.merge = self.scope["_merge_codex_agents"]
        self.root = MemoryPath("/source")
        self.pack = self.root / "src.codex"
        self.target = MemoryPath("/synthetic-project/AGENTS.md")
        MemoryPath.texts = {"/source/shared/AGENTS.shared.md": "Shared rules.\n",
                            "/source/src.codex/AGENTS.codex.md": "Codex rules.\n"}

    def invoke(self, project_scope, dry_run):
        output = io.StringIO()
        kwargs = {"project_scope": project_scope} if "project_scope" in inspect.signature(self.merge).parameters else {}
        with contextlib.redirect_stdout(output):
            self.merge(self.root, self.pack, self.target, dry_run, **kwargs)
        return output.getvalue()

    def test_project_preview_warns_without_write_or_fixed_limit(self):
        output = self.invoke(project_scope=True, dry_run=True)
        self.assertIn("standalone project instruction budget may be exceeded", output)
        self.assertIn("effective client budget", output)
        self.assertIn("not verified", output)
        self.assertIn("some rules may not be loaded", output)
        self.assertNotIn("32768", output)
        self.assertIn("[dry-run]", output)
        self.assertEqual(self.writes, [])

    def test_unicode_count_matches_in_memory_rendered_content(self):
        MemoryPath.texts["/source/shared/AGENTS.shared.md"] = "Общие правила.\n"
        MemoryPath.texts["/source/src.codex/AGENTS.codex.md"] = "客户端规则。\n"
        output = self.invoke(project_scope=True, dry_run=False)
        self.assertEqual(len(self.writes), 1)
        target, content, owner = self.writes[0]
        expected_pack = (self.scope["CODEX_BEGIN"] + "\nОбщие правила.\n\n"
                         + "客户端规则。\n" + self.scope["CODEX_END"] + "\n")
        self.assertEqual(content, expected_pack + "\n" + self.existing)
        self.assertEqual(target, self.target)
        self.assertIsNone(owner)
        self.assertIn(f"rendered document: {len(content.encode('utf-8'))} UTF-8 bytes", output)

    def test_global_scope_omits_project_warning(self):
        output = self.invoke(project_scope=False, dry_run=True)
        self.assertNotIn("project instruction budget", output)
        self.assertEqual(self.writes, [])

    def test_project_call_uses_existing_installer_mode(self):
        calls = [n for n in ast.walk(self.tree) if isinstance(n, ast.Call)
                 and isinstance(n.func, ast.Name) and n.func.id == "_merge_codex_agents"]
        self.assertEqual(len(calls), 1)
        keywords = [k for k in calls[0].keywords if k.arg == "project_scope"]
        self.assertEqual(len(keywords), 1)
        target_owner = next(n for n in self.tree.body
                            if isinstance(n, ast.FunctionDef) and n.name == "_target")
        modes = {n.value.value for n in ast.walk(target_owner)
                 if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
                 and isinstance(n.value.value, str)
                 and any(isinstance(t, ast.Name) and t.id == "mode" for t in n.targets)}
        self.assertEqual(modes, {"global", "target", "repo"})
        condition = compile(ast.Expression(keywords[0].value), str(SOURCE), "eval")
        for mode in modes:
            with self.subTest(mode=mode):
                self.assertEqual(eval(condition, {"__builtins__": {}, "mode": mode}),
                                 mode != "global")


if __name__ == "__main__":
    unittest.main()
