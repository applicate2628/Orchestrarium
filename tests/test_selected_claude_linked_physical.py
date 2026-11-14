"""Physical selected-instruction receiving; no live profiles or models."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import pytest

from test_provider_prompt_projections import _load_installer, ROOT


def _link(path, target):
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(path), str(target)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
    else:
        path.symlink_to(target, target_is_directory=True)


@pytest.mark.parametrize("kind", ["agents", "commands"])
@pytest.mark.parametrize("mode", ["success", "rollback", "receipt-rollback", "stale", "wrong-owner", "source-drift"])
@pytest.mark.parametrize("selection", ["individual", "receipt"])
def test_selected_linked_instruction_preserves_logical_receipt_and_neighbors(
    tmp_path, kind, mode, selection,
):
    installer = _load_installer()
    home = tmp_path / "home"
    target = home / ".claude"
    target.mkdir(parents=True)
    physical = tmp_path / "physical"
    physical.mkdir()
    _link(target / kind, physical)
    source = tmp_path / "source"
    (source / kind).mkdir(parents=True)
    key = kind + "/example.md"
    (source / key).write_bytes(b"new instruction\n")
    leaf = physical / "example.md"
    leaf.write_bytes(b"old instruction\n")
    neighbor = physical / "custom.md"
    neighbor.write_bytes(b"preserve user content\n")
    receipt = target / installer._PROVIDER_RECEIPT_NAME
    if selection == "receipt":
        outcome = installer._ReceiptOutcome(".claude/" + key, "file", None, leaf.read_bytes(), intent="create")
        plan = installer._plan_receipt_changes(None, "claude", "global", (outcome,), installer._markdown_document_context)
        receipt.write_bytes(installer._serialize_receipt_delta(None, plan))
    receipt_before = receipt.read_bytes() if receipt.exists() else None
    resolved, authority = installer._resolve_global_claude_linked_subroot(
        ROOT, target, "global", kind,
    )
    transaction = installer._InstallTransaction(
        [leaf, receipt], enabled=True, track_fresh_files=True,
    )
    digest = hashlib.sha256(leaf.read_bytes()).hexdigest()
    if mode == "stale":
        digest = "0" * 64

    def operation():
        with transaction:
            logical_owner = installer._CreateOnlyMutablePath(home, transaction, dry_run=False)
            physical_owner = installer._CreateOnlyMutablePath(
                resolved, transaction, dry_run=False, linked_authority=authority,
            )
            if selection == "receipt":
                receipt_digest = hashlib.sha256(receipt_before).hexdigest()
                if mode == "stale":
                    receipt_digest = "0" * 64
                batch = installer._prepare_receipted_claude_instructions(
                    receipt_digest, source, target, "global", logical_owner, (kind,),
                    instruction_owners={kind: physical_owner},
                )
            else:
                batch = installer._prepare_selected_claude_instructions(
                    {key: digest}, source, target, "global", logical_owner,
                    instruction_owners={kind: physical_owner},
                )
            if mode == "source-drift":
                (source / key).write_bytes(b"changed source")
            selected_owner = logical_owner if mode == "wrong-owner" else physical_owner
            installer._apply_selected_replacement(
                batch, key, (source / key,), leaf, selected_owner, False,
            )
            if mode == "rollback":
                raise RuntimeError("injected late failure")
            installer._record_selected_provider_receipt(batch)
            if mode == "receipt-rollback":
                assert leaf.read_bytes() == b"new instruction\n"
                written_receipt = receipt.read_bytes()
                assert written_receipt != receipt_before
                assert json.loads(written_receipt)["files"][".claude/" + key] == hashlib.sha256(leaf.read_bytes()).hexdigest()
                raise RuntimeError("injected failure after receipt replacement")
            transaction.commit()

    if mode == "success":
        operation()
        assert leaf.read_bytes() == b"new instruction\n"
        data = json.loads(receipt.read_bytes())
        assert data["files"][".claude/" + key] == hashlib.sha256(leaf.read_bytes()).hexdigest()
    else:
        error = RuntimeError if mode in {"rollback", "receipt-rollback"} else ValueError
        message = "^injected failure after receipt replacement$" if mode == "receipt-rollback" else None
        with pytest.raises(error, match=message):
            operation()
        assert leaf.read_bytes() == b"old instruction\n"
        assert (receipt.read_bytes() if receipt.exists() else None) == receipt_before
    assert neighbor.read_bytes() == b"preserve user content\n"
    assert (target / kind).resolve() == physical.resolve()


def test_public_linked_instruction_batch_receives_both_roots(tmp_path, monkeypatch):
    installer = _load_installer()
    home = tmp_path / "home"
    home.mkdir()
    for variable in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(variable, str(home))
    assert installer.install("claude", ["--global", "--no-hypothesis-hook"]) == 0
    target = home / ".claude"
    arguments = ["--global", "--no-hypothesis-hook"]
    selected = []
    for kind in ("agents", "commands"):
        physical = tmp_path / ("physical-" + kind)
        (target / kind).rename(physical)
        _link(target / kind, physical)
        source = next(iter(sorted((ROOT / "src.claude" / kind).glob("*.md"))))
        path = physical / source.name
        expected = path.read_bytes()
        path.write_bytes(b"explicitly selected synthetic authored instruction\n")
        arguments += ["--replace-claude-instruction",
                      kind + "/" + source.name + "=" + hashlib.sha256(path.read_bytes()).hexdigest()]
        neighbor = physical / "custom-neighbor.md"
        neighbor.write_bytes(b"preserve unrelated custom instruction\n")
        selected.append((kind, physical, path, expected, neighbor))
    assert installer.install("claude", arguments) == 0
    receipt = json.loads((target / installer._PROVIDER_RECEIPT_NAME).read_bytes())
    for kind, physical, path, expected, neighbor in selected:
        assert path.read_bytes() == expected
        assert neighbor.read_bytes() == b"preserve unrelated custom instruction\n"
        assert (target / kind).resolve() == physical.resolve()
        assert receipt["files"][".claude/" + kind + "/" + path.name] == hashlib.sha256(expected).hexdigest()
    assert installer.install("claude", arguments) == 1
    for _kind, _physical, path, expected, neighbor in selected:
        assert path.read_bytes() == expected
        assert neighbor.read_bytes() == b"preserve unrelated custom instruction\n"


@pytest.mark.parametrize("kind", ["agents", "commands"])
@pytest.mark.parametrize("when", ["before-write", "after-write"])
def test_linked_selected_retarget_never_writes_foreign_target(tmp_path, kind, when):
    installer = _load_installer()
    home = tmp_path / "home"
    target = home / ".claude"
    target.mkdir(parents=True)
    original, foreign = tmp_path / "original", tmp_path / "foreign"
    original.mkdir()
    foreign.mkdir()
    logical = target / kind
    _link(logical, original)
    source = tmp_path / "source"
    (source / kind).mkdir(parents=True)
    key = kind + "/example.md"
    (source / key).write_bytes(b"new instruction")
    leaf = original / "example.md"
    leaf.write_bytes(b"original instruction")
    foreign_leaf = foreign / "example.md"
    foreign_leaf.write_bytes(b"foreign bytes")
    receipt = target / installer._PROVIDER_RECEIPT_NAME
    resolved, authority = installer._resolve_global_claude_linked_subroot(ROOT, target, "global", kind)
    transaction = installer._InstallTransaction([leaf, receipt], enabled=True, track_fresh_files=True)

    def retarget():
        if os.name == "nt":
            assert logical.is_junction()
            logical.rmdir()  # Remove this fixture's junction object, never its target.
        else:
            assert logical.is_symlink()
            logical.unlink()
        _link(logical, foreign)

    with pytest.raises((ValueError, RuntimeError)):
        with transaction:
            logical_owner = installer._CreateOnlyMutablePath(home, transaction, dry_run=False)
            physical_owner = installer._CreateOnlyMutablePath(
                resolved, transaction, dry_run=False, linked_authority=authority,
            )
            batch = installer._prepare_selected_claude_instructions(
                {key: hashlib.sha256(leaf.read_bytes()).hexdigest()}, source, target,
                "global", logical_owner, instruction_owners={kind: physical_owner},
            )
            if when == "before-write":
                retarget()
            installer._apply_selected_replacement(
                batch, key, (source / key,), leaf, physical_owner, False,
            )
            if when == "after-write":
                retarget()
            installer._record_selected_provider_receipt(batch)
            transaction.commit()
    assert foreign_leaf.read_bytes() == b"foreign bytes"
    assert not receipt.exists()
    assert logical.resolve() == foreign.resolve()
    if when == "before-write":
        assert leaf.read_bytes() == b"original instruction"
    else:
        # Changed link authority may prevent inverse settlement; never call it successful rollback.
        assert leaf.read_bytes() == b"new instruction"
