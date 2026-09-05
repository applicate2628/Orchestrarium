"""Run one disjoint full-collection shard and preserve its actual outcomes."""
from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

import pytest

from windows_owned_workspace import current_user_owned_workspace

sys.path.insert(0, str(Path.cwd()))
out = Path(os.environ['RUNNER_TEMP']) / 'pr4-audit-evidence'
out.mkdir(parents=True, exist_ok=True)
source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
assert source == os.environ['SOURCE_HEAD'], 'source revision drifted'
shard = int(os.environ['AUDIT_SHARD'])
metadata = {'source': source, 'shard': shard, 'shards': 6, 'python': sys.version, 'platform': platform.platform()}


class Audit:
    def pytest_collection_modifyitems(self, session, config, items):
        files = sorted({item.path.relative_to(config.rootpath).as_posix() for item in items})
        admitted = set(files[shard::6])
        selected = [item for item in items if item.path.relative_to(config.rootpath).as_posix() in admitted]
        deselected = [item for item in items if item.path.relative_to(config.rootpath).as_posix() not in admitted]
        manifest = dict(metadata, files=files, all_nodeids=[item.nodeid for item in items], selected_nodeids=[item.nodeid for item in selected])
        (out / 'collection.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        if not selected:
            raise pytest.UsageError('empty audit shard')
        config.hook.pytest_deselected(items=deselected)
        items[:] = selected

    def pytest_runtest_logreport(self, report):
        row = {'nodeid': report.nodeid, 'when': report.when, 'outcome': report.outcome, 'duration': report.duration}
        if report.failed or report.skipped:
            row['longrepr'] = str(report.longrepr)
        with (out / 'outcomes.jsonl').open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row) + '\n')


with (out / 'dependencies.txt').open('w', encoding='utf-8') as stream:
    subprocess.run([sys.executable, '-m', 'pip', 'freeze'], stdout=stream, check=True)
with current_user_owned_workspace(Path.cwd()) as ownership:
    metadata.update(ownership)
    (out / 'environment.json').write_text(json.dumps(metadata, indent=2), encoding='utf-8')
    code = pytest.main(['-q', '-ra', '--tb=short', '--timeout=600', '--durations=20', '--junitxml=' + str(out / 'junit.xml')], plugins=[Audit()])
(out / 'exit-code.txt').write_text(str(int(code)) + '\n', encoding='ascii')
raise SystemExit(code)
