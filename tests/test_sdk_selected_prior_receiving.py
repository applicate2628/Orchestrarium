"""Exact selected replacements reach the SDK's enclosing ownership guard."""
import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts/production_installer.py"


class SelectedPriorReceivingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(SOURCE.read_bytes())
        install = next(n for n in cls.tree.body if isinstance(n, ast.FunctionDef) and n.name == "install")
        cls.guard = next(n for n in ast.walk(install) if isinstance(n, ast.If)
            and any(isinstance(c, ast.Assign) and any(isinstance(t, ast.Name)
                and t.id == "previous_record" for t in c.targets) for c in n.body))
        cls.guard_code = compile(ast.Module(body=[cls.guard], type_ignores=[]), str(SOURCE), "exec")
        cls.install = install

    def scope(self, *, files=None, configs=None, selected=(), observed=None):
        anchor = Path("installation")
        record = {"files": files or {}, "configs": configs or {}}
        node = lambda digest: NS(kind="file", data=digest, python_identity=(1, 2))
        current = {anchor / key: node(value) for key, value in (observed or {}).items()}
        return dict(ownership_before="{}", root=ROOT, provider="claude", mode="global",
            transaction=NS(_expected={anchor: current}, enabled=True), mutable_anchor=anchor,
            canonical_plan=NS(lead_receipt=None), canonical_skills_target=anchor / "skills",
            _provider_ownership_module=lambda root: NS(decode_record=lambda *a: record),
            _provider_configuration_module=lambda root: NS(block_digest=lambda *a: "modified"),
            _selected_lead_prior_files=Mock(return_value={}),
            selected_updates=(NS(outcomes=tuple(NS(path=p) for p in selected),
                                 items={p: object() for p in selected}) if selected else None),
            config_before={anchor / key: "modified text" for key in (configs or {})},
            _claude_document_context=None, Path=Path, hashlib=hashlib,
            _LEAD_RECEIPT_NAME="lead-receipt.json")

    def test_preparation_precedes_prior_guard(self):
        prepares = [n for n in ast.walk(self.install) if isinstance(n, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "selected_updates" for t in n.targets)]
        self.assertTrue(prepares)
        self.assertLess(max(n.lineno for n in prepares), self.guard.lineno)

    def test_exact_selected_file_accepts_modified_preimage(self):
        scope = self.scope(files={"agents/reviewer.md": "old"},
            selected=("agents/reviewer.md",), observed={"agents/reviewer.md": "modified"})
        exec(self.guard_code, scope)

    def test_selected_file_does_not_exempt_neighbor(self):
        scope = self.scope(files={"agents/reviewer.md": "old", "agents/other.md": "old"},
            selected=("agents/reviewer.md",), observed={"agents/other.md": "modified"})
        with self.assertRaisesRegex(ValueError, "E_PROVIDER_PAYLOAD_MODIFIED: agents/other.md"):
            exec(self.guard_code, scope)

    def test_without_selection_modified_file_still_refuses(self):
        scope = self.scope(files={"agents/reviewer.md": "old"}, observed={"agents/reviewer.md": "modified"})
        with self.assertRaisesRegex(ValueError, "E_PROVIDER_PAYLOAD_MODIFIED"):
            exec(self.guard_code, scope)

    def test_exact_selected_block_accepts_modified_preimage(self):
        scope = self.scope(configs={"AGENTS.md": dict(kind="block", blockKind="codex", sha256="old")},
                           selected=("AGENTS.md",))
        exec(self.guard_code, scope)

    def test_selected_block_does_not_exempt_neighbor(self):
        scope = self.scope(configs={"other.md": dict(kind="block", blockKind="codex", sha256="old")},
                           selected=("AGENTS.md",))
        with self.assertRaisesRegex(ValueError, "E_PROVIDER_CONFIG_MODIFIED: other.md"):
            exec(self.guard_code, scope)

    def test_bound_lead_file_bridge_updates_only_exact_member(self):
        scope = self.scope(files={"skills/lead/body.md": "old"}, observed={"skills/lead/body.md": "modified"})
        scope["_selected_lead_prior_files"].return_value = {Path("installation/skills/lead/body.md"): "modified"}
        exec(self.guard_code, scope)
        scope["_selected_lead_prior_files"].assert_called_once_with(
            scope["canonical_plan"], scope["canonical_skills_target"], scope["transaction"])

    def test_bridge_failure_is_not_hidden(self):
        scope = self.scope(files={"skills/lead/body.md": "old"})
        scope["_selected_lead_prior_files"].side_effect = ValueError("selection drift")
        with self.assertRaisesRegex(ValueError, "selection drift"):
            exec(self.guard_code, scope)

    def test_modified_lead_selection_uses_bound_current_receipt(self):
        key = "skills/lead-receipt.json"
        payload = b"current receipt"
        scope = self.scope(files={key: "old"}, observed={key: hashlib.sha256(payload).hexdigest()})
        scope["canonical_plan"].lead_receipt = NS(selection=("receipt", "tree", "stage"))
        scope["_assert_lead_receipt_current"] = Mock(return_value=(payload, (1, 2)))
        exec(self.guard_code, scope)
        scope["_assert_lead_receipt_current"].assert_called_once_with(
            scope["canonical_plan"].lead_receipt, Path("installation") / key, scope["transaction"])

    def test_lead_receipt_identity_drift_refuses_selection(self):
        key = "skills/lead-receipt.json"
        scope = self.scope(files={key: "old"}, observed={key: "modified"})
        scope["canonical_plan"].lead_receipt = NS(selection=("receipt", "tree", "stage"))
        scope["_assert_lead_receipt_current"] = Mock(return_value=(b"current", (3, 4)))
        with self.assertRaisesRegex(ValueError, "E_PROVIDER_PAYLOAD_MODIFIED"):
            exec(self.guard_code, scope)


if __name__ == "__main__":
    unittest.main()
