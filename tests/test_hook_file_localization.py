"""Actual leaf-link transaction fixtures; no installed user configuration touched."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("hook_localization_backend", ROOT / "scripts/production_installer.py")
PI = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PI
SPEC.loader.exec_module(PI)


def fixture(tmp_path):
    anchor = tmp_path / "home"
    target = anchor / ".codex"
    target.mkdir(parents=True)
    shared = tmp_path / "shared"
    shared.mkdir()
    marker, script, event, matcher = next(iter(PI._hook_specs("codex", anchor / ".agents/skills/lead")))
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("# synthetic owned script, never executed\n")
    helper = PI._load_module_from_path("localization_hook_helper", ROOT / "scripts/install-hypothesis-hook.py")
    host = "windows" if PI.os.name == "nt" else "posix"
    hook_target = helper.resolve_hook_target(str(script), host, "codex")
    entry = helper.build_codex_entry(hook_target, host, event, matcher)
    data = {"hooks": {event: [entry]}, "foreign": {"keep": [1, 2]}}
    payload = (json.dumps(data, indent=3) + "\n").encode()
    source = shared / "hooks.json"
    source.write_bytes(payload)
    link = target / "hooks.json"
    link.symlink_to(source)
    owned = dict(event=event, marker=marker, context={k:v for k,v in entry.items() if k != "hooks"}, handler=entry["hooks"][0])
    ownership = PI._provider_ownership_module(ROOT)
    receipt = target / ownership.RECEIPT_NAME
    receipt.write_bytes(ownership.encode_record({script.relative_to(anchor).as_posix(): hashlib.sha256(script.read_bytes()).hexdigest()}, "codex", "global", configs={".codex/hooks.json": dict(kind="hooks", handlers=[owned], agentAdded=False)}))
    return anchor, source, link, receipt, payload


def test_localize_preserves_foreign_source_and_link_backup(tmp_path):
    anchor, source, link, receipt, payload = fixture(tmp_path)
    original_target = link.readlink()
    original_identity = link.lstat().st_ino
    result = PI._localize_hook_file(ROOT, "codex", anchor, "global", apply=True)
    assert result["status"] == "localized"
    assert not link.is_symlink() and link.read_bytes() == payload
    backup = Path(result["link_backup"])
    assert backup.is_symlink() and backup.readlink() == original_target
    assert backup.lstat().st_ino == original_identity
    assert source.read_bytes() == payload


def test_preview_has_no_effects(tmp_path):
    anchor, source, link, receipt, payload = fixture(tmp_path)
    before = sorted(str(p) for p in tmp_path.rglob("*"))
    assert PI._localize_hook_file(ROOT, "codex", anchor, "global", apply=False)["status"] == "preview"
    assert before == sorted(str(p) for p in tmp_path.rglob("*"))
    assert link.is_symlink() and source.read_bytes() == payload


def test_unowned_receipt_refused(tmp_path):
    anchor, source, link, receipt, payload = fixture(tmp_path)
    receipt.unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        PI._localize_hook_file(ROOT, "codex", anchor, "global", apply=True)
    assert link.is_symlink() and source.read_bytes() == payload


def test_failure_after_link_publication_restores_link_and_sidecar(tmp_path, monkeypatch):
    anchor, source, link, receipt, payload = fixture(tmp_path)
    inventory = link.parent / PI.CODEX_HOOK_INVENTORY
    inventory.write_bytes(b"old local inventory")
    inventory_identity = inventory.lstat().st_ino
    original = link.readlink()
    real = PI._CreateOnlyMutablePath.retain_path
    def fail_after(owner, *args, **kwargs):
        result = real(owner, *args, **kwargs)
        raise RuntimeError("injected sidecar failure")
    monkeypatch.setattr(PI._CreateOnlyMutablePath, "retain_path", fail_after)
    with pytest.raises(RuntimeError, match="injected sidecar failure"):
        PI._localize_hook_file(ROOT, "codex", anchor, "global", apply=True)
    assert link.is_symlink() and link.readlink() == original
    assert source.read_bytes() == payload
    assert inventory.read_bytes() == b"old local inventory"
    assert inventory.lstat().st_ino == inventory_identity


def test_inventory_same_byte_replacement_after_admission_is_not_adopted(tmp_path, monkeypatch):
    anchor, source, link, receipt, payload = fixture(tmp_path)
    inventory = link.parent / PI.CODEX_HOOK_INVENTORY
    inventory.write_bytes(b"old local inventory")
    original = link.readlink()
    inventory_identity = inventory.lstat().st_ino
    retained = inventory.with_name(inventory.name + ".user-prior")
    replacement_identity = None
    real = PI._apply_hook_file_localization

    def replace_after_admission(plan, transaction, owner):
        nonlocal replacement_identity
        inventory.rename(retained)
        inventory.write_bytes(b"old local inventory")
        replacement_identity = inventory.lstat().st_ino
        return real(plan, transaction, owner)

    monkeypatch.setattr(PI, "_apply_hook_file_localization", replace_after_admission)
    with pytest.raises((ValueError, PI._InstallFailure)):
        PI._localize_hook_file(ROOT, "codex", anchor, "global", apply=True)
    assert link.is_symlink() and link.readlink() == original
    assert source.read_bytes() == payload
    assert inventory.read_bytes() == b"old local inventory"
    assert inventory.lstat().st_ino == replacement_identity != inventory_identity
    assert retained.read_bytes() == b"old local inventory"
    assert retained.lstat().st_ino == inventory_identity


def test_shared_source_drift_refused_before_placement(tmp_path, monkeypatch):
    anchor, source, link, receipt, payload = fixture(tmp_path)
    real = PI._apply_hook_file_localization
    def drift(plan, transaction, owner):
        source.write_bytes(b"later user edit")
        return real(plan, transaction, owner)
    monkeypatch.setattr(PI, "_apply_hook_file_localization", drift)
    with pytest.raises(PI._InstallFailure, match="E_HOOK_LOCALIZATION_DRIFT"):
        PI._localize_hook_file(ROOT, "codex", anchor, "global", apply=True)
    assert link.is_symlink() and source.read_bytes() == b"later user edit"


def test_modified_owned_script_refused(tmp_path):
    anchor, source, link, receipt, payload = fixture(tmp_path)
    record = json.loads(receipt.read_bytes())
    script = anchor / next(iter(record["files"]))
    script.write_bytes(b"later script")
    with pytest.raises(ValueError, match="managed script digest"):
        PI._localize_hook_file(ROOT, "codex", anchor, "global", apply=True)
    assert link.is_symlink() and source.read_bytes() == payload


def test_local_sidecar_retained_shared_sidecar_untouched(tmp_path):
    anchor, source, link, receipt, payload = fixture(tmp_path)
    inventory = link.parent / PI.CODEX_HOOK_INVENTORY
    inventory.write_bytes(b"local stale")
    shared_inventory = source.parent / PI.CODEX_HOOK_INVENTORY
    shared_inventory.write_bytes(b"shared unchanged")
    PI._localize_hook_file(ROOT, "codex", anchor, "global", apply=True)
    assert not inventory.exists()
    assert inventory.with_name(inventory.name + ".orche-localization-prior").read_bytes() == b"local stale"
    assert shared_inventory.read_bytes() == b"shared unchanged"


def test_option_is_normal_install_phase_not_separate_apply_command():
    args = PI._parser("codex").parse_args(["--localize-hook-file", "--dry-run"])
    assert args.localize_hook_file and not args.apply
    import inspect
    source = inspect.getsource(PI.install)
    assert source.index("_apply_hook_file_localization(hook_localization, transaction, create_only)") < source.index("config_before =")


def test_later_local_edit_is_not_overwritten_by_rollback(tmp_path, monkeypatch):
    anchor, source, link, receipt, payload = fixture(tmp_path)
    real = PI._apply_hook_file_localization
    def later_edit(plan, transaction, owner):
        real(plan, transaction, owner)
        link.write_bytes(b"later user local edit")
        raise RuntimeError("injected later failure")
    monkeypatch.setattr(PI, "_apply_hook_file_localization", later_edit)
    with pytest.raises(PI._InstallFailure):
        PI._localize_hook_file(ROOT, "codex", anchor, "global", apply=True)
    assert not link.is_symlink() and link.read_bytes() == b"later user local edit"
    assert link.with_name(link.name + ".orche-localization-link").is_symlink()
    assert source.read_bytes() == payload


def test_linked_parent_is_not_implicitly_admitted(tmp_path):
    anchor, source, link, receipt, payload = fixture(tmp_path)
    moved = anchor / "moved"
    link.parent.rename(moved)
    (anchor / ".codex").symlink_to(moved, target_is_directory=True)
    with pytest.raises(ValueError, match="linked parent"):
        PI._localize_hook_file(ROOT, "codex", anchor, "global", apply=True)
    assert source.read_bytes() == payload


def test_existing_registration_owner_updates_only_local_after_materialization(tmp_path):
    anchor, source, link, receipt, payload = fixture(tmp_path)
    plan = PI._plan_hook_file_localization(ROOT, "codex", anchor, "global")
    paths = [link, plan.backup, plan.inventory, plan.inventory_backup, *(p for p, _ in plan.dependencies)]
    helper = PI._load_module_from_path("localization_compose_helper", ROOT / "scripts/install-hypothesis-hook.py")
    data = json.loads(payload)
    event, groups = next(iter(data["hooks"].items()))
    entry = groups[0]
    updated = json.loads(json.dumps(entry))
    updated["hooks"][0]["statusMessage"] = "Updated managed status"
    marker, script, _event, _matcher = next(iter(PI._hook_specs("codex", anchor / ".agents/skills/lead")))
    with PI._InstallTransaction(paths, enabled=True, link_object_paths=(link,), readonly_paths=(source,)) as transaction:
        owner = PI._CreateOnlyMutablePath(anchor, transaction, dry_run=False)
        PI._apply_hook_file_localization(plan, transaction, owner)
        PI._transform_hook_registration(helper, link, owner, marker, event, "codex",
            "windows" if PI.os.name == "nt" else "posix", entry=updated,
            managed_targets={marker: {str(script)}})
        transaction.commit()
    actual = json.loads(link.read_bytes())
    assert actual["foreign"] == data["foreign"]
    assert actual["hooks"][event][0]["hooks"][0]["statusMessage"] == "Updated managed status"
    assert source.read_bytes() == payload


def test_public_normal_install_localization_phase(tmp_path, monkeypatch):
    """Real source install/update, no hook health/native Codex invocation."""
    project = tmp_path / "project"
    project.mkdir()
    def no_native(*args, **kwargs):
        raise AssertionError("native hook health is outside this offline test")
    monkeypatch.setattr(PI, "_run_hook_health_bounded", no_native)
    args = ["--target", str(project), "--allow-unsafe-target", "--no-hypothesis-hook"]
    assert PI.install("codex", args) == 0
    client = PI.get_client("codex")
    marker, script, event, matcher = next(iter(PI._hook_specs("codex", project / client["canonical_runtime"])))
    helper = PI._load_module_from_path("public_localization_helper", ROOT / "scripts/install-hypothesis-hook.py")
    host = "windows" if PI.os.name == "nt" else "posix"
    entry = helper.build_codex_entry(helper.resolve_hook_target(str(script), host, "codex"), host, event, matcher)
    shared = tmp_path / "shared"
    shared.mkdir()
    source = shared / "hooks.json"
    payload = (json.dumps({"hooks": {event: [entry]}, "foreign": "unchanged"}, indent=3) + "\n").encode()
    source.write_bytes(payload)
    registration = project / client["registration"]
    assert not registration.exists()
    registration.symlink_to(source)
    codec = PI._provider_ownership_module(ROOT)
    receipt = project / client["provider_root"] / codec.RECEIPT_NAME
    record = codec.decode_record(receipt.read_bytes(), "codex", "project")
    record.setdefault("configs", {})[client["registration"]] = dict(kind="hooks", handlers=[dict(
        event=event, marker=marker, context={k:v for k,v in entry.items() if k != "hooks"}, handler=entry["hooks"][0])], agentAdded=False)
    # Explicit synthetic historical receipt input; actual installer and digest unchanged.
    record["files"][script.relative_to(project).as_posix()] = hashlib.sha256(script.read_bytes()).hexdigest()
    receipt.write_bytes(codec.serialize_record(record, "codex", "project"))
    inventory = registration.parent / PI.CODEX_HOOK_INVENTORY
    inventory.write_bytes(b"stale local inventory")
    registration_identity = registration.lstat().st_ino
    inventory_identity = inventory.lstat().st_ino
    receipt_before = receipt.read_bytes()
    assert PI.install("codex", [*args, "--localize-hook-file", "--dry-run"]) == 0
    assert registration.is_symlink() and registration.lstat().st_ino == registration_identity
    assert source.read_bytes() == payload
    assert inventory.read_bytes() == b"stale local inventory"
    assert inventory.lstat().st_ino == inventory_identity
    assert receipt.read_bytes() == receipt_before
    assert not PI.os.path.lexists(registration.with_name(registration.name + ".orche-localization-link"))
    assert not PI.os.path.lexists(inventory.with_name(inventory.name + ".orche-localization-prior"))
    assert PI.install("codex", [*args, "--localize-hook-file"]) == 0
    assert not registration.is_symlink() and registration.read_bytes() == payload
    assert source.read_bytes() == payload
    assert registration.with_name(registration.name + ".orche-localization-link").is_symlink()
    assert not inventory.exists()
    assert inventory.with_name(inventory.name + ".orche-localization-prior").read_bytes() == b"stale local inventory"
    updated_record = codec.decode_record(receipt.read_bytes(), "codex", "project")
    assert updated_record["configs"][client["registration"]] == record["configs"][client["registration"]]


@pytest.mark.parametrize("member", ["source", "receipt"])
def test_same_byte_dependency_replacement_is_not_adopted(tmp_path, monkeypatch, member):
    anchor, source, link, receipt, payload = fixture(tmp_path)
    real = PI._plan_hook_file_localization
    def replace(*args, **kwargs):
        plan = real(*args, **kwargs)
        path = source if member == "source" else receipt
        saved = path.read_bytes()
        prior = path.with_name(path.name + ".user-prior")
        path.rename(prior)
        path.write_bytes(saved)
        return plan
    monkeypatch.setattr(PI, "_plan_hook_file_localization", replace)
    with pytest.raises((ValueError, PI._InstallFailure)):
        PI._localize_hook_file(ROOT, "codex", anchor, "global", apply=True)
    assert link.is_symlink() and source.read_bytes() == payload


def test_prepared_payload_failure_settles_temporary(tmp_path, monkeypatch):
    anchor, source, link, receipt, payload = fixture(tmp_path)
    real = PI._InstallTransaction._prepare_payload_file
    def fail_after_prepare(transaction, *args, **kwargs):
        real(transaction, *args, **kwargs)
        raise RuntimeError("injected prepare failure")
    monkeypatch.setattr(PI._InstallTransaction, "_prepare_payload_file", fail_after_prepare)
    with pytest.raises(RuntimeError, match="injected prepare failure"):
        PI._localize_hook_file(ROOT, "codex", anchor, "global", apply=True)
    assert not list(link.parent.glob(".orchestrarium-hook-local-*"))
    assert link.is_symlink() and source.read_bytes() == payload


@pytest.mark.parametrize("other_readonly", [False, True])
def test_external_mutable_image_is_not_silently_filtered(tmp_path, other_readonly):
    from types import SimpleNamespace
    anchor = tmp_path / "home"
    anchor.mkdir()
    external = tmp_path / "external.txt"
    external.write_bytes(b"not an admitted read-only input")
    node = PI._InstallTransaction._capture_node(external)
    transaction = SimpleNamespace(_original={external: {external: node}},
        _expected={external: {external: node}}, _temporary=None, _migration_retention={},
        _effects=[], paths=(external,), _readonly_paths=(tmp_path / "different",) if other_readonly else ())
    with pytest.raises(ValueError, match="external mutation image"):
        PI._record_provider_install(ROOT, "codex", "global", anchor / ".codex", anchor,
            transaction, SimpleNamespace(dry_run=False), None, {}, anchor / "AGENTS.md",
            anchor / "mode", anchor / "hooks.json", anchor / "lead", False)
    assert not (anchor / ".codex/.orche-install.v1.json").exists()
    assert external.read_bytes() == b"not an admitted read-only input"
