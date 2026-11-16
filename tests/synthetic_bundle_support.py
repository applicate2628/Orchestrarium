"""Synthetic expected records for unrelated bundle fixtures, never qualification."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory


def build_synthetic_bundle(builder, source, runtime, output, *, target, release):
    notices = source / 'scripts/distribution/notices'
    if not notices.exists():
        # Minimal fake source fixtures predate the notice-binding contract.
        assert source != Path(__file__).resolve().parents[1]
        notices.mkdir(parents=True)
        (notices / 'SYNTHETIC-NOTICE.txt').write_text('Synthetic fixture, not legal evidence.\n')
    runtime_inventory = (builder._payload_inventory(runtime, builder._runtime_ignore(runtime, target))
                         if runtime.is_dir() else {'missing': ['file', '0' * 64, False]})
    record = {'schemaVersion': 1, 'target': target,
              'runtime': runtime_inventory or {'empty': ['file', '0' * 64, False]},
              'notices': builder._payload_inventory(notices, builder._notice_ignore(notices))}
    with TemporaryDirectory(prefix='orche-synthetic-record-') as temporary:
        evidence = Path(temporary) / 'runtime-evidence.json'
        evidence.write_text(json.dumps(record), encoding='utf-8')
        return builder.build(source, runtime, output, target=target, release=release,
                             runtime_evidence=evidence)
