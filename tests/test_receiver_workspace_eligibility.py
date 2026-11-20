"""The optional route declines unsupported workspace spelling before effects."""

import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest import mock


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "scripts/universal-hooks/scripts/receiver_transport.py"
)


def _load_transport():
    # Isolate unrelated Windows-only imports; no native transport is exercised.
    imports = {
        "bounded_pipe": ("Broker",),
        "windows_identity": ("PinnedFile", "ProcessWitness", "SameHelperLifecycle", "pipe_process", "canonical"),
        "transfer_binding": ("ScopeBinding", "TransferBinding"),
        "receiver_scope": ("Invocation", "ReceiverScope"),
        "qualifier": ("qualify", "valid_receiver_endpoint"),
    }
    stubs = {
        name: types.SimpleNamespace(**{member: mock.Mock() for member in members})
        for name, members in imports.items()
    }
    spec = importlib.util.spec_from_file_location("receiver_workspace_fixture", SOURCE)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, stubs):
        spec.loader.exec_module(module)
    return module


class ReceiverWorkspaceEligibilityTest(unittest.TestCase):
    def test_unsupported_spelling_declines_before_any_optional_attempt(self):
        transport = _load_transport()
        for profile in ("C:/Users/Example Name/AppData/Local", "C:/Users/Exämple/AppData/Local"):
            with (
                self.subTest(profile=profile),
                mock.patch.dict(transport.os.environ, {"LOCALAPPDATA": profile}),
                mock.patch.object(transport, "qualify", side_effect=AssertionError("optional route started")) as qualify,
                mock.patch.object(transport.pathlib.Path, "mkdir") as mkdir,
                mock.patch.object(transport.tempfile, "mkdtemp") as scratch,
                mock.patch.object(transport, "Broker") as broker,
                mock.patch.object(transport.subprocess, "Popen") as launch,
            ):
                self.assertIsNone(transport.run_target(None, ".", "origin", "tip", "destination"))
                for action in (qualify, mkdir, scratch, broker, launch):
                    action.assert_not_called()

    def test_existing_spelling_still_invokes_qualification(self):
        transport = _load_transport()
        with (
            mock.patch.dict(transport.os.environ, {"LOCALAPPDATA": "C:/Users/Example/AppData/Local"}),
            mock.patch.object(transport, "qualify", return_value=types.SimpleNamespace(eligible=False)) as qualify,
            mock.patch.object(transport.pathlib.Path, "mkdir") as mkdir,
        ):
            self.assertIsNone(transport.run_target(None, ".", "origin", "tip", "destination"))
            qualify.assert_called_once()
            mkdir.assert_not_called()


    @unittest.skipUnless(sys.platform == "win32", "Windows selects the optional receiver")
    def test_ordinary_route_is_still_admitted_once_after_workspace_decline(self):
        from test_git_push_gate_hook import CANONICAL_HOOK, _load_gate_module

        transport = _load_transport()
        gate = _load_gate_module(CANONICAL_HOOK, "receiver_workspace_fallback_test")
        args = ("C:/synthetic", "origin", "a" * 40, "refs/heads/topic")
        for admitted in (False, True):
            with (
                self.subTest(admitted=admitted),
                mock.patch.dict(sys.modules, {"receiver_transport": transport}),
                mock.patch.dict(transport.os.environ, {"LOCALAPPDATA": "C:/Users/Fixture Name/Local"}),
                mock.patch.object(transport, "qualify") as optional,
                mock.patch.object(gate, "_normalize_repository_workdir", return_value=args[0]),
                mock.patch.object(gate, "_prove_repository_root", return_value=args[0]),
                mock.patch.object(gate, "_resolve_executable", return_value="git.exe"),
                mock.patch.object(gate, "_regular_identity", return_value=("synthetic",)),
                mock.patch.object(gate, "_native_configuration_query"),
                mock.patch.object(gate, "parse_native_argument_vector", return_value=object()),
                mock.patch.object(gate, "_qualify_native_parsed_push", return_value=admitted) as admission,
                mock.patch.object(gate.subprocess, "run", return_value=types.SimpleNamespace(returncode=0)) as launch,
            ):
                self.assertEqual(gate._target_local_push_main(list(args)), 0 if admitted else 2)
                optional.assert_not_called()
                admission.assert_called_once()
                if admitted:
                    launch.assert_called_once()
                    self.assertIn("--verify", launch.call_args.args[0])
                else:
                    launch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
