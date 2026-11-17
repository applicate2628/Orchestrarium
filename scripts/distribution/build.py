"""Assemble a local Orche bundle; no downloads, installation, signing or activation.

Runtime input must already have verified provenance and its required dependencies.
Inputs must remain quiescent and the destination-parent hierarchy exclusively
controlled throughout assembly/retention/launch. This local builder is not a
sandbox against a hostile concurrent writer and does not authenticate a release.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import json
from pathlib import Path
import re
import shutil
import stat

TARGETS = {
    'linux-x64': 'bin/python3', 'linux-arm64': 'bin/python3',
    'macos-x64': 'bin/python3', 'macos-arm64': 'bin/python3',
    'windows-x64': 'python.exe', 'windows-arm64': 'python.exe',
}
APP_INPUTS = ('install.py', 'scripts', 'src.codex', 'adapters', 'shared',
              'references-codex', 'docs', 'README.md',
              'INSTALL.md', 'RELEASE_NOTES.md', 'LICENSE', 'AGENTS.md', 'CLAUDE.md',
              'pyproject.toml', 'assets/branding')
IGNORE = shutil.ignore_patterns('__pycache__', '*.pyc', '.DS_Store')

PYTHON_PACKAGE_DIRS = frozenset({'site-packages', 'dist-packages'})
CLI_ENTRY_NAMES = frozenset({'codex', 'codex.exe', 'codex.cmd', 'codex-script.py'})
# The pinned Linux SDK runtime does not use the optional Berkeley DB backend.
RUNTIME_OMISSIONS = {
    'linux-x64': frozenset({'lib/python3.15/lib-dynload/_dbm.cpython-315-x86_64-linux-gnu.so'}),
}

SH = '''#!/bin/sh
set -eu
case "$0" in
  */*) directory=${0%/*} ;;
  *) directory=. ;;
esac
root=$(CDPATH= cd -P "$directory" && pwd)
exec "$root/python/bin/python3" -I "$root/launch.py" "$@"
'''
PS = '''# Orche: local launcher, not a downloader or a second installer.
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'python/python.exe') -I (Join-Path $PSScriptRoot 'launch.py') @args
exit $LASTEXITCODE
'''


def _ordinary_directory_path(path: Path, *, missing_ok: bool = False) -> None:
    """Refuse static alias/reparse traversal before normalizing a selected path."""
    for part in (*reversed(path.parents), path):
        try:
            metadata = part.lstat()
        except FileNotFoundError:
            if missing_ok:
                continue
            raise
        if (getattr(metadata, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT
            or not stat.S_ISDIR(metadata.st_mode)):
            raise ValueError('Bundle roots and destination parents must be ordinary directories')


def _is_embedded_cli_package(name: str) -> bool:
    name = name.casefold()
    return name == 'codex_cli_bin' or (
        name.startswith('openai_codex_cli_bin-') and name.endswith('.dist-info')
    )


def _validate_tree(path: Path, boundary: Path, *, runtime: bool = False) -> None:
    metadata = path.lstat()
    if getattr(metadata, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError('Reparse points are not bundle inputs')
    if stat.S_ISLNK(metadata.st_mode):
        target = path.resolve(strict=True)
        if not target.is_relative_to(boundary):
            raise ValueError('Input link escapes its payload root')
        if runtime:
            name = path.name.casefold()
            parent = path.parent.name.casefold()
            linked_cli = parent in PYTHON_PACKAGE_DIRS and _is_embedded_cli_package(name)
            linked_entry = parent in {'bin', 'scripts'} and name in CLI_ENTRY_NAMES
            linked_site = name in PYTHON_PACKAGE_DIRS and target.is_dir() and any(
                _is_embedded_cli_package(child.name) for child in target.iterdir()
            )
            linked_entries = name in {'bin', 'scripts'} and target.is_dir() and any(
                child.name.casefold() in CLI_ENTRY_NAMES for child in target.iterdir()
            )
            if linked_cli or linked_entry or linked_site or linked_entries:
                raise ValueError('Linked embedded Codex CLI input is not supported; prepare an unlinked runtime')
    elif stat.S_ISDIR(metadata.st_mode):
        for child in path.iterdir():
            _validate_tree(child, boundary, runtime=runtime)
    elif not stat.S_ISREG(metadata.st_mode):
        raise ValueError('Special files are not bundle inputs')


def _copy_leaf(source, destination):
    # Preserve links observed by copy2 for final validation. Its link check and
    # open are not atomic: concurrent leaf/ancestor replacement is unsupported.
    return shutil.copy2(source, destination, follow_symlinks=False)


def _payload_inventory(root: Path, ignore=None) -> dict:
    """Exact selected bytes/link spellings; not provenance or authentication."""
    result = {}
    def walk(directory):
        children = sorted(directory.iterdir(), key=lambda path: path.name)
        ignored = set(ignore(str(directory), [p.name for p in children])) if ignore else set()
        for path in children:
            if path.name in ignored:
                continue
            name = path.relative_to(root).as_posix()
            metadata = path.lstat()
            if stat.S_ISLNK(metadata.st_mode):
                result[name] = ['link', os.readlink(path)]
            elif stat.S_ISDIR(metadata.st_mode):
                result[name] = ['directory']
                walk(path)
            elif stat.S_ISREG(metadata.st_mode):
                with path.open('rb') as stream:
                    digest = hashlib.file_digest(stream, 'sha256').hexdigest()
                result[name] = ['file', digest, bool(metadata.st_mode & 0o111)]
            else:
                raise ValueError('Unsupported runtime evidence member')
    walk(root)
    return result

def _read_runtime_evidence(path: Path, target: str) -> tuple[bytes, dict]:
    # Supplied only after independent preparation/notice qualification. Matching
    # this record does not establish authenticity, approval or legal completeness.
    raw = path.read_bytes()
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate runtime evidence field')
            result[key] = value
        return result
    data = json.loads(raw, object_pairs_hook=unique)
    if (type(data) is not dict or set(data) != {'schemaVersion', 'target', 'runtime', 'notices'}
        or type(data['schemaVersion']) is not int or data['schemaVersion'] != 1
        or data['target'] != target or type(data['runtime']) is not dict
        or not data['runtime'] or type(data['notices']) is not dict or not data['notices']):
        raise ValueError('Unsupported runtime evidence record')
    for section in ('runtime', 'notices'):
        for member in data[section].values():
            if type(member) is list and (
                member == ['directory']
                or (len(member) == 2 and member[0] == 'link' and type(member[1]) is str)
                or (len(member) == 3 and member[0] == 'file'
                    and type(member[1]) is str and re.fullmatch(r'[0-9a-f]{64}', member[1])
                    and type(member[2]) is bool)
            ):
                continue
            raise ValueError('Unsupported runtime evidence member')
    return raw, data

def _verify_runtime_evidence(runtime, notices, data, *, runtime_ignore=None):
    if _payload_inventory(runtime, runtime_ignore) != data['runtime']:
        raise ValueError('Runtime payload does not match its qualified evidence')
    if _payload_inventory(notices, _notice_ignore(notices)) != data['notices']:
        raise ValueError('Runtime notices do not match their qualified evidence')


def _historical_notice_names(relative, names):
    if relative == 'openai-codex':
        return {name for name in names if name in {'native', 'rust-dependencies'}}
    return set()


def _notice_ignore(root: Path):
    def ignore(directory, names):
        ignored = set(IGNORE(directory, names))
        ignored.update(_historical_notice_names(Path(directory).relative_to(root).as_posix(), names))
        return ignored
    return ignore



def _runtime_ignore(runtime: Path, target: str):
    def ignore_runtime(directory, names):
        ignored = set(IGNORE(directory, names))
        relative = Path(directory).relative_to(runtime)
        omissions = RUNTIME_OMISSIONS.get(target, ())
        for name in names:
            candidate = (relative / name).as_posix()
            if (candidate.casefold() if target.startswith('windows-') else candidate) in omissions:
                ignored.add(name)
        # The adapter supplies an explicitly selected external Codex executable.
        # Do not distribute the SDK wheel's separate bundled CLI or its metadata.
        if relative.name.casefold() in PYTHON_PACKAGE_DIRS:
            ignored.update(name for name in names if _is_embedded_cli_package(name))
        if relative.as_posix().casefold() in {'.', 'bin', 'scripts'}:
            ignored.update(name for name in names if name.casefold() in CLI_ENTRY_NAMES)
        return ignored

    return ignore_runtime


def build(source: Path, runtime: Path, output: Path, *, target: str, release: str, runtime_evidence: Path | None = None) -> Path:
    if target not in TARGETS or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._+-]{0,127}', release):
        raise ValueError('Explicit supported target and safe release identity required')
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    _ordinary_directory_path(output.parent, missing_ok=True)
    source, runtime = source.absolute(), runtime.absolute()
    _ordinary_directory_path(source)
    _ordinary_directory_path(runtime)
    source, runtime = source.resolve(strict=True), runtime.resolve(strict=True)
    if output.resolve(strict=False).is_relative_to(runtime) or output.resolve(strict=False).is_relative_to(source):
        raise ValueError('Output must be outside the input payloads')
    interpreter = runtime / TARGETS[target]
    if not interpreter.is_file():
        raise ValueError('Selected runtime lacks its target interpreter')
    def ignore_app(directory, names):
        ignored = set(IGNORE(directory, names))
        relative = Path(directory).relative_to(source).as_posix()
        prefix = 'scripts/distribution/notices/'
        if relative.startswith(prefix):
            ignored.update(_historical_notice_names(relative.removeprefix(prefix), names))
        return ignored

    _validate_tree(runtime, runtime, runtime=True)
    for name in APP_INPUTS:
        item = source / name
        if not item.exists():
            raise ValueError('Application input is missing: ' + name)
        _validate_tree(item, source)
    if runtime_evidence is None:
        raise ValueError('An independently qualified runtime evidence record is required')
    evidence_bytes, evidence = _read_runtime_evidence(runtime_evidence, target)
    ignore_runtime = _runtime_ignore(runtime, target)
    notices = source / 'scripts/distribution/notices'
    _verify_runtime_evidence(runtime, notices, evidence, runtime_ignore=ignore_runtime)
    # Exclusive creation: never replace another output. An interrupted build is
    # retained for diagnosis and is not launchable until the manifest is written.
    output.mkdir(parents=True, exist_ok=False)

    shutil.copytree(runtime, output / 'python', symlinks=True,
                    ignore=ignore_runtime, copy_function=_copy_leaf)
    app = output / 'app'; app.mkdir()
    for name in APP_INPUTS:
        item = source / name
        if stat.S_ISDIR(item.lstat().st_mode):
            shutil.copytree(item, app / name, symlinks=True, ignore=ignore_app, copy_function=_copy_leaf)
        else:
            _copy_leaf(item, app / name)
    _copy_leaf(source / 'scripts/distribution/launch.py', output / 'launch.py')
    if target.startswith('windows-'):
        (output / 'orche.ps1').write_text(PS, encoding='utf-8')
    else:
        entry = output / 'orche'; entry.write_text(SH, encoding='utf-8'); entry.chmod(0o755)
    _validate_tree(output, output.resolve())
    _verify_runtime_evidence(output / 'python', app / 'scripts/distribution/notices', evidence)
    with (output / 'runtime-evidence.json').open('xb') as stream:
        stream.write(evidence_bytes)
    manifest = {'schemaVersion': 2, 'product': 'Orche', 'release': release,
                'target': target, 'python': 'python/' + TARGETS[target], 'entry': 'app/install.py',
                'runtimeEvidence': 'runtime-evidence.json',
                'runtimeEvidenceSha256': hashlib.sha256(evidence_bytes).hexdigest()}
    with (output / 'bundle.json').open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2); stream.write('\n')
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--runtime-evidence', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--target', choices=tuple(TARGETS), required=True)
    parser.add_argument('--release', required=True, help='Use development for a local prototype; do not invent product versioning')
    args = parser.parse_args()
    build(args.source, args.runtime, args.output, target=args.target, release=args.release, runtime_evidence=args.runtime_evidence)


if __name__ == '__main__':
    main()
