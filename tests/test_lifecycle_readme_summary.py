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
