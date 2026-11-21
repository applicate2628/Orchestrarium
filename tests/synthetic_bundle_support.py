"""Synthetic expected records for unrelated bundle fixtures, never qualification."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory


def synthetic_notice_root(source, target):
    return source / 'scripts/distribution/notices/python-build-standalone' / (target + '-cp315')


def synthetic_record(builder, runtime, notices, target):
    runtime_inventory = (builder._payload_inventory(runtime, builder.IGNORE)
                         if runtime.is_dir() else {})
    return {'schemaVersion': 2, 'target': target, 'runtimeProfile': builder.RUNTIME_PROFILE,
            'runtime': runtime_inventory or {'empty': ['file', '0' * 64, False]},
            'notices': builder._payload_inventory(notices, builder._notice_selection(notices, target))}


def build_synthetic_bundle(builder, source, runtime, output, *, target, release):
    notices = source / 'scripts/distribution/notices'
    if not notices.exists():
        # Minimal fake sources supply a synthetic notice for the selected target.
        assert source != Path(__file__).resolve().parents[1]
        selected = synthetic_notice_root(source, target)
        selected.mkdir(parents=True)
        (selected / 'SYNTHETIC-NOTICE.txt').write_text('Synthetic fixture, not legal evidence.\n')
    record = synthetic_record(builder, runtime, notices, target)
    with TemporaryDirectory(prefix='orche-synthetic-record-') as temporary:
        evidence = Path(temporary) / 'runtime-evidence.json'
        evidence.write_text(json.dumps(record), encoding='utf-8')
        return builder.build(source, runtime, output, target=target, release=release,
                             runtime_evidence=evidence)
