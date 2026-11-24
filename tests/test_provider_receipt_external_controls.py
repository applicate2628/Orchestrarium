"""External control leaves stay distinct from provider payload ownership."""
import os
from pathlib import Path

import pytest

from _module_loading_support import load_module
from _filesystem_fixture_support import _make_file_symlink

ROOT = Path(__file__).resolve().parents[1]
installer = load_module(ROOT / "scripts/production_installer.py", "external_control_receipt_backend")
codec = load_module(ROOT / "scripts/installation/ownership.py", "external_control_receipt_codec")


@pytest.mark.parametrize("case", [
    "selected", "neighbor", "unadmitted", "directory", "bytes",
    "replacement", "absent-drift", "late-bytes",
])
def test_provider_receipt_excludes_only_exact_current_admitted_controls(tmp_path, monkeypatch, case):
    home = tmp_path / "home"
    target = home / ".codex"
    target.mkdir(parents=True)
    outside = tmp_path / "shared"
    outside.mkdir()
    registration = target / "hooks.json"
    storage = outside / "hooks.json"
    storage.write_bytes(b'{"hooks": {}}\n')
    _make_file_symlink(registration, storage)
    raw_target = os.readlink(registration)
    inventory = outside / "codex-hook-inventory.json"
    if case != "absent-drift":
        inventory.write_bytes(b'{"owned": true}\n')
    receipt = target / codec.RECEIPT_NAME
    paths = [receipt, registration, storage, inventory]
    controls = [storage, inventory]
    if case in {"neighbor", "directory"}:
        neighbor = outside / "foreign.txt"
        neighbor.write_bytes(b"foreign neighbor\n")
        paths.append(neighbor if case == "neighbor" else outside)
        if case == "directory":
            controls = [outside]
    elif case == "unadmitted":
        extra = tmp_path / "unselected.json"
        extra.write_bytes(b"{}\n")
        controls.append(extra)
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(storage.read_bytes())
    transaction = installer._InstallTransaction(paths, enabled=True,
        link_object_paths=(registration,))
    owner = installer._CreateOnlyMutablePath(home, transaction, dry_run=False)
    monkeypatch.setattr(installer, "_capture_provider_configs", lambda *args: {})
    observed_foreign = {}
    create = owner.create_file

    def create_then_modify(relative, payload, **keywords):
        result = create(relative, payload, **keywords)
        if case == "late-bytes" and relative == receipt.relative_to(home):
            inventory.write_bytes(b"foreign inventory\n")
            observed_foreign[inventory] = transaction._capture_node(inventory)
        return result

    monkeypatch.setattr(owner, "create_file", create_then_modify)

    def record():
        with transaction:
            if case == "bytes":
                storage.write_bytes(b"foreign registration\n")
                observed_foreign[storage] = transaction._capture_node(storage)
            elif case == "replacement":
                os.rename(storage, tmp_path / "retained-registration.json")
                os.rename(replacement, storage)
                observed_foreign[storage] = transaction._capture_node(storage)
            elif case == "absent-drift":
                inventory.write_bytes(b"foreign absent slot\n")
                observed_foreign[inventory] = transaction._capture_node(inventory)
            installer._record_provider_install(ROOT, "codex", "global", target, home,
                transaction, owner, None, {}, target / "AGENTS.md", None,
                registration, home / ".agents/skills/lead", True,
                control_paths=tuple(controls))
            transaction.commit()

    if case == "selected":
        record()
        received = codec.decode_record(receipt.read_bytes(), "codex", "global")
        assert received["files"] == {}
        assert received.get("directories", []) == []
        assert storage.read_bytes() == b'{"hooks": {}}\n'
        assert inventory.read_bytes() == b'{"owned": true}\n'
    else:
        with pytest.raises((ValueError, installer._InstallFailure)) as caught:
            record()
        primary = caught.value.cause if isinstance(caught.value, installer._InstallFailure) and caught.value.cause else caught.value
        if case in {"neighbor", "directory"}:
            assert "external mutation image" in str(primary)
            assert neighbor.read_bytes() == b"foreign neighbor\n"
        elif case == "unadmitted":
            assert "missing admitted mutation image" in str(primary)
        else:
            assert isinstance(primary, installer._InstallFailure)
            assert primary.stable_id == "E_PROVIDER_RECEIPT_DRIFT"
            assert caught.value.recovery_path is not None
            for path, node in observed_foreign.items():
                assert transaction._point_matches(path, node, check_file_content=True)
        assert not receipt.exists()
    assert registration.is_symlink()
    assert os.readlink(registration) == raw_target
