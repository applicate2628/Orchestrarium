"""Qualify conservative preservation, not historical retarget detection.

The existing uninstall owner refuses both unchanged and retargeted linked roots.
Ordinary controls distinguish that boundary from a universally failing fixture.
These checks do not establish supported linked-root removal.
"""
import hashlib
import os
import subprocess
from pathlib import Path

import pytest
from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]


def link(path, target):
    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(path), str(target)],
                                capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        path.symlink_to(target, target_is_directory=True)


@pytest.mark.parametrize("kind", ["agents", "commands"])
@pytest.mark.parametrize("apply", [False, True])
@pytest.mark.parametrize("layout", ["ordinary", "linked-unchanged", "linked-retargeted"])
def test_logical_receipt_preserves_linked_instruction_roots(tmp_path, monkeypatch, kind, apply, layout, capsys):
    linked = layout != "ordinary"
    retargeted = layout == "linked-retargeted"
    backend = load_module(ROOT / "scripts/production_installer.py", "retarget_uninstall_backend")
    codec = load_module(ROOT / "scripts/installation/ownership.py", "retarget_uninstall_codec")
    home = tmp_path / "home"
    target = home / ".claude"
    target.mkdir(parents=True)
    for variable in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(variable, str(home))
    first = tmp_path / "original" if linked else target / kind
    second = tmp_path / "foreign"
    for folder in (first, second):
        folder.mkdir()
        (folder / "example.md").write_bytes(b"same historical payload")
        (folder / "custom.md").write_bytes(b"preserve custom")
    logical = target / kind
    if linked:
        link(logical, first)
    key = ".claude/" + kind + "/example.md"
    receipt = target / codec.RECEIPT_NAME
    receipt.write_bytes(codec.encode_record(
        {key: hashlib.sha256((first / "example.md").read_bytes()).hexdigest()},
        "claude", "global", configs={},
    ))
    receipt_before = receipt.read_bytes()
    before = {path: path.read_bytes() for folder in (first, second) for path in folder.iterdir()}
    if retargeted:
        if os.name == "nt":
            assert logical.is_junction()
            logical.rmdir()
        else:
            logical.unlink()
        link(logical, second)
    arguments = ["--global", "--uninstall"] + (["--apply"] if apply else [])
    result = backend.install("claude", arguments)
    captured = capsys.readouterr()
    output = captured.out + captured.err
    if not linked:
        assert result == 0, output
        assert (first / "example.md").exists() != apply
        assert (first / "custom.md").read_bytes() == b"preserve custom"
        assert (second / "example.md").read_bytes() == b"same historical payload"
        if not apply:
            assert receipt.read_bytes() == receipt_before
        return
    assert result == 1
    assert "uninstall preserved unverified state" in output
    assert receipt.read_bytes() == receipt_before
    assert {path: path.read_bytes() for path in before} == before
    assert set(first.iterdir()) | set(second.iterdir()) == set(before)
    assert logical.resolve() == (second if retargeted else first).resolve()
