"""Offline fixture acquisition tests; no network, installation or provider launch."""
import hashlib
import importlib.util
import io
from pathlib import Path
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("codex_fixture_acquisition", ROOT / "scripts/maintenance/fetch-codex-source-fixtures.py")
owner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(owner)


def fixture():
    payloads = {"client.py": b"# synthetic client\n", "v2_all.py": b"# synthetic models\n"}
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, data in payloads.items():
            archive.writestr("openai_codex/" + name, data)
    wheel = stream.getvalue()
    release = {"version": "1.2.3", "wheel_url": "https://files.pythonhosted.org/synthetic.whl",
               "wheel_sha256": hashlib.sha256(wheel).hexdigest(),
               "sources": {name: {"member": "openai_codex/" + name,
                                 "git_blob_sha1": hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()}
                           for name, data in payloads.items()}}
    return release, wheel, payloads


def test_exact_verified_sources_and_idempotent_reuse(tmp_path):
    release, wheel, payloads = fixture()
    first = owner.acquire(release, tmp_path, fetch=lambda _: wheel)
    before = {path: path.stat().st_mtime_ns for path in first}
    assert {path.name: path.read_bytes() for path in first} == payloads
    assert owner.acquire(release, tmp_path, fetch=lambda _: wheel) == first
    assert before == {path: path.stat().st_mtime_ns for path in first}


@pytest.mark.parametrize("fault", ["wheel", "source"])
def test_corruption_fails_before_materialization(tmp_path, fault):
    release, wheel, _ = fixture()
    if fault == "wheel":
        release["wheel_sha256"] = "0" * 64
    else:
        release["sources"]["v2_all.py"]["git_blob_sha1"] = "0" * 40
    with pytest.raises(ValueError, match="mismatch"):
        owner.acquire(release, tmp_path, fetch=lambda _: wheel)
    assert list(tmp_path.iterdir()) == []


def test_differing_existing_file_is_preserved(tmp_path):
    release, wheel, _ = fixture()
    target = tmp_path / release["version"]
    target.mkdir()
    (target / "client.py").write_bytes(b"unrelated data")
    with pytest.raises(ValueError, match="preserve"):
        owner.acquire(release, tmp_path, fetch=lambda _: wheel)
    assert (target / "client.py").read_bytes() == b"unrelated data"
    assert not (target / "v2_all.py").exists()


def test_unknown_version_refused_before_network(monkeypatch):
    monkeypatch.setattr(owner, "acquire", lambda *_a, **_kw: pytest.fail("must not acquire"))
    with pytest.raises(SystemExit) as caught:
        owner.main(["--version", "999.999.999"])
    assert caught.value.code == 2


def test_non_pypi_endpoint_is_not_fetched():
    with pytest.raises(ValueError, match="official PyPI"):
        owner.download("https://example.invalid/synthetic.whl")
