"""Assemble a local Orche bundle; no downloads, installation, signing or activation.

Runtime input must already have verified provenance and its required dependencies.
Inputs must remain quiescent and the destination-parent hierarchy exclusively
controlled throughout assembly/retention/launch. This local builder is not a
sandbox against a hostile concurrent writer and does not authenticate a release.
"""
from __future__ import annotations

import argparse
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


def _validate_tree(path: Path, boundary: Path) -> None:
    metadata = path.lstat()
    if getattr(metadata, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT:
        raise ValueError('Reparse points are not bundle inputs')
    if stat.S_ISLNK(metadata.st_mode):
        if not path.resolve(strict=True).is_relative_to(boundary):
            raise ValueError('Input link escapes its payload root')
    elif stat.S_ISDIR(metadata.st_mode):
        # Classify a directory before traversal; never recurse into a reparse root.
        for child in path.iterdir():
            _validate_tree(child, boundary)
    elif not stat.S_ISREG(metadata.st_mode):
        raise ValueError('Special files are not bundle inputs')


def _copy_leaf(source, destination):
    # Preserve links observed by copy2 for final validation. Its link check and
    # open are not atomic: concurrent leaf/ancestor replacement is unsupported.
    return shutil.copy2(source, destination, follow_symlinks=False)


def build(source: Path, runtime: Path, output: Path, *, target: str, release: str) -> Path:
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
    _validate_tree(runtime, runtime)
    for name in APP_INPUTS:
        item = source / name
        if not item.exists():
            raise ValueError('Application input is missing: ' + name)
        _validate_tree(item, source)
    # Exclusive creation: never replace another output. An interrupted build is
    # retained for diagnosis and is not launchable until the manifest is written.
    output.mkdir(parents=True, exist_ok=False)
    shutil.copytree(runtime, output / 'python', symlinks=True, ignore=IGNORE, copy_function=_copy_leaf)
    app = output / 'app'; app.mkdir()
    for name in APP_INPUTS:
        item = source / name
        if stat.S_ISDIR(item.lstat().st_mode):
            shutil.copytree(item, app / name, symlinks=True, ignore=IGNORE, copy_function=_copy_leaf)
        else:
            _copy_leaf(item, app / name)
    _copy_leaf(source / 'scripts/distribution/launch.py', output / 'launch.py')
    if target.startswith('windows-'):
        (output / 'orche.ps1').write_text(PS, encoding='utf-8')
    else:
        entry = output / 'orche'; entry.write_text(SH, encoding='utf-8'); entry.chmod(0o755)
    _validate_tree(output, output.resolve())
    manifest = {'schemaVersion': 1, 'product': 'Orche', 'release': release,
                'target': target, 'python': 'python/' + TARGETS[target], 'entry': 'app/install.py'}
    with (output / 'bundle.json').open('x', encoding='utf-8') as stream:
        json.dump(manifest, stream, indent=2); stream.write('\n')
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--runtime', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--target', choices=tuple(TARGETS), required=True)
    parser.add_argument('--release', required=True, help='Use development for a local prototype; do not invent product versioning')
    args = parser.parse_args()
    build(args.source, args.runtime, args.output, target=args.target, release=args.release)


if __name__ == '__main__':
    main()
