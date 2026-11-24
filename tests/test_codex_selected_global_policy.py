"""Selected Codex updates reuse only a captured matching native global policy."""
import ast
from dataclasses import dataclass
import hashlib
import importlib.util
import tempfile
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
SOURCE = ROOT / "scripts/production_installer.py"


class CodexSelectedGlobalPolicyTests(unittest.TestCase):
    def setUp(self):
        self.root = Path("synthetic-selected-memory").absolute()
        self.document = self.root / "AGENTS.md"
        self.receipt = self.root / ".codex/.orche-install.v1.json"
        self.node = object()
        self.owner = SimpleNamespace(anchor=self.root, transaction=object(),
            _file_parent_identities=Mock(return_value=()),
            _assert_bound_file=Mock(return_value=b"old"))
        self.scope = {"dataclass": dataclass, "hashlib": hashlib, "Path": Path, "os": os,
            "_admitted_mutation_image": lambda tx, p: {p: self.node}}
        names = {"_SelectedSource", "_SelectedGlobalPolicy", "_SelectedReplacement",
                 "_assert_selected_sources", "_assert_selected_replacement", "_apply_selected_replacement", "_selected_error", "_codex_instruction_pack"}
        nodes = [n for n in ast.parse(SOURCE.read_bytes()).body
                 if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in names]
        module = ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(
            module="__future__", names=[ast.alias(name="annotations")], level=0)] + nodes,
            type_ignores=[]))
        exec(compile(module, "selected-global-policy", "exec"), self.scope)

    def prepare_global(self, *, changed=False, missing=False):
        from installation import configuration
        from installation.receipt_plan import Outcome
        from installer_markdown import document_context
        tree = ast.parse(SOURCE.read_bytes())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == "_prepare_selected_codex_document")
        module = ast.fix_missing_locations(ast.Module(body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
            function], type_ignores=[]))
        shared, codex = "shared rule\n", "codex rule\n"
        begin, end = "<!-- BEGIN ORCHESTRARIUM CODEX PACK -->", "<!-- END ORCHESTRARIUM CODEX PACK -->"
        payload = lambda a, b: a.rstrip() + "\n\n" + b.rstrip() + "\n"
        full = begin + "\n" + payload(shared, codex) + end
        short = begin + "\n" + "global-backed reference\n" + end + "\n"
        global_path = self.root / "native-home" / "AGENTS.md"
        root, source = self.root / "repository", self.root / "repository" / "src.codex"
        originals = {
            root / "shared" / "AGENTS.shared.md": shared.encode(),
            source / "AGENTS.codex.md": codex.encode(),
            global_path: b"changed policy" if changed else full.encode(),
        }
        captures = []
        def capture(path, transaction):
            captures.append(path)
            return self.scope["_SelectedSource"](path, self.node, originals[path])
        matcher = Mock(return_value=None if missing else global_path)
        prepared = Mock(return_value="prepared")
        self.owner.destination = lambda p: self.root / p
        self.scope.update(
            CODEX_BEGIN=begin, CODEX_END=end,
            _capture_selected_source=capture,
            _codex_instruction_pack=Mock(return_value=(short, "AGENTS.md")),
            _codex_document_payload=payload,
            _matching_native_codex_global_policy=matcher,
            _provider_configuration_module=lambda root: configuration,
            _markdown_document_context=document_context,
            _render_selected_document=Mock(return_value="new"),
            _ReceiptOutcome=Outcome,
            _prepare_selected_provider_updates=prepared,
            _PROVIDER_RECEIPT_NAME=".orche-install.v1.json")
        exec(compile(module, "isolated-selected-preparation", "exec"), self.scope)
        run = lambda: self.scope["_prepare_selected_codex_document"](
            (hashlib.sha256(b"old").hexdigest(), (0, 3)), root, source,
            self.receipt.parent, self.document, "project", self.owner, prefer_global=True)
        return run, captures, matcher, prepared, global_path, full

    def test_global_preparation_captures_resolved_native_path_not_cwd_filename(self):
        run, captures, matcher, prepared, global_path, full = self.prepare_global()
        self.assertEqual(run(), "prepared")
        self.assertEqual(captures[-1], global_path)
        matcher.assert_called_once_with(self.root / "repository", self.document,
                                        full + "\n", return_path=True)
        selected = prepared.call_args.args[4]["AGENTS.md"]
        self.assertEqual(len(selected.sources), 2)
        self.assertEqual(selected.global_policy.source.path, global_path)
        self.assertEqual(selected.global_policy.source.raw, full.encode())

    def test_global_preparation_rejects_changed_captured_policy_bytes(self):
        run, captures, matcher, prepared, global_path, full = self.prepare_global(changed=True)
        with self.assertRaisesRegex(ValueError, "global source changed"):
            run()
        prepared.assert_not_called()
        self.scope["_render_selected_document"].assert_not_called()

    def test_global_preparation_rejects_disappearing_match_before_capture(self):
        run, captures, matcher, prepared, global_path, full = self.prepare_global(missing=True)
        with self.assertRaisesRegex(ValueError, "global source"):
            run()
        self.assertNotIn(global_path, captures)
        prepared.assert_not_called()

    def apply_prepared(self):
        run, _, matcher, prepared, _, _ = self.prepare_global()
        run()
        selected = prepared.call_args.args[4]["AGENTS.md"]
        tx = SimpleNamespace(_image_file_bytes=lambda path, node:
            next(w.raw for w in (*selected.sources, selected.global_policy.source) if w.path == path))
        self.owner.transaction = tx
        self.owner.linked_authority = None
        self.owner.replace_exact_file = Mock(side_effect=lambda *a:
            setattr(self.owner._assert_bound_file, "return_value", selected.after))
        batch = SimpleNamespace(provider="codex", owner=self.owner,
                                items={"AGENTS.md": selected}, received={})
        apply = lambda: self.scope["_apply_selected_replacement"](
            batch, "AGENTS.md", tuple(w.path for w in selected.sources),
            self.document, self.owner, False)
        return apply, selected, matcher, batch

    def test_actual_prepare_then_apply_accepts_two_source_public_route(self):
        apply, selected, matcher, batch = self.apply_prepared()
        apply()
        self.owner.replace_exact_file.assert_called_once()
        self.assertEqual(batch.received["AGENTS.md"], self.node)

    def test_actual_apply_rejects_visible_global_path_change_before_write(self):
        apply, selected, matcher, batch = self.apply_prepared()
        matcher.return_value = selected.global_policy.source.path.with_name("AGENTS.override.md")
        with self.assertRaisesRegex(ValueError, "global source selection"):
            apply()
        self.owner.replace_exact_file.assert_not_called()

    def test_explicit_standalone_does_not_consult_global_source(self):
        matcher = Mock(return_value="AGENTS.md")
        self.scope.update(CODEX_BEGIN="begin", CODEX_END="end",
            _codex_document_payload=lambda a, b: a + b,
            _matching_native_codex_global_policy=matcher)
        pack, source = self.scope["_codex_instruction_pack"](self.root, self.document, "shared", "codex",
                                                             prefer_global=False)
        self.assertEqual(pack, "begin\nsharedcodexend\n")
        self.assertIsNone(source)
        matcher.assert_not_called()

    def test_matching_global_uses_same_short_body_for_both_renderers(self):
        matcher = Mock(return_value="AGENTS.override.md")
        self.scope.update(CODEX_BEGIN="begin", CODEX_END="end",
            _codex_document_payload=lambda a, b: a + b,
            _matching_native_codex_global_policy=matcher)
        pack, source = self.scope["_codex_instruction_pack"](self.root, self.document, "shared", "codex",
                                                             prefer_global=True)
        self.assertIn("global-backed", pack)
        self.assertNotIn("sharedcodex", pack)
        self.assertEqual(source, "AGENTS.override.md")

    def test_unproved_global_falls_back_to_full_policy(self):
        self.scope.update(CODEX_BEGIN="begin", CODEX_END="end",
            _codex_document_payload=lambda a, b: a + b,
            _matching_native_codex_global_policy=Mock(return_value=None))
        pack, source = self.scope["_codex_instruction_pack"](self.root, self.document, "shared", "codex",
                                                             prefer_global=True)
        self.assertEqual(pack, "begin\nsharedcodexend\n")
        self.assertIsNone(source)

    def test_public_selected_route_preserves_explicit_standalone_and_global_policy(self):
        tree = ast.parse(SOURCE.read_bytes())
        install = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "install")
        call = next(n for n in ast.walk(install) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name) and n.func.id == "_prepare_selected_codex_document")
        policy = next(k.value for k in call.keywords if k.arg == "prefer_global")
        for mode, standalone, expected in [("global", False, False), ("global", True, False),
                                           ("project", False, True), ("project", True, False)]:
            with self.subTest(mode=mode, standalone=standalone):
                value = eval(compile(ast.Expression(body=policy), "selection-policy", "eval"),
                    {"mode": mode, "args": SimpleNamespace(standalone_instructions=standalone)})
                self.assertEqual(value, expected)


    def test_matcher_preserves_name_api_and_returns_exact_visible_path(self):
        spec = importlib.util.spec_from_file_location("selected_global_matcher", SOURCE)
        backend = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = backend
        spec.loader.exec_module(backend)
        with tempfile.TemporaryDirectory(prefix="codex-global-selection-") as temporary:
            home = Path(temporary)
            document = home / "project" / "AGENTS.md"
            base = home / "AGENTS.md"
            override = home / "AGENTS.override.md"
            pack = backend.CODEX_BEGIN + "\npolicy\n" + backend.CODEX_END + "\n"
            base.write_bytes(pack.encode())
            with patch.dict(os.environ, {"CODEX_HOME": str(home)}):
                self.assertEqual(backend._matching_native_codex_global_policy(ROOT, document, pack), "AGENTS.md")
                self.assertEqual(backend._matching_native_codex_global_policy(ROOT, document, pack,
                                                                               return_path=True), base)
                witness = backend._SelectedSource(base, object(), base.read_bytes())
                policy = backend._SelectedGlobalPolicy(ROOT, document, pack, witness)
                selected = SimpleNamespace(sources=(), global_policy=policy)
                owner = SimpleNamespace(transaction=SimpleNamespace(
                    _image_file_bytes=lambda path, node: path.read_bytes()))
                backend._assert_selected_sources(selected, owner, "codex")
                override.write_bytes(pack.encode())
                # Even an equivalent higher-priority policy changes the bound source.
                with self.assertRaisesRegex(ValueError, "global source selection"):
                    backend._assert_selected_sources(selected, owner, "codex")
                self.assertEqual(backend._matching_native_codex_global_policy(ROOT, document, pack,
                                                                               return_path=True), override)
                override.write_bytes(b"different visible override")
                with self.assertRaisesRegex(ValueError, "global source selection"):
                    backend._assert_selected_sources(selected, owner, "codex")
                other_home = home / "other-home"
                other_home.mkdir()
                (other_home / "AGENTS.md").write_bytes(pack.encode())
                with patch.dict(os.environ, {"CODEX_HOME": str(other_home)}):
                    with self.assertRaisesRegex(ValueError, "global source selection"):
                        backend._assert_selected_sources(selected, owner, "codex")

                self.assertIsNone(backend._matching_native_codex_global_policy(ROOT, document, pack,
                                                                              return_path=True))


if __name__ == "__main__":
    unittest.main()
