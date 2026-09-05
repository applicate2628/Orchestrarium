"""Audit-only partitioning; collector state is isolated from test environments."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest

# Tests may replace os.environ, os.name, cwd, and subprocess functions. Capture
# the collector's own configuration once, before importing or running tests.
_ENV = dict(os.environ)
_OS = os.name
_ROOT = str(Path.cwd())
_REPORT_DIR = Path(_ENV['AUDIT_REPORT_DIR']).resolve()
_REPORT_DIR.mkdir(parents=True, exist_ok=True)
_EXPECTED_HEAD = _ENV['AUDIT_EXPECTED_HEAD']
_TOTAL = int(_ENV['AUDIT_SHARDS'])
_INDEX = int(_ENV['AUDIT_INDEX'])
_POPEN = subprocess.Popen
_OPEN = open
_DUMPS = json.dumps
_ROWS = []


def _head():
    process = _POPEN(['git', '-C', _ROOT, 'rev-parse', 'HEAD'],
                     env=_ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate(timeout=30)
    if process.returncode:
        raise RuntimeError('could not verify audit source revision')
    return stdout.decode('ascii').strip()


def _write(name, value):
    with _OPEN(str(_REPORT_DIR / name), 'w', encoding='utf-8') as stream:
        stream.write(_DUMPS(value, ensure_ascii=True, indent=2) + '\n')


def _flush():
    with _OPEN(str(_REPORT_DIR / 'reports.jsonl'), 'w', encoding='utf-8') as stream:
        for row in _ROWS:
            stream.write(_DUMPS(row, ensure_ascii=True) + '\n')


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    if not 0 <= _INDEX < _TOTAL or _head() != _EXPECTED_HEAD:
        raise pytest.UsageError('invalid audit partition or changed source revision')
    ordered = sorted(items, key=lambda item: (hashlib.sha256(item.nodeid.encode()).digest(), item.nodeid))
    identifiers = [item.nodeid for item in ordered]
    if len(set(identifiers)) != len(identifiers):
        raise pytest.UsageError('duplicate audit node identifiers')
    selected = ordered[_INDEX::_TOTAL]
    if not selected:
        raise pytest.UsageError('empty audit partition')
    kept = {id(item) for item in selected}
    deselected = [item for item in items if id(item) not in kept]
    items[:] = selected
    config.hook.pytest_deselected(items=deselected)
    _write('inventory.json', {'head': _EXPECTED_HEAD, 'os': _OS, 'index': _INDEX,
           'shards': _TOTAL, 'collected': identifiers,
           'selected': [item.nodeid for item in selected],
           'collection_sha256': hashlib.sha256(_DUMPS(identifiers).encode()).hexdigest()})


def pytest_runtest_logreport(report):
    row = {'nodeid': report.nodeid, 'when': report.when, 'outcome': report.outcome,
           'duration': report.duration, 'subtest': hasattr(report, 'context')}
    if report.failed:
        row['failure'] = report.longreprtext
    elif report.skipped:
        row['skip_reason'] = str(report.longrepr)
    _ROWS.append(row)
    if report.failed:
        print(f'\nAUDIT FAILURE: {report.nodeid} [{report.when}]\n{report.longreprtext}\n', flush=True)
    # No filesystem operations while call-stage monkeypatch fixtures are active.
    if report.when == 'teardown':
        _flush()


def pytest_sessionfinish(session, exitstatus):
    head = _head()
    if head != _EXPECTED_HEAD:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
    _flush()
    _write('exit.json', {'exitstatus': int(session.exitstatus), 'head': head})
