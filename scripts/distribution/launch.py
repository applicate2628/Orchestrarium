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
import re
import stat
import subprocess
import sys


PUBLICATION_MATCHER_TARGET = 'windows-x64'
PUBLICATION_MATCHER_PATH = 'native/orche-publication-match.exe'
PUBLICATION_MATCHER_NOTICES = 'native/THIRD-PARTY-NOTICES.txt'
_MANIFEST_V3_FIELDS = {'schemaVersion', 'product', 'release', 'target', 'python', 'entry',
                       'runtimeProfile', 'runtimeEvidence', 'runtimeEvidenceSha256'}


def _publication_matcher_record(target: str, digest: object) -> dict:
    if (target != PUBLICATION_MATCHER_TARGET or type(digest) is not str
            or re.fullmatch(r'[0-9a-f]{64}', digest) is None):
        raise ValueError('Publication matcher requires a Windows x64 target and qualified SHA-256')
    return {'path': PUBLICATION_MATCHER_PATH, 'sha256': digest}


def _ordinary_native_member(path: Path):
    # The release directory owner excludes competing writers. Observe ordinary
    # paths directly rather than following a static link/reparse substitution.
    for directory in path.parents:
        info = directory.lstat()
        if (not stat.S_ISDIR(info.st_mode)
                or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ValueError('Publication matcher parent is not an ordinary directory')
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
            or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
        raise ValueError('Publication matcher is not a direct ordinary file')
    return info


def verify_publication_matcher_notices(path: Path, digest: str) -> Path:
    info = _ordinary_native_member(path)
    with path.open('rb') as stream:
        if not info.st_size or hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
            raise ValueError('Publication matcher notices differ from the qualified SHA-256')
    return path


def verify_publication_matcher(path: Path, digest: str) -> Path:
    info = _ordinary_native_member(path)
    with path.open('rb') as stream:
        dos = stream.read(64)
        if len(dos) != 64 or dos[:2] != b'MZ':
            raise ValueError('Publication matcher is not a Windows x64 executable image')
        pe = int.from_bytes(dos[60:64], 'little')
        if pe < len(dos) or pe + 26 > info.st_size:
            raise ValueError('Publication matcher has an invalid executable header')
        stream.seek(pe)
        image = stream.read(26)
        characteristics = int.from_bytes(image[22:24], 'little')
        if (len(image) != 26 or image[:4] != b'PE\0\0'
                or int.from_bytes(image[4:6], 'little') != 0x8664
                or int.from_bytes(image[20:22], 'little') < 2
                or characteristics & 0x2002 != 0x0002
                or int.from_bytes(image[24:26], 'little') != 0x20B):
            raise ValueError('Publication matcher is not a Windows x64 executable image')
        stream.seek(0)
        if hashlib.file_digest(stream, 'sha256').hexdigest() != digest:
            raise ValueError('Publication matcher differs from the qualified SHA-256')
    return path


def publication_matcher(root: Path, data: dict) -> Path | None:
    record = data.get('publicationMatcher')
    if record is None:
        return None
    matcher = verify_publication_matcher(root / PUBLICATION_MATCHER_PATH, record['sha256'])
    verify_publication_matcher_notices(root / PUBLICATION_MATCHER_NOTICES,
                                       data['publicationMatcherNoticesSha256'])
    return matcher


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
    version = data.get('schemaVersion') if type(data) is dict else None
    if (type(version) is not int or version not in (3, 4)
        or set(data) != (_MANIFEST_V3_FIELDS | {'publicationMatcher', 'publicationMatcherNoticesSha256'} if version == 4 else _MANIFEST_V3_FIELDS)
        or data['runtimeProfile'] != 'cpython-stdlib-only'
        or data['product'] != 'Orche' or type(data['release']) is not str or not data['release'].strip()
        or data['runtimeEvidence'] != 'runtime-evidence.json'
        or type(data['runtimeEvidenceSha256']) is not str
        or data['target'] != current_target() or data['entry'] != 'app/install.py'):
        raise ValueError('Unsupported or mismatched bundle manifest')
    if version == 4:
        record = data['publicationMatcher']
        if (type(record) is not dict
                or record != _publication_matcher_record(data['target'], record.get('sha256'))):
            raise ValueError('Invalid publication matcher record')
        notice_digest = data['publicationMatcherNoticesSha256']
        if type(notice_digest) is not str or re.fullmatch(r'[0-9a-f]{64}', notice_digest) is None:
            raise ValueError('Invalid publication matcher notices record')
    evidence = _member(root, data['runtimeEvidence']).read_bytes()
    if hashlib.sha256(evidence).hexdigest() != data['runtimeEvidenceSha256']:
        raise ValueError('Runtime evidence bytes differ from the bundle manifest')
    return data


def resolve_launch(root: Path, executable: Path) -> tuple[Path, Path]:
    root = root.resolve(strict=True)
    data = _manifest(root)
    publication_matcher(root, data)
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
    root = root.resolve(strict=True)
    data = _manifest(root)
    helper = publication_matcher(root, data)
    helper_options = ({'publication_matcher': helper,
                       'publication_matcher_sha256': data['publicationMatcher']['sha256'],
                       'publication_matcher_notices': root / PUBLICATION_MATCHER_NOTICES,
                       'publication_matcher_notices_sha256': data['publicationMatcherNoticesSha256']}
                      if helper is not None else {})
    builder_path = _member(root, 'app/scripts/distribution/build.py')
    spec = importlib.util.spec_from_file_location('orche_bundle_build', builder_path)
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    destination = builder.build(root / 'app', root / 'python', destination,
                                target=data['target'], release=data['release'],
                                runtime_evidence=_member(root, data['runtimeEvidence']),
                                **helper_options).resolve(strict=True)
    # Re-read the retained manifest and selected native member before handing
    # the output to either a retain-only caller or the retained launch.
    retained = _manifest(destination)
    if any(retained.get(field) != data.get(field)
           for field in ('publicationMatcher', 'publicationMatcherNoticesSha256')):
        raise ValueError('Retained publication matcher or notices differ from the original')
    publication_matcher(destination, retained)
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
