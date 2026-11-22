"""The optional Rust matcher is one exact, retained application member."""
import hashlib
import importlib.util
import json
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from synthetic_bundle_support import synthetic_record

SOURCE = Path(__file__).resolve().parents[1]
DIST = SOURCE / "scripts/distribution"
MATCHER = "native/orche-publication-match.exe"


def load(name):
    spec = importlib.util.spec_from_file_location("orche_fixture_" + name, DIST / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def payload(tmp_path):
    builder, launcher = load("build"), load("launch")
    target = "windows-x64"
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "python.exe").write_bytes(b"Synthetic interpreter, never executed")
    source_digest = tmp_path / "runtime-evidence.json"
    source_digest.write_text(json.dumps(synthetic_record(builder, runtime, DIST / "notices", target)))
    candidate = tmp_path / "matcher.exe"
    # A header fragment for classification only; there are no sections or instructions.
    content = bytearray(90)
    content[:2] = b"MZ"
    content[60:64] = (64).to_bytes(4, "little")
    content[64:68] = b"PE\0\0"
    content[68:70] = (0x8664).to_bytes(2, "little")
    content[84:86] = (240).to_bytes(2, "little")
    content[86:88] = (2).to_bytes(2, "little")
    content[88:90] = (0x20B).to_bytes(2, "little")
    candidate.write_bytes(content)
    options = dict(target=target, release="development", runtime_evidence=source_digest)
    return SimpleNamespace(builder=builder, launcher=launcher, runtime=runtime,
                           candidate=candidate, options=options,
                           digest=hashlib.sha256(content).hexdigest())


def build(payload, root, **override):
    options = dict(payload.options)
    options.update(publication_matcher=payload.candidate,
                   publication_matcher_sha256=payload.digest)
    options.update(override)
    return payload.builder.build(SOURCE, payload.runtime, root, **options)


def test_windows_matcher_survives_retention(payload, tmp_path, monkeypatch):
    launcher = payload.launcher
    monkeypatch.setattr(launcher, "current_target", lambda: "windows-x64")
    root = build(payload, tmp_path / "bundle")
    new = tmp_path / "retained"
    original = json.loads((root / "bundle.json").read_text())
    assert original["schemaVersion"] == 4
    assert original["publicationMatcher"] == {"path": MATCHER, "sha256": payload.digest}
    assert launcher.resolve_launch(root, root / "python/python.exe")[1] == root / "app/install.py"
    assert launcher.retain_bundle(root, new) == (new / "python/python.exe", new / "launch.py")
    assert (new / MATCHER).read_bytes() == payload.candidate.read_bytes()
    assert json.loads((new / "bundle.json").read_text()) == original
    assert not (new / "app/native").exists()


@pytest.mark.parametrize("damage", ["missing", "changed", "reparse", "bad-path"])
def test_declared_matcher_failure_precedes_active_launch_and_retention(payload, tmp_path, monkeypatch, damage):
    launcher = payload.launcher
    monkeypatch.setattr(launcher, "current_target", lambda: "windows-x64")
    root = build(payload, tmp_path / "bundle")
    leaf = root / MATCHER
    if damage == "missing":
        leaf.unlink()
    elif damage == "changed":
        leaf.write_bytes(leaf.read_bytes() + b"changed")
    elif damage == "reparse":
        initial = Path.lstat
        def lstat(path):
            if path == leaf.parent:
                return SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
            return initial(path)
        monkeypatch.setattr(Path, "lstat", lstat)
    else:
        data = json.loads((root / "bundle.json").read_text())
        data["publicationMatcher"]["path"] = "unqualified/orche-publication-match.exe"
        (root / "bundle.json").write_text(json.dumps(data))
    if damage != "bad-path":
        # Old registration can be identified without starting or opening its matcher.
        assert launcher._manifest(root)["publicationMatcher"]["sha256"] == payload.digest
    with pytest.raises((OSError, ValueError)):
        launcher.resolve_launch(root, root / "python/python.exe")
    new = tmp_path / "retained"
    with pytest.raises((OSError, ValueError)):
        launcher.retain_bundle(root, new)
    assert not new.exists()


@pytest.mark.parametrize("case", ["wrong-target", "wrong-digest", "missing-digest", "not-pe"])
def test_builder_refuses_unqualified_matcher_before_creating_output(payload, tmp_path, case):
    options = {}
    if case == "wrong-target":
        options["target"] = "linux-x64"
    elif case == "wrong-digest":
        options["publication_matcher_sha256"] = "0" * 64
    elif case == "missing-digest":
        options["publication_matcher_sha256"] = None
    else:
        payload.candidate.write_bytes(b"not a native image")
        options["publication_matcher_sha256"] = hashlib.sha256(b"not a native image").hexdigest()
    new = tmp_path / "bundle"
    with pytest.raises(ValueError, match="[Mm]atcher"):
        build(payload, new, **options)
    assert not new.exists()


def test_version_three_does_not_adopt_an_unrecorded_matcher(payload, tmp_path, monkeypatch):
    launcher = payload.launcher
    monkeypatch.setattr(launcher, "current_target", lambda: "windows-x64")
    old = payload.builder.build(SOURCE, payload.runtime, tmp_path / "old", **payload.options)
    leaf = old / MATCHER
    leaf.parent.mkdir()
    leaf.write_bytes(payload.candidate.read_bytes())
    assert launcher._manifest(old)["schemaVersion"] == 3
    assert launcher.resolve_launch(old, old / "python/python.exe")[1] == old / "app/install.py"
    new = tmp_path / "retained"
    launcher.retain_bundle(old, new)
    assert launcher._manifest(new)["schemaVersion"] == 3
    assert not (new / MATCHER).exists()


def test_publication_matcher_command_line_uses_same_qualified_builder(payload, tmp_path, monkeypatch):
    import sys

    output = tmp_path / "command-line"
    monkeypatch.setattr(sys, "argv", [
        str(DIST / "build.py"), "--source", str(SOURCE),
        "--runtime", str(payload.runtime), "--runtime-evidence",
        str(payload.options["runtime_evidence"]), "--target", "windows-x64",
        "--release", "development", "--output", str(output),
        "--publication-matcher", str(payload.candidate),
        "--publication-matcher-sha256", payload.digest,
    ])
    payload.builder.main()
    assert (output / MATCHER).read_bytes() == payload.candidate.read_bytes()


def test_wrong_pe_architecture_cannot_be_admitted_by_its_actual_digest(payload, tmp_path):
    raw = bytearray(payload.candidate.read_bytes())
    raw[68:70] = (0xAA64).to_bytes(2, "little")
    payload.candidate.write_bytes(raw)
    output = tmp_path / "bundle"
    with pytest.raises(ValueError, match="Windows x64"):
        build(payload, output, publication_matcher_sha256=hashlib.sha256(raw).hexdigest())
    assert not output.exists()
