"""Remote carrier observation is not target-host publication qualification."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
DIRECTORIES = (
    ROOT / 'scripts/universal-hooks/scripts',
    ROOT / 'src.codex/skills/lead/scripts',
    ROOT / 'src.claude/agents/scripts',
)
NAME = 'mcp__codex_apps__remote_desktop_commander_start_process'
FAILURE = 'PGG-REMOTE-EXECUTION-UNBOUND'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=DIRECTORIES, ids=('canonical', 'codex', 'claude'))
def owner(request):
    directory = request.param
    sys.path.insert(0, str(directory))
    try:
        # Other gate tests retain classes from their original module instance.
        # Restore the import registry instead of leaking the last pack mirror.
        with mock.patch.dict(sys.modules):
            common = load(directory / 'hook_common.py', 'hook_common')
            preflight = load(directory / 'git_push_gate_preflight.py', 'git_push_gate_preflight')
            yield common, preflight, directory
    finally:
        sys.path.pop(0)


def envelope(command='git push origin main', **extra):
    return {'tool_name': NAME, 'tool_input': {'command': command, **extra}}


def test_exact_remote_identity_and_one_command_carrier(owner):
    common, _, _ = owner
    acquired = common.acquire_tool_input(NAME, {'command': 'git status', 'shell': 'powershell.exe'})
    assert acquired.raw_name == NAME
    assert acquired.operation == 'rdc_start_process'
    assert acquired.resolved and acquired.command == 'git status'
    for name in ('start_process', 'rdc_start_process', 'tools.rdc_start_process',
                 'functions.' + NAME, NAME.upper(), NAME + '_other',
                 'mcp__other__start_process', 'mcp__codex_apps__other_start_process'):
        assert common.normalize_tool_operation(name) is None
        assert not common.acquire_tool_input(name, {'command': 'git status'}).resolved
    for payload in (None, {}, {'command': ''}, {'command': ' '}, {'command': 1},
                    {'cmd': 'git status'}, {'command': 'git status', 'cmd': ''},
                    {'command': 'git status', 'cmd': 'git status'}):
        assert not common.acquire_tool_input(NAME, payload).resolved


@pytest.mark.parametrize('shell,dialect', (
    ('powershell.exe', 'powershell'), ('pwsh', 'powershell'),
    ('bash', 'posix'), ('/bin/sh', 'posix'),
    (None, 'unsupported'), ('', 'unsupported'), ('cmd.exe', 'unsupported'),
    ({}, 'unsupported'), ('powershell.exe -NoProfile', 'unsupported'),
))
def test_remote_dialect_is_explicit_and_not_gate_host_os(owner, shell, dialect):
    _, preflight, _ = owner
    with mock.patch.object(preflight, '_host_command_dialect', side_effect=AssertionError('gate-host fallback')):
        resolution = preflight.resolve_command_dialect(NAME, {'shell': shell})
    assert resolution.dialect == dialect
    assert resolution.exact is (dialect != 'unsupported')


@pytest.mark.parametrize('command', (
    'git push origin main', 'git push --dry-run origin main',
    'git push --no-verify origin main', 'git -C push origin main',
    "& 'C:\\Program Files\\Git\\cmd\\git.exe' '-C' 'C:\\synthetic-repo' 'push' 'origin' 'HEAD:refs/heads/main'",
    'git push origin main; Write-Output done',
))
def test_remote_publication_never_borrows_controller_or_heavy_authority(owner, command):
    _, preflight, _ = owner
    data = envelope(command, shell='powershell.exe', deviceId='synthetic-device', link_id='synthetic-account')
    data['cwd'] = str(ROOT)
    with mock.patch.object(preflight, '_repository_workdir', side_effect=AssertionError('controller cwd borrowed')), \
         mock.patch.object(preflight, '_recover_mislabeled_command_dialect', side_effect=AssertionError('remote dialect recovered')):
        result = preflight.build_preflight(data)
    assert preflight.validate_preflight_result(result) is result
    assert (result.outcome, result.continuation, result.failure_id) == ('DEFER', 'RENDER_DENY', FAILURE)
    assert result.repository_workdir == result.repository_workdir_source == ''


@pytest.mark.parametrize('extra', (
    {}, {'shell': None}, {'shell': 'cmd.exe'}, {'shell': {}},
    {'shell': 'powershell.exe', 'deviceId': 'another-device', 'link_id': 'another-account'},
    {'shell': 'powershell.exe', 'deviceId': '', 'link_id': ''},
    {'shell': 'powershell.exe', 'remote_verified': True, 'workdir': 'C:\\same-path-different-host'},
))
def test_remote_selection_fields_cannot_attest_host_binding(owner, extra):
    _, preflight, _ = owner
    result = preflight.build_preflight(envelope(**extra))
    assert preflight.validate_preflight_result(result) is result
    assert result.failure_id == FAILURE and result.continuation == 'RENDER_DENY'


@pytest.mark.parametrize('payload', (None, {}, {'command': ''}, {'command': 4},
    {'cmd': 'git push origin main'}, {'command': 'git push origin main', 'cmd': ''}))
def test_missing_remote_command_remains_non_authorizing(owner, payload):
    _, preflight, _ = owner
    result = preflight.build_preflight({'tool_name': NAME, 'tool_input': payload})
    assert result.failure_id == 'PGG-PARSE-UNCERTAIN'
    assert result.continuation == 'RENDER_DENY'


def test_remote_nonpublication_and_unknown_dialect_keep_separate_contracts(owner):
    _, preflight, _ = owner
    ordinary = preflight.build_preflight(envelope("Write-Output 'git push is only data'", shell='powershell.exe'))
    assert ordinary.reason_id == 'PFP-ALLOW-NON-PUSH'
    assert ordinary.dialect == 'powershell'
    for extra in ({}, {'shell': 'cmd.exe'}):
        unknown = preflight.build_preflight(envelope('printf ready', **extra))
        assert unknown.reason_id == 'PFP-ABSTAIN-NO-PUBLICATION-EVIDENCE'
        assert unknown.outcome == 'ABSTAIN' and unknown.dialect == 'unsupported'
    unrelated = preflight.build_preflight({'tool_name': 'mcp__other__start_process', 'tool_input': {'command': 'git push origin main'}})
    assert unrelated.reason_id == 'PFP-ALLOW-NO-COMMAND'


def test_public_runner_reports_remote_hold_without_running_git(owner):
    _, _, directory = owner
    result = subprocess.run([sys.executable, '-B', str(directory / 'check-git-push-gate-runner.py')],
                            input=json.dumps(envelope(shell='powershell.exe')), text=True,
                            capture_output=True, timeout=30)
    assert result.returncode == 0 and result.stderr == ''
    decision = json.loads(result.stdout)['hookSpecificOutput']
    assert decision['permissionDecision'] == 'deny'
    assert FAILURE in decision['permissionDecisionReason']
    assert 'target' in decision['permissionDecisionReason'].lower()


def test_remote_navigation_does_not_interpret_controller_cwd(owner):
    _, _, directory = owner
    policy = load(directory / 'mcp_continuity_policy.py', 'rdc_mcp_continuity_policy')
    with mock.patch.object(policy._ScopeCoordinate, 'from_cwd', side_effect=AssertionError('controller cwd interpreted')), \
         mock.patch.object(policy, '_search_invocations', side_effect=AssertionError('remote command interpreted locally')):
        assert not policy.classify_tool_choice(NAME, {'command': 'rg symbol src', 'shell': 'powershell.exe'}, str(ROOT))


@pytest.mark.parametrize('command,shell', (
    ('git -c core.hooksPath=disabled push origin main', 'bash'),
    ('bash -c "git push origin main"', 'bash'),
    ('pwsh -Command "git push origin main"', 'powershell.exe'),
    ('git push origin main; other_command', 'cmd.exe'),
    ('git push --dry-run origin main', None),
))
def test_remote_bypass_wrapper_and_unknown_shell_candidates_refuse(owner, command, shell):
    _, preflight, _ = owner
    with mock.patch.object(preflight, '_repository_workdir', side_effect=AssertionError('controller cwd borrowed')):
        result = preflight.build_preflight(envelope(command, shell=shell))
    assert result.failure_id == FAILURE and result.continuation == 'RENDER_DENY'


def test_existing_subagent_exemption_is_not_new_remote_qualification(owner):
    _, preflight, _ = owner
    data = envelope(shell='powershell.exe')
    data['agent_id'] = 'synthetic-existing-subagent'
    result = preflight.build_preflight(data)
    assert result.reason_id == 'PFP-ALLOW-SUBAGENT'
    assert result.parsed is None and result.repository_workdir == ''
