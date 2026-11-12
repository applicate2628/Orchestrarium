"""Offline common-directory discovery without importing Windows transport APIs."""
import ast
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
NODE = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == '_repository_config_paths')
NAMESPACE = dict(pathlib=__import__('pathlib'), subprocess=subprocess,
                 canonical=lambda p: os.path.normcase(os.path.abspath(p)))
exec(compile(ast.Module(body=[NODE], type_ignores=[]), 'receiver-layout', 'exec'), NAMESPACE)
discover = NAMESPACE['_repository_config_paths']


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

    def test_owner_pins_indirections_before_recheck(self):
        node = next(n for n in TREE.body if isinstance(n, ast.FunctionDef) and n.name == 'prepare_portable_batch')
        body = ast.get_source_segment(SOURCE, node)
        self.assertIn('expected={canonical(local_paths[0]),', body)
        self.assertIn('*local_paths,*initial.origins,*initial.executables', body)
        self.assertLess(body.index('pins.append(PinnedFile(name))'),
                        body.index('if _repository_config_paths(GIT,source,env)!=local_paths'))
        self.assertIn('unsupported portable owner platform', body)
        self.assertIn('if qualify(', body)
        self.assertIn('apply=False', body)

    def test_mirrors(self):
        for name in ('src.codex/skills/lead/scripts/receiver_transport.py',
                     'src.claude/agents/scripts/receiver_transport.py'):
            self.assertEqual((ROOT / name).read_text(), SOURCE)


if __name__ == '__main__':
    unittest.main()
