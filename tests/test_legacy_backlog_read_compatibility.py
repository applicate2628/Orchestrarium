"""Historical backlog is readable without granting canonical write authority."""
import pytest
from test_mutate_work_item import load_module, quick_status, run_cli, tree_file_bytes


LEGACY = (b"# Historical admitted task\n\n- status: backlog\n"
          b"- admission: direct human request\n- priority: unassigned\n"
          b"- parent: earlier-context\n\nRequires a separate active work item.\n")


def seeded(tmp_path, data=LEGACY):
    module = load_module()
    root = tmp_path / "repo"
    module.create_candidate(root, "historical-task", b"Task: Fixture seed.\n")
    path = root / "work-items/backlog/historical-task.md"
    path.write_bytes(data)
    module.refresh_readme(root)
    return module, root, path


def test_existing_legacy_backlog_is_read_only_compatible(tmp_path):
    module, root, path = seeded(tmp_path)
    before = tree_file_bytes(root)
    identity = path.stat().st_ino
    assert module.audit(root) == ("backlog/historical-task.md",)
    assert module.observe_readme(root)["matches"] is True
    result = run_cli("audit", "--root", str(root))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "AUDIT: PASS" in result.stdout
    assert tree_file_bytes(root) == before and path.stat().st_ino == identity
    assert path.read_bytes() == LEGACY
    board = (root / "work-items/README.md").read_text(encoding="utf-8")
    assert module.LEGACY_READ_CLASSIFICATION in board
    assert "status=backlog" in board
    assert not (root / "work-items/active/historical-task").exists()


def test_legacy_read_does_not_authorize_create_or_start(tmp_path):
    module, root, path = seeded(tmp_path)
    before = tree_file_bytes(root)
    with pytest.raises(module.LifecycleError) as created:
        module.create_candidate(root, "new-legacy", LEGACY)
    assert created.value.failure_id == "WI-README-STALE"
    assert tree_file_bytes(root) == before
    with pytest.raises(module.LifecycleError) as started:
        module.start_item(root, "historical-task", quick_status().encode())
    assert started.value.failure_id == "WI-CATEGORY-STATUS-INVALID"
    assert tree_file_bytes(root) == before and path.read_bytes() == LEGACY


@pytest.mark.parametrize("damage", ("duplicate", "conflicting", "conflicting-last-candidate", "schema", "schema-star", "schema-star-bold", "active", "unknown"))
def test_legacy_compatibility_does_not_admit_other_invalid_states(tmp_path, damage):
    module = load_module()
    data = LEGACY
    if damage == "duplicate":
        data += b"\nstatus: backlog\n"
    elif damage == "conflicting":
        data = b"status: candidate\n" + data
    elif damage == "conflicting-last-candidate":
        data += b"\nstatus: candidate\n"
    elif damage == "schema":
        data += b"\n" + module.WORK_ITEM_SCHEMA_MARKER.encode() + b"\n"
    elif damage in {"schema-star", "schema-star-bold"}:
        marker = "**Lifecycle-schema**" if damage == "schema-star-bold" else "Lifecycle-schema"
        data += ("\n* " + marker + ": work-items-physical-v1\n").encode()
    elif damage == "unknown":
        data = data.replace(b"status: backlog", b"status: backlogged")
    module, root, path = seeded(tmp_path, data)
    if damage == "active":
        target = root / "work-items/active/historical-task/status.md"
        target.parent.mkdir(parents=True)
        path.rename(target)
        module.refresh_readme(root)
    before = tree_file_bytes(root)
    with pytest.raises(module.LifecycleError) as refused:
        module.audit(root)
    assert refused.value.failure_id == "WI-CATEGORY-STATUS-INVALID"
    assert tree_file_bytes(root) == before


def test_other_candidate_can_be_created_without_rewriting_legacy(tmp_path):
    module, root, path = seeded(tmp_path)
    identity = path.stat().st_ino
    module.create_candidate(root, "independent", b"status: candidate\nTask: Separate request.\n")
    assert path.read_bytes() == LEGACY and path.stat().st_ino == identity
    assert module.audit(root) == ("backlog/historical-task.md",)


def test_legacy_read_does_not_silently_refresh_a_stale_generated_view(tmp_path):
    module, root, path = seeded(tmp_path)
    readme = root / "work-items/README.md"
    readme.write_bytes(readme.read_bytes().replace(b"WI-LEGACY-READ-COMPAT", b"older stored diagnostic"))
    before = tree_file_bytes(root)
    with pytest.raises(module.LifecycleError) as stale:
        module.audit(root)
    assert stale.value.failure_id == "WI-README-STALE"
    assert module.observe_readme(root)["matches"] is False
    assert tree_file_bytes(root) == before
    module.refresh_readme(root)
    assert module.audit(root) == ("backlog/historical-task.md",)
    assert path.read_bytes() == LEGACY
