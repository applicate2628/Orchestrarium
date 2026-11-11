import importlib.util
import pathlib
import sys
import types
import unittest
from unittest.mock import patch

PATH = pathlib.Path(__file__).resolve().parents[1] / 'scripts/universal-hooks/scripts/check-git-push-gate.py'
sys.path.insert(0, str(PATH.parent))
ROOT = str(pathlib.Path.cwd() / 'fixture-repo')
GIT = str(pathlib.Path(sys.executable).parent / ('git.exe' if sys.platform == 'win32' else 'git'))
PYTHON = sys.executable
OTHER_GIT = str(pathlib.Path.cwd() / 'other' / 'git')
spec = importlib.util.spec_from_file_location('gate_candidate', PATH)
gate = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = gate
spec.loader.exec_module(gate)
ORIGINAL_QUALIFY = gate._qualify_native_parsed_push


class TargetLocalTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.args = [ROOT, 'origin', 'a' * 40, 'refs/heads/fix']
        self.config = ('-c', 'hook.' + gate.NATIVE_PUBLICATION_HOOK + '.command=owned')
        replacements = {
            '_normalize_repository_workdir': lambda *a, **kw: ROOT,
            '_prove_repository_root': lambda *a, **kw: ROOT,
            '_resolve_executable': lambda *a: GIT,
            '_native_configuration_query': lambda *a, **kw: None,
            'native_git_config_arguments': lambda: self.config,
            '_regular_identity': lambda *a, **kw: (1,),
            '_qualify_native_parsed_push': self.qualify,
        }
        for name, value in replacements.items():
            p = patch.object(gate, name, value)
            p.start()
            self.addCleanup(p.stop)
        p = patch.object(gate.subprocess, 'run', self.launch)
        p.start()
        self.addCleanup(p.stop)

    def qualify(self, parsed, *unused):
        self.calls.append(('qualify', parsed))
        return True

    def launch(self, argv, **kwargs):
        self.calls.append(('launch', argv, kwargs))
        return types.SimpleNamespace(returncode=0)

    def test_same_direct_argv_is_qualified_and_launched(self):
        self.assertEqual(gate._target_local_push_main(self.args), 0)
        parsed = self.calls[0][1]
        argv = self.calls[1][1]
        self.assertEqual(gate.native_push_invocation(parsed).command.tokens, argv)
        self.assertEqual(argv, (GIT, '-C', ROOT, *self.config,
            'push', '--verify', '--', 'origin', 'a' * 40 + ':refs/heads/fix'))
        self.assertEqual(self.calls[1][2], {'cwd': ROOT, 'shell': False, 'check': False})

    def test_bad_inputs_never_launch(self):
        for args in [self.args + ['--no-verify'], [ROOT, '-c', 'a'*40, 'refs/heads/fix'],
                     [ROOT, 'origin', 'HEAD', 'refs/heads/fix'],
                     [ROOT, 'origin', 'a'*40, 'refs/tags/fix']]:
            self.assertEqual(gate._target_local_push_main(args), 2)
        self.assertFalse(self.calls)

    def test_ref_grammar_refusal_never_launches(self):
        with patch.object(gate, '_native_configuration_query', side_effect=gate.PrRouteDenied('PGG-NATIVE-CONFIGURATION')):
            self.assertEqual(gate._target_local_push_main(self.args), 2)
        self.assertFalse(self.calls)

    def test_native_qualification_refusal_never_launches(self):
        with patch.object(gate, '_qualify_native_parsed_push', side_effect=gate.PrRouteDenied('PGG-NATIVE-DISABLED')):
            self.assertEqual(gate._target_local_push_main(self.args), 2)
        self.assertFalse(self.calls)

    def test_path_drift_never_launches(self):
        with patch.object(gate, '_resolve_executable', side_effect=[GIT, OTHER_GIT]):
            self.assertEqual(gate._target_local_push_main(self.args), 2)
        self.assertEqual([c[0] for c in self.calls], ['qualify'])

    def test_identity_drift_never_launches(self):
        with patch.object(gate, '_regular_identity', side_effect=[(1,), (2,)]):
            self.assertEqual(gate._target_local_push_main(self.args), 2)
        self.assertEqual([c[0] for c in self.calls], ['qualify'])

    def test_git_failure_is_not_success(self):
        with patch.object(gate.subprocess, 'run', return_value=types.SimpleNamespace(returncode=128)):
            self.assertEqual(gate._target_local_push_main(self.args), 128)

    def test_old_entry_delegates_unchanged_context(self):
        value = types.SimpleNamespace(parsed='parsed', repository_workdir=ROOT, repository_workdir_source='tool')
        with patch.object(gate, '_qualify_native_parsed_push', return_value=True) as qualify:
            self.assertTrue(gate._qualify_native_push_command(value))
            qualify.assert_called_once_with('parsed', ROOT, 'tool')

    def test_direct_argv_rejects_nested_or_decorated_provenance(self):
        from git_push_gate_preflight import literal_direct_command
        parsed = gate.parse_native_argument_vector((GIT, 'status'), 'test', 0)
        self.assertIsNotNone(literal_direct_command(parsed))
        for changes in ({'depth': 1}, {'parent': parsed.identity},
                        {'parent_source_span': (0, 1)}, {'wrapper_id': 'env'},
                        {'payload_composition': 'joined'}, {'contributing_spans': ((0, 1),)}):
            self.assertIsNone(literal_direct_command(parsed._replace(
                identity=parsed.identity._replace(**changes))))
        self.assertIsNone(literal_direct_command(parsed._replace(raw_command='git status')))
        for changes in ({'nesting_context': 'nested'}, {'boundary_before': ';'},
                        {'boundary_after': ';'}, {'normalization_state': 'changed'},
                        {'command_count': 2}, {'ordinal': 1}, {'source_span': (1, 3)}):
            self.assertIsNone(literal_direct_command(parsed._replace(commands=(
                parsed.commands[0]._replace(**changes),))))

    def test_actual_native_qualifier_accepts_owned_vector(self):
        # Exercise real parser and qualifier; only OS/Git observations are fake.
        interpreter = types.SimpleNamespace(absolute_resolved_path=PYTHON)
        expected = gate.shlex.join((PYTHON, str(PATH.resolve()), '--git-pre-push'))
        prefix = 'hook.' + gate.NATIVE_PUBLICATION_HOOK + '.'
        config = tuple(word for pair in [
            (prefix + 'command', expected), (prefix + 'event', ''),
            (prefix + 'event', 'pre-push'), (prefix + 'enabled', 'true'),
            (prefix + 'parallel', 'false')] for word in ('-c', '='.join(pair)))
        def values(git, options, cwd, key, **kwargs):
            return {
                prefix + 'command': (expected.encode(),),
                prefix + 'enabled': (b'true',),
                prefix + 'parallel': (b'false',),
                prefix + 'event': (b'', b'pre-push'),
            }.get(key, ())
        def query(git, options, cwd, arguments, **kwargs):
            return types.SimpleNamespace(stdout={
                ('hook', 'list', '-z', '--show-scope', 'pre-push'):
                    b'command\t' + gate.NATIVE_PUBLICATION_HOOK.encode() + b'\0',
                ('rev-parse', '--show-toplevel'): (ROOT + '\n').encode(),
                ('rev-parse', '--show-object-format'): b'sha1\n',
                ('check-ref-format', 'refs/heads/fix'): b'',
            }[arguments], returncode=0)
        with patch.object(gate, '_qualify_native_parsed_push', ORIGINAL_QUALIFY), \
             patch.object(gate, 'native_git_config_arguments', return_value=config), \
             patch.object(gate, '_prepare_selected_repository_workdir', return_value=ROOT), \
             patch.object(gate, '_bind_literal_executable_identity'), \
             patch.object(gate, '_interpreter_identity', return_value=interpreter), \
             patch.object(gate, '_native_config_values', side_effect=values), \
             patch.object(gate, '_native_configuration_query', side_effect=query):
            self.assertEqual(gate._target_local_push_main(self.args), 0)
        self.assertEqual([c[0] for c in self.calls], ['launch'])


if __name__ == '__main__':
    unittest.main()
