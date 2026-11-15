"""Opt-in real provider receiving matrix in caller-owned disposable storage.

Only public/private POSIX admission gates are substituted. No filesystem or
health runner is mocked. The caller owns fixture disposition after inspection.
"""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import time
import traceback
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix" and
                     os.environ.get("ORCHESTRARIUM_RUN_POSIX_RECEIVING") == "1",
                     "Explicit native receiving run with owned TMPDIR required")
class PosixProviderReceivingTests(unittest.TestCase):
    def setUp(self):
        configured = os.environ.get("TMPDIR")
        self.assertTrue(configured, "Caller must select disposable storage")
        self.assertTrue(Path(configured).is_dir())
        spec = importlib.util.spec_from_file_location("provider_receiving",
                                                     ROOT / "scripts/production_installer.py")
        self.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.module
        spec.loader.exec_module(self.module)
        self.source_bytes = (ROOT / "scripts/production_installer.py").read_bytes()
        self.root = Path(tempfile.mkdtemp(prefix="provider-receiving-", dir=configured))
        self.home = self.root / "home"
        self.project = self.root / "project"
        self.staging = self.root / "staging"
        for directory in (self.home, self.project, self.staging):
            directory.mkdir()
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {"HOME": str(self.home),
            "TMPDIR": str(self.staging), "PYTHONDONTWRITEBYTECODE": "1",
            "ORCHESTRARIUM_NO_HYPOTHESIS_HOOK": ""}))
        self.stack.enter_context(patch.object(self.module.tempfile, "tempdir", str(self.staging)))
        self.stack.enter_context(patch.object(self.module, "_installer_platform_admitted", lambda: True))
        self.stack.enter_context(patch.object(self.module, "_require_transaction_disposal_backend", lambda: None))
        self.marker = self.home / "user.txt"
        self.marker.write_bytes(b"Unrelated user content")
        print("RECEIVING FIXTURE", self.root, flush=True)

    def invoke(self, provider, *, global_install=False, extra=()):
        current_source = (ROOT / "scripts/production_installer.py").read_bytes()
        self.source_bytes = getattr(self, "source_bytes", current_source)
        self.assertEqual(current_source, self.source_bytes, "Receiving source changed during run")
        args = ["--global"] if global_install else [
            "--target", str(self.project), "--allow-unsafe-target"]
        output = io.StringIO()
        started = time.monotonic()
        # Controlled fixture diagnostics retain the original failure, unlike the
        # intentionally redacted public message. No live profile is inspected.
        finish = self.module._finish_install_result
        def report(*values, **kwargs):
            for value in values:
                if isinstance(value, BaseException):
                    traceback.print_exception(value)
            return finish(*values, **kwargs)
        # Hooks remain enabled, including their actual bounded health subprocesses.
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output), \
                patch.object(self.module, "_finish_install_result", report):
            code = self.module.install(provider, [*args, *extra])
        text = output.getvalue()
        self.assertEqual((ROOT / "scripts/production_installer.py").read_bytes(),
                         self.source_bytes, "Receiving source changed during run")
        print(provider, "global" if global_install else "project",
              "elapsed", round(time.monotonic() - started, 2), "code", code, flush=True)
        print(text[-18000:], flush=True)
        self.assertEqual(code, 0, text)
        self.assertIn("RESULT: OK", text)
        self.assertEqual(list(self.staging.iterdir()), [], text)
        self.assertEqual(self.marker.read_bytes(), b"Unrelated user content")
        return text

    def test_claude_project_fresh_repeat_hooks(self):
        self.invoke("claude")
        registration = self.project / ".claude/settings.json"
        self.assertTrue(registration.is_file())
        settings = registration.read_bytes()
        self.invoke("claude")
        self.assertEqual(registration.read_bytes(), settings)

    def test_codex_global_fresh_repeat_without_hooks(self):
        self.invoke("codex", global_install=True, extra=("--no-hypothesis-hook",))
        config = self.home / ".codex/config.toml"
        before = config.read_bytes()
        self.invoke("codex", global_install=True, extra=("--no-hypothesis-hook",))
        self.assertEqual(config.read_bytes(), before)

    def test_codex_global_fresh_repeat_hooks(self):
        # Do not substitute a fake host executable for native hook-list receiving.
        self.module._hook_health_module(ROOT).resolve_codex_command(os.environ.get("CODEX_BIN"))
        self.invoke("codex", global_install=True)
        config = self.home / ".codex/config.toml"
        self.assertTrue(config.is_file())
        before = config.read_bytes()
        self.invoke("codex", global_install=True)
        self.assertEqual(config.read_bytes(), before)

    def receive_selected_nonlead_upgrade(self, provider="codex"):
        import json
        skills = self.home / ".agents/skills"
        receipt = skills / ".orchestrarium-nonlead-skills-receipt.v1.json"
        saved = self.root / "prior-nonlead-receipt.json"
        receipt.rename(saved)
        selected = skills / "knowledge-archivist"
        selected_file = selected / "SKILL.md"
        expected = (ROOT / "src.codex/skills/knowledge-archivist/SKILL.md").read_bytes()
        selected_file.write_bytes(expected + b"\nFixture legacy content\n")
        observed = self.module._tree_sha256(selected, ignore_runtime_cache=True)
        sibling = skills / "analyst"
        sibling_before = self.module._tree_sha256(sibling, ignore_runtime_cache=True)
        source_before = (ROOT / "src.codex/skills/knowledge-archivist/SKILL.md").read_bytes()
        self.invoke(provider, global_install=True, extra=(
            "--replace-unreceipted-skill-sha256", "knowledge-archivist=tree-v2:" + observed))
        self.assertEqual(selected_file.read_bytes(), expected)
        self.assertEqual(self.module._tree_sha256(sibling, ignore_runtime_cache=True), sibling_before)
        data = json.loads(receipt.read_bytes())
        self.assertEqual(data["schema"], "orchestrarium.canonical-nonlead-skills-install.v2")
        self.assertEqual(data["skills"]["knowledge-archivist"]["members"],
                         dict(self.module._stage_tree_manifest(selected, ignore_runtime_cache=True)))
        self.assertEqual((ROOT / "src.codex/skills/knowledge-archivist/SKILL.md").read_bytes(), source_before)
        self.assertTrue(saved.is_file())
        self.assertEqual([p for p in self.home.rglob("*") if p.name.startswith((
            ".orchestrarium-retained-", ".orchestrarium-move-probe-",
            ".knowledge-archivist.upgrade."))], [])

    def test_claude_global_fresh_repeat_hooks(self):
        self.invoke("claude", global_install=True)
        registration = self.home / ".claude/settings.json"
        self.assertTrue(registration.is_file())
        settings = registration.read_bytes()
        self.invoke("claude", global_install=True)
        self.assertEqual(registration.read_bytes(), settings)
        self.receive_selected_nonlead_upgrade("claude")


if __name__ == "__main__":
    unittest.main()
