"""Post-commit disposal must retain admitted native observations."""
from pathlib import Path
import pytest
from test_mutate_work_item import load_module, _seed_legacy_backlog


@pytest.mark.parametrize("surface", ("source", "marker", "target"))
def test_cleanup_refuses_drift_after_domain_validation(tmp_path: Path, surface: str):
    module = load_module()
    root = tmp_path / "repo"
    slug = "cleanup-currentness"
    _seed_legacy_backlog(root, slug, {"brief.md": b"original retained evidence\n"})
    module.refresh_readme(root, allow_marker_bootstrap=True)
    original = module._validated_legacy_cleanup_residue
    changed = []
    def validate_then_drift(backlog, item_slug, target):
        result = original(backlog, item_slug, target)
        residue, marker, _ = result
        path = residue / "source/brief.md" if surface == "source" else marker if surface == "marker" else target
        path.write_bytes(b"foreign replacement after domain validation\n")
        changed.append(path)
        return result
    module._validated_legacy_cleanup_residue = validate_then_drift
    try:
        with pytest.raises(module.LifecycleError) as refused:
            module.convert_legacy_candidate(root, slug, b"status: candidate\nTask: Preserve evidence.\n")
    finally:
        module._validated_legacy_cleanup_residue = original
    assert refused.value.failure_id == "WI-CATEGORY-MIGRATION-INVENTORY"
    assert "changed" in str(refused.value)
    assert len(changed) == 1
    assert changed[0].read_bytes() == b"foreign replacement after domain validation\n"
    residue = next((root / "work-items/backlog").glob(f".{slug}.legacy-candidate.*"))
    assert (residue / "source/brief.md").is_file()
    assert (residue / module.LEGACY_CLEANUP_FILE).is_file()
    if surface != "target":
        assert b"original retained evidence" in (root / "work-items/backlog" / (slug + ".md")).read_bytes()


@pytest.mark.parametrize("unlocked_owner", (False, True))
def test_cleanup_requires_current_held_owner(tmp_path: Path, monkeypatch, unlocked_owner: bool):
    module = load_module()
    target = tmp_path / "candidate.md"
    marker = tmp_path / "marker.json"
    target.write_bytes(b"committed candidate\n")
    marker.write_bytes(b"retained cleanup marker\n")
    held = module.LifecycleTransaction(tmp_path) if unlocked_owner else None
    token = module._CURRENT_LIFECYCLE_TRANSACTION.set(held)
    def unexpected_capture(*args, **kwargs):
        pytest.fail("cleanup read an input before requiring its held owner")
    monkeypatch.setattr(module, "_capture_file_snapshot", unexpected_capture)
    try:
        with pytest.raises(module.LifecycleError) as refused:
            module._finish_committed_legacy_cleanup(target, None, marker, "transaction")
    finally:
        module._CURRENT_LIFECYCLE_TRANSACTION.reset(token)
    assert refused.value.failure_id == "WI-LEGACY-CLEANUP-AFTER-COMMIT"
    assert "held lifecycle owner" in str(refused.value)
    assert target.read_bytes() == b"committed candidate\n"
    assert marker.read_bytes() == b"retained cleanup marker\n"


@pytest.mark.parametrize("surface", ("marker", "target"))
def test_sidecar_only_replay_refuses_drift_after_domain_validation(tmp_path: Path, monkeypatch, surface: str):
    module = load_module()
    root = tmp_path / "repo"
    slug = "cleanup-sidecar-currentness"
    _seed_legacy_backlog(root, slug, {"brief.md": b"original retained evidence\n"})
    module.refresh_readme(root, allow_marker_bootstrap=True)
    backlog = root / "work-items/backlog"
    candidate_data = b"status: candidate\nTask: Preserve evidence.\n"
    original_remove = module._remove_lifecycle_file
    def retain_sidecar(path, **kwargs):
        if path.parent == backlog and path.name.startswith(".legacy-candidate-cleanup."):
            raise OSError("injected sidecar retention")
        return original_remove(path, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(module, "_remove_lifecycle_file", retain_sidecar)
        with pytest.raises(module.LifecycleError) as failed:
            module.convert_legacy_candidate(root, slug, candidate_data)
    assert failed.value.failure_id == "WI-LEGACY-CLEANUP-AFTER-COMMIT"
    assert not list(backlog.glob(f".{slug}.legacy-candidate.*"))
    target = backlog / f"{slug}.md"
    marker = next(backlog.glob(".legacy-candidate-cleanup.*.json"))
    before = {path: path.read_bytes() for path in (target, marker, root / "work-items/README.md")}
    original_validate = module._validated_legacy_cleanup_residue
    validations = 0
    changed = marker if surface == "marker" else target
    def validate_then_drift(*args):
        nonlocal validations
        result = original_validate(*args)
        validations += 1
        # Replay selects once, then the cleanup owner validates captured inputs.
        if validations == 2:
            assert result[0] is None
            changed.write_bytes(b"foreign replacement after domain validation\n")
        return result
    monkeypatch.setattr(module, "_validated_legacy_cleanup_residue", validate_then_drift)
    with pytest.raises(module.LifecycleError) as refused:
        module.convert_legacy_candidate(root, slug, candidate_data)
    assert refused.value.failure_id == "WI-CATEGORY-MIGRATION-INVENTORY"
    assert "changed" in str(refused.value)
    assert validations == 2
    assert changed.read_bytes() == b"foreign replacement after domain validation\n"
    for path, data in before.items():
        if path != changed:
            assert path.read_bytes() == data
