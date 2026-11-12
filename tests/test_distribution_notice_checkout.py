"""Qualified notice bytes must survive Git even with automatic CRLF enabled."""
from pathlib import Path
import shutil
import subprocess
import pytest

ROOT = Path(__file__).resolve().parents[1]

@pytest.mark.parametrize("payload", [b"first\nsecond\n", b"first\r\nsecond\r\n"])
def test_notice_index_preserves_exact_bytes(tmp_path, payload):
    git = shutil.which("git")
    if git is None:
        pytest.skip("Git required for checkout policy receiving")
    def run(*args):
        return subprocess.run([git,"-c","core.autocrlf=true",*args],cwd=tmp_path,
                              capture_output=True,check=True).stdout
    run("init")
    (tmp_path/".gitattributes").write_bytes((ROOT/".gitattributes").read_bytes())
    relative = "scripts/distribution/notices/fixture/LICENSE"
    notice = tmp_path/relative
    notice.parent.mkdir(parents=True)
    notice.write_bytes(payload)
    run("add",".gitattributes",relative)
    assert run("show",":"+relative) == payload
    notice.unlink()
    run("checkout-index","--",relative)
    assert notice.read_bytes() == payload
