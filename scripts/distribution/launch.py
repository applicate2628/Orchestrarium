"""Orche's shared bundled-Python entry; pack policy stays in install.py.

This is a local payload consistency check, NOT publisher authentication. The
channel must authenticate the complete release before executing its interpreter.
"""
from __future__ import annotations

import importlib.util
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import subprocess
import sys


def current_target() -> str:
    system = {'win32': 'windows', 'linux': 'linux', 'darwin': 'macos'}.get(sys.platform)
    machine = platform.machine().lower()
    arch = {'amd64': 'x64', 'x86_64': 'x64', 'arm64': 'arm64', 'aarch64': 'arm64'}.get(machine)
    if system is None or arch is None:
        raise ValueError('Unsupported operating system or architecture')
    return f'{system}-{arch}'


def _member(root: Path, relative: object) -> Path:
    if type(relative) is not str or not relative or '\\' in relative or ':' in relative:
        raise ValueError('Invalid bundle-relative path')
    path = PurePosixPath(relative)
    if path.is_absolute() or '..' in path.parts or any(ord(c) < 32 for c in relative):
        raise ValueError('Invalid bundle-relative path')
    result = root.joinpath(*path.parts)
    resolved = result.resolve(strict=True)
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError('Bundle member is missing or escapes the bundle')
    return result


def _manifest(root: Path) -> dict:
    with _member(root, 'bundle.json').open('rb') as stream:
        raw = stream.read(16385)
    if len(raw) > 16384:
        raise ValueError('Bundle manifest exceeds its size limit')
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate bundle field')
            result[key] = value
        return result
    data = json.loads(raw, object_pairs_hook=unique)
    if (type(data) is not dict or set(data) != {'schemaVersion', 'product', 'release', 'target', 'python', 'entry', 'runtimeProfile', 'runtimeEvidence', 'runtimeEvidenceSha256'}
        or type(data['schemaVersion']) is not int or data['schemaVersion'] != 3 or data['runtimeProfile'] != 'cpython-stdlib-only'
        or data['product'] != 'Orche' or type(data['release']) is not str or not data['release'].strip()
        or data['runtimeEvidence'] != 'runtime-evidence.json'
        or type(data['runtimeEvidenceSha256']) is not str
        or data['target'] != current_target() or data['entry'] != 'app/install.py'):
        raise ValueError('Unsupported or mismatched bundle manifest')
    evidence = _member(root, data['runtimeEvidence']).read_bytes()
    if hashlib.sha256(evidence).hexdigest() != data['runtimeEvidenceSha256']:
        raise ValueError('Runtime evidence bytes differ from the bundle manifest')
    return data


def resolve_launch(root: Path, executable: Path) -> tuple[Path, Path]:
    root = root.resolve(strict=True)
    data = _manifest(root)
    python = _member(root, data['python'])
    entry = _member(root, data['entry'])
    if not os.path.samefile(python, executable):
        raise ValueError('Launch with this bundle\'s Python; no system fallback')
    return python, entry


def retain_bundle(root: Path, destination: Path) -> tuple[Path, Path]:
    """Copy into an explicitly selected permanent location before pack effects.

    Existing locations are never adopted or replaced. Old releases are retained;
    their registered hooks may still use them. Assembly has one implementation.
    """
    if not destination.is_absolute():
        raise ValueError('Retention requires an absolute destination')
    data = _manifest(root)
    builder_path = _member(root, 'app/scripts/distribution/build.py')
    spec = importlib.util.spec_from_file_location('orche_bundle_build', builder_path)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    destination = builder.build(root / 'app', root / 'python', destination,
                                target=data['target'], release=data['release'],
                                runtime_evidence=_member(root, data['runtimeEvidence'])).resolve(strict=True)
    return _member(destination, data['python']), _member(destination, 'launch.py')


def child_environment(source: dict[str, str]) -> dict[str, str]:
    result = {key: value for key, value in source.items() if not key.upper().startswith('PYTHON')}
    result.update(PYTHONNOUSERSITE='1', PYTHONDONTWRITEBYTECODE='1')
    return result


def _exec_child(python: str, args: list[str], env: dict[str, str]) -> int:
    if sys.platform == 'win32':
        # Windows execve does not provide POSIX replacement/argv semantics.
        # A sequence without a shell preserves quoting and waits for the result.
        return subprocess.run(args, env=env).returncode
    os.execve(python, args, env)
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        root = Path(__file__).resolve().parent
        python, entry = resolve_launch(root, Path(sys.executable))
        args = list(sys.argv[1:] if argv is None else argv)
        lifetime = args[0] if args else None
        if lifetime == '--retain-only':
            if len(args) != 2 or not Path(args[1]).is_absolute():
                print('Orche: --retain-only requires exactly one absolute destination and no installer options.',
                      file=sys.stderr)
                return 2
            retain_bundle(root, Path(args[1]))
            print('Orche: bundle retained; no pack installation started.')
            return 0

        permanent = lifetime in ('--permanent-runtime', '--retain-to')
        destination = None
        if lifetime == '--permanent-runtime':
            args = args[1:]
        elif lifetime == '--retain-to':
            if len(args) < 2 or not Path(args[1]).is_absolute():
                print('Orche: --retain-to requires an absolute destination.', file=sys.stderr)
                return 2
            destination = Path(args[1])
            args = args[2:]
        if any(flag in args for flag in ('--retain-only', '--retain-to', '--permanent-runtime')):
            print('Orche: specify one runtime lifetime option before installer options.', file=sys.stderr)
            return 2
        help_requested = '--help' in args or '-h' in args
        dry_run = '--dry-run' in args or '-DryRun' in args
        read_only = help_requested or dry_run
        if '--shared-hook-runtime' in args:
            if dry_run and destination is not None:
                print('Orche: shared-hook preview must use --permanent-runtime; '
                      '--retain-to would write a bundle.', file=sys.stderr)
                return 2
            if not permanent or help_requested or any(flag in args for flag in ('--uninstall', '--apply')):
                print('Orche: --shared-hook-runtime requires a pack installation with '
                      '--retain-to ABSOLUTE_DIRECTORY or --permanent-runtime.', file=sys.stderr)
                return 2
        if not permanent and not read_only:
            print('Orche: apply requires --retain-to ABSOLUTE_DIRECTORY or '
                  '--permanent-runtime. Keep the selected runtime while installed hooks use it.',
                  file=sys.stderr)
            return 2
        if destination is not None:
            python, entry = retain_bundle(root, destination)
            # Explicit retention is the lifetime decision for the retained launch.
            args = ['--permanent-runtime', *args]
        return _exec_child(str(python), [str(python), '-I', '-B', str(entry), *args],
                           child_environment(dict(os.environ)))
    except (OSError, ValueError, UnicodeError):
        print('Orche: bundled runtime is unavailable or inconsistent. No pack installation started; an incomplete retained copy may remain.', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
