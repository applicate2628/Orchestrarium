"""Run every assigned test file and retain failures without hiding other results."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--shard', type=int, required=True)
    parser.add_argument('--total', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.total < 1 or not 0 <= args.shard < args.total:
        parser.error('invalid shard')
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    files = sorted(Path('tests').glob('test_*.py'), key=lambda path: path.name)
    selected = files[args.shard::args.total]
    if not selected:
        raise SystemExit('empty shard')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    (output / 'identity.json').write_text(json.dumps({
        'head': head, 'python': sys.version, 'platform': sys.platform,
        'shard': args.shard, 'total': args.total,
        'all_files': [str(path) for path in files],
        'selected_files': [str(path) for path in selected],
    }, indent=2), encoding='utf-8')
    results = []
    for path in selected:
        start = time.monotonic()
        command = [sys.executable, '-m', 'pytest', '-q', '-ra', str(path),
                   '--durations=3', '--junitxml=' + str(output / (path.stem + '.xml'))]
        with (output / (path.stem + '.log')).open('w', encoding='utf-8') as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                       start_new_session=os.name != 'nt')
            timed_out = False
            try:
                status = process.wait(timeout=600)
            except subprocess.TimeoutExpired:
                timed_out = True
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(process.pid)],
                                   stdout=log, stderr=subprocess.STDOUT, timeout=30)
                else:
                    os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=30)
                status = 124
                log.write('\nAUDIT_TIMEOUT: no passing result inferred.\n')
        result = {'file': str(path), 'exit': status, 'timeout': timed_out,
                  'seconds': round(time.monotonic() - start, 2)}
        print(json.dumps(result), flush=True)
        results.append(result)
        (output / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    return int(any(result['exit'] for result in results))


if __name__ == '__main__':
    raise SystemExit(main())
