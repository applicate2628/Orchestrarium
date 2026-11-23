"""Receiver-inventory qualification is an optimization, never a new denial."""
import types
import unittest
from unittest import mock
import importlib.util
import sys
from pathlib import Path
CANONICAL_HOOK = Path(__file__).resolve().parents[1] / "scripts/universal-hooks/scripts/check-git-push-gate.py"

def _load_gate_module(path, name):
    def load(source, key):
        spec = importlib.util.spec_from_file_location(key, source)
        module = importlib.util.module_from_spec(spec)
        sys.modules[key] = module
        spec.loader.exec_module(module)
        return module
    load(path.with_name("hook_common.py"), "hook_common")
    preflight = load(path.with_name("git_push_gate_preflight.py"), "git_push_gate_preflight")
    gate = load(path, name)
    gate._a3_preflight = preflight
    return gate

def observation():
    directory = {"pathEncoding": "posix-bytes", "pathBase64": "L3JlcG8=", "device": "1", "inode": "2"}
    return {"status": "captured", "repository": {
        "kind": "native-worktree-v1", "objectFormat": "sha1",
        "commonGit": directory, "worktreeGit": directory, "worktreeRoot": directory,
    }, "diagnostic": "none"}


class ReceiverInventoryQualificationTests(unittest.TestCase):
    def setUp(self):
        self.g = _load_gate_module(CANONICAL_HOOK, "receiver_inventory_gate")
        self.native = self.g.NativePushInput("origin", "https://example.invalid/repo.git", b"")
    def check(self, *, vcs=(), value=b"false\n", status=0, native=None):
        with mock.patch.object(self.g, "_native_config_values", return_value=vcs), mock.patch.object(self.g, "_native_configuration_query", return_value=types.SimpleNamespace(returncode=status, stdout=value)):
            return self.g._native_receiver_inventory_qualified(native or self.native, "repo", "git")
    def test_ordinary_https(self):
        self.assertTrue(self.check())
    def test_redirect_initial_true_missing_malformed_fallback(self):
        for value,status in [(b"initial\n",0),(b"true\n",0),(b"",1),(b"false\nextra",0)]:
            self.assertFalse(self.check(value=value,status=status))
    def test_named_helper_even_empty_falls_back(self):
        for vcs in [(b"custom",),(b"",),(b"https",)]:
            self.assertFalse(self.check(vcs=vcs))
    def test_other_transports_credentials_queries_fall_back(self):
        for endpoint in ["ssh://example.invalid/repo","D:/repo","ext::receiver","http://example.invalid/repo","https://user@example.invalid/repo","https://example.invalid/repo?x=1","https://example.invalid/repo#x"]:
            self.assertFalse(self.check(native=self.g.NativePushInput("origin",endpoint,b"")))
    def test_raw_helper_spelling_is_not_urlsplit_normalization(self):
        for endpoint in ["HTTPS://example.invalid/repo", " https://example.invalid/repo", "https://example.invalid/repo\n", "https://exam\tple.invalid/repo", "https://example.invalid/re po", "https://example.invalid/repo\x7f"]:
            self.assertFalse(self.check(native=self.g.NativePushInput("origin", endpoint, b"")))

    def test_missing_context_falls_back_without_query(self):
        with mock.patch.object(self.g, "_native_configuration_query") as query:
            self.assertFalse(self.g._native_receiver_inventory_qualified(self.native,None,None))
            query.assert_not_called()
    def test_configuration_query_denial_falls_back(self):
        with mock.patch.object(self.g, "_native_config_values", side_effect=self.g.PrRouteDenied("PGG-NATIVE-CONFIGURATION")):
            self.assertFalse(self.g._native_receiver_inventory_qualified(self.native,"repo","git"))
    def test_exact_effective_url_query(self):
        with mock.patch.object(self.g,"_native_config_values",return_value=()) as values, mock.patch.object(self.g,"_native_configuration_query",return_value=types.SimpleNamespace(returncode=0,stdout=b"false\n")) as query:
            self.assertTrue(self.g._native_receiver_inventory_qualified(self.native,"repo","git"))
            values.assert_called_once_with("git",(),"repo","remote.origin.vcs")
            query.assert_called_once_with("git",(),"repo",("config","--type=bool","--get-urlmatch","http.followRedirects",self.native.endpoint),accepted=(0,1))
    def test_real_git_inherited_config_and_url_override(self):
        import os
        import shutil
        git = shutil.which("git")
        if git is None:
            self.skipTest("Git unavailable")
        root = str(CANONICAL_HOOK.parents[3])
        native = self.g.NativePushInput("receiver_inventory_test", "https://example.invalid/repo.git", b"")
        env = {
            "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "http.followRedirects",
            "GIT_CONFIG_VALUE_0": "false", "GIT_CONFIG_PARAMETERS": "",
        }
        with mock.patch.dict(os.environ, env):
            self.assertTrue(self.g._native_receiver_inventory_qualified(native, root, git))
            with mock.patch.dict(os.environ, {
                "GIT_CONFIG_COUNT": "2",
                "GIT_CONFIG_KEY_1": "http.https://example.invalid/.followRedirects",
                "GIT_CONFIG_VALUE_1": "true",
            }):
                self.assertFalse(self.g._native_receiver_inventory_qualified(native, root, git))
            with mock.patch.dict(os.environ, {
                "GIT_CONFIG_COUNT": "2",
                "GIT_CONFIG_KEY_1": "remote.receiver_inventory_test.vcs",
                "GIT_CONFIG_VALUE_1": "custom",
            }):
                self.assertFalse(self.g._native_receiver_inventory_qualified(native, root, git))

    def test_owned_push_default_https_is_nonredirecting_without_persisting_config(self):
        import os
        import shutil
        import subprocess
        import tempfile
        git = shutil.which("git")
        if git is None:
            self.skipTest("Git unavailable")
        with tempfile.TemporaryDirectory() as root, mock.patch.dict(os.environ, {
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        }):
            def command(*args):
                return subprocess.check_output([git, "-C", root, *args])
            command("init", "-q")
            command("remote", "add", "origin", "https://fetch.example.invalid/fetch.git")
            command("remote", "set-url", "--push", "origin", self.native.endpoint)
            before = (Path(root) / ".git" / "config").read_bytes()
            options = self.g._native_default_receiver_config("origin", root, git)
            self.assertEqual(options, ("-c", f"http.{self.native.endpoint}.followRedirects=false"))
            hook = Path(root) / ".git" / "hooks" / "pre-push"
            hook.write_bytes(b'#!/bin/sh\ntest "$(git config --type=bool --get-urlmatch http.followRedirects "$1")" = false\n')
            hook.chmod(0o755)
            command(*options, "hook", "run", "pre-push", "--", self.native.endpoint)
            self.assertEqual(
                command(*options, "config", "--type=bool", "--get-urlmatch",
                        "http.followRedirects", self.native.endpoint), b"false\n")
            self.assertEqual((Path(root) / ".git" / "config").read_bytes(), before)
            command("config", "http.followRedirects", "initial")
            self.assertEqual(self.g._native_default_receiver_config("origin", root, git), ())
            command("config", "--unset", "http.followRedirects")
            command("config", "remote.origin.vcs", "custom")
            self.assertEqual(self.g._native_default_receiver_config("origin", root, git), ())
            command("config", "--unset", "remote.origin.vcs")
            command("remote", "set-url", "--push", "--add", "origin", "https://other.example.invalid/a.git")
            self.assertEqual(self.g._native_default_receiver_config("origin", root, git), ())

    def test_selection_hash_binds_qualification(self):
        with mock.patch.object(self.g,"_native_receiver_inventory_qualified",return_value=False):
            old,old_binding=self.g._native_push_selection(self.native,observation(),self.g._native_canonical_bytes)
        with mock.patch.object(self.g,"_native_receiver_inventory_qualified",return_value=True):
            new,new_binding=self.g._native_push_selection(self.native,observation(),self.g._native_canonical_bytes)
        self.assertFalse(old["receiverInventory"])
        self.assertTrue(new["receiverInventory"])
        self.assertNotEqual(old_binding.selection_sha256,new_binding.selection_sha256)

if __name__ == "__main__":
    unittest.main()
