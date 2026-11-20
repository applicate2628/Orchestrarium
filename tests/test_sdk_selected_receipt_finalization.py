"""Exercise the SDK receipt finalizer with real semantic codecs and memory storage."""
import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace as NS
import sys
import unittest
from unittest.mock import Mock
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from installation import ownership, configuration
from installation.receipt_plan import Outcome, plan_changes, serialize_delta
from installation.clients import get_client
from installer_markdown import document_context
sha = lambda b: hashlib.sha256(b).hexdigest()

class SelectedReceiptFinalizationTests(unittest.TestCase):
    def setup_case(self, *, linked=False, block=False, crlf=False):
        self.provider = "codex" if block else "claude"
        self.scope_name = "global" if linked else "project"
        anchor = Path("memory-anchor").absolute()
        target = anchor / ("." + self.provider)
        self.receipt = target / ownership.RECEIPT_NAME
        key = "AGENTS.md" if block else ".claude/agents/worker.md"
        old, new = b"old", b"new"
        configs = {}
        if block:
            old = configuration.merge_owned_block(None, "codex", "old rule\n", document_context).encode()
            digest = configuration.block_digest(old.decode(), "codex", document_context)
            new = configuration.merge_owned_block(old.decode(), "codex", "new rule\n", document_context,
                                                  expected_digest=digest).encode()
            configs[key] = dict(kind="block", blockKind="codex", sha256=digest)
        self.raw = ownership.encode_record({} if block else {key:sha(old)},
                         self.provider, self.scope_name, configs=configs)
        if crlf:
            self.raw = self.raw.replace(b"\n", b"\r\n")
        span = configuration.owned_block(old.decode(), "codex", document_context) if block else None
        outcome = Outcome(key, "block" if block else "file", old, new, "replace", sha(old), span)
        plan = plan_changes(self.raw, self.provider, self.scope_name, (outcome,), document_context)
        self.other = "." + self.provider + "/agents/other." + ("toml" if block else "md")
        path = (anchor.parent / "linked-storage/worker.md") if linked else anchor / key
        current = {path:NS(kind="file", data=sha(new)),
                   anchor / self.other:NS(kind="file", data=sha(b"other"))}
        self.tx = NS(_original={"x":{path:NS(kind="file", data=sha(old))}},
            _expected={"x":current}, _temporary=None, _migration_retention=(), _effects=(),
            paths=(anchor, path.parent), _slice_a_created=[])
        self.owner = NS(dry_run=False, anchor=anchor, transaction=self.tx,
            create_file=Mock(), replace_file_atomic=Mock(), replace_exact_file=Mock())
        selected = NS(path=path, owner=self.owner)
        self.batch = NS(owner=self.owner, provider=self.provider, scope=self.scope_name, receipt=self.receipt,
            receipt_before=self.raw, items={key:selected}, received={key:current[path]},
            outcomes=(outcome,), payload=serialize_delta(self.raw, plan))
        self.configs = {(".agents" if block else ".claude") + "/.agents-mode.yaml":dict(kind="file",sha256=sha(b"mode"))}
        if block:
            self.configs[key] = dict(kind="block",blockKind="codex",
                sha256=configuration.block_digest(new.decode(),"codex",document_context))
        self.stored = self.raw
        self.owner.replace_exact_file.side_effect = lambda relative, digest, payload: setattr(self, "stored", payload)
        self.owner.replace_file_atomic.side_effect = lambda relative, payload, **kw: setattr(self, "stored", payload)
        self.read = Mock(side_effect=lambda p, o, **kw:self.stored.decode() if kw.get("preserve_newlines") else self.stored.decode().replace("\r\n","\n"))
        self.assert_selected = Mock()
        scope = dict(hashlib=hashlib, Path=Path, _provider_ownership_module=lambda r:ownership,
            get_client=get_client, _read_owned_text=self.read,
            _capture_provider_configs=lambda *a:self.configs,
            _assert_selected_replacement=self.assert_selected,
            _selected_error=lambda *a,**k:ValueError(str(a)),
            _InstallFailure=lambda *a:ValueError(str(a)),
            _plan_receipt_changes=plan_changes, _markdown_document_context=document_context)
        import installation.receipt_plan as rp
        if hasattr(rp, "compose_selected_candidate"):
            scope["_compose_selected_candidate"] = rp.compose_selected_candidate
        tree=ast.parse((ROOT/"scripts/production_installer.py").read_bytes())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="_record_provider_install")
        exec(compile(ast.Module(body=[fn],type_ignores=[]),"actual-finalizer","exec"),scope)
        self.run_finalizer=lambda:scope["_record_provider_install"](ROOT,self.provider,self.scope_name,target,
            anchor,self.tx,self.owner,self.raw.decode(),{},None,None,None,None,False,
            selected_updates=self.batch)
        return new, key

    def test_linked_selected_physical_file_is_recorded_by_logical_key(self):
        new,key=self.setup_case(linked=True)
        self.run_finalizer()
        payload=self.owner.replace_exact_file.call_args.args[2]
        record=ownership.decode_record(payload,self.provider,self.scope_name)
        self.assertEqual(record["files"][key],sha(new))
        self.assertEqual(record["files"][self.other],sha(b"other"))

    def test_crlf_receipt_uses_exact_selected_writer(self):
        self.setup_case(crlf=True)
        self.run_finalizer()
        self.assertEqual(self.owner.replace_exact_file.call_args.args[1],sha(self.raw))
        self.owner.replace_file_atomic.assert_not_called()

    def test_selected_block_preserves_unrelated_payload_and_config(self):
        new,key=self.setup_case(block=True)
        self.run_finalizer()
        call=self.owner.replace_exact_file.call_args or self.owner.replace_file_atomic.call_args
        payload=call.args[-1]
        record=ownership.decode_record(payload,self.provider,self.scope_name)
        self.assertEqual(record["files"][self.other],sha(b"other"))
        self.assertEqual(record["configs"],self.configs)

    def test_line_ending_drift_refuses_receipt_write(self):
        self.setup_case()
        self.stored = self.raw.replace(b"\n", b"\r\n")
        with self.assertRaises(ValueError):
            self.run_finalizer()
        self.owner.replace_exact_file.assert_not_called()
        self.owner.replace_file_atomic.assert_not_called()

    def test_receipt_postwrite_corruption_is_detected(self):
        self.setup_case()
        self.owner.replace_exact_file.side_effect = lambda *a: setattr(self, "stored", b"wrong")
        self.owner.replace_file_atomic.side_effect = lambda *a, **k: setattr(self, "stored", b"wrong")
        with self.assertRaisesRegex(ValueError, "receipt outcome"):
            self.run_finalizer()

    def test_selected_source_drift_prevents_write(self):
        self.setup_case()
        self.assert_selected.side_effect = ValueError("source drift")
        with self.assertRaisesRegex(ValueError, "source drift"):
            self.run_finalizer()
        self.owner.replace_exact_file.assert_not_called()

    def test_selected_source_drift_during_publication_is_detected(self):
        self.setup_case()
        self.assert_selected.side_effect = [None, ValueError("source drift")]
        with self.assertRaisesRegex(ValueError, "source drift"):
            self.run_finalizer()

    def test_unselected_route_keeps_atomic_writer(self):
        self.setup_case()
        self.batch = None
        self.run_finalizer()
        self.owner.replace_file_atomic.assert_called_once()
        self.owner.replace_exact_file.assert_not_called()

if __name__=="__main__":
    unittest.main()
