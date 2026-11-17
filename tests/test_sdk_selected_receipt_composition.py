"""SDK receipt composition preserves complete install outcomes during selection."""
import hashlib
import importlib.util
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from installation import ownership


def digest(data):
    return hashlib.sha256(data).hexdigest()


class SelectedReceiptCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("sdk_receipt_composition_backend", ROOT / "scripts/production_installer.py")
        cls.backend = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = cls.backend
        spec.loader.exec_module(cls.backend)

    def test_selected_instruction_retains_other_updated_payload_and_copy_layout(self):
        self.check_composition(complete=True)

    def test_incomplete_selected_outcomes_cannot_publish_receipt(self):
        self.check_composition(complete=False)

    def check_composition(self, *, complete):
        backend = self.backend
        with tempfile.TemporaryDirectory(prefix="receipt-composition-") as temporary:
            anchor = Path(temporary)
            target = anchor / ".claude"
            selected_path = ".claude/agents/reviewer.md"
            skill_path = ".claude/skills/backend-engineer/SKILL.md"
            before = ownership.encode_record({skill_path: digest(b"old skill")}, "claude", "project", configs={})
            node = lambda payload: SimpleNamespace(kind="file", data=digest(payload))
            old_skill, new_skill = node(b"old skill"), node(b"new skill")
            old_selected, new_selected = node(b"user selected"), node(b"selected replacement")
            original = {anchor / skill_path: old_skill, anchor / selected_path: old_selected}
            current = {anchor / skill_path: new_skill, anchor / selected_path: new_selected}
            transaction = SimpleNamespace(_original={target: original}, _expected={target: current},
                _temporary=None, _migration_retention=(), _effects=(), paths=(target,), _slice_a_created=())
            owner = SimpleNamespace(dry_run=False, transaction=transaction, anchor=anchor,
                replace_file_atomic=Mock(), replace_exact_file=Mock(), create_file=Mock())
            selected = SimpleNamespace(owner=owner, path=anchor / selected_path)
            stored = [before]
            owner.replace_exact_file.side_effect = lambda relative, sha, data: stored.__setitem__(0, data)
            outcome = SimpleNamespace(path=selected_path, kind="file", after=b"selected replacement")
            payload = ownership.serialize_record(dict(schema=ownership.SCHEMA, provider="claude",
                scope="project", files={skill_path:digest(b"old skill"), selected_path:digest(outcome.after)},
                configs={}, layout=ownership.LAYOUT), "claude", "project")
            batch = SimpleNamespace(owner=owner, provider="claude", scope="project", receipt=target / ownership.RECEIPT_NAME,
                receipt_before=before, items={"agents/reviewer.md":selected},
                received={"agents/reviewer.md":new_selected} if complete else {}, outcomes=(outcome,), payload=payload)
            configs = {".claude/CLAUDE.md":dict(kind="block",blockKind="claude",sha256="b"*64)}
            with patch.object(backend,"_read_owned_text",side_effect=lambda *a, **k: stored[0].decode()), \
                 patch.object(backend,"_capture_provider_configs",return_value=configs), \
                 patch.object(backend,"_assert_selected_replacement") as verify:
                call = lambda: backend._record_provider_install(ROOT,"claude","project",target,anchor,
                    transaction,owner,before.decode(),{},target/"CLAUDE.md",target/"mode",target/"settings.json",
                    target/"agents",False,selected_updates=batch)
                if not complete:
                    with self.assertRaises(ValueError):
                        call()
                    owner.replace_file_atomic.assert_not_called()
                    owner.replace_exact_file.assert_not_called()
                    return
                call()
                self.assertEqual(verify.call_count, 2)
                verify.assert_called_with(selected,owner,new_selected,"claude")
            owner.replace_file_atomic.assert_not_called()
            owner.replace_exact_file.assert_called_once()
            self.assertEqual(owner.replace_exact_file.call_args.args[:2],
                             (batch.receipt.relative_to(anchor), digest(before)))
            result = ownership.decode_record(owner.replace_exact_file.call_args.args[2],"claude","project")
            self.assertEqual(result["layout"],ownership.LAYOUT)
            self.assertEqual(result["files"],{skill_path:digest(b"new skill"),selected_path:digest(outcome.after)})
            self.assertEqual(result["configs"],configs)
