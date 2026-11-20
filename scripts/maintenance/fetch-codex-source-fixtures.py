#!/usr/bin/env python3
"""Acquire reviewed Codex API source fixtures, without installing or running SDKs."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import urllib.parse
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tests/fixtures/codex-sdk-sources.json"


def download(url: str) -> bytes:
    if urllib.parse.urlparse(url).scheme != "https" or urllib.parse.urlparse(url).hostname != "files.pythonhosted.org":
        raise ValueError("expected an official PyPI wheel URL")
    with urllib.request.urlopen(url) as response:
        return response.read()


def acquire(release: dict, destination: Path, *, fetch=download) -> list[Path]:
    version = release["version"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", version):
        raise ValueError("invalid reviewed release directory")
    sources = release["sources"]
    if set(sources) != {"client.py", "v2_all.py"}:
        raise ValueError("expected the two reviewed public source files")
    raw = fetch(release["wheel_url"])
    if hashlib.sha256(raw).hexdigest() != release["wheel_sha256"]:
        raise ValueError("wheel SHA256 mismatch")
    verified = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for name, record in sources.items():
            payload = archive.read(record["member"])
            blob = hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest()
            if blob != record["git_blob_sha1"]:
                raise ValueError(f"source Git blob mismatch: {name}")
            verified[name] = payload
    target = destination / version
    for parent in (destination, target):
        if parent.is_symlink():
            raise ValueError("fixture directory must not redirect writes")
    for name, payload in verified.items():
        path = target / name
        if path.is_symlink() or (path.exists() and path.read_bytes() != payload):
            raise ValueError(f"preserve differing existing fixture: {name}")
    target.mkdir(parents=True, exist_ok=True)
    for name, payload in verified.items():
        path = target / name
        if not path.exists():
            with path.open("xb") as handle:
                handle.write(payload)
    return [target / name for name in verified]


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="append", help="reviewed version; repeat to select several (default: all)")
    args = parser.parse_args(argv)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if manifest["schema_version"] != 1:
        parser.error("unsupported source fixture manifest")
    releases = manifest["releases"]
    selected = set(args.version or [release["version"] for release in releases])
    unknown = selected - {release["version"] for release in releases}
    if unknown:
        parser.error("version not present in reviewed source evidence: " + ", ".join(sorted(unknown)))
    for release in releases:
        if release["version"] in selected:
            paths = acquire(release, ROOT / ".scratch/sdk-api-fixture")
            print(f"Verified Codex {release['version']}: " + ", ".join(path.name for path in paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
