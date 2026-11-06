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
