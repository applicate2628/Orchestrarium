"""Offline common-directory discovery without importing Windows transport APIs."""
import ast
import contextlib
import io
import sys
from types import SimpleNamespace
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SOURCE = (ROOT / 'scripts/universal-hooks/scripts/receiver_transport.py').read_text()
TREE = ast.parse(SOURCE)
DEFINITIONS = {n.name: n for n in TREE.body if isinstance(n, ast.FunctionDef)}
NODES = [DEFINITIONS[name] for name in ('_repository_config_paths', '_owner_git_environment')]
NAMESPACE = dict(pathlib=__import__('pathlib'), subprocess=subprocess,
                 canonical=lambda p: os.path.normcase(os.path.abspath(p)))
exec(compile(ast.Module(body=NODES, type_ignores=[]), 'receiver-layout', 'exec'), NAMESPACE)
discover = NAMESPACE['_repository_config_paths']
owner_git_environment = NAMESPACE['_owner_git_environment']


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.git = shutil.which('git')
        if not self.git:
            self.skipTest('Git unavailable')
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.repo = self.base / 'repository with spaces'
        self.env = {k: v for k, v in os.environ.items() if not k.upper().startswith('GIT_')}
        self.env.update(GIT_CONFIG_NOSYSTEM='1', GIT_CONFIG_GLOBAL=os.devnull)
        self.run_git('init', str(self.repo))

    def run_git(self, *args):
        return subprocess.run([self.git, *args], env=self.env, check=True, capture_output=True)

    def test_regular(self):
        self.assertEqual(discover(self.git, self.repo, self.env), (str(self.repo / '.git/config'),))

    def test_linked_worktree(self):
        self.run_git('-C', str(self.repo), '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                     'commit', '--allow-empty', '-m', 'fixture')
        linked = self.base / 'linked workspace'
        self.run_git('-C', str(self.repo), 'worktree', 'add', '--detach', str(linked))
        paths = discover(self.git, linked, self.env)
        self.assertEqual(paths[0], str(self.repo / '.git/config'))
        self.assertEqual(paths[1], str(linked / '.git'))
        self.assertEqual(Path(paths[2]).name, 'commondir')
        self.assertEqual(len(paths), 3)
        # Run the common pin/freeze owner with real discovery and a recorded pin provider.
        held = []
        namespace = dict(NAMESPACE, GIT=self.git, PinnedFile=lambda name: name)
        node = DEFINITIONS['_pin_and_freeze_owner_config']
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'receiver-owner', 'exec'), namespace)
        qualification = SimpleNamespace(origins=(paths[0],), executables=())
        env = dict(self.env)
        namespace['_pin_and_freeze_owner_config'](linked, env, paths, qualification, held)
        self.assertEqual(held, list(paths))
        self.assertNotEqual(env['GIT_CONFIG_GLOBAL'], self.env['GIT_CONFIG_GLOBAL'])
        def changed(*args):
            self.assertEqual(held, list(paths))  # Holds precede the independent reread.
            return paths[:1]
        namespace['_repository_config_paths'] = changed
        held.clear()
        env = dict(self.env)
        with self.assertRaisesRegex(ValueError, 'repository config paths changed'):
            namespace['_pin_and_freeze_owner_config'](linked, env, paths, qualification, held)
        self.assertEqual(env, self.env)
        Path(paths[2]).unlink()
        with self.assertRaises(ValueError):
            discover(self.git, linked, self.env)

    def test_existing_same_directory_pointer_is_pinned(self):
        pointer = self.repo / '.git/commondir'
        pointer.write_text('.\n')
        paths = discover(self.git, self.repo, self.env)
        self.assertEqual(paths, (str(self.repo / '.git/config'), str(pointer)))

    def test_bare_refused(self):
        bare = self.base / 'bare'
        self.run_git('init', '--bare', str(bare))
        with self.assertRaisesRegex(ValueError, 'unsupported repository root'):
            discover(self.git, bare, self.env)

    def test_missing_repository_refused(self):
        with self.assertRaisesRegex(ValueError, 'discovery failed'):
            discover(self.git, self.base / 'missing', self.env)

    def test_ambiguous_response_refused(self):
        for output in (b'relative\nrelative\n', b'/a\n/b\n/c\n', b'x' * 65537):
            with self.subTest(output=output[:20]), patch.object(subprocess, 'run', return_value=
                    subprocess.CompletedProcess([], 0, output, b'')), self.assertRaises(ValueError):
                discover(self.git, self.repo, self.env)

    def test_owner_supplied_executable_is_used_unchanged(self):
        original = subprocess.run
        with patch.object(subprocess, 'run', wraps=original) as run:
            discover(self.git, self.repo, self.env)
        self.assertEqual(run.call_args.args[0][0], self.git)

    def test_both_owners_pin_indirections_then_qualify_again_before_launch(self):
        common = ast.get_source_segment(SOURCE, DEFINITIONS['_pin_and_freeze_owner_config'])
        self.assertLess(common.index('pins.append(PinnedFile(name))'),
                        common.index('if _repository_config_paths(GIT,source,env)!=local_paths'))
        for name in ('run_target', 'prepare_portable_batch'):
            body = ast.get_source_segment(SOURCE, DEFINITIONS[name])
            self.assertIn('_owner_config_origins_match(', body)
            self.assertNotIn("source/'.git/config'", body)
            recheck = body.index('_pin_and_freeze_owner_config(')
            self.assertGreater(body.index('qualify(', recheck), recheck)
            self.assertGreater(body.index('_owner_push_endpoint(', recheck), recheck)

    def test_owner_endpoint_query_never_returns_raw_git_error(self):
        namespace = dict(subprocess=subprocess, valid_receiver_endpoint=lambda x: True)
        node = DEFINITIONS['_owner_push_endpoint']
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'receiver-endpoint', 'exec'), namespace)
        read = namespace['_owner_push_endpoint']
        failure = subprocess.CalledProcessError(2, ['synthetic'], stderr=b'private-fixture-text')
        with patch.object(subprocess, 'check_output', side_effect=failure) as query:
            with self.assertRaisesRegex(ValueError, '^unqualified endpoint inspection$') as caught:
                read(self.git, self.repo, 'origin', (), self.env)
            self.assertEqual(query.call_args.kwargs['stderr'], subprocess.PIPE)
            self.assertTrue(caught.exception.__suppress_context__)
            self.assertNotIn('private-fixture-text', str(caught.exception))

    def test_admitted_target_never_launches_after_endpoint_drift(self):
        # Run the target owner through payload rendering and the pinned reread.
        # All platform/process peers are fixtures, and no push can be launched.
        from unittest.mock import Mock
        import pathlib, shlex, time
        current = 'https://github.com/example/first.git'
        later = 'https://github.com/example/later.git'
        qualification = SimpleNamespace(eligible=True, origins=(), executables=())
        broker = Mock()
        launch = Mock(side_effect=AssertionError('fixture must not launch Git'))
        environment = SimpleNamespace(environ=dict(self.env, LOCALAPPDATA=str(self.base)),
                                      urandom=os.urandom, getpid=os.getpid)
        def pin(path):
            return SimpleNamespace(sha256={
                self.git: '9c75f3f41eb5686bacde4b7c4fdfcd7970e8b699ee05c8d7a0cc9c8a7ddaffe8',
                'fixture-helper': 'ad461657eca12dfeb50f281d107ac3760ac355a20882e4a3b0d470cb6bab77c6',
            }.get(str(path)), close=lambda: None)
        endpoint = Mock(side_effect=(current, later))
        namespace = dict(pathlib=pathlib, shlex=shlex, sys=sys, os=environment, tempfile=tempfile,
                         time=time, GIT=self.git, HELPER='fixture-helper',
                         _owner_git_environment=owner_git_environment, qualify=lambda *a, **k: qualification,
                         _repository_config_paths=lambda *a: ('config',), _owner_config_origins_match=lambda *a: True,
                         _owner_push_endpoint=endpoint, _pin_and_freeze_owner_config=lambda *a: None,
                         Broker=lambda *a, **k: broker, NATIVE_CALLBACK='# fixture only',
                         PinnedFile=pin, subprocess=SimpleNamespace(Popen=launch), __file__=__file__)
        node = DEFINITIONS['run_target']
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'receiver-owner', 'exec'), namespace)
        gate = SimpleNamespace(SCAN_TIMEOUT_SECONDS=30, __file__=__file__)
        with self.assertRaisesRegex(ValueError, 'effective endpoint changed before pins'):
            namespace['run_target'](gate, self.repo, 'origin', 'HEAD', 'refs/heads/topic')
        launch.assert_not_called()
        broker.close.assert_called_once()
        self.assertEqual(endpoint.call_count, 2)
        rendered = list(self.base.rglob('relay.py'))
        self.assertEqual(len(rendered), 1)
        self.assertIn(current, rendered[0].read_text())
        self.assertNotIn(later, rendered[0].read_text())

    def test_initial_receiver_qualification_refusal_runs_no_transfer_or_discovery(self):
        node = DEFINITIONS['run_target']
        def refuse(*args, **kwargs):
            # Simulate an unexpected value: the fallback must render only its own fixed label.
            return SimpleNamespace(eligible=False, reason='private fixture text')
        namespace = dict(pathlib=__import__('pathlib'), sys=sys, os=os, GIT=self.git,
                         _owner_git_environment=owner_git_environment, qualify=refuse)
        exec(compile(ast.Module(body=[node], type_ignores=[]), 'receiver-owner', 'exec'), namespace)
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertIsNone(namespace['run_target'](None, self.repo, 'origin', 'HEAD', 'main'))
        self.assertEqual(stderr.getvalue(),
                         'Receiver scope: target-local qualification refused; using ordinary publication checks.\n')

    def test_owner_disables_pager_without_mutating_ambient_or_overrides(self):
        original = dict(self.env, Git_Pager='unused-fixture-pager', HTTPS_PROXY='fixture-proxy')
        actual = owner_git_environment(original)
        self.assertEqual(actual, dict(self.env, GIT_PAGER='cat', HTTPS_PROXY='fixture-proxy'))
        self.assertEqual(original['Git_Pager'], 'unused-fixture-pager')
        self.assertNotIn('GIT_PAGER', original)
        self.assertEqual(discover(self.git, self.repo, actual), (str(self.repo / '.git/config'),))

    def test_both_owner_routes_use_private_env_for_direct_git_calls(self):
        for name in ('run_target', 'prepare_portable_batch'):
            body = ast.get_source_segment(SOURCE, DEFINITIONS[name])
            self.assertEqual(body.count('_owner_git_environment(os.environ)'), 1)
            self.assertNotIn('dict(os.environ', body)
            for call in ast.walk(DEFINITIONS[name]):
                if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
                    continue
                if not isinstance(call.func.value, ast.Name) or call.func.value.id != 'subprocess':
                    continue
                child_env = next(k.value.id for k in call.keywords if k.arg == 'env')
                self.assertEqual(child_env, 'transfer_env' if call.func.attr == 'Popen' else 'env')

    def test_mirrors(self):
        for name in ('src.codex/skills/lead/scripts/receiver_transport.py',
                     'src.claude/agents/scripts/receiver_transport.py'):
            self.assertEqual((ROOT / name).read_text(), SOURCE)


if __name__ == '__main__':
    unittest.main()
