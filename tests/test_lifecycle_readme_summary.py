import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "mutate-work-item.py"
LIFECYCLE_SCHEMA_MARKER = "Lifecycle-schema: work-items-physical-v1"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "lifecycle_readme_summary_mutate_work_item",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_recently_completed_row_summarizes_and_points_to_unchanged_closure(
    tmp_path: Path,
) -> None:
    module = load_module()
    root = tmp_path / "repo"
    work_items = root / "work-items"

    write(
        work_items / "backlog" / "queued-item.md",
        "status: candidate\n"
        "Task: Queue compact renderer\n"
        "Next action: Run queued item\n",
    )
    write(
        work_items / "active" / "active-item" / "status.md",
        "status: active\n"
        "Task: Keep active renderer\n"
        "Current step: Verify active row\n",
    )

    archived = work_items / "archive" / "2026-08" / "long-closure"
    write(
        archived / "status.md",
        f"status: completed\n{LIFECYCLE_SCHEMA_MARKER}\n",
    )
    long_outcome = " ".join(["Delivered the complete lifecycle result."] * 24)
    long_residual = " ".join(["Operators retain a documented follow-up."] * 24)
    closure_bytes = (
        "Closed: 2026-08-12T10:11:12Z\n"
        f"Outcome: {long_outcome}\n\n"
        "The canonical closure keeps additional outcome evidence in later paragraphs.\n\n"
        "Evidence: focused renderer regression\n"
        f"Residual risk: {long_residual}\n\n"
        "The canonical closure keeps additional residual-risk context here.\n"
        f"{LIFECYCLE_SCHEMA_MARKER}\n"
    ).encode("utf-8")
    archived.mkdir(parents=True, exist_ok=True)
    (archived / "closure.md").write_bytes(closure_bytes)

    completed_entry = next(
        entry
        for entry in module.collect_readme_entries(root)
        if entry.logical_reference == "work-item:long-closure"
    )
    assert completed_entry.label == long_outcome
    assert completed_entry.detail == long_residual

    rendered = module.render_readme_bytes(
        root,
        static_guide_override="",
    ).decode("utf-8")
    rows = [line for line in rendered.splitlines() if line.startswith("- [")]

    assert (
        "- [ ] [Queue compact renderer](backlog/queued-item.md) — Run queued item"
        in rows
    )
    assert (
        "- [ ] [Keep active renderer](active/active-item/status.md) — "
        "Verify active row — [work item](active/active-item/status.md)"
        in rows
    )
    completed_row = next(row for row in rows if "long-closure" in row)
    assert completed_row == (
        "- [x] [long-closure](archive/2026-08/long-closure/closure.md)"
    )
    assert len(completed_row) < 120
    assert long_outcome not in rendered
    assert long_residual not in rendered
    assert (archived / "closure.md").read_bytes() == closure_bytes


def test_retirement_catalogue_keeps_historical_inputs_and_strict_current_audit(tmp_path, monkeypatch):
    import json
    import pytest

    module = load_module()
    root = tmp_path / "repo"
    slug = "retirement-input-role"
    source = root / "work-items/backlog" / slug / "design.md"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"Synthetic never-admitted proposal.\n")
    module.refresh_readme(root, allow_marker_bootstrap=True)
    archived = module.retire_legacy_backlog(root, slug, b"Rejected before admission.\n",
                                          "2026-08-01T00:00:00Z")
    metadata = archived / "legacy-retirement.json"
    original_metadata = metadata.read_bytes()
    original_payload = (archived / "design.md").read_bytes()
    baseline_entry = module._archived_work_item_entry(archived)
    baseline_digest = module._input_digest([baseline_entry], root / "work-items")
    baseline_render = module.render_readme_bytes(root)
    consumer = root / "work-items/consumer.json"
    consumer.write_bytes(json.dumps({"literal": f"work-items/backlog/{slug}/design.md"}).encode())
    original_read = module._input_bytes
    reads = []
    strict = [False]
    def selected_input(path, *args, **kwargs):
        if Path(path) == consumer:
            reads.append(strict[0])
            if not strict[0]:
                raise module.LifecycleError("WI-TEST-REQUIRED-INPUT", "historical catalogue selected a NEW current consumer")
        return original_read(path, *args, **kwargs)
    monkeypatch.setattr(module, "_input_bytes", selected_input)

    entries = module.collect_readme_entries(root)
    historical = next(entry for entry in entries if entry.logical_reference == f"work-item:{slug}")
    assert historical == baseline_entry
    assert historical.source_paths == baseline_entry.source_paths
    assert module._input_digest([historical], root / "work-items") == baseline_digest
    assert module.render_readme_bytes(root) == baseline_render
    first = module.refresh_readme(root)
    assert module.refresh_readme(root) == first
    assert (root / "work-items/README.md").read_bytes() == baseline_render
    assert reads == []

    # Default strict integrity still acquires and rejects the actual later
    # citation; no scanner/mutable-consumer logic is weakened.
    strict[0] = True
    with pytest.raises(module.LifecycleError, match="mutable record retains a retired backlog path"):
        module._legacy_retirement_entry(archived, metadata)
    assert reads and all(reads)
    strict[0] = False
    with pytest.raises((PermissionError, module.LifecycleError)):
        module._archived_work_item_entry(archived)
    reads.clear()
    with pytest.raises(ValueError, match="unsupported.*input role"):
        module._legacy_retirement_entry(archived, metadata, input_role="unknown")

    # Historical mode still consumes/qualifies its actual archive inputs.
    (archived / "design.md").write_bytes(b"X" + original_payload[1:])  # Same length: hash check must still reject.
    with pytest.raises(module.LifecycleError, match="source digest differs"):
        module._archived_work_item_entry(archived, input_role="historical-catalogue")
    (archived / "design.md").write_bytes(original_payload)
    saved_payload = root / "saved-payload.bin"
    (archived / "design.md").rename(saved_payload)
    (archived / "design.md").mkdir()
    with pytest.raises(module.LifecycleError, match="missing source payload"):
        module._archived_work_item_entry(archived, input_role="historical-catalogue")
    (archived / "design.md").rmdir()
    saved_payload.rename(archived / "design.md")
    valid = json.loads(original_metadata)
    mutations = [
        {**valid, "status": "invented-active-state"},
        {**valid, "terminalAt": "2026-09-01T00:00:00Z"},
        {**valid, "syntheticTransitions": ["invented"]},
        {**valid, "incomingLinks": {"result": "physical", "references": []}},
        {**valid, "sourceFiles": [{**valid["sourceFiles"][0], "byteLength": 999}]},
    ]
    for corrupted in mutations:
        metadata.write_bytes(json.dumps(corrupted).encode())
        with pytest.raises(module.LifecycleError):
            module._archived_work_item_entry(archived, input_role="historical-catalogue")
    metadata.write_bytes(original_metadata)
    extra = archived / "unrecorded.md"
    extra.write_bytes(b"Unrecorded archive payload.\n")
    with pytest.raises(module.LifecycleError, match="source inventory"):
        module._archived_work_item_entry(archived, input_role="historical-catalogue")
    extra.unlink()
    assert reads == []
    assert module._archived_work_item_entry(archived, input_role="historical-catalogue") == baseline_entry
    assert module._input_digest([baseline_entry], root / "work-items") == baseline_digest
