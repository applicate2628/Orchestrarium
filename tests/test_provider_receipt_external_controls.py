"""External hook controls retain their publication and namespace authority."""
import os
from pathlib import Path

import pytest

from _module_loading_support import load_module
from _filesystem_fixture_support import _make_file_symlink, _make_directory_junction

ROOT = Path(__file__).resolve().parents[1]
installer = load_module(ROOT / "scripts/production_installer.py", "external_control_receipt_backend")
codec = load_module(ROOT / "scripts/installation/ownership.py", "external_control_receipt_codec")


@pytest.mark.parametrize("case", [
    "selected", "neighbor", "document", "unadmitted", "wrong-owner", "bytes",
    "replacement", "late-bytes", "inventory-gone", "leaf-before", "leaf-during",
    "leaf-same-target", "intermediate-before", "intermediate-during", "junction-during",
])
def test_provider_receipt_excludes_only_exact_current_admitted_controls(tmp_path, monkeypatch, case):
    home = tmp_path / "home"
    target = home / ".codex"
    target.mkdir(parents=True)
    outside = tmp_path / "shared"
    outside.mkdir()
    storage = outside / "hooks.json"
    storage.write_bytes(b'{"hooks": {}}\n')
    inventory = outside / "codex-hook-inventory.json"
    inventory.write_bytes(b'{"owned": true}\n')
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "hooks.json").write_bytes(b'{"foreign": true}\n')
    (foreign / inventory.name).write_bytes(b'{"foreignInventory": true}\n')
    intermediate = case.startswith(("intermediate-", "junction-"))
    route = tmp_path / "route"
    if intermediate:
        if case.startswith("junction-"):
            _make_directory_junction(route, outside)
        else:
            route.symlink_to(outside, target_is_directory=True)
    registration = target / "hooks.json"
    _make_file_symlink(registration, (route if intermediate else outside) / "hooks.json")
    initial_link = installer._InstallTransaction._capture_node(registration)
    receipt = target / codec.RECEIPT_NAME
    paths = [receipt, registration, storage]
    if case != "unadmitted":
        paths.append(inventory)
    if case in {"neighbor", "document"}:
        neighbor = outside / ("AGENTS.md" if case == "document" else "foreign.txt")
        neighbor.write_bytes(b"foreign neighbor\n")
        paths.append(neighbor)
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(storage.read_bytes())
    transaction = installer._InstallTransaction(paths, enabled=True,
        link_object_paths=(registration,))
    owner = installer._CreateOnlyMutablePath(home, transaction, dry_run=False)
    health = installer._hook_health_module(ROOT)
    monkeypatch.setattr(installer, "_capture_provider_configs", lambda *args: {})
    observed_foreign = {}
    create = owner.create_file

    def change_pointer():
        pointer = route if intermediate else registration
        original = transaction._capture_node(pointer)
        raw_target = os.readlink(pointer)
        retained = tmp_path / "retained-pointer"
        os.rename(pointer, retained)
        if intermediate:
            if case.startswith("junction-"):
                _make_directory_junction(pointer, foreign)
            else:
                pointer.symlink_to(foreign, target_is_directory=True)
        else:
            _make_file_symlink(pointer, Path(raw_target) if case == "leaf-same-target" else foreign / "hooks.json")
        assert transaction._point_matches(retained, original, check_file_content=True)
        observed_foreign[pointer] = transaction._capture_node(pointer)

    def create_then_modify(relative, payload, **keywords):
        result = create(relative, payload, **keywords)
        if relative == receipt.relative_to(home):
            if case == "late-bytes":
                inventory.write_bytes(b"foreign inventory\n")
                observed_foreign[inventory] = transaction._capture_node(inventory)
            elif case.endswith("-during") or case == "leaf-same-target":
                change_pointer()
        return result

    monkeypatch.setattr(owner, "create_file", create_then_modify)

    def record():
        with transaction:
            # Same existing authority factory used immediately after real hook
            # publication; its old witnesses are retained across the fault.
            authority = health._inventory_authority(registration, inventory, for_write=False)
            hook_owner = owner
            if case == "wrong-owner":
                hook_owner = installer._CreateOnlyMutablePath(home,
                    installer._InstallTransaction([], enabled=False), dry_run=False)
            if case == "bytes":
                storage.write_bytes(b"foreign registration\n")
                observed_foreign[storage] = transaction._capture_node(storage)
            elif case == "replacement":
                os.rename(storage, tmp_path / "retained-registration.json")
                os.rename(replacement, storage)
                observed_foreign[storage] = transaction._capture_node(storage)
            elif case == "inventory-gone":
                os.rename(inventory, tmp_path / "retained-inventory.json")
            elif case.endswith("-before"):
                change_pointer()
            installer._record_provider_install(ROOT, "codex", "global", target, home,
                transaction, owner, None, {}, target / "AGENTS.md", None,
                registration, home / ".agents/skills/lead", True,
                hook_control=(hook_owner, health, authority))
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
        if case in {"neighbor", "document"}:
            assert "external mutation image" in str(primary)
            assert neighbor.read_bytes() == b"foreign neighbor\n"
        elif case == "unadmitted":
            assert "missing admitted mutation image" in str(primary)
        elif case == "wrong-owner":
            assert "hook control owner" in str(primary)
        else:
            assert primary.stable_id in {"E_PROVIDER_RECEIPT_DRIFT", "E_HOOK_INVENTORY_TARGET_INVALID"}
            for path, node in observed_foreign.items():
                assert transaction._point_matches(path, node, check_file_content=True)
            if isinstance(caught.value, installer._InstallFailure) and caught.value.members:
                assert caught.value.recovery_path is not None
        assert not receipt.exists()
    if not case.startswith("leaf-"):
        assert transaction._point_matches(registration, initial_link, check_file_content=True)
    assert (foreign / "hooks.json").read_bytes() == b'{"foreign": true}\n'
    assert (foreign / inventory.name).read_bytes() == b'{"foreignInventory": true}\n'
