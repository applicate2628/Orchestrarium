"""Pure AST census tests. Never import or execute the installer module."""
from __future__ import annotations
import ast
import copy
from collections import Counter
from dataclasses import dataclass
import os
import inspect
from pathlib import Path
from types import SimpleNamespace
import unittest

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "scripts/production_installer.py"
CLASSES = {"_PostMaterializationWriterDestination"}
CONSTANTS = {
    "_CODEX_RETIRED_PS1",
    "_POST_MATERIALIZATION_WRITER_CALLS",
    "_POST_MATERIALIZATION_NONWRITER_CALLS",
    "_POST_MATERIALIZATION_ARTIFACT_CLASS",
}
HELPERS = {
    "_assert_canonical_lead_postwrite_free",
    "_is_lexically_under",
    "_post_materialization_call_name",
    "_post_materialization_writer_source_census",
}

def load_pure_census():
    text = SOURCE.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(SOURCE))
    selected = []
    install_source = None
    found = set()
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id in CONSTANTS:
                # Selected declarations are literal collections, optionally frozenset.
                expression = node.value
                if isinstance(expression, ast.Call):
                    assert isinstance(expression.func, ast.Name) and expression.func.id == "frozenset"
                    assert len(expression.args) == 1 and not expression.keywords
                    expression = expression.args[0]
                ast.literal_eval(expression)
                selected.append(copy.deepcopy(node))
                found.add(target.id)
        elif isinstance(node, ast.ClassDef) and node.name in CLASSES:
            selected.append(copy.deepcopy(node))
            found.add(node.name)
        elif isinstance(node, ast.FunctionDef):
            if node.name in HELPERS:
                selected.append(copy.deepcopy(node))
                found.add(node.name)
            elif node.name == "install":
                install_source = ast.get_source_segment(text, node)
    assert found == CONSTANTS | HELPERS | CLASSES and install_source
    source_cell = [install_source]
    sentinel = object()
    def actual_install_source(target):
        assert target is sentinel
        return source_cell[0]
    namespace = {"__name__": __name__, "ast": ast, "Path": Path, "os": os,
                 "Counter": Counter, "dataclass": dataclass,
                 "inspect": SimpleNamespace(getsource=actual_install_source),
                 "install": sentinel}
    # Execute only selected exact pure helpers, a data record, and literal declarations.
    # install() is only source text and is never compiled or executed.
    module = ast.Module(body=selected, type_ignores=[])
    exec(compile(ast.fix_missing_locations(module), str(SOURCE), "exec"), namespace)
    return namespace, source_cell

def inject_unknown_writer(source):
    tree = ast.parse(source)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == "_apply_canonical_skills_plan"]
    assert len(calls) == 2
    after = max(node.end_lineno for node in calls)
    boundaries = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.If)
                  and node.lineno > after and isinstance(node.test, ast.Attribute)
                  and isinstance(node.test.value, ast.Name) and node.test.value.id == "args"
                  and node.test.attr == "dry_run"]
    boundary = min(boundaries) - 1
    lines = source.splitlines(keepends=True)
    indentation = lines[boundary][:-len(lines[boundary].lstrip())]
    lines.insert(boundary, indentation + "_future_unregistered_writer()\n")
    return "".join(lines)

class PostMaterializationSourceCensus(unittest.TestCase):
    def test_current_source_has_exact_declared_writer_ids(self):
        namespace, _ = load_pure_census()
        expected = set(namespace["_POST_MATERIALIZATION_ARTIFACT_CLASS"])
        self.assertEqual(set(namespace["_post_materialization_writer_source_census"]()), expected)
        self.assertEqual(namespace["_POST_MATERIALIZATION_WRITER_CALLS"]["_apply_selected_replacement"],
                         ("provider-doc",))
        self.assertIn("_warn_codex_project_budget", namespace["_POST_MATERIALIZATION_NONWRITER_CALLS"])
        self.assertNotIn("_apply_selected_replacement", namespace["_POST_MATERIALIZATION_NONWRITER_CALLS"])

    def test_unknown_late_writer_remains_rejected(self):
        namespace, source_cell = load_pure_census()
        source_cell[0] = inject_unknown_writer(source_cell[0])
        with self.assertRaisesRegex(ValueError, "_future_unregistered_writer"):
            namespace["_post_materialization_writer_source_census"]()

    def test_provider_document_cannot_target_canonical_lead(self):
        namespace, _ = load_pure_census()
        record = namespace["_PostMaterializationWriterDestination"]
        guard = namespace["_assert_canonical_lead_postwrite_free"]
        # Path values only: no fixture creation, native writes or resolver calls.
        project = Path("pure-census-project")
        lead = project / ".agents/skills/lead"
        ordinary_document = record("provider-doc", "provider-doc", project / "AGENTS.md")
        guard(lead, (ordinary_document,))
        forbidden_document = record("provider-doc", "provider-doc", lead / "AGENTS.md")
        with self.assertRaisesRegex(ValueError, "^E_CANONICAL_LEAD_POSTWRITE"):
            guard(lead, (forbidden_document,))

if __name__ == "__main__":
    unittest.main(verbosity=2)
