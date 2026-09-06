"""Historic source pins must survive the operator's checkout preferences."""
from __future__ import annotations

import io
import subprocess
import tarfile
from pathlib import Path

import pytest

from tests.fixtures.git_history import archive_revision


@pytest.mark.parametrize("autocrlf,eol", [("true", "crlf"), ("false", "crlf"), ("input", "lf")])
def test_history_archive_does_not_rewrite_lf_or_accepted_prior_crlf(tmp_path: Path, autocrlf: str, eol: str) -> None:
    def git(*args: str) -> bytes:
        return subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True, timeout=30).stdout

    git("init", "-q")
    git("config", "user.name", "History fixture")
    git("config", "user.email", "history-fixture@example.invalid")
    git("config", "core.autocrlf", "false")
    (tmp_path / ".gitattributes").write_bytes(b"legacy.txt -text\n")
    contents = {"policy.json": b'{"preserve":"source"}\n', "legacy.txt": b"accepted\r\nprior\r\n"}
    for name, content in contents.items():
        (tmp_path / name).write_bytes(content)
    git("add", ".")
    git("commit", "-qm", "Exact historical bytes")
    git("config", "core.autocrlf", autocrlf)
    git("config", "core.eol", eol)
    with tarfile.open(fileobj=io.BytesIO(archive_revision(tmp_path, "HEAD")), mode="r:") as archive:
        for name, expected in contents.items():
            assert archive.extractfile(name).read() == expected, name
    # Asking for a single subtree/file must retain the same behavior.
    with tarfile.open(fileobj=io.BytesIO(archive_revision(tmp_path, "HEAD", "policy.json")), mode="r:") as archive:
        assert archive.extractfile("policy.json").read() == contents["policy.json"]
